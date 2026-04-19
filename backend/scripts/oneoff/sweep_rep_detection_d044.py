"""D-044 parameter sweep: grid over (savgol_window, savgol_polyorder,
prominence_deg, min_rep_duration_s) and report rep count per fixture.

Writes /tmp/d044-sweep.csv with columns:
    fixture,window,polyorder,prominence,min_rep_s,sm_reps,pv_reps,hybrid_reps

No implementation files are modified — the sweep monkey-patches the module
constants locally inside each iteration, then restores them. Operator-run.

Usage:
    uv run python scripts/oneoff/sweep_rep_detection_d044.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np  # noqa: E402

from app.cv import rep_detection  # noqa: E402
from app.cv.pose_extraction import extract_landmarks  # noqa: E402
from app.cv.signal_processing import calculate_joint_angles, smooth_signal  # noqa: E402


FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "e2e" / "fixtures"
FIXTURES = [
    "atharva-bench.mov",
    "atharva-bench-nw-10s-720p.mp4",
    "atharva-squat.mov",
    "atharva-deadlift.mov",
]

WINDOWS = (7, 11, 15, 21)
POLYS = (2, 3)
PROMINENCES = (20.0, 25.0, 30.0, 35.0, 40.0)
MIN_REP_S_VALUES = (0.5, 0.75, 1.0, 1.5)


def _raw_elbow_or_hip(landmarks_per_frame: list[np.ndarray], exercise: str) -> np.ndarray:
    joint_key = "elbow_angle" if exercise == "bench" else "hip_angle"
    raw: list[float] = []
    for frame in landmarks_per_frame:
        raw.append(float(calculate_joint_angles(frame, exercise)[joint_key]))
    return np.array(raw, dtype=float)


def _fixture_to_exercise(name: str) -> tuple[str, str]:
    if "bench" in name:
        return "bench", "flat"
    if "squat" in name:
        return "squat", "standard"
    return "deadlift", "conventional"


def main() -> int:
    out_csv = Path("/tmp") / "d044-sweep.csv"
    rows: list[dict] = []

    for fixture_name in FIXTURES:
        fixture = FIXTURES_DIR / fixture_name
        if not fixture.exists():
            print(f"skip (missing): {fixture}")
            continue
        print(f"extract: {fixture.name}")
        landmarks_per_frame, fps, _, _ = extract_landmarks(str(fixture))
        exercise, variant = _fixture_to_exercise(fixture_name)
        raw = _raw_elbow_or_hip(landmarks_per_frame, exercise)

        for window in WINDOWS:
            for poly in POLYS:
                if poly >= window:
                    continue
                smoothed = smooth_signal(raw, window=window, polyorder=poly)
                for prom in PROMINENCES:
                    for min_rep_s in MIN_REP_S_VALUES:
                        orig_prom = rep_detection._PROMINENCE_DEG[exercise]
                        orig_min = rep_detection._MIN_REP_DURATION_S
                        rep_detection._PROMINENCE_DEG[exercise] = prom
                        rep_detection._MIN_REP_DURATION_S = min_rep_s
                        try:
                            sm = rep_detection._detect_reps_state_machine(
                                smoothed, exercise, variant, fps
                            )
                            pv = rep_detection._detect_reps_peak_valley(
                                smoothed, exercise, fps
                            )
                            hy = rep_detection.detect_reps(
                                smoothed, landmarks_per_frame, exercise, variant, fps
                            )
                        finally:
                            rep_detection._PROMINENCE_DEG[exercise] = orig_prom
                            rep_detection._MIN_REP_DURATION_S = orig_min
                        rows.append({
                            "fixture": fixture_name,
                            "window": window,
                            "polyorder": poly,
                            "prominence": prom,
                            "min_rep_s": min_rep_s,
                            "sm_reps": len(sm),
                            "pv_reps": len(pv),
                            "hybrid_reps": len(hy),
                        })

    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
