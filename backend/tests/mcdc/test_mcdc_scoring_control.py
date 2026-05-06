"""MC/DC truth-table tests for ControlScore (scoring.py).

Conditions tested
-----------------
1. ControlScore.compute — two-tier descent: descent < high_s / elif descent < caution_s
   (high_s = 1.0, caution_s = 1.5)
2. ControlScore.compute — compound AND: rep_std is not None AND rep_std > std_caution
   (std_caution = 0.5)
3. ControlScore.compute — deadlift lockout chain:
     exercise_type == "deadlift"
     AND lockout_angle is not None
     AND lockout_angle < min_lockout  (min_lockout = 150.0)
"""

from pathlib import Path

import pytest

from app.config import ThresholdConfig
from app.cv.scoring import ControlScore

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


@pytest.fixture()
def scorer() -> ControlScore:
    return ControlScore()


# ---------------------------------------------------------------------------
# 1. Two-tier descent penalty
#    high_s = 1.0, caution_s = 1.5
#
#    Row | descent           | penalty | badge                      | varied condition
#    ----|-------------------|---------|----------------------------|------------------
#    1   | >= caution (1.5)  | 0       | none                       | both false → no branch
#    2   | [high, caution)   | -2.0    | descent_too_fast_caution   | first < false, second < true
#    3   | < high (1.0)      | -3.0    | descent_too_fast_high      | first < true (short-circuits)
# ---------------------------------------------------------------------------
class TestControlDescentTwoTier:
    """MC/DC truth table for the two-tier descent penalty."""

    def _compute(
        self,
        scorer: ControlScore,
        cfg: ThresholdConfig,
        descent: float,
    ) -> tuple[float, list]:
        metrics = {"descent_duration_s": descent}
        return scorer.compute(metrics, None, cfg, "squat")

    def test_row1_no_penalty_when_descent_at_or_above_caution(
        self, scorer: ControlScore, cfg: ThresholdConfig
    ) -> None:
        """Row 1: descent >= caution_s (1.5) → no penalty, no badge."""
        score, badges = self._compute(scorer, cfg, descent=1.5)

        assert score == 10.0
        assert badges == []

    def test_row2_caution_penalty_when_descent_between_high_and_caution(
        self, scorer: ControlScore, cfg: ThresholdConfig
    ) -> None:
        """Row 2: high_s <= descent < caution_s → -2.0 and caution badge."""
        score, badges = self._compute(scorer, cfg, descent=1.2)

        assert score == 8.0
        assert len(badges) == 1
        assert badges[0].issue_key == "descent_too_fast_caution"
        assert badges[0].severity == "High"

    def test_row3_high_penalty_when_descent_below_high(
        self, scorer: ControlScore, cfg: ThresholdConfig
    ) -> None:
        """Row 3: descent < high_s (1.0) → -3.0 and high badge."""
        score, badges = self._compute(scorer, cfg, descent=0.8)

        assert score == 7.0
        assert len(badges) == 1
        assert badges[0].issue_key == "descent_too_fast_high"
        assert badges[0].severity == "High"


# ---------------------------------------------------------------------------
# 2. Rep duration std compound AND
#    Condition A: rep_std is not None
#    Condition B: rep_std > std_caution (0.5)
#
#    Gate fires only when A AND B.
#
#    Row | A     | B     | fire? | varied condition
#    ----|-------|-------|-------|------------------
#    1   | False | -     | False | A alone controls
#    2   | True  | False | False | B alone controls (A=True, B=False)
#    3   | True  | True  | True  | B controls vs row 2
# ---------------------------------------------------------------------------
class TestControlRepDurationStd:
    """MC/DC truth table for the rep duration std compound AND gate."""

    def _compute_std(
        self,
        scorer: ControlScore,
        cfg: ThresholdConfig,
        rep_std: float | None,
    ) -> tuple[float, list]:
        metrics: dict = {}
        if rep_std is not None:
            metrics["rep_duration_std"] = rep_std
        return scorer.compute(metrics, None, cfg, "squat")

    def test_row1_no_penalty_when_rep_std_absent(
        self, scorer: ControlScore, cfg: ThresholdConfig
    ) -> None:
        """Row 1: rep_std not present → gate skipped entirely."""
        score, badges = self._compute_std(scorer, cfg, rep_std=None)

        assert score == 10.0
        badge_keys = [b.issue_key for b in badges]
        assert "rep_duration_inconsistent" not in badge_keys

    def test_row2_no_penalty_when_rep_std_at_or_below_threshold(
        self, scorer: ControlScore, cfg: ThresholdConfig
    ) -> None:
        """Row 2: rep_std present but <= 0.5 → no penalty (B is False)."""
        score, badges = self._compute_std(scorer, cfg, rep_std=0.5)

        assert score == 10.0
        badge_keys = [b.issue_key for b in badges]
        assert "rep_duration_inconsistent" not in badge_keys

    def test_row3_penalty_when_rep_std_above_threshold(
        self, scorer: ControlScore, cfg: ThresholdConfig
    ) -> None:
        """Row 3: rep_std present AND > 0.5 → -1.0 and inconsistent badge."""
        score, badges = self._compute_std(scorer, cfg, rep_std=0.6)

        assert score == 9.0
        assert len(badges) == 1
        assert badges[0].issue_key == "rep_duration_inconsistent"
        assert badges[0].severity == "Medium"


