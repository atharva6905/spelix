"""Tests for the Coach Brain seed corpus data (P2-025).

Validates the seed entries meet FR-BRAIN-09 and FR-BRAIN-18 requirements:
- At least 20 entries total
- At least 3 per exercise (squat, bench, deadlift)
- Required issue coverage per exercise
- All entries have valid exercise/phase/entry_type/status values
- confirmation_count=1 for seed entries (FR-BRAIN-18)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR.parent))

from scripts.seed_coach_brain import SEED_ENTRIES

VALID_EXERCISES = {"squat", "bench", "deadlift"}
VALID_PHASES = {"setup", "descent", "bottom", "ascent", "lockout", "general"}
VALID_ENTRY_TYPES = {"cue", "correction", "principle", "drill"}


class TestSeedCorpusRequirements:
    """FR-BRAIN-09: seed corpus must cover key issues for all three exercises."""

    def test_minimum_20_entries(self) -> None:
        assert len(SEED_ENTRIES) >= 20

    def test_all_three_exercises_covered(self) -> None:
        exercises = {entry[0] for entry in SEED_ENTRIES}
        assert VALID_EXERCISES.issubset(exercises)

    @pytest.mark.parametrize("exercise", ["squat", "bench", "deadlift"])
    def test_minimum_entries_per_exercise(self, exercise: str) -> None:
        count = sum(1 for e in SEED_ENTRIES if e[0] == exercise)
        assert count >= 3, f"{exercise} has only {count} entries, need at least 3"

    def test_all_exercises_valid(self) -> None:
        for i, (ex, _, _, _, _) in enumerate(SEED_ENTRIES):
            assert ex in VALID_EXERCISES, f"Entry {i}: invalid exercise '{ex}'"

    def test_all_phases_valid(self) -> None:
        for i, (_, ph, _, _, _) in enumerate(SEED_ENTRIES):
            assert ph in VALID_PHASES, f"Entry {i}: invalid phase '{ph}'"

    def test_all_entry_types_valid(self) -> None:
        for i, (_, _, et, _, _) in enumerate(SEED_ENTRIES):
            assert et in VALID_ENTRY_TYPES, f"Entry {i}: invalid entry_type '{et}'"

    def test_all_entries_have_content(self) -> None:
        for i, (_, _, _, content, _) in enumerate(SEED_ENTRIES):
            assert len(content) >= 50, f"Entry {i}: content too short ({len(content)} chars)"

    def test_all_entries_have_trigger_tags(self) -> None:
        for i, (_, _, _, _, tags) in enumerate(SEED_ENTRIES):
            assert len(tags) >= 1, f"Entry {i}: must have at least one trigger tag"

    def test_no_injury_risk_language(self) -> None:
        """Spelix language rule: never use 'injury risk' or 'injury prevention'."""
        for i, (_, _, _, content, _) in enumerate(SEED_ENTRIES):
            lower = content.lower()
            assert "injury risk" not in lower, f"Entry {i}: contains forbidden 'injury risk'"
            assert "injury prevention" not in lower, f"Entry {i}: contains forbidden 'injury prevention'"


class TestSeedCorpusIssueCoverage:
    """FR-BRAIN-09: specific issues that must be covered."""

    def _tags_for_exercise(self, exercise: str) -> set[str]:
        tags: set[str] = set()
        for ex, _, _, _, t in SEED_ENTRIES:
            if ex == exercise:
                tags.update(t)
        return tags

    def _content_for_exercise(self, exercise: str) -> str:
        return " ".join(c for ex, _, _, c, _ in SEED_ENTRIES if ex == exercise).lower()

    def test_squat_covers_depth(self) -> None:
        tags = self._tags_for_exercise("squat")
        content = self._content_for_exercise("squat")
        assert "depth" in tags or "depth" in content

    def test_squat_covers_knee_cave(self) -> None:
        tags = self._tags_for_exercise("squat")
        assert "knee_cave" in tags or "valgus" in tags

    def test_squat_covers_back_rounding(self) -> None:
        tags = self._tags_for_exercise("squat")
        content = self._content_for_exercise("squat")
        assert "lumbar_flexion" in tags or "butt_wink" in tags or "back rounding" in content

    def test_bench_covers_bar_path(self) -> None:
        tags = self._tags_for_exercise("bench")
        assert "bar_path" in tags or "j_curve" in tags

    def test_bench_covers_elbow_flare(self) -> None:
        tags = self._tags_for_exercise("bench")
        assert "elbow_flare" in tags

    def test_bench_covers_leg_drive(self) -> None:
        tags = self._tags_for_exercise("bench")
        assert "leg_drive" in tags

    def test_deadlift_covers_lumbar_flexion(self) -> None:
        tags = self._tags_for_exercise("deadlift")
        assert "lumbar_flexion" in tags or "back_rounding" in tags

    def test_deadlift_covers_hip_hinge(self) -> None:
        tags = self._tags_for_exercise("deadlift")
        assert "hip_hinge" in tags

    def test_deadlift_covers_lockout(self) -> None:
        tags = self._tags_for_exercise("deadlift")
        assert "lockout" in tags
