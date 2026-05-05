"""MC/DC truth-table tests for SafetyScore (scoring.py).

Conditions under test
---------------------
1. SafetyScore.compute — confidence cap:
       C1: confidence < 0.50
   Truth table:
       C1=T → score = min(score, 5.0)
       C1=F → score unchanged

2. SafetyScore._score_squat — torso_lean two-tier:
       C2: torso_lean > high          (3.0 penalty, "torso_lean_high")
       C3: torso_lean > caution       (1.5 penalty, "torso_lean_caution" — only if C2 is False)
   Truth table (ordered — elif chain):
       C2=T, C3=any  → high penalty (C2 independently causes it)
       C2=F, C3=T    → caution penalty (C3 independently causes it when C2 flips F)
       C2=F, C3=F    → no penalty

   Also: torso_lean None-guard:
       None  → skip the block entirely
       not None → evaluate C2/C3

3. SafetyScore._score_squat — knee_angle None-guard + below-min:
       C4: knee_angle_at_depth is not None
       C5: knee_angle_at_depth < min_knee
   Truth table:
       C4=F          → skip (None)
       C4=T, C5=F    → no penalty
       C4=T, C5=T    → 2.0 penalty, "knee_angle_at_depth_low"

4. SafetyScore._score_deadlift — hip_angle compound OR:
       C6: hip_angle < min_hip
       C7: hip_angle > max_hip
   Truth table (MC/DC — each condition independently switches outcome):
       C6=F, C7=F → no penalty
       C6=T, C7=F → penalty (C6 flips outcome)
       C6=F, C7=T → penalty (C7 flips outcome)

   Also: hip_angle None-guard:
       None  → skip

5. SafetyScore._score_bench — elbow_angle compound OR:
       C8: elbow_angle < min_elbow
       C9: elbow_angle > max_elbow
   Truth table:
       C8=F, C9=F → no penalty
       C8=T, C9=F → penalty (C8 flips outcome)
       C8=F, C9=T → penalty (C9 flips outcome)

6. SafetyScore._score_bench — shoulder threshold:
       C10: shoulder_angle > max_shoulder
   Truth table:
       C10=F → no penalty
       C10=T → 2.0 penalty, "shoulder_angle_high"
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig
from app.cv.scoring import SafetyScore


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


@pytest.fixture()
def scorer() -> SafetyScore:
    return SafetyScore()


# ---------------------------------------------------------------------------
# 1. Confidence cap
# ---------------------------------------------------------------------------


class TestSafetyComputeConfidenceCap:
    """MC/DC for: if confidence < 0.50: score = min(score, 5.0)"""

    def test_confidence_low_caps_score__squat_perfect_form(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C1=T (confidence=0.30 < 0.50) — score must be capped at 5.0 even
        when form metrics are perfect (score would otherwise be 10.0)."""
        metrics = {
            "confidence_score": 0.30,
            # no torso_lean, no knee_angle — so base score stays 10.0
        }
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 5.0, f"Expected 5.0 but got {score}"

    def test_confidence_high_does_not_cap__squat_perfect_form(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C1=F (confidence=0.80 >= 0.50) — cap branch never fires; score stays 10.0."""
        metrics = {
            "confidence_score": 0.80,
        }
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0, f"Expected 10.0 but got {score}"

    def test_confidence_boundary_exactly_050_does_not_cap(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C1=F (confidence=0.50 is NOT < 0.50) — boundary: cap should NOT fire."""
        metrics = {
            "confidence_score": 0.50,
        }
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0, f"Expected 10.0 but got {score}"


# ---------------------------------------------------------------------------
# 2. Squat torso_lean two-tier
# ---------------------------------------------------------------------------


class TestSafetyScoreSquatTorsoLean:
    """MC/DC for the two-tier torso_lean elif chain in _score_squat."""

    def test_torso_lean_none__skips_block(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """torso_lean=None — None-guard fires, entire block skipped, score 10.0."""
        metrics = {"confidence_score": 1.0}  # no torso_lean key
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0
        assert not any(b.issue_key.startswith("torso_lean") for b in badges)

    def test_torso_lean_below_caution__no_penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C2=F, C3=F — torso lean below caution threshold → no penalty."""
        caution = cfg.get("squat", "torso_lean_caution_deg")  # 45.0
        metrics = {
            "confidence_score": 1.0,
            "torso_lean": caution - 1.0,  # 44.0 — below caution
        }
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0
        assert not any(b.issue_key.startswith("torso_lean") for b in badges)

    def test_torso_lean_between_caution_and_high__caution_penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C2=F, C3=T — torso lean above caution but below high → 1.5 penalty,
        'torso_lean_caution' badge. C3 independently determines outcome when C2=F."""
        caution = cfg.get("squat", "torso_lean_caution_deg")  # 45.0
        high = cfg.get("squat", "torso_lean_high_deg")  # 60.0
        metrics = {
            "confidence_score": 1.0,
            "torso_lean": (caution + high) / 2.0,  # 52.5 — in caution zone
        }
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == pytest.approx(10.0 - 1.5)
        assert any(b.issue_key == "torso_lean_caution" for b in badges)
        assert not any(b.issue_key == "torso_lean_high" for b in badges)

    def test_torso_lean_above_high__high_penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C2=T — torso lean above high threshold → 3.0 penalty, 'torso_lean_high' badge.
        C2=T independently determines outcome regardless of C3."""
        high = cfg.get("squat", "torso_lean_high_deg")  # 60.0
        metrics = {
            "confidence_score": 1.0,
            "torso_lean": high + 5.0,  # 65.0 — above high
        }
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == pytest.approx(10.0 - 3.0)
        assert any(b.issue_key == "torso_lean_high" for b in badges)
        assert not any(b.issue_key == "torso_lean_caution" for b in badges)


# ---------------------------------------------------------------------------
# 3. Squat knee_angle_at_depth None-guard + below-min
# ---------------------------------------------------------------------------


class TestSafetyScoreSquatKneeAngle:
    """MC/DC for knee_angle_at_depth None-guard and below-min condition."""

    def test_knee_angle_none__skips_block(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C4=F — knee_angle_at_depth absent → block skipped, no penalty."""
        metrics = {"confidence_score": 1.0}  # no knee_angle_at_depth
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0
        assert not any(b.issue_key == "knee_angle_at_depth_low" for b in badges)

    def test_knee_angle_above_min__no_penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C4=T, C5=F — knee angle present and above minimum → no penalty."""
        min_knee = cfg.get("squat", "knee_angle_at_depth_min_deg")  # 60.0
        metrics = {
            "confidence_score": 1.0,
            "knee_angle_at_depth": min_knee + 10.0,  # 70.0 — safe
        }
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == 10.0
        assert not any(b.issue_key == "knee_angle_at_depth_low" for b in badges)

    def test_knee_angle_below_min__penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C4=T, C5=T — knee angle below minimum → 2.0 penalty, badge issued.
        C5 independently switches outcome when C4=T."""
        min_knee = cfg.get("squat", "knee_angle_at_depth_min_deg")  # 60.0
        metrics = {
            "confidence_score": 1.0,
            "knee_angle_at_depth": min_knee - 5.0,  # 55.0 — acute
        }
        score, badges = scorer.compute(metrics, None, cfg, "squat")
        assert score == pytest.approx(10.0 - 2.0)
        assert any(b.issue_key == "knee_angle_at_depth_low" for b in badges)


# ---------------------------------------------------------------------------
# 4. Deadlift hip_angle compound OR
# ---------------------------------------------------------------------------


class TestSafetyDeadliftHipAngle:
    """MC/DC for: if hip_angle < min_hip or hip_angle > max_hip"""

    def test_hip_angle_none__skips_block(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """hip_angle_at_bottom absent → None-guard fires, no penalty."""
        metrics = {"confidence_score": 1.0}
        score, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert score == 10.0
        assert not any(b.issue_key == "hip_angle_extreme" for b in badges)

    def test_hip_angle_in_range__no_penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C6=F, C7=F — hip angle within [min_hip, max_hip] → no penalty."""
        min_hip = cfg.get("deadlift", "hip_angle_at_bottom_min_deg")  # 50.0
        max_hip = cfg.get("deadlift", "hip_angle_at_bottom_max_deg")  # 110.0
        metrics = {
            "confidence_score": 1.0,
            "hip_angle_at_bottom": (min_hip + max_hip) / 2.0,  # 80.0
        }
        score, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert score == 10.0
        assert not any(b.issue_key == "hip_angle_extreme" for b in badges)

    def test_hip_angle_below_min__penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C6=T, C7=F — hip angle below minimum → penalty.
        C6 independently switches the OR to True."""
        min_hip = cfg.get("deadlift", "hip_angle_at_bottom_min_deg")  # 50.0
        metrics = {
            "confidence_score": 1.0,
            "hip_angle_at_bottom": min_hip - 10.0,  # 40.0
        }
        score, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert score == pytest.approx(10.0 - 2.0)
        assert any(b.issue_key == "hip_angle_extreme" for b in badges)

    def test_hip_angle_above_max__penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C6=F, C7=T — hip angle above maximum → penalty.
        C7 independently switches the OR to True."""
        max_hip = cfg.get("deadlift", "hip_angle_at_bottom_max_deg")  # 110.0
        metrics = {
            "confidence_score": 1.0,
            "hip_angle_at_bottom": max_hip + 15.0,  # 125.0
        }
        score, badges = scorer.compute(metrics, None, cfg, "deadlift")
        assert score == pytest.approx(10.0 - 2.0)
        assert any(b.issue_key == "hip_angle_extreme" for b in badges)


# ---------------------------------------------------------------------------
# 5. Bench elbow_angle compound OR
# ---------------------------------------------------------------------------


class TestSafetyBenchElbowAngle:
    """MC/DC for: if elbow_angle < min_elbow or elbow_angle > max_elbow"""

    def test_elbow_angle_in_range__no_penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C8=F, C9=F — elbow angle within [min_elbow, max_elbow] → no penalty."""
        min_elbow = cfg.get("bench", "elbow_angle_at_bottom_min_deg")  # 60.0
        max_elbow = cfg.get("bench", "elbow_angle_at_bottom_max_deg")  # 100.0
        metrics = {
            "confidence_score": 1.0,
            "elbow_angle_at_bottom": (min_elbow + max_elbow) / 2.0,  # 80.0
        }
        score, badges = scorer.compute(metrics, None, cfg, "bench")
        assert score == 10.0
        assert not any(b.issue_key == "elbow_angle_extreme" for b in badges)

    def test_elbow_angle_below_min__penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C8=T, C9=F — elbow angle below minimum → 2.0 penalty.
        C8 independently switches the OR to True."""
        min_elbow = cfg.get("bench", "elbow_angle_at_bottom_min_deg")  # 60.0
        metrics = {
            "confidence_score": 1.0,
            "elbow_angle_at_bottom": min_elbow - 10.0,  # 50.0
        }
        score, badges = scorer.compute(metrics, None, cfg, "bench")
        assert score == pytest.approx(10.0 - 2.0)
        assert any(b.issue_key == "elbow_angle_extreme" for b in badges)

    def test_elbow_angle_above_max__penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C8=F, C9=T — elbow angle above maximum → 2.0 penalty.
        C9 independently switches the OR to True."""
        max_elbow = cfg.get("bench", "elbow_angle_at_bottom_max_deg")  # 100.0
        metrics = {
            "confidence_score": 1.0,
            "elbow_angle_at_bottom": max_elbow + 15.0,  # 115.0
        }
        score, badges = scorer.compute(metrics, None, cfg, "bench")
        assert score == pytest.approx(10.0 - 2.0)
        assert any(b.issue_key == "elbow_angle_extreme" for b in badges)


# ---------------------------------------------------------------------------
# 6. Bench shoulder_angle threshold
# ---------------------------------------------------------------------------


class TestSafetyBenchShoulderAngle:
    """MC/DC for: if shoulder_angle > max_shoulder"""

    def test_shoulder_angle_below_max__no_penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C10=F — shoulder angle within safe range → no penalty."""
        max_shoulder = cfg.get("bench", "shoulder_angle_at_bottom_max_deg")  # 90.0
        metrics = {
            "confidence_score": 1.0,
            "shoulder_angle_at_bottom": max_shoulder - 10.0,  # 80.0
        }
        score, badges = scorer.compute(metrics, None, cfg, "bench")
        assert score == 10.0
        assert not any(b.issue_key == "shoulder_angle_high" for b in badges)

    def test_shoulder_angle_above_max__penalty(
        self, scorer: SafetyScore, cfg: ThresholdConfig
    ) -> None:
        """C10=T — shoulder angle exceeds maximum → 2.0 penalty, badge issued.
        C10 independently switches outcome."""
        max_shoulder = cfg.get("bench", "shoulder_angle_at_bottom_max_deg")  # 90.0
        metrics = {
            "confidence_score": 1.0,
            "shoulder_angle_at_bottom": max_shoulder + 10.0,  # 100.0
        }
        score, badges = scorer.compute(metrics, None, cfg, "bench")
        assert score == pytest.approx(10.0 - 2.0)
        assert any(b.issue_key == "shoulder_angle_high" for b in badges)
