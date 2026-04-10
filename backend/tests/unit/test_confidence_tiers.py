"""
Unit tests for Phase 1 Tier 1–5 confidence algorithm.

Requirements: FR-CVPL-20 through FR-CVPL-25

Uses synthetic numpy arrays — no real video. Each frame is (33, 5):
columns [x, y, z, visibility, presence]. Values are already sigmoid-guarded
at ingestion by pose_extraction._guard_sigmoid.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.config import ThresholdConfig
from app.cv.confidence import (
    compute_confidence_result,
    compute_session_confidence,
    confidence_label,
    _tier1_landmark_conf,
    _tier2_angle_conf,
    _tier3_frame_conf,
    _tier4_phase_adjusted,
    _tier5_rep_confidence,
)
from app.cv.types import ConfidenceResult


def _make_frame(vis: dict[int, float] | None = None,
                pres: dict[int, float] | None = None,
                default_vis: float = 0.9,
                default_pres: float = 0.9) -> np.ndarray:
    """Build a synthetic (33, 5) landmark frame."""
    frame = np.zeros((33, 5), dtype=np.float64)
    frame[:, 3] = default_vis   # visibility
    frame[:, 4] = default_pres  # presence
    if vis:
        for idx, v in vis.items():
            frame[idx, 3] = v
    if pres:
        for idx, p in pres.items():
            frame[idx, 4] = p
    return frame


# ---------------------------------------------------------------------------
# Tier 1 — per-landmark (FR-CVPL-20)
# ---------------------------------------------------------------------------

class TestTier1:
    def test_no_double_sigmoid(self) -> None:
        """Critical: vis=0.8 * pres=0.6 = 0.48, NOT sigmoid(0.48)≈0.618."""
        frame = _make_frame(vis={23: 0.8}, pres={23: 0.6})
        result = _tier1_landmark_conf(frame, 23)
        assert result == pytest.approx(0.48, abs=1e-9)

    def test_zero_presence_zeroes_conf(self) -> None:
        frame = _make_frame(vis={11: 0.95}, pres={11: 0.0})
        assert _tier1_landmark_conf(frame, 11) == 0.0

    def test_zero_visibility_zeroes_conf(self) -> None:
        frame = _make_frame(vis={11: 0.0}, pres={11: 0.95})
        assert _tier1_landmark_conf(frame, 11) == 0.0

    def test_perfect_visibility_and_presence(self) -> None:
        frame = _make_frame(vis={25: 1.0}, pres={25: 1.0})
        assert _tier1_landmark_conf(frame, 25) == 1.0

    def test_returns_float(self) -> None:
        frame = _make_frame()
        result = _tier1_landmark_conf(frame, 0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Tier 2 — per-angle (FR-CVPL-21)
# ---------------------------------------------------------------------------

class TestTier2:
    def test_min_of_three_landmarks(self) -> None:
        """Three landmark confs [0.9*0.9=0.81, 0.6*0.8=0.48, 0.8*0.7=0.56] → min=0.48."""
        frame = _make_frame(
            vis={11: 0.9, 12: 0.6, 13: 0.8},
            pres={11: 0.9, 12: 0.8, 13: 0.7},
        )
        result = _tier2_angle_conf(frame, 11, 12, 13)
        expected_min = min(0.9 * 0.9, 0.6 * 0.8, 0.8 * 0.7)
        assert result == pytest.approx(expected_min, abs=1e-9)

    def test_all_equal(self) -> None:
        frame = _make_frame(default_vis=0.7, default_pres=0.7)
        result = _tier2_angle_conf(frame, 23, 24, 25)
        assert result == pytest.approx(0.49, abs=1e-9)

    def test_one_bad_landmark_dominates(self) -> None:
        """One unreliable landmark invalidates the entire angle (SRS: 'minimum, not mean')."""
        frame = _make_frame(
            vis={23: 0.95, 24: 0.1, 25: 0.95},
            pres={23: 0.95, 24: 0.95, 25: 0.95},
        )
        result = _tier2_angle_conf(frame, 23, 24, 25)
        assert result == pytest.approx(0.1 * 0.95, abs=1e-9)


# ---------------------------------------------------------------------------
# Tier 3 — per-frame weighted mean (FR-CVPL-22)
# ---------------------------------------------------------------------------

class TestTier3:
    def test_weighted_mean(self) -> None:
        """weights {23: 1.0, 11: 0.5}, confs 23=0.8*0.9=0.72, 11=0.4*0.5=0.20
        → (0.72*1.0 + 0.20*0.5) / 1.5 = 0.5467"""
        frame = _make_frame(vis={23: 0.8, 11: 0.4}, pres={23: 0.9, 11: 0.5})
        weights = {23: 1.0, 11: 0.5}
        result = _tier3_frame_conf(frame, weights)
        expected = (0.8 * 0.9 * 1.0 + 0.4 * 0.5 * 0.5) / 1.5
        assert result == pytest.approx(expected, abs=1e-9)

    def test_empty_weights_returns_zero(self) -> None:
        frame = _make_frame()
        assert _tier3_frame_conf(frame, {}) == 0.0

    def test_uniform_weights(self) -> None:
        """Equal weights → simple mean of landmark confs."""
        frame = _make_frame(
            vis={23: 0.8, 24: 0.6},
            pres={23: 1.0, 24: 1.0},
        )
        weights = {23: 1.0, 24: 1.0}
        result = _tier3_frame_conf(frame, weights)
        assert result == pytest.approx((0.8 + 0.6) / 2, abs=1e-9)


# ---------------------------------------------------------------------------
# Tier 4 — phase-adjusted (FR-CVPL-23)
# ---------------------------------------------------------------------------

class TestTier4:
    def test_occlusion_multiplier_squat(self) -> None:
        """Bottom-of-rep frame for squat: tier3=0.8 * 0.75 = 0.6."""
        cfg = ThresholdConfig()
        result = _tier4_phase_adjusted(
            tier3_score=0.8,
            frame_offset=5,     # at depth
            depth_frame_offset=5,
            rep_frame_count=20,
            exercise_type="squat",
            cfg=cfg,
        )
        multiplier = cfg.get("phase_multipliers", "high_occlusion")["squat_deep_hip_fold"]
        assert result == pytest.approx(0.8 * multiplier, abs=1e-9)

    def test_transition_multiplier(self) -> None:
        """Mid-rep frame not near depth: tier3=0.8 * 0.90 = 0.72."""
        cfg = ThresholdConfig()
        result = _tier4_phase_adjusted(
            tier3_score=0.8,
            frame_offset=50,
            depth_frame_offset=5,
            rep_frame_count=100,  # bottom_window=10, frame 50 is well outside ±10 of depth at 5
            exercise_type="squat",
            cfg=cfg,
        )
        assert result == pytest.approx(0.8 * 0.90, abs=1e-9)

    def test_static_peak_no_reduction(self) -> None:
        """First frame of rep: static_peak multiplier = 1.0."""
        cfg = ThresholdConfig()
        result = _tier4_phase_adjusted(
            tier3_score=0.8,
            frame_offset=0,
            depth_frame_offset=10,
            rep_frame_count=20,
            exercise_type="squat",
            cfg=cfg,
        )
        assert result == pytest.approx(0.8 * 1.0, abs=1e-9)

    def test_bench_occlusion(self) -> None:
        cfg = ThresholdConfig()
        result = _tier4_phase_adjusted(
            tier3_score=0.8,
            frame_offset=5,
            depth_frame_offset=5,
            rep_frame_count=20,
            exercise_type="bench",
            cfg=cfg,
        )
        multiplier = cfg.get("phase_multipliers", "high_occlusion")["bench_supine"]
        assert result == pytest.approx(0.8 * multiplier, abs=1e-9)


# ---------------------------------------------------------------------------
# Tier 5 — 10th percentile (FR-CVPL-24)
# ---------------------------------------------------------------------------

class TestTier5:
    def test_10th_percentile(self) -> None:
        scores = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.95, 0.95, 0.95, 0.95]
        result = _tier5_rep_confidence(scores)
        expected = float(np.percentile(scores, 10))
        assert result == pytest.approx(expected, abs=1e-9)

    def test_empty_returns_zero(self) -> None:
        assert _tier5_rep_confidence([]) == 0.0

    def test_single_frame(self) -> None:
        assert _tier5_rep_confidence([0.75]) == pytest.approx(0.75, abs=1e-9)

    def test_all_same(self) -> None:
        """If all frame scores identical, 10th percentile = that value."""
        assert _tier5_rep_confidence([0.8] * 10) == pytest.approx(0.8, abs=1e-9)


# ---------------------------------------------------------------------------
# compute_confidence_result integration
# ---------------------------------------------------------------------------

class TestComputeConfidenceResult:
    def test_returns_confidence_result(self) -> None:
        frames = [_make_frame(default_vis=0.85, default_pres=0.90) for _ in range(10)]
        cfg = ThresholdConfig()
        result = compute_confidence_result(
            landmarks_per_frame=frames,
            start_frame=0,
            end_frame=9,
            exercise_type="squat",
            depth_frame_idx=5,
            cfg=cfg,
        )
        assert isinstance(result, ConfidenceResult)
        assert result.rep_index == 0  # default
        assert result.tier5 > 0.0
        assert result.label in ("High", "Moderate", "Low", "Very Low")

    def test_low_visibility_produces_low_label(self) -> None:
        frames = [_make_frame(default_vis=0.3, default_pres=0.3) for _ in range(10)]
        cfg = ThresholdConfig()
        result = compute_confidence_result(
            landmarks_per_frame=frames,
            start_frame=0,
            end_frame=9,
            exercise_type="squat",
            depth_frame_idx=5,
            cfg=cfg,
        )
        assert result.label in ("Low", "Very Low")

    def test_high_visibility_produces_high_label(self) -> None:
        frames = [_make_frame(default_vis=0.95, default_pres=0.95) for _ in range(10)]
        cfg = ThresholdConfig()
        result = compute_confidence_result(
            landmarks_per_frame=frames,
            start_frame=0,
            end_frame=9,
            exercise_type="squat",
            depth_frame_idx=50,  # outside range → no occlusion penalty, all transition/static_peak
            cfg=cfg,
        )
        assert result.label == "High"

    def test_bench_exercise(self) -> None:
        frames = [_make_frame(default_vis=0.85, default_pres=0.90) for _ in range(10)]
        cfg = ThresholdConfig()
        result = compute_confidence_result(
            landmarks_per_frame=frames,
            start_frame=0,
            end_frame=9,
            exercise_type="bench",
            depth_frame_idx=5,
            cfg=cfg,
        )
        assert isinstance(result, ConfidenceResult)
        assert result.tier5 > 0.0


# ---------------------------------------------------------------------------
# Existing functions still work (FR-CVPL-25 labels unchanged)
# ---------------------------------------------------------------------------

class TestConfidenceLabelUnchanged:
    @pytest.mark.parametrize("score,expected", [
        (0.80, "High"),
        (0.95, "High"),
        (0.79, "Moderate"),
        (0.65, "Moderate"),
        (0.64, "Low"),
        (0.50, "Low"),
        (0.49, "Very Low"),
        (0.0, "Very Low"),
    ])
    def test_label_thresholds(self, score: float, expected: str) -> None:
        assert confidence_label(score) == expected

    def test_session_confidence_mean(self) -> None:
        assert compute_session_confidence([0.8, 0.6, 0.7]) == pytest.approx(0.7, abs=1e-9)

    def test_session_confidence_empty(self) -> None:
        assert compute_session_confidence([]) == 0.0