# ---------------------------------------------------------------------------
# 3. Deadlift lockout chain
#    Condition A: exercise_type == "deadlift"
#    Condition B: lockout_angle is not None
#    Condition C: lockout_angle < min_lockout (150.0)
#
#    Penalty fires only when A AND B AND C.
#
#    Row | A     | B     | C     | fire? | varied condition
#    ----|-------|-------|-------|-------|------------------
#    1   | False | -     | -     | False | A alone controls (non-deadlift)
#    2   | True  | False | -     | False | B alone controls
#    3   | True  | True  | False | False | C alone controls
#    4   | True  | True  | True  | True  | C controls vs row 3
# ---------------------------------------------------------------------------
class TestControlDeadliftLockout:
    """MC/DC truth table for the deadlift lockout chain."""

    def _compute_lockout(
        self,
        scorer: ControlScore,
        cfg: ThresholdConfig,
        exercise_type: str,
        lockout_angle: float | None,
    ) -> tuple[float, list]:
        metrics: dict = {}
        if lockout_angle is not None:
            metrics["knee_angle_at_lockout"] = lockout_angle
        return scorer.compute(metrics, None, cfg, exercise_type)

    def test_row1_no_penalty_for_non_deadlift_exercise(
        self, scorer: ControlScore, cfg: ThresholdConfig
    ) -> None:
        """Row 1: exercise is squat → lockout block never entered."""
        score, badges = self._compute_lockout(
            scorer, cfg, exercise_type="squat", lockout_angle=130.0
        )

        assert score == 10.0
        badge_keys = [b.issue_key for b in badges]
        assert "lockout_incomplete" not in badge_keys

    def test_row2_no_penalty_when_deadlift_but_lockout_angle_absent(
        self, scorer: ControlScore, cfg: ThresholdConfig
    ) -> None:
        """Row 2: deadlift but knee_angle_at_lockout not in metrics → skip."""
        score, badges = self._compute_lockout(
            scorer, cfg, exercise_type="deadlift", lockout_angle=None
        )

        assert score == 10.0
        badge_keys = [b.issue_key for b in badges]
        assert "lockout_incomplete" not in badge_keys

    def test_row3_no_penalty_when_deadlift_angle_above_min(
        self, scorer: ControlScore, cfg: ThresholdConfig
    ) -> None:
        """Row 3: deadlift, angle present, angle >= min_lockout (150) → no penalty."""
        score, badges = self._compute_lockout(
            scorer, cfg, exercise_type="deadlift", lockout_angle=155.0
        )

        assert score == 10.0
        badge_keys = [b.issue_key for b in badges]
        assert "lockout_incomplete" not in badge_keys

    def test_row4_penalty_when_deadlift_angle_below_min(
        self, scorer: ControlScore, cfg: ThresholdConfig
    ) -> None:
        """Row 4: deadlift, angle present, angle < min_lockout (150) → -1.5 and badge."""
        score, badges = self._compute_lockout(
            scorer, cfg, exercise_type="deadlift", lockout_angle=140.0
        )

        assert score == 8.5
        assert len(badges) == 1
        assert badges[0].issue_key == "lockout_incomplete"
        assert badges[0].severity == "Medium"
