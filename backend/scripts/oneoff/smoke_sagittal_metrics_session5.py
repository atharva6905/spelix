"""Session 5 smoke script — dump per-rep Session-5 metric values for all 3
atharva fixtures. Output is CSV-formatted on stdout for paste-into-chat
per /goal evidence-surfacing protocol.

Not run in CI — calibration aid only.

Usage:
    uv run --directory backend python scripts/oneoff/smoke_sagittal_metrics_session5.py
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


_PER_EXERCISE_SESSION5_KEYS = {
    "squat": ("ankle_dorsiflexion_deg", "heel_rise_flag", "shin_angle_deg"),
    "bench": ("wrist_alignment_deg", "bar_touch_height_pct", "arch_deg"),
    "deadlift": ("setup_shoulder_x_offset", "setup_knee_angle_deg"),
}


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
    keys = _PER_EXERCISE_SESSION5_KEYS[exercise]
    print(f"# fixture={fixture.name} exercise={exercise} variant={variant} "
          f"side={side} fps={fps:.1f} reps={len(rep_metrics)}")
    print("rep_index," + ",".join(keys))
    for r in rep_metrics:
        vals = [str(r.metrics.get(k)) for k in keys]
        print(f"{r.rep_index}," + ",".join(vals))
    print()
    return 0


def main() -> int:
    rc = 0
    rc |= _run(_FIXTURES_DIR / "atharva-squat.mov", "squat", "standard")
    rc |= _run(_FIXTURES_DIR / "atharva-bench.mov", "bench", "flat")
    rc |= _run(_FIXTURES_DIR / "atharva-deadlift.mov", "deadlift", "conventional")
    return rc


if __name__ == "__main__":
    sys.exit(main())
