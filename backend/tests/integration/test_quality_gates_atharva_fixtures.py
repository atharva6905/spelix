"""Real-video quality-gate integration test against atharva-* fixtures.

Marked ``@pytest.mark.slow`` — runs MediaPipe BlazePose Heavy on three
~20-26 s 1080p videos. ~3-5 min wall-clock on a laptop CPU. Skipped in CI
by default; run locally before merging quality-gate changes.

To run:
    uv run pytest tests/integration/test_quality_gates_atharva_fixtures.py -v -m slow

Acceptance criterion AC-1 of:
    docs/superpowers/specs/2026-04-24-commercial-gym-quality-gate-design.md
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from app.cv.pose_extraction import extract_landmarks
from app.cv.quality_gates import run_quality_gates


def _find_fixtures_dir() -> Path:
    """Locate e2e/fixtures relative to the git repo main worktree.

    When running from a git worktree the file system root differs from the
    main checkout. We use ``git worktree list`` to locate the main worktree
    and look for fixtures there first, then fall back to the repo root
    computed from this file's path.
    """
    # Allow explicit override via environment variable
    env_path = os.environ.get("SPELIX_FIXTURES_DIR")
    if env_path:
        return Path(env_path)

    # Try to find the main worktree via git
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("worktree "):
                    candidate = Path(line.split(" ", 1)[1]) / "e2e" / "fixtures"
                    if candidate.exists():
                        return candidate
    except Exception:
        pass

    # Default: relative to this file (backend/tests/integration/ → repo root)
    return Path(__file__).resolve().parents[3] / "e2e" / "fixtures"


FIXTURES_DIR = _find_fixtures_dir()

FIXTURE_TABLE = [
    ("atharva-squat.mov", "squat"),
    ("atharva-bench.mov", "bench"),
    ("atharva-deadlift.mov", "deadlift"),
]


@pytest.mark.slow
@pytest.mark.parametrize("filename,exercise_type", FIXTURE_TABLE)
def test_atharva_fixture_passes_quality_gate(
    filename: str, exercise_type: str
) -> None:
    """All 3 commercial-gym fixtures must pass the gate after the
    anchor + visibility-gated changes (ADR-QGATE-COMMERCIAL-GYM).

    Each fixture is a 1080×1920 portrait, ~60 fps, 20-26 s commercial-gym
    shoot with 3-6 bystanders in the background. Pre-fix: all 3 rejected.
    Post-fix: all 3 must pass.
    """
    video_path = FIXTURES_DIR / filename
    if not video_path.exists():
        pytest.skip(f"Missing fixture: {video_path}")

    landmarks, fps, width, height = extract_landmarks(str(video_path))

    # Do NOT pass video_path — check_video_file calls FFprobe which has
    # codec-support issues with .mov files in the local Windows environment
    # (the gate is tested separately in unit/test_quality_gates.py::TestCheckVideoFile).
    # This test focuses on check_single_person and check_framing which are the
    # landmark-based gates changed by ADR-QGATE-COMMERCIAL-GYM.
    result = run_quality_gates(
        landmarks_per_frame=landmarks,
        frame_width=width,
        frame_height=height,
        exercise_type=exercise_type,
    )

    # Print per-check metrics for diagnosis
    for check in result.checks:
        status = "PASS" if check.passed else "FAIL"
        print(
            f"  [{status}] {check.name}: metric={check.metric_value:.4f} "
            f"thr={check.threshold:.4f} level={check.level}"
        )

    failed_checks = [c for c in result.checks if not c.passed and c.level == "error"]
    assert result.passed is True, (
        f"{filename} rejected by quality gate. Failing error-level checks:\n"
        + "\n".join(
            f"  {c.name}: metric={c.metric_value:.4f} thr={c.threshold:.4f} "
            f"msg={c.user_message!r}"
            for c in failed_checks
        )
    )
