"""MC/DC truth-table tests for TechniqueScore (scoring.py).

Conditions tested
-----------------
1. TechniqueScore.compute — compound AND: depth_std is not None AND depth_std > 10.0
2. TechniqueScore._score_bench — negated range: not (70.0 <= elbow_angle <= 90.0)

Note: The two-tier elbow_flare branch was removed in cv-audit cleanup
2026-05-22 (audit item A-1). It read a metric that metric_extraction.py never
produces — it would require a frontal-plane camera. Its MC/DC truth table is
no longer needed.
"""

from pathlib import Path

import pytest

from app.config import ThresholdConfig
from app.cv.scoring import TechniqueScore

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


@pytest.fixture()
def scorer() -> TechniqueScore:
    return TechniqueScore()


# ---------------------------------------------------------------------------
# 1. Compound AND: depth_std is not None AND depth_std > 10.0
# ---------------------------------------------------------------------------
class TestTechniqueDepthStdAnd:
    """MC/DC truth table for the rep-consistency penalty gate.

    Condition A: depth_std is not None
    Condition B: depth_std > 10.0

    Gate fires only when A AND B.

    Row | A     | B     | fire? | varied condition
    ----|-------|-------|-------|------------------
    1   | False | -     | False | A (A alone controls)
    2   | True  | False | False | B (B alone controls)
    3   | True  | True  | True  | B (B controls vs row 2)
    """

    def _base_metrics(self) -> dict:
        return {"confidence_score": 1.0}

    def test_row1_depth_std_absent_no_penalty(
        self, scorer: TechniqueScore, cfg: ThresholdConfig
    ) -> None:
        """A=False → gate does not fire; rep_consistency_low badge absent."""
        metrics = self._base_metrics()
        # depth_angle_std key is not present (None via .get())
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        badge_keys = [b.issue_key for b in badges]
        assert "rep_consistency_low" not in badge_keys
        assert score == pytest.approx(10.0, abs=5.0)  # no consistency penalty

    def test_row2_depth_std_present_below_threshold_no_penalty(
        self, scorer: TechniqueScore, cfg: ThresholdConfig
    ) -> None:
        """A=True, B=False → gate does not fire; no badge."""
        metrics = {**self._base_metrics(), "depth_angle_std": 10.0}  # exactly at threshold, not >
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        badge_keys = [b.issue_key for b in badges]
        assert "rep_consistency_low" not in badge_keys

    def test_row3_depth_std_present_above_threshold_penalty_applied(
        self, scorer: TechniqueScore, cfg: ThresholdConfig
    ) -> None:
        """A=True, B=True → gate fires; badge added and score reduced."""
        metrics = {**self._base_metrics(), "depth_angle_std": 15.0}  # 15 > 10
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        badge_keys = [b.issue_key for b in badges]
        assert "rep_consistency_low" in badge_keys
        # Expected penalty: min(3.0, (15.0 - 10.0) * 0.2) = min(3.0, 1.0) = 1.0
        assert score == pytest.approx(10.0 - 1.0, abs=0.01)


# ---------------------------------------------------------------------------
# 2. Negated range: not (70.0 <= elbow_angle <= 90.0)
# ---------------------------------------------------------------------------
class TestTechniqueBenchElbowRange:
    """MC/DC truth table for elbow-angle-off-target penalty.

    The condition is: not (target_min <= elbow_angle <= target_max)
    where target_min=70.0, target_max=90.0 (HARDCODED in source).

    Row | in range? | penalty? | badge?
    ----|-----------|----------|-------
    1   | True      | No       | absent
    2   | angle<70  | Yes      | present
    3   | angle>90  | Yes      | present
    """

    def _bench_metrics(self, elbow_angle: float) -> dict:
        return {
            "confidence_score": 1.0,
            "elbow_angle_at_bottom": elbow_angle,
        }

    def test_row1_angle_in_range_no_penalty(
        self, scorer: TechniqueScore, cfg: ThresholdConfig
    ) -> None:
        """Angle = 80° (within [70, 90]) → no penalty, badge absent."""
        metrics = self._bench_metrics(80.0)
        score, badges = scorer.compute(metrics, None, cfg, "bench")
        badge_keys = [b.issue_key for b in badges]
        assert "elbow_angle_off_target" not in badge_keys
        assert score == pytest.approx(10.0, abs=5.0)

    def test_row2_angle_below_minimum_penalty_applied(
        self, scorer: TechniqueScore, cfg: ThresholdConfig
    ) -> None:
        """Angle = 60° (< 70) → penalty of 1.5, badge present."""
        metrics = self._bench_metrics(60.0)
        score, badges = scorer.compute(metrics, None, cfg, "bench")
        badge_keys = [b.issue_key for b in badges]
        assert "elbow_angle_off_target" in badge_keys
        # Penalty is exactly 1.5 (hardcoded)
        assert score == pytest.approx(10.0 - 1.5, abs=0.01)

    def test_row3_angle_above_maximum_penalty_applied(
        self, scorer: TechniqueScore, cfg: ThresholdConfig
    ) -> None:
        """Angle = 100° (> 90) → penalty of 1.5, badge present."""
        metrics = self._bench_metrics(100.0)
        score, badges = scorer.compute(metrics, None, cfg, "bench")
        badge_keys = [b.issue_key for b in badges]
        assert "elbow_angle_off_target" in badge_keys
        assert score == pytest.approx(10.0 - 1.5, abs=0.01)


# Section 3 (two-tier elbow_flare branch) removed 2026-05-22 along with the
# dead code in scoring.py. See cv-audit cleanup, audit item A-1.
