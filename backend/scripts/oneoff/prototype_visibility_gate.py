"""D-044 prototype: test visibility-gated angle interpolation against all 4 fixtures.

Extracts each fixture's landmarks ONCE (cached), then loops over thresholds
to measure rep count per fixture. Operator-run, not in CI. Discarded after
D-044 ships.

Usage:
    PYTHONUNBUFFERED=1 uv run python scripts/oneoff/prototype_visibility_gate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np  # noqa: E402

from app.cv.pose_extraction import extract_landmarks  # noqa: E402
from app.cv.rep_detection import detect_reps  # noqa: E402
from app.cv.signal_processing import calculate_joint_angles, smooth_signal  # noqa: E402


FIXTURES = [
    ("atharva-bench.mov", "bench", "flat", "elbow_angle", (12, 14, 16)),
    ("atharva-bench-nw-10s-720p.mp4", "bench", "flat", "elbow_angle", (12, 14, 16)),
    ("atharva-squat.mov", "squat", "standard", "hip_angle", (12, 24, 26)),
    ("atharva-deadlift.mov", "deadlift", "conventional", "hip_angle", (12, 24, 26)),
]

GT = {
    "atharva-bench.mov": 5,
    "atharva-bench-nw-10s-720p.mp4": 1,
    "atharva-squat.mov": 5,
    "atharva-deadlift.mov": 5,
}


def sig(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def main() -> int:
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "e2e" / "fixtures"

    # Cache extraction results
    cache: dict[str, tuple] = {}
    for fname, ex, variant, ang_key, idx in FIXTURES:
        path = fixtures_dir / fname
        print(f"extract: {fname}", flush=True)
        landmarks, fps, _, _ = extract_landmarks(str(path))
        # compute angle + per-frame min-confidence once
        angles: list[float] = []
        confs: list[float] = []
        for lm in landmarks:
            a = calculate_joint_angles(lm, ex)[ang_key]
            c = min(sig(lm[i, 3]) * sig(lm[i, 4]) for i in idx)
            angles.append(a)
            confs.append(c)
        cache[fname] = (
            np.array(angles, dtype=float),
            np.array(confs, dtype=float),
            landmarks,
            fps,
            ex,
            variant,
        )

    # Baseline (no gating) — sanity check we reproduce the earlier baseline
    print("\n=== BASELINE (no gating) ===", flush=True)
    for fname, _, _, _, _ in FIXTURES:
        angles, _, landmarks, fps, ex, variant = cache[fname]
        reps = detect_reps(smooth_signal(angles), landmarks, ex, variant, fps)
        print(f"  {fname}: reps={len(reps)} (GT={GT[fname]})", flush=True)

    for t in [0.25, 0.30, 0.35, 0.40]:
        print(f"\n=== threshold={t} ===", flush=True)
        for fname, _, _, _, _ in FIXTURES:
            angles, confs, landmarks, fps, ex, variant = cache[fname]
            mask = confs < t
            if mask.any() and not mask.all():
                valid = np.where(~mask)[0]
                gated = np.interp(np.arange(len(angles)), valid, angles[valid])
            else:
                gated = angles.copy()
            reps = detect_reps(smooth_signal(gated), landmarks, ex, variant, fps)
            print(
                f"  {fname}: masked={mask.sum():>4}/{len(angles)} ({100 * mask.sum() / len(angles):.1f}%) reps={len(reps)} (GT={GT[fname]})",
                flush=True,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
