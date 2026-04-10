"""
Unit tests for exercise auto-detection heuristic.

Requirements: FR-XDET-03, FR-XDET-04, FR-XDET-07

Uses synthetic landmark data — no real video.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.cv.exercise_detection import (
    DetectionResult,
    _classify_single_frame,
    _compute_scores,
    detect_exercise_heuristic,
)


# ---------------------------------------------------------------------------
# Helpers — build synthetic (33, 5) frames for each exercise posture
# ---------------------------------------------------------------------------

def _make_frame(
    positions: dict[int, tuple[float, float, float]] | None = None,
    default_vis: float = 0.9,
) -> np.ndarray:
    """Build a (33, 5) frame with specified landmark positions.

    positions: {landmark_index: (x, y, z)}
    All landmarks get default_vis for both visibility and presence.
    """
    frame = np.zeros((33, 5), dtype=np.float64)
    frame[:, 3] = default_vis  # visibility
    frame[:, 4] = default_vis  # presence
    if positions:
        for idx, (x, y, z) in positions.items():
            frame[idx, 0] = x
            frame[idx, 1] = y
            frame[idx, 2] = z
    return frame


def _squat_standing_frame() -> np.ndarray:
    """Upright standing: shoulders above hips above knees above ankles."""
    return _make_frame({
        11: (0.45, 0.25, 0.0),  # left shoulder
        12: (0.55, 0.25, 0.0),  # right shoulder
        23: (0.45, 0.50, 0.0),  # left hip
        24: (0.55, 0.50, 0.0),  # right hip
        25: (0.45, 0.75, 0.0),  # left knee
        26: (0.55, 0.75, 0.0),  # right knee
        27: (0.45, 0.95, 0.0),  # left ankle
        28: (0.55, 0.95, 0.0),  # right ankle
        13: (0.40, 0.35, 0.0),  # left elbow
        14: (0.60, 0.35, 0.0),  # right elbow
        15: (0.38, 0.28, 0.0),  # left wrist
        16: (0.62, 0.28, 0.0),  # right wrist
    })


def _squat_bottom_frame() -> np.ndarray:
    """Deep squat: hips near knee level, significant knee and hip flexion."""
    return _make_frame({
        11: (0.45, 0.25, 0.0),
        12: (0.55, 0.25, 0.0),
        23: (0.45, 0.60, 0.0),  # hips lower
        24: (0.55, 0.60, 0.0),
        25: (0.40, 0.65, 0.0),  # knees forward
        26: (0.60, 0.65, 0.0),
        27: (0.38, 0.90, 0.0),
        28: (0.62, 0.90, 0.0),
        13: (0.40, 0.35, 0.0),
        14: (0.60, 0.35, 0.0),
        15: (0.38, 0.28, 0.0),
        16: (0.62, 0.28, 0.0),
    })


def _bench_frame() -> np.ndarray:
    """Bench press: supine — shoulders and hips at similar y, torso horizontal."""
    return _make_frame({
        11: (0.30, 0.50, 0.0),
        12: (0.30, 0.60, 0.0),
        23: (0.70, 0.50, 0.0),
        24: (0.70, 0.60, 0.0),
        25: (0.85, 0.70, 0.0),
        26: (0.85, 0.40, 0.0),
        27: (0.95, 0.70, 0.0),
        28: (0.95, 0.40, 0.0),
        13: (0.30, 0.35, 0.0),  # elbows out
        14: (0.30, 0.75, 0.0),
        15: (0.20, 0.35, 0.0),  # wrists above (pressing)
        16: (0.20, 0.75, 0.0),
    })


def _deadlift_bottom_frame() -> np.ndarray:
    """Deadlift bottom: significant hip hinge, moderate knee bend, torso lean."""
    return _make_frame({
        11: (0.40, 0.35, 0.0),  # shoulders forward
        12: (0.60, 0.35, 0.0),
        23: (0.50, 0.50, 0.0),
        24: (0.55, 0.50, 0.0),
        25: (0.48, 0.72, 0.0),  # less knee bend than squat
        26: (0.55, 0.72, 0.0),
        27: (0.48, 0.95, 0.0),
        28: (0.55, 0.95, 0.0),
        13: (0.35, 0.50, 0.0),
        14: (0.65, 0.50, 0.0),
        15: (0.35, 0.65, 0.0),  # hands near floor
        16: (0.65, 0.65, 0.0),
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClassifySingleFrame:
    def test_returns_expected_keys(self) -> None:
        frame = _squat_standing_frame()
        result = _classify_single_frame(frame)
        expected_keys = {"torso_vertical", "hip_angle", "knee_angle",
                         "elbow_angle", "shoulder_y", "hip_y"}
        assert set(result.keys()) == expected_keys

    def test_upright_torso_has_small_angle(self) -> None:
        frame = _squat_standing_frame()
        result = _classify_single_frame(frame)
        assert result["torso_vertical"] < 20  # mostly upright

    def test_bench_has_large_torso_angle(self) -> None:
        frame = _bench_frame()
        result = _classify_single_frame(frame)
        assert result["torso_vertical"] > 40  # near horizontal


class TestComputeScores:
    def test_empty_features_returns_uniform(self) -> None:
        scores = _compute_scores([])
        assert scores["squat"] == pytest.approx(0.33, abs=0.01)
        assert scores["bench"] == pytest.approx(0.33, abs=0.01)

    def test_scores_sum_to_one(self) -> None:
        features = [_classify_single_frame(_squat_bottom_frame())]
        scores = _compute_scores(features)
        assert sum(scores.values()) == pytest.approx(1.0, abs=1e-9)


class TestDetectExerciseHeuristic:
    def test_returns_detection_result(self) -> None:
        frames = [_squat_standing_frame()] * 5
        result = detect_exercise_heuristic(frames)
        assert isinstance(result, DetectionResult)
        assert result.method == "heuristic"
        assert 0.0 <= result.confidence <= 1.0

    def test_empty_frames(self) -> None:
        result = detect_exercise_heuristic([])
        assert result.confidence == 0.0
        assert result.details["error"] == "no_frames"

    def test_low_visibility_fallback(self) -> None:
        """Frames with vis=0.1 should be skipped."""
        frames = [_make_frame(default_vis=0.1)] * 10
        result = detect_exercise_heuristic(frames)
        assert result.confidence == 0.0
        assert result.details["error"] == "no_visible_frames"

    def test_squat_detected(self) -> None:
        """Mix of standing + bottom squat frames should detect squat."""
        frames = (
            [_squat_standing_frame()] * 5
            + [_squat_bottom_frame()] * 5
            + [_squat_standing_frame()] * 5
        )
        result = detect_exercise_heuristic(frames)
        assert result.detected_type == "squat"
        assert result.confidence > 0.3

    def test_bench_detected(self) -> None:
        """Bench frames should detect bench."""
        frames = [_bench_frame()] * 15
        result = detect_exercise_heuristic(frames)
        assert result.detected_type == "bench"
        assert result.confidence > 0.3

    def test_deadlift_detected(self) -> None:
        """Deadlift frames should detect deadlift."""
        frames = (
            [_squat_standing_frame()] * 5
            + [_deadlift_bottom_frame()] * 5
            + [_squat_standing_frame()] * 5
        )
        result = detect_exercise_heuristic(frames)
        assert result.detected_type == "deadlift"
        assert result.confidence > 0.3

    def test_default_variant_squat(self) -> None:
        frames = [_squat_bottom_frame()] * 10
        result = detect_exercise_heuristic(frames)
        if result.detected_type == "squat":
            assert result.detected_variant == "high_bar"

    def test_default_variant_bench(self) -> None:
        frames = [_bench_frame()] * 10
        result = detect_exercise_heuristic(frames)
        if result.detected_type == "bench":
            assert result.detected_variant == "flat"

    def test_details_contains_scores(self) -> None:
        frames = [_squat_standing_frame()] * 5
        result = detect_exercise_heuristic(frames)
        assert "scores" in result.details
        assert "frames_analyzed" in result.details
        assert result.details["frames_analyzed"] > 0

    def test_sample_count_respected(self) -> None:
        """With many frames, should only analyze sample_count."""
        frames = [_squat_standing_frame()] * 100
        result = detect_exercise_heuristic(frames, sample_count=5)
        assert result.details["frames_analyzed"] <= 5
