"""Integration test — lifter-side detection on the 3 atharva fixtures
(Session 2, L2-LIFTER-SIDE-05).

Runs detection against real pose data extracted from each fixture. The
detected side is printed via ``capsys`` so it appears in the pytest
output and PR description.

Ground-truth verification: open each fixture video and eyeball which
side of the lifter faces the camera. If detection disagrees, that is a
STOP trigger per the Session 2 /goal STOP clauses.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.cv.lifter_side import detect_lifter_side
from app.cv.pose_extraction import extract_landmarks

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "e2e" / "fixtures"

FIXTURES = [
    ("atharva-squat.mov", "squat"),
    ("atharva-bench.mov", "bench"),
    ("atharva-deadlift.mov", "deadlift"),
]


@pytest.mark.integration
@pytest.mark.parametrize("filename,exercise", FIXTURES)
def test_detect_lifter_side_on_atharva_fixture(
    filename: str, exercise: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Detected side is captured in stdout; eyeball against the video frame."""
    fixture_path = FIXTURE_DIR / filename
    if not fixture_path.exists():
        pytest.skip(f"Fixture not available: {fixture_path}")

    landmarks, fps, _w, _h = extract_landmarks(str(fixture_path))
    if not landmarks:
        pytest.skip(f"No landmarks extracted from {filename}")

    session = np.stack(landmarks)
    side = detect_lifter_side(session, fps=fps)

    assert side in ("left", "right"), f"unexpected side {side!r}"
    with capsys.disabled():
        print(f"\n[lifter-side] {filename} ({exercise}) detected: {side}")


@pytest.mark.integration
def test_detect_lifter_side_is_stable_on_repeat_invocations() -> None:
    """Same input → same output across N calls (no randomness)."""
    fixture_path = FIXTURE_DIR / "atharva-squat.mov"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not available: {fixture_path}")
    landmarks, fps, _w, _h = extract_landmarks(str(fixture_path))
    session = np.stack(landmarks)
    sides = {detect_lifter_side(session, fps=fps) for _ in range(3)}
    assert len(sides) == 1, f"detection unstable across runs: {sides}"
