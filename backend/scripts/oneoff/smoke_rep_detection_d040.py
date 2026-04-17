"""D-040 smoke test: verify rep count on partial-lockout bench fixture.

Deletable after the D-040/D-041 PR merges. Runs pose extraction and
rep detection against the session 44 regression fixture and prints
the rep count - must be > 0 after D-040 (was 0 before).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure `app.*` is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.cv.pose_extraction import extract_landmarks  # noqa: E402
from app.cv.rep_detection import detect_reps  # noqa: E402
from app.cv.signal_processing import compute_angle_timeseries  # noqa: E402


FIXTURE = (
    Path(__file__).parent.parent.parent.parent
    / "e2e"
    / "fixtures"
    / "atharva-bench-nw-10s-720p.mp4"
)


def main() -> int:
    if not FIXTURE.exists():
        print(f"Fixture not found: {FIXTURE}")
        return 1

    # extract_landmarks returns (landmarks_per_frame, fps, width, height)
    landmarks_per_frame, fps, _, _ = extract_landmarks(str(FIXTURE))
    print(f"Frames: {len(landmarks_per_frame)}, FPS: {fps:.1f}")

    angle_ts = compute_angle_timeseries(landmarks_per_frame, "bench")
    elbow = angle_ts["elbow_angle"]
    print(
        f"Elbow angle min/max/mean: "
        f"{elbow.min():.1f} / {elbow.max():.1f} / {elbow.mean():.1f}"
    )

    reps = detect_reps(elbow, landmarks_per_frame, "bench", "flat", fps)
    print(f"Detected reps: {len(reps)}")
    for rep in reps:
        print(
            f"  rep {rep.rep_index}: frames {rep.start_frame}..{rep.end_frame}, "
            f"min_angle {rep.min_angle:.1f}"
        )

    if len(reps) == 0:
        print("FAIL: D-040 fix ineffective - got 0 reps on partial-lockout fixture")
        return 1
    print("PASS: rep count > 0 on partial-lockout bench fixture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
