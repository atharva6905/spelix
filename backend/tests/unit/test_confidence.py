"""
Unit tests for app.cv.confidence (FR-CVPL-16, FR-RESL-08, FR-REPM-04, FR-SCOR-10).

All tests use synthetic numpy arrays — no real video, no DB, no IO.
Landmark arrays: shape (33, 5) per frame — [x, y, z, visibility, presence].
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.cv.confidence import (
    compute_rep_confidence,
    compute_session_confidence,
    confidence_guidance,
    confidence_label,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_frame(visibility_by_index: dict[int, float], default_vis: float = 0.9) -> np.ndarray:
    """
    Create a (33, 5) landmark array.

    Parameters
    ----------
    visibility_by_index:
        Mapping from landmark index to raw visibility value (may be logit).
    default_vis:
        Visibility used for all landmarks not in visibility_by_index.
    """
    frame = np.zeros((33, 5), dtype=np.float64)
    for i in range(33):
        frame[i, 3] = visibility_by_index.get(i, default_vis)
    return frame


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-float(x)))


# ---------------------------------------------------------------------------
# Exercise-specific landmark sets
# ---------------------------------------------------------------------------

SQUAT_LANDMARKS = {23, 24, 25, 26, 27, 28}
BENCH_LANDMARKS = {11, 12, 13, 14, 15, 16}


# ---------------------------------------------------------------------------
# Tests: compute_rep_confidence
# ---------------------------------------------------------------------------


class TestComputeRepConfidence:
    def test_squat_uses_hip_knee_ankle_landmarks(self):
        """Squat/deadlift confidence uses landmarks 23-28 only."""
        # Set squat landmarks to known sigmoid-able value 2.0
        # Other landmarks to 0.0 (sigmoid(0.0)=0.5)
        vis_map = {idx: 2.0 for idx in SQUAT_LANDMARKS}
        for i in range(33):
            if i not in SQUAT_LANDMARKS:
                vis_map[i] = 0.0

        frame = _make_frame(vis_map)
        frames = [frame] * 3  # 3 frames

        result = compute_rep_confidence(frames, start_frame=0, end_frame=2, exercise_type="squat")

        expected = _sigmoid(2.0)
        assert abs(result - expected) < 1e-9

    def test_deadlift_uses_same_landmarks_as_squat(self):
        """Deadlift uses the same landmark set as squat (23-28)."""
        vis_map = {idx: 1.5 for idx in SQUAT_LANDMARKS}
        for i in range(33):
            if i not in SQUAT_LANDMARKS:
                vis_map[i] = -5.0  # sigmoid(-5) ≈ 0.0067

        frame = _make_frame(vis_map)
        frames = [frame] * 2

        squat_result = compute_rep_confidence(frames, 0, 1, "squat")
        deadlift_result = compute_rep_confidence(frames, 0, 1, "deadlift")

        assert abs(squat_result - deadlift_result) < 1e-9

    def test_bench_uses_shoulder_elbow_wrist_landmarks(self):
        """Bench confidence uses landmarks 11-16 only."""
        vis_map = {idx: 3.0 for idx in BENCH_LANDMARKS}
        for i in range(33):
            if i not in BENCH_LANDMARKS:
                vis_map[i] = 0.0  # sigmoid(0)=0.5

        frame = _make_frame(vis_map)
        frames = [frame] * 2

        result = compute_rep_confidence(frames, 0, 1, "bench")

        expected = _sigmoid(3.0)
        assert abs(result - expected) < 1e-9

    def test_bench_vs_squat_differ_with_different_landmark_visibility(self):
        """Bench and squat should produce different scores when landmark sets differ."""
        # Squat landmarks visible=2.0, bench landmarks visible=-2.0
        vis_map: dict[int, float] = {}
        for idx in SQUAT_LANDMARKS:
            vis_map[idx] = 2.0
        for idx in BENCH_LANDMARKS:
            vis_map[idx] = -2.0

        frame = _make_frame(vis_map)
        frames = [frame] * 2

        squat_result = compute_rep_confidence(frames, 0, 1, "squat")
        bench_result = compute_rep_confidence(frames, 0, 1, "bench")

        assert squat_result > bench_result

    def test_frame_range_respected(self):
        """Only frames in [start_frame, end_frame] are used."""
        # Frame 0: all squat landmarks vis=0.0 (sigmoid→0.5)
        # Frames 1-3: all squat landmarks vis=4.0 (sigmoid→high)
        vis_low = {idx: 0.0 for idx in SQUAT_LANDMARKS}
        vis_high = {idx: 4.0 for idx in SQUAT_LANDMARKS}
        frame_low = _make_frame(vis_low)
        frame_high = _make_frame(vis_high)

        frames = [frame_low, frame_high, frame_high, frame_high]

        # Use only frames 1-3 (all high)
        result_high_range = compute_rep_confidence(frames, start_frame=1, end_frame=3, exercise_type="squat")
        # Use only frame 0 (low)
        result_low_range = compute_rep_confidence(frames, start_frame=0, end_frame=0, exercise_type="squat")

        assert result_high_range > result_low_range

    def test_known_mean_single_frame(self):
        """Exact mean check: single frame, all squat landmarks same visibility."""
        raw_vis = 1.0  # sigmoid(1.0) = 0.7310585...
        vis_map = {idx: raw_vis for idx in SQUAT_LANDMARKS}
        frame = _make_frame(vis_map)

        result = compute_rep_confidence([frame], start_frame=0, end_frame=0, exercise_type="squat")

        expected = _sigmoid(raw_vis)
        assert abs(result - expected) < 1e-9

    def test_known_mean_multi_frame_multi_landmark(self):
        """Exact mean check: two frames with distinct visibility values."""
        # Frame 0: squat landmarks vis=0.0 → sigmoid=0.5
        # Frame 1: squat landmarks vis=2.0 → sigmoid≈0.8808
        frame0 = _make_frame({idx: 0.0 for idx in SQUAT_LANDMARKS})
        frame1 = _make_frame({idx: 2.0 for idx in SQUAT_LANDMARKS})

        result = compute_rep_confidence([frame0, frame1], start_frame=0, end_frame=1, exercise_type="squat")

        expected = (_sigmoid(0.0) + _sigmoid(2.0)) / 2.0
        assert abs(result - expected) < 1e-9

    def test_result_in_unit_interval(self):
        """Return value must always be in [0, 1]."""
        frame = _make_frame({idx: 10.0 for idx in SQUAT_LANDMARKS})
        result = compute_rep_confidence([frame], 0, 0, "squat")
        assert 0.0 <= result <= 1.0

        frame_neg = _make_frame({idx: -10.0 for idx in SQUAT_LANDMARKS})
        result_neg = compute_rep_confidence([frame_neg], 0, 0, "squat")
        assert 0.0 <= result_neg <= 1.0

    def test_sigmoid_applied_to_out_of_range_values(self):
        """Values outside [0, 1] are passed through sigmoid before averaging."""
        raw_logit = 5.0  # sigmoid(5.0) ≈ 0.9933
        raw_in_range = 0.9  # sigmoid(0.9) ≈ 0.7109 — NOT the same as raw 0.9

        frame_logit = _make_frame({idx: raw_logit for idx in SQUAT_LANDMARKS})
        frame_in_range = _make_frame({idx: raw_in_range for idx in SQUAT_LANDMARKS})

        result_logit = compute_rep_confidence([frame_logit], 0, 0, "squat")
        result_in_range = compute_rep_confidence([frame_in_range], 0, 0, "squat")

        # sigmoid(5.0) vs sigmoid(0.9) — sigmoid always applied
        assert abs(result_logit - _sigmoid(raw_logit)) < 1e-9
        assert abs(result_in_range - _sigmoid(raw_in_range)) < 1e-9

    def test_invalid_exercise_type_raises(self):
        """Unknown exercise type should raise ValueError."""
        frame = _make_frame({})
        with pytest.raises((ValueError, KeyError)):
            compute_rep_confidence([frame], 0, 0, "cycling")


# ---------------------------------------------------------------------------
# Tests: compute_session_confidence
# ---------------------------------------------------------------------------


class TestComputeSessionConfidence:
    def test_mean_of_rep_confidences(self):
        """Session confidence is the simple mean of per-rep scores."""
        rep_scores = [0.8, 0.6, 0.7]
        result = compute_session_confidence(rep_scores)
        assert abs(result - (0.8 + 0.6 + 0.7) / 3) < 1e-9

    def test_single_rep(self):
        """Single-rep session confidence equals that rep's confidence."""
        result = compute_session_confidence([0.75])
        assert abs(result - 0.75) < 1e-9

    def test_all_ones(self):
        result = compute_session_confidence([1.0, 1.0, 1.0])
        assert abs(result - 1.0) < 1e-9

    def test_all_zeros(self):
        result = compute_session_confidence([0.0, 0.0])
        assert abs(result - 0.0) < 1e-9

    def test_result_in_unit_interval(self):
        """Output must be in [0, 1] for valid inputs."""
        result = compute_session_confidence([0.5, 0.9, 0.3])
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Tests: confidence_label
# ---------------------------------------------------------------------------


