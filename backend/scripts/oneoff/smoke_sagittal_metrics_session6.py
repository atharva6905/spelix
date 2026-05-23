"""Session 6 smoke script — dump per-rep Session-6 metric values for the
deadlift and bench atharva fixtures. Output is CSV-formatted on stdout for
paste-into-chat per /goal evidence-surfacing protocol.

Not run in CI — calibration aid only.

Usage:
    uv run --directory backend python scripts/oneoff/smoke_sagittal_metrics_session6.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

# Make `app.*` importable + wire ThresholdConfig to v1.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BACKEND_ROOT))
_V1_PATH = _BACKEND_ROOT.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig  # noqa: E402
from app.cv.lifter_side import detect_lifter_side  # noqa: E402
from app.cv.metric_extraction import extract_rep_metrics  # noqa: E402
from app.cv.pose_extraction import extract_landmarks  # noqa: E402
from app.cv.rep_detection import detect_reps  # noqa: E402
from app.cv.signal_processing import compute_angle_timeseries  # noqa: E402


_FIXTURES_DIR = _BACKEND_ROOT.parent / "e2e" / "fixtures"


def _run(fixture: Path, exercise: str, variant: str) -> int:
    if not fixture.exists():
        print(f"SKIP: fixture missing: {fixture}", file=sys.stderr)
        return 0
    landmarks, fps, _w, _h = extract_landmarks(str(fixture))
    if not landmarks:
        print(f"FAIL: no landmarks for {fixture.name}", file=sys.stderr)
        return 1
    session = np.stack(landmarks)
    side = detect_lifter_side(session, fps=fps)
    angles = compute_angle_timeseries(landmarks, exercise_type=exercise, lifter_side=side)
    cfg = ThresholdConfig(_V1_PATH)
    primary = angles["hip_angle"] if exercise != "bench" else angles["elbow_angle"]
    reps = detect_reps(
        angle_timeseries=primary,
        landmarks_per_frame=landmarks,
        exercise_type=exercise,
        exercise_variant=variant,
        fps=fps,
        cfg=cfg,
    )
    rep_metrics = extract_rep_metrics(
        reps=reps,
        landmarks_per_frame=landmarks,
        angle_timeseries=angles,
        exercise_type=exercise,
        exercise_variant=variant,
        fps=fps,
        lifter_side=side,
    )
    print(f"# fixture={fixture.name} exercise={exercise} variant={variant} "
          f"side={side} fps={fps:.1f} reps={len(rep_metrics)}")
    if exercise == "deadlift":
        print("rep_index,setup,liftoff,knee_pass,lockout")
        for r in rep_metrics:
            d = r.metrics.get("bar_to_hip_distance", {})
            if not isinstance(d, dict):
                d = {}
            row = (
                str(r.rep_index),
                str(d.get("setup")),
                str(d.get("liftoff")),
                str(d.get("knee_pass")),
                str(d.get("lockout")),
            )
            print(",".join(row))
    elif exercise == "bench":
        print("rep_index,shoulder_protraction_proxy_px")
        for r in rep_metrics:
            v = r.metrics.get("shoulder_protraction_proxy_px")
            print(f"{r.rep_index},{v}")
    print()
    return 0


def main() -> int:
    rc = 0
    rc |= _run(_FIXTURES_DIR / "atharva-deadlift.mov", "deadlift", "conventional")
    rc |= _run(_FIXTURES_DIR / "atharva-bench.mov", "bench", "flat")
    return rc


if __name__ == "__main__":
    sys.exit(main())
