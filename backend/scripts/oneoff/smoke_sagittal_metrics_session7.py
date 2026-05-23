"""Session 7 smoke script — dump per-rep Session-7 metric values for all three
atharva fixtures. Output is CSV-formatted on stdout for paste-into-chat per
/goal evidence-surfacing protocol.

Not run in CI — calibration aid only.

Outputs per fixture:
  squat:     rep_index, lumbar_flexion_proxy_delta_deg, technique_consistency_std, lifter_side
  bench:     rep_index, bar_path_classification, technique_consistency_std(N/A), lifter_side
  deadlift:  rep_index, lumbar_flexion_proxy_delta_deg, technique_consistency_std, lifter_side

Also prints the session-modal bar_path_classification for the bench run.

Usage:
    uv run --directory backend python scripts/oneoff/smoke_sagittal_metrics_session7.py
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
from app.cv.metric_extraction import (  # noqa: E402
    extract_rep_metrics,
    session_modal_bar_path_classification,
)
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
    if exercise in ("squat", "deadlift"):
        print("rep_index,lumbar_flexion_proxy_delta_deg,technique_consistency_std,lifter_side")
        for r in rep_metrics:
            lumbar = r.metrics.get("lumbar_flexion_proxy_delta_deg")
            tcs = r.metrics.get("technique_consistency_std")
            print(f"{r.rep_index},{lumbar},{tcs},{side}")
    elif exercise == "bench":
        modal = session_modal_bar_path_classification(rep_metrics)
        print(f"# session_modal_bar_path_classification={modal}")
        print("rep_index,bar_path_classification,lifter_side")
        for r in rep_metrics:
            label = r.metrics.get("bar_path_classification")
            print(f"{r.rep_index},{label},{side}")
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