class TestConfidenceLabel:
    @pytest.mark.parametrize(
        "score, expected_label",
        [
            (1.00, "High"),
            (0.80, "High"),        # boundary: exactly 0.80 → High
            (0.79, "Moderate"),    # boundary: 0.79 → Moderate
            (0.65, "Moderate"),    # boundary: 0.65 → Moderate
            (0.64, "Low"),         # boundary: 0.64 → Low
            (0.50, "Low"),         # boundary: 0.50 → Low
            (0.49, "Very Low"),    # boundary: 0.49 → Very Low
            (0.00, "Very Low"),
            (0.73, "Moderate"),
            (0.55, "Low"),
            (0.82, "High"),
        ],
    )
    def test_label_boundaries(self, score: float, expected_label: str):
        assert confidence_label(score) == expected_label

    def test_returns_string(self):
        assert isinstance(confidence_label(0.7), str)


# ---------------------------------------------------------------------------
# Tests: confidence_guidance
# ---------------------------------------------------------------------------


class TestConfidenceGuidance:
    def test_high_guidance(self):
        result = confidence_guidance("High")
        assert result == (
            "Landmark visibility is strong — high confidence in analysis accuracy."
        )

    def test_moderate_guidance(self):
        result = confidence_guidance("Moderate")
        assert result == (
            "Moderate landmark visibility — results are generally reliable but may have minor inaccuracies."
        )

    def test_low_guidance(self):
        result = confidence_guidance("Low")
        assert result == (
            "Low landmark visibility — results should be interpreted with caution. "
            "Consider re-recording with better lighting or camera angle."
        )

    def test_very_low_guidance(self):
        result = confidence_guidance("Very Low")
        assert result == (
            "Very low landmark visibility — analysis accuracy is significantly reduced. "
            "We strongly recommend re-recording."
        )

    def test_all_labels_return_non_empty_string(self):
        for label in ["High", "Moderate", "Low", "Very Low"]:
            result = confidence_guidance(label)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_unknown_label_raises(self):
        """Unknown label should raise ValueError."""
        with pytest.raises((ValueError, KeyError)):
            confidence_guidance("Unknown")


# ---------------------------------------------------------------------------
# Tests: round-trip label + guidance
# ---------------------------------------------------------------------------


class TestRoundTrip:
    @pytest.mark.parametrize(
        "score, expected_label",
        [
            (0.90, "High"),
            (0.72, "Moderate"),
            (0.55, "Low"),
            (0.30, "Very Low"),
        ],
    )
    def test_label_then_guidance_matches(self, score: float, expected_label: str):
        """confidence_label → confidence_guidance pipeline produces non-empty strings."""
        label = confidence_label(score)
        assert label == expected_label
        guidance = confidence_guidance(label)
        assert len(guidance) > 0
