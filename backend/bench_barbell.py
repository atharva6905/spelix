"""Diagnostic benchmark for D-035 — cv2.HoughCircles cost at 1080p.

Runs three modes on a local video:
  Mode 1 — cap.read() only (I/O baseline)
  Mode 2 — detect_barbell_in_frame at source resolution (current code)
  Mode 3 — detect_barbell_in_frame with 480p downscale (proposed fix)

Mode 3 is skipped if _downscale_for_detection does not exist yet (pre-fix
baseline). Run pre-fix to confirm the hypothesis; run post-fix to quantify
the speedup.

Run inside the worker container:
    docker cp backend/bench_barbell.py spelix-worker-1:/tmp/bench_barbell.py
    docker exec spelix-worker-1 python /tmp/bench_barbell.py /tmp/bench.mov
"""
from __future__ import annotations

import sys
import time

import cv2


def _mode1_read_only(path: str) -> tuple[int, float]:
    cap = cv2.VideoCapture(path)
    t0 = time.perf_counter()
    n = 0
    while True:
        ret, _ = cap.read()
        if not ret:
            break
        n += 1
    cap.release()
    return n, time.perf_counter() - t0


def _mode2_current_detection(path: str) -> tuple[int, float, int]:
    sys.path.insert(0, "/app")
    from app.cv.barbell_detection import detect_barbell_in_frame

    cap = cv2.VideoCapture(path)
    t0 = time.perf_counter()
    n = 0
    detected = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        n += 1
        if detect_barbell_in_frame(frame) is not None:
            detected += 1
    cap.release()
    return n, time.perf_counter() - t0, detected


def _mode3_downscaled(path: str) -> tuple[int, float, int] | None:
    sys.path.insert(0, "/app")
    try:
        from app.cv.barbell_detection import _downscale_for_detection  # noqa: F401
    except ImportError:
        return None
    # After the fix lands, detect_barbell_in_frame itself downscales, so
    # mode 3 is identical to mode 2 in call-shape but measures post-fix cost.
    from app.cv.barbell_detection import detect_barbell_in_frame

    cap = cv2.VideoCapture(path)
    t0 = time.perf_counter()
    n = 0
    detected = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        n += 1
        if detect_barbell_in_frame(frame) is not None:
            detected += 1
    cap.release()
    return n, time.perf_counter() - t0, detected


def _print_row(label: str, frames: int, total_s: float, detected: int | None) -> None:
    per_ms = (total_s / max(frames, 1)) * 1000
    det_str = f"{detected}/{frames}" if detected is not None else "—"
    print(f"  {label:<40s} frames={frames}  total={total_s:7.2f}s  per_frame={per_ms:8.1f}ms  detected={det_str}")


def main(video_path: str) -> None:
    print("=== D-035 barbell detection benchmark ===")
    print(f"video: {video_path}")

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    print(f"source: {w}x{h} @ {fps:.2f}fps\n")

    print("Mode 1 — cap.read() only (I/O baseline):")
    n1, t1 = _mode1_read_only(video_path)
    _print_row("read-only", n1, t1, None)

    print("\nMode 2 — current detect_barbell_in_frame (source resolution):")
    n2, t2, d2 = _mode2_current_detection(video_path)
    _print_row("detect@source", n2, t2, d2)

    print("\nMode 3 — proposed detect_barbell_in_frame (480p downscale):")
    result = _mode3_downscaled(video_path)
    if result is None:
        print("  (skipped — _downscale_for_detection not yet implemented)")
    else:
        n3, t3, d3 = result
        _print_row("detect@480p", n3, t3, d3)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python bench_barbell.py /tmp/bench.mov")
        raise SystemExit(2)
    main(sys.argv[1])
