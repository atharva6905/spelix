"""D-044 diagnostic harness: trace atharva-bench.mov through the rep detector.

Extracts landmarks, prints raw + smoothed elbow angle stats, runs the state
machine and peak/valley detector SEPARATELY (bypassing the hybrid chooser),
logs state transitions + valley indices, writes a PNG plot of raw vs smoothed
signal with detected rep boundaries overlaid.

Operator-run. Not in CI. Matplotlib imported lazily.

Usage:
    uv run python scripts/oneoff/diagnose_rep_detection_d044.py <fixture_name>
Examples:
    uv run python scripts/oneoff/diagnose_rep_detection_d044.py atharva-bench.mov
    uv run python scripts/oneoff/diagnose_rep_detection_d044.py atharva-bench-nw-10s-720p.mp4
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np  # noqa: E402

from app.cv.pose_extraction import extract_landmarks  # noqa: E402
from app.cv.rep_detection import (  # noqa: E402
    _detect_reps_peak_valley,
    _detect_reps_state_machine,
    detect_reps,
)
from app.cv.signal_processing import calculate_joint_angles, smooth_signal  # noqa: E402


def _raw_elbow_series(landmarks_per_frame: list[np.ndarray]) -> np.ndarray:
    raw: list[float] = []
    for frame in landmarks_per_frame:
        angles = calculate_joint_angles(frame, "bench")
        raw.append(float(angles["elbow_angle"]))
    return np.array(raw, dtype=float)


def _plot_signal(
    raw: np.ndarray,
    smoothed: np.ndarray,
    sm_reps: list,
    pv_reps: list,
    out_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(raw, color="lightgray", linewidth=0.8, label="raw elbow angle")
    ax.plot(smoothed, color="steelblue", linewidth=1.5, label="smoothed (savgol w=7 p=3)")
    for rep in sm_reps:
        ax.axvspan(rep.start_frame, rep.end_frame, color="green", alpha=0.15)
    for rep in pv_reps:
        ax.axvline(
            (rep.start_frame + rep.end_frame) // 2,
            color="red",
            linewidth=0.8,
            linestyle="--",
        )
    ax.axhline(160, color="black", linewidth=0.5, linestyle=":", label="standing (160°)")
    ax.axhline(90, color="black", linewidth=0.5, linestyle=":", label="depth (90°)")
    ax.set_xlabel("frame")
    ax.set_ylabel("elbow angle (°)")
    ax.set_title(f"D-044 diagnostic — SM green-shaded, PV red-dashed — {out_path.stem}")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: diagnose_rep_detection_d044.py <fixture_filename>")
        return 2

    fixture_name = sys.argv[1]
    fixture = (
        Path(__file__).parent.parent.parent.parent
        / "e2e"
        / "fixtures"
        / fixture_name
    )
    if not fixture.exists():
        print(f"fixture not found: {fixture}")
        return 1

    landmarks_per_frame, fps, _, _ = extract_landmarks(str(fixture))
    n_frames = len(landmarks_per_frame)
    print(f"fixture: {fixture.name}")
    print(f"frames: {n_frames}  fps: {fps:.2f}  duration: {n_frames / fps:.1f}s")

    raw = _raw_elbow_series(landmarks_per_frame)
    smoothed = smooth_signal(raw, window=7, polyorder=3)
    print(
        f"raw   elbow min/max/mean/std: "
        f"{raw.min():.1f} / {raw.max():.1f} / {raw.mean():.1f} / {raw.std():.2f}"
    )
    print(
        f"smooth elbow min/max/mean/std: "
        f"{smoothed.min():.1f} / {smoothed.max():.1f} / {smoothed.mean():.1f} / {smoothed.std():.2f}"
    )
    print(f"frame-to-frame |delta| mean (raw):    {np.abs(np.diff(raw)).mean():.3f}°")
    print(f"frame-to-frame |delta| mean (smooth): {np.abs(np.diff(smoothed)).mean():.3f}°")

    sm_reps = _detect_reps_state_machine(smoothed, "bench", "flat", fps)
    pv_reps = _detect_reps_peak_valley(smoothed, "bench", fps)
    hy_reps = detect_reps(smoothed, landmarks_per_frame, "bench", "flat", fps)

    print(f"state-machine reps: {len(sm_reps)}")
    for rep in sm_reps:
        print(
            f"  SM rep {rep.rep_index}: frames {rep.start_frame}..{rep.end_frame} "
            f"min_angle {rep.min_angle:.1f}"
        )
    print(f"peak/valley reps:   {len(pv_reps)}")
    for rep in pv_reps:
        print(
            f"  PV rep {rep.rep_index}: frames {rep.start_frame}..{rep.end_frame} "
            f"min_angle {rep.min_angle:.1f}"
        )
    print(f"HYBRID (production) reps: {len(hy_reps)}")

    out = Path("/tmp") / f"d044-{fixture.stem}.png"
    _plot_signal(raw, smoothed, sm_reps, pv_reps, out)
    print(f"plot written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
