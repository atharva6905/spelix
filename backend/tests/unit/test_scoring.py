"""Unit tests for app.cv.scoring — ScoreComponent Protocol + four concrete scorers.

Requirements: FR-SCOR-01 through FR-SCOR-08

All tests use synthetic metric dicts — no real video, no DB, no IO.
ThresholdConfig is loaded from config/thresholds_v1.json via THRESHOLD_CONFIG_PATH env var.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Point ThresholdConfig at the v1 file for all scoring tests.
# MUST be set before any `app.*` import so the ThresholdConfig loader picks it up.
_V1_PATH = (
    Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
)
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig  # noqa: E402
from app.cv.scoring import (  # noqa: E402
    ControlScore,
    OverallFormScore,
    PathBalanceScore,
    SafetyScore,
    ScoreComponent,
    TechniqueScore,
    score_descriptor,
)
from app.cv.types import BadgeResult, ScoreResult  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


@pytest.fixture()
def scorer() -> OverallFormScore:
    return OverallFormScore()


# ---------------------------------------------------------------------------
# SafetyScore tests (FR-SCOR-01)
# ---------------------------------------------------------------------------


def test_safety_perfect_form_returns_10(cfg: ThresholdConfig) -> None:
    """All metrics within safe ranges → score = 10.0."""
    metrics = {
        "torso_lean": 20.0,
        "knee_angle_at_depth": 85.0,
        "confidence_score": 0.95,
    }
    score, badges = SafetyScore().compute(metrics, None, cfg, "squat")
    assert score == 10.0
    assert badges == []


def test_safety_extreme_torso_lean_penalty(cfg: ThresholdConfig) -> None:
    """Squat torso_lean=70° (above high threshold 60°) → score ≤ 7.0, badge severity=High."""
    metrics = {
        "torso_lean": 70.0,
        "confidence_score": 0.95,
    }
    score, badges = SafetyScore().compute(metrics, None, cfg, "squat")
    assert score <= 7.0
    severities = [b.severity for b in badges]
    assert "High" in severities


def test_safety_caution_torso_lean_penalty(cfg: ThresholdConfig) -> None:
    """Squat torso_lean=50° (above caution 45°, below high 60°) → 7.0 < score < 10.0, badge severity=Medium."""
    metrics = {
        "torso_lean": 50.0,
        "confidence_score": 0.95,
    }
    score, badges = SafetyScore().compute(metrics, None, cfg, "squat")
    assert 7.0 < score < 10.0
    severities = [b.severity for b in badges]
    assert "Medium" in severities
    assert "High" not in severities


def test_safety_caps_at_5_when_very_low_confidence(cfg: ThresholdConfig) -> None:
    """Confidence < 0.50 → safety score capped at 5.0."""
    metrics = {
        "torso_lean": 20.0,
        "confidence_score": 0.30,
    }
    score, _ = SafetyScore().compute(metrics, None, cfg, "squat")
    assert score <= 5.0


# ---------------------------------------------------------------------------
# TechniqueScore tests (FR-SCOR-02)
# ---------------------------------------------------------------------------


def test_technique_missing_depth_penalty(cfg: ThresholdConfig) -> None:
    """Squat depth_angle=110° (above parallel 90°) → score < 8.0."""
    metrics = {"depth_angle": 110.0}
    score, badges = TechniqueScore().compute(metrics, None, cfg, "squat")
    assert score < 8.0


def test_technique_perfect_depth(cfg: ThresholdConfig) -> None:
    """Squat depth_angle=85° → no depth penalty."""
    metrics = {"depth_angle": 85.0}
    score_with_good_depth, badges_good = TechniqueScore().compute(
        metrics, None, cfg, "squat"
    )
    metrics_bad = {"depth_angle": 110.0}
    score_with_bad_depth, _ = TechniqueScore().compute(
        metrics_bad, None, cfg, "squat"
    )
    assert score_with_good_depth > score_with_bad_depth


def test_technique_rep_consistency_penalty(cfg: ThresholdConfig) -> None:
    """High std dev across reps → penalty applied."""
    metrics_consistent = {"depth_angle": 85.0}
    metrics_inconsistent = {"depth_angle": 85.0, "depth_angle_std": 15.0}
    score_consistent, _ = TechniqueScore().compute(
        metrics_consistent, None, cfg, "squat"
    )
    score_inconsistent, _ = TechniqueScore().compute(
        metrics_inconsistent, None, cfg, "squat"
    )
    assert score_inconsistent < score_consistent


# ---------------------------------------------------------------------------
# PathBalanceScore tests (FR-SCOR-03)
# ---------------------------------------------------------------------------


def test_path_balance_none_bar_path_returns_5(cfg: ThresholdConfig) -> None:
    """bar_path=None → score=5.0, badge with 'insufficient data'."""
    score, badges = PathBalanceScore().compute({}, None, cfg, "squat")
    assert score == 5.0
    assert len(badges) == 1
    assert "insufficient" in badges[0].message.lower()


def test_path_balance_consistent_path_high_score(cfg: ThresholdConfig) -> None:
    """path_consistency=0.98 → score ≥ 9.0."""
    bar_path = {"path_consistency": 0.98, "ap_deviation_px": 0.01}
    score, badges = PathBalanceScore().compute({}, bar_path, cfg, "squat")
    assert score >= 9.0


def test_path_balance_poor_consistency_penalty(cfg: ThresholdConfig) -> None:
    """path_consistency=0.7 → score < 7.0."""
    bar_path = {"path_consistency": 0.7, "ap_deviation_px": 0.01}
    score, badges = PathBalanceScore().compute({}, bar_path, cfg, "squat")
    assert score < 7.0


# ---------------------------------------------------------------------------
# ControlScore tests (FR-SCOR-04)
# ---------------------------------------------------------------------------


def test_control_slow_eccentric_no_penalty(cfg: ThresholdConfig) -> None:
    """descent_duration_s=3.0 → no penalty (above caution threshold)."""
    metrics = {"descent_duration_s": 3.0}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    assert score == 10.0
    assert badges == []


def test_control_fast_eccentric_penalty(cfg: ThresholdConfig) -> None:
    """descent_duration_s=0.5 → penalty, badge severity=High."""
    metrics = {"descent_duration_s": 0.5}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    assert score < 10.0
    severities = [b.severity for b in badges]
    assert "High" in severities


def test_control_lockout_penalty_deadlift(cfg: ThresholdConfig) -> None:
    """knee_angle_at_lockout=140° (below 150° min) → penalty."""
    metrics_good = {"knee_angle_at_lockout": 160.0}
    metrics_bad = {"knee_angle_at_lockout": 140.0}
    score_good, _ = ControlScore().compute(metrics_good, None, cfg, "deadlift")
    score_bad, _ = ControlScore().compute(metrics_bad, None, cfg, "deadlift")
    assert score_bad < score_good


# ---------------------------------------------------------------------------
# OverallFormScore tests (FR-SCOR-05)
# ---------------------------------------------------------------------------


def test_overall_weighted_composite(cfg: ThresholdConfig) -> None:
    """Known 4 scores (10, 8, 6, 4) with weights (0.4, 0.3, 0.2, 0.1) → 8.0."""

    class _FixedScorer:
        def __init__(
            self,
            internal_name: str,
            display_name: str,
            weight: float,
            fixed_score: float,
        ) -> None:
            self.internal_name = internal_name
            self.display_name = display_name
            self.weight = weight
            self._fixed_score = fixed_score

        def compute(
            self,
            metrics: dict,
            bar_path: dict | None,
            cfg: ThresholdConfig,
            exercise_type: str,
        ) -> tuple[float, list]:
            return self._fixed_score, []

    scorers = [
        _FixedScorer("movement_quality", "Movement Quality", 0.40, 10.0),
        _FixedScorer("technique", "Technique", 0.30, 8.0),
        _FixedScorer("path_balance", "Path & Balance", 0.20, 6.0),
        _FixedScorer("control", "Control", 0.10, 4.0),
    ]
    result = OverallFormScore(components=scorers).compute({}, None, cfg, "squat")
    assert result.overall == pytest.approx(8.0, abs=0.01)


# ---------------------------------------------------------------------------
# score_descriptor tests (FR-SCOR-07)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score,expected",
    [
        (9.5, "Elite"),
        (9.0, "Elite"),
        (8.0, "Advanced"),
        (7.5, "Advanced"),
        (6.0, "Intermediate"),
        (5.5, "Intermediate"),
        (4.0, "Needs Work"),
        (3.5, "Needs Work"),
        (2.0, "Needs Attention"),
        (1.0, "Needs Attention"),
    ],
)
def test_score_descriptor_boundaries(
    score: float, expected: str, cfg: ThresholdConfig
) -> None:
    assert score_descriptor(score, cfg) == expected


# ---------------------------------------------------------------------------
# Protocol extensibility test (FR-SCOR-06)
# ---------------------------------------------------------------------------


def test_protocol_extensibility(cfg: ThresholdConfig) -> None:
    """A 5th scorer satisfying ScoreComponent Protocol works without base changes."""

    class TempoScore:
        weight: float = 0.05
        display_name: str = "Tempo"
        internal_name: str = "tempo"

        def compute(
            self,
            metrics: dict,
            bar_path: dict | None,
            cfg: ThresholdConfig,
            exercise_type: str,
        ) -> tuple[float, list[BadgeResult]]:
            return 8.0, []

    assert isinstance(TempoScore(), ScoreComponent)

    # Renormalise weights to sum to 1.0 for a clean test
    components = [
        SafetyScore(),
        TechniqueScore(),
        PathBalanceScore(),
        ControlScore(),
        TempoScore(),
    ]
    # OverallFormScore accepts any list — it doesn't enforce weight sum
    result = OverallFormScore(components=components).compute(
        {"confidence_score": 0.9}, None, cfg, "squat"
    )
    assert isinstance(result, ScoreResult)
    assert result.overall >= 1.0
    assert result.overall <= 10.0


# ---------------------------------------------------------------------------
# Clamping tests
# ---------------------------------------------------------------------------


def test_score_clamped_to_range(cfg: ThresholdConfig) -> None:
    """Extreme penalties must not produce score < 1.0 or > 10.0."""

    class _ExtremelyBadScorer:
        weight: float = 1.0
        display_name: str = "Movement Quality"
        internal_name: str = "safety"

        def compute(
            self,
            metrics: dict,
            bar_path: dict | None,
            cfg: ThresholdConfig,
            exercise_type: str,
        ) -> tuple[float, list]:
            return -999.0, []  # absurdly low raw score

    result = OverallFormScore(components=[_ExtremelyBadScorer()]).compute(
        {}, None, cfg, "squat"
    )
    assert result.overall >= 1.0

    class _ExtremelyGoodScorer:
        weight: float = 1.0
        display_name: str = "Movement Quality"
        internal_name: str = "safety"

        def compute(
            self,
            metrics: dict,
            bar_path: dict | None,
            cfg: ThresholdConfig,
            exercise_type: str,
        ) -> tuple[float, list]:
            return 999.0, []  # absurdly high raw score

    result_high = OverallFormScore(components=[_ExtremelyGoodScorer()]).compute(
        {}, None, cfg, "squat"
    )
    assert result_high.overall <= 10.0


# ---------------------------------------------------------------------------
# Exercise support test
# ---------------------------------------------------------------------------


def test_all_exercises_supported(cfg: ThresholdConfig) -> None:
    """squat, bench, deadlift all return valid ScoreResult."""
    scorer = OverallFormScore()
    squat_metrics = {
        "torso_lean": 25.0,
        "depth_angle": 85.0,
        "confidence_score": 0.90,
        "descent_duration_s": 2.0,
    }
    bench_metrics = {
        "elbow_angle_at_bottom": 80.0,
        "shoulder_angle_at_bottom": 70.0,
        "confidence_score": 0.90,
        "descent_duration_s": 2.0,
    }
    deadlift_metrics = {
        "hip_angle_at_bottom": 80.0,
        "torso_lean_at_start": 30.0,
        "confidence_score": 0.90,
        "knee_angle_at_lockout": 165.0,
    }
    bar_path = {"path_consistency": 0.95, "ap_deviation_px": 0.02}

    for exercise, metrics in [
        ("squat", squat_metrics),
        ("bench", bench_metrics),
        ("deadlift", deadlift_metrics),
    ]:
        result = scorer.compute(metrics, bar_path, cfg, exercise)
        assert isinstance(result, ScoreResult), f"Expected ScoreResult for {exercise}"
        assert 1.0 <= result.overall <= 10.0, (
            f"Overall score out of range for {exercise}: {result.overall}"
        )
        assert len(result.dimensions) == 4, (
            f"Expected 4 dimensions for {exercise}, got {len(result.dimensions)}"
        )
        for dim in result.dimensions:
            assert 1.0 <= dim.score <= 10.0, (
                f"Dimension {dim.internal_name} score out of range: {dim.score}"
            )


def test_technique_score_ignores_elbow_flare_deg_metric(
    cfg: ThresholdConfig,
) -> None:
    """Regression: `elbow_flare_deg` is a frontal-plane metric that cannot be
    measured from a single sagittal-view camera. The scoring branch that read
    it was removed in cv-audit cleanup 2026-05-22 (audit item A-1). This test
    asserts that feeding the (impossible) metric through scoring does NOT
    mutate the score or produce a badge — it is silently ignored, NOT acted on.
    """
    scorer = TechniqueScore()
    metrics_without = {
        "confidence_score": 1.0,
        "elbow_angle_at_bottom": 80.0,
    }
    metrics_with = {
        **metrics_without,
        "elbow_flare_deg": 90.0,  # impossible from sagittal view — must be ignored
    }
    score_without, badges_without = scorer.compute(metrics_without, None, cfg, "bench")
    score_with, badges_with = scorer.compute(metrics_with, None, cfg, "bench")
    assert score_with == score_without, "elbow_flare_deg must not affect score"
    assert badges_with == badges_without, "elbow_flare_deg must not produce badges"


# ---------------------------------------------------------------------------
# Session 4 — ThresholdConfig knobs
# ---------------------------------------------------------------------------


def test_threshold_config_has_session4_entries(cfg: ThresholdConfig) -> None:
    """Session 4: thresholds_v1.json must expose depth_classification + ecc_con_ratio knobs."""
    # Categorical default for squat depth gate.
    assert cfg.get("squat", "depth_classification_min") == "at_parallel"
    # Ecc/con ratio scoring window (Wilk et al. 1993 tempo prescription).
    assert cfg.get("control", "ecc_con_ratio_target_min") == pytest.approx(1.0)
    assert cfg.get("control", "ecc_con_ratio_target_max") == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Session 4 — TechniqueScore.depth_classification branch
# ---------------------------------------------------------------------------


def test_session4_technique_depth_classification_at_parallel_no_new_dock(cfg: ThresholdConfig) -> None:
    """depth_classification == 'at_parallel' → no NEW depth_classification badge."""
    metrics = {
        "depth_classification": "at_parallel",
    }
    score, badges = TechniqueScore().compute(metrics, None, cfg, "squat")
    issue_keys = [b.issue_key for b in badges]
    assert "squat_depth_classification_above" not in issue_keys


def test_session4_technique_depth_classification_above_parallel_docks_1_5(
    cfg: ThresholdConfig,
) -> None:
    """above_parallel + threshold 'at_parallel' → -1.5 dock, severity Medium."""
    metrics = {
        # No legacy depth_angle key — isolates the new branch.
        "depth_classification": "above_parallel",
    }
    score, badges = TechniqueScore().compute(metrics, None, cfg, "squat")
    assert score == pytest.approx(10.0 - 1.5, abs=0.01)
    new_badges = [b for b in badges if b.issue_key == "squat_depth_classification_above"]
    assert len(new_badges) == 1
    assert new_badges[0].severity == "Medium"
    assert new_badges[0].dimension == "Technique"
    assert "above parallel" in new_badges[0].message.lower()


def test_session4_technique_depth_classification_above_with_strict_threshold_docks_2_5(
    cfg: ThresholdConfig, tmp_path,
) -> None:
    """Stricter threshold (below_parallel) → -2.5 dock instead of -1.5."""
    import json
    base = json.loads(_V1_PATH.read_text(encoding="utf-8"))
    base["squat"]["depth_classification_min"]["value"] = "below_parallel"
    tweaked = tmp_path / "thresholds_strict.json"
    tweaked.write_text(json.dumps(base), encoding="utf-8")
    strict_cfg = ThresholdConfig(tweaked)

    metrics = {"depth_classification": "above_parallel"}
    score, badges = TechniqueScore().compute(metrics, None, strict_cfg, "squat")
    assert score == pytest.approx(10.0 - 2.5, abs=0.01)
    new_badges = [b for b in badges if b.issue_key == "squat_depth_classification_above"]
    assert len(new_badges) == 1


def test_session4_technique_depth_classification_below_parallel_no_dock(cfg: ThresholdConfig) -> None:
    """Going below parallel with at_parallel threshold → no dock from new branch."""
    metrics = {"depth_classification": "below_parallel"}
    score, badges = TechniqueScore().compute(metrics, None, cfg, "squat")
    new_badges = [b for b in badges if b.issue_key == "squat_depth_classification_above"]
    assert new_badges == []
    assert score == 10.0


def test_session4_technique_depth_classification_ignored_for_bench(cfg: ThresholdConfig) -> None:
    """Bench must NOT read depth_classification — squat-only metric."""
    metrics = {"depth_classification": "above_parallel"}
    score, badges = TechniqueScore().compute(metrics, None, cfg, "bench")
    new_badges = [b for b in badges if b.issue_key == "squat_depth_classification_above"]
    assert new_badges == []


# ---------------------------------------------------------------------------
# Session 4 — ControlScore.ecc_con_ratio branch
# ---------------------------------------------------------------------------


def test_session4_control_ecc_con_balanced_no_dock(cfg: ThresholdConfig) -> None:
    """Aggregate ratio inside [1.0, 3.0] → no dock from ecc_con_ratio branch."""
    metrics = {"ecc_con_ratio": 1.8}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    keys = [b.issue_key for b in badges]
    assert "ecc_con_ratio_rushed" not in keys
    assert "ecc_con_ratio_excessive" not in keys
    assert score == 10.0


def test_session4_control_ecc_con_rushed_docks_1_0_high(cfg: ThresholdConfig) -> None:
    """ratio < target_min → dock 1.0, severity High."""
    metrics = {"ecc_con_ratio": 0.5}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    assert score == pytest.approx(10.0 - 1.0, abs=0.01)
    rushed = [b for b in badges if b.issue_key == "ecc_con_ratio_rushed"]
    assert len(rushed) == 1
    assert rushed[0].severity == "High"
    assert rushed[0].dimension == "Control"
    assert "eccentric" in rushed[0].message.lower()


def test_session4_control_ecc_con_excessive_docks_0_5_medium(cfg: ThresholdConfig) -> None:
    """ratio > target_max → dock 0.5, severity Medium."""
    metrics = {"ecc_con_ratio": 4.0}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    assert score == pytest.approx(10.0 - 0.5, abs=0.01)
    excessive = [b for b in badges if b.issue_key == "ecc_con_ratio_excessive"]
    assert len(excessive) == 1
    assert excessive[0].severity == "Medium"


def test_session4_control_ecc_con_works_for_all_three_exercises(cfg: ThresholdConfig) -> None:
    """ControlScore.ecc_con_ratio applies to squat / bench / deadlift identically."""
    for ex in ("squat", "bench", "deadlift"):
        metrics = {"ecc_con_ratio": 0.5}
        score, badges = ControlScore().compute(metrics, None, cfg, ex)
        rushed = [b for b in badges if b.issue_key == "ecc_con_ratio_rushed"]
        assert len(rushed) == 1, f"missing dock for exercise={ex}"


def test_session4_control_ecc_con_no_metric_no_dock(cfg: ThresholdConfig) -> None:
    """Missing key (analyses scored before Session 4) → no dock from new branch."""
    metrics: dict[str, float] = {}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    new = [b for b in badges if b.issue_key.startswith("ecc_con_ratio_")]
    assert new == []
    assert score == 10.0


def test_session4_control_ecc_con_zero_value_no_dock(cfg: ThresholdConfig) -> None:
    """Sentinel 0.0 (no ascent) is treated as missing — no dock."""
    metrics = {"ecc_con_ratio": 0.0}
    score, badges = ControlScore().compute(metrics, None, cfg, "squat")
    new = [b for b in badges if b.issue_key.startswith("ecc_con_ratio_")]
    assert new == []
    assert score == 10.0
