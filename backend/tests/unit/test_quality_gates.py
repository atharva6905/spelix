"""
Unit tests for quality_gates.py (FR-CVPL-03 through FR-CVPL-11).

All tests use synthetic numpy arrays with known visibility values — no real video.
Landmark array shape per frame: (33, 5) — [x, y, z, visibility, presence].
"""

import math

import numpy as np

from app.cv.quality_gates import (
    GateCheckResult,
    QualityGateResult,
    check_body_visibility,
    check_framing,
    run_quality_gates,
    sigmoid,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# Landmark indices used by body-visibility gate
VISIBILITY_LANDMARKS = [11, 12, 13, 14, 23, 24, 25, 26]


def _make_landmarks_frame(
    *,
    visibility: float = 0.9,
    x: float = 0.5,
    y: float = 0.5,
) -> np.ndarray:
    """Return a (33, 5) array where every landmark has the given visibility."""
    frame = np.zeros((33, 5), dtype=np.float32)
    frame[:, 0] = x       # x
    frame[:, 1] = y       # y
    frame[:, 2] = 0.0     # z
    frame[:, 3] = visibility  # visibility (column index 3)
    frame[:, 4] = visibility  # presence  (column index 4)
    return frame


def _make_n_frames(n: int = 5, **kwargs) -> list[np.ndarray]:
    """Return a list of n identical frames."""
    return [_make_landmarks_frame(**kwargs) for _ in range(n)]


def _make_framing_frames(
    *,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
    visibility: float = 0.9,
    n: int = 5,
) -> list[np.ndarray]:
    """
    Return n frames where landmarks are spread to produce a bounding box
    of approximately [x_min, y_min] → [x_max, y_max] in normalised coords.

    Two corner landmarks are set explicitly; the rest are at the centre.
    Visibility is set high enough that landmarks are counted as visible
    after sigmoid (sigmoid(visibility) > 0.5).
    """
    frames = []
    for _ in range(n):
        frame = _make_landmarks_frame(
            visibility=visibility,
            x=(x_min + x_max) / 2,
            y=(y_min + y_max) / 2,
        )
        # Landmark 0: top-left corner
        frame[0, 0] = x_min
        frame[0, 1] = y_min
        # Landmark 32: bottom-right corner
        frame[32, 0] = x_max
        frame[32, 1] = y_max
        frames.append(frame)
    return frames


# ---------------------------------------------------------------------------
# sigmoid helper
# ---------------------------------------------------------------------------


class TestSigmoid:
    def test_zero_gives_half(self):
        assert abs(sigmoid(0.0) - 0.5) < 1e-6

    def test_positive_large_near_one(self):
        assert sigmoid(10.0) > 0.999

    def test_negative_large_near_zero(self):
        # sigmoid(-5) ≈ 0.0067
        result = sigmoid(-5.0)
        assert abs(result - 0.006692850924284856) < 1e-6

    def test_minus_two_is_about_0_12(self):
        # sigmoid(-2) ≈ 0.119
        result = sigmoid(-2.0)
        assert abs(result - (1 / (1 + math.exp(2)))) < 1e-6

    def test_works_on_numpy_scalar(self):
        val = np.float32(0.0)
        assert abs(sigmoid(val) - 0.5) < 1e-6


# ---------------------------------------------------------------------------
# check_body_visibility
# ---------------------------------------------------------------------------


class TestBodyVisibility:
    def test_returns_gate_check_result(self):
        frames = _make_n_frames(visibility=0.9)
        result = check_body_visibility(frames)
        assert isinstance(result, GateCheckResult)

    def test_passes_when_visibility_high(self):
        # Visibility 0.9 is already in [0,1]; sigmoid(0.9) ≈ 0.71 → well above 0.30
        frames = _make_n_frames(visibility=0.9)
        result = check_body_visibility(frames)
        assert result.passed is True

    def test_rejects_when_visibility_low(self):
        # Visibility -2.0 is a pre-sigmoid logit; sigmoid(-2) ≈ 0.12 < 0.30
        frames = _make_n_frames(visibility=-2.0)
        result = check_body_visibility(frames)
        assert result.passed is False

    def test_rejects_at_exact_threshold_boundary_below(self):
        # We want mean after sigmoid to be exactly below 0.30.
        # sigmoid(x) = 0.29  →  x = log(0.29 / 0.71) ≈ -0.896
        logit_just_below = math.log(0.29 / 0.71)
        frames = _make_n_frames(visibility=logit_just_below)
        result = check_body_visibility(frames)
        assert result.passed is False

    def test_passes_at_threshold_boundary_above(self):
        # sigmoid(x) = 0.31  →  x = log(0.31 / 0.69) ≈ -0.798
        logit_just_above = math.log(0.31 / 0.69)
        frames = _make_n_frames(visibility=logit_just_above)
        result = check_body_visibility(frames)
        assert result.passed is True

    def test_uses_only_first_five_frames(self):
        # First 5 frames: high visibility. Remaining: low. Must still pass.
        good_frames = _make_n_frames(5, visibility=0.9)
        bad_frames = _make_n_frames(10, visibility=-5.0)
        combined = good_frames + bad_frames
        result = check_body_visibility(combined)
        assert result.passed is True

    def test_correct_reject_user_message(self):
        frames = _make_n_frames(visibility=-2.0)
        result = check_body_visibility(frames)
        assert "not clearly visible" in result.user_message.lower() or \
               "good lighting" in result.user_message.lower() or \
               "body is not" in result.user_message.lower()

    def test_metric_value_is_mean_sigmoid_visibility(self):
        # All frames identical visibility=0.8; sigmoid(0.8) ≈ 0.6899
        frames = _make_n_frames(visibility=0.8)
        result = check_body_visibility(frames)
        expected = sigmoid(0.8)
        assert abs(result.metric_value - expected) < 1e-4

    def test_threshold_is_0_30(self):
        frames = _make_n_frames(visibility=0.9)
        result = check_body_visibility(frames)
        assert abs(result.threshold - 0.30) < 1e-6

    def test_level_is_error(self):
        frames = _make_n_frames(visibility=0.9)
        result = check_body_visibility(frames)
        assert result.level == "error"

    def test_name_identifies_gate(self):
        frames = _make_n_frames(visibility=0.9)
        result = check_body_visibility(frames)
        assert "visibility" in result.name.lower() or "body" in result.name.lower()

    def test_only_target_landmarks_affect_metric(self):
        # Make all non-target landmarks invisible (logit -10 → sigmoid ≈ 0),
        # and target landmarks high visibility. Gate must pass.
        frames = []
        for _ in range(5):
            frame = np.zeros((33, 5), dtype=np.float32)
            frame[:, 3] = -10.0  # all very low
            for idx in VISIBILITY_LANDMARKS:
                frame[idx, 3] = 5.0  # high sigmoid visibility
            frames.append(frame)
        result = check_body_visibility(frames)
        assert result.passed is True

    def test_pre_sigmoid_logit_minus_two_rejects(self):
        """Explicit regression for the MediaPipe logit gotcha."""
        frames = _make_n_frames(visibility=-2.0)
        result = check_body_visibility(frames)
        assert result.passed is False
        assert result.metric_value < 0.30


# ---------------------------------------------------------------------------
# check_framing
# ---------------------------------------------------------------------------


class TestFraming:
    def test_returns_gate_check_result(self):
        frames = _make_n_frames(visibility=0.9)
        result = check_framing(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert isinstance(result, GateCheckResult)

    def test_passes_normal_bounding_box(self):
        # Bounding box covers ~50% of the frame area → should pass (30–80%)
        frames = _make_framing_frames(
            x_min=0.25, y_min=0.1, x_max=0.75, y_max=0.9, visibility=0.9
        )
        result = check_framing(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert result.passed is True

    def test_rejects_too_small_bounding_box(self):
        # Tiny box: 10% × 10% = 1% of frame area → < 30% → reject
        frames = _make_framing_frames(
            x_min=0.45, y_min=0.45, x_max=0.55, y_max=0.55, visibility=0.9
        )
        result = check_framing(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert result.passed is False

    def test_rejects_too_large_bounding_box(self):
        # Full frame: 100% × 100% = 100% → > 80% → reject
        frames = _make_framing_frames(
            x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0, visibility=0.9
        )
        result = check_framing(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert result.passed is False

    def test_too_small_user_message_mentions_closer(self):
        frames = _make_framing_frames(
            x_min=0.45, y_min=0.45, x_max=0.55, y_max=0.55, visibility=0.9
        )
        result = check_framing(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert "closer" in result.user_message.lower() or \
               "move closer" in result.user_message.lower() or \
               "too far" in result.user_message.lower()

    def test_too_large_user_message_mentions_step_back(self):
        frames = _make_framing_frames(
            x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0, visibility=0.9
        )
        result = check_framing(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert "step back" in result.user_message.lower() or \
               "too close" in result.user_message.lower() or \
               "back" in result.user_message.lower()

    def test_uses_only_first_five_frames(self):
        # First 5 frames: proper framing. Next 10: tiny box. Should pass.
        good = _make_framing_frames(
            x_min=0.2, y_min=0.1, x_max=0.8, y_max=0.9, visibility=0.9, n=5
        )
        bad = _make_framing_frames(
            x_min=0.49, y_min=0.49, x_max=0.51, y_max=0.51, visibility=0.9, n=10
        )
        result = check_framing(good + bad, FRAME_WIDTH, FRAME_HEIGHT)
        assert result.passed is True

    def test_only_visible_landmarks_count_for_bounding_box(self):
        # Set all landmarks to invisible (visibility logit -10),
        # then place two visible ones inside the 30–80% range.
        frames = []
        for _ in range(5):
            frame = np.zeros((33, 5), dtype=np.float32)
            frame[:, 0] = 0.5
            frame[:, 1] = 0.5
            frame[:, 3] = -10.0  # sigmoid ≈ 0, invisible

            # Two visible landmarks forming a reasonable box
            frame[0, 0] = 0.2
            frame[0, 1] = 0.1
            frame[0, 3] = 5.0   # sigmoid ≈ 1.0, visible

            frame[32, 0] = 0.8
            frame[32, 1] = 0.9
            frame[32, 3] = 5.0

            frames.append(frame)
        result = check_framing(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert result.passed is True

    def test_level_is_error(self):
        frames = _make_n_frames(visibility=0.9)
        result = check_framing(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert result.level == "error"

    def test_name_identifies_framing(self):
        frames = _make_n_frames(visibility=0.9)
        result = check_framing(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert "framing" in result.name.lower() or "frame" in result.name.lower()


# ---------------------------------------------------------------------------
# run_quality_gates (combined)
# ---------------------------------------------------------------------------


class TestRunQualityGates:
    def test_returns_quality_gate_result(self):
        frames = _make_n_frames(visibility=0.9)
        result = run_quality_gates(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert isinstance(result, QualityGateResult)

    def test_all_pass_gives_passed_true(self):
        frames = _make_framing_frames(
            x_min=0.2, y_min=0.1, x_max=0.8, y_max=0.9, visibility=0.9
        )
        result = run_quality_gates(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert result.passed is True
        assert result.status == "passed"

    def test_visibility_fail_gives_passed_false(self):
        # Low visibility, but reasonable framing
        frames = _make_framing_frames(
            x_min=0.2, y_min=0.1, x_max=0.8, y_max=0.9, visibility=-2.0
        )
        result = run_quality_gates(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert result.passed is False
        assert result.status == "rejected"

    def test_framing_fail_gives_passed_false(self):
        # Good visibility, but tiny bounding box
        frames = _make_framing_frames(
            x_min=0.49, y_min=0.49, x_max=0.51, y_max=0.51, visibility=0.9
        )
        result = run_quality_gates(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert result.passed is False
        assert result.status == "rejected"

    def test_both_fail_gives_passed_false(self):
        frames = _make_framing_frames(
            x_min=0.49, y_min=0.49, x_max=0.51, y_max=0.51, visibility=-2.0
        )
        result = run_quality_gates(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert result.passed is False
        assert result.status == "rejected"

    def test_checks_list_contains_both_gates(self):
        frames = _make_n_frames(visibility=0.9)
        result = run_quality_gates(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert len(result.checks) == 2

    def test_checks_list_type(self):
        frames = _make_n_frames(visibility=0.9)
        result = run_quality_gates(frames, FRAME_WIDTH, FRAME_HEIGHT)
        for check in result.checks:
            assert isinstance(check, GateCheckResult)

    def test_fewer_than_five_frames_handled_gracefully(self):
        # Only 3 frames — should not crash
        frames = _make_framing_frames(
            x_min=0.2, y_min=0.1, x_max=0.8, y_max=0.9, visibility=0.9, n=3
        )
        result = run_quality_gates(frames, FRAME_WIDTH, FRAME_HEIGHT)
        # Result validity more important than pass/fail value
        assert isinstance(result, QualityGateResult)

    def test_visibility_check_fail_is_in_checks(self):
        frames = _make_framing_frames(
            x_min=0.2, y_min=0.1, x_max=0.8, y_max=0.9, visibility=-2.0
        )
        result = run_quality_gates(frames, FRAME_WIDTH, FRAME_HEIGHT)
        failed = [c for c in result.checks if not c.passed]
        assert any(
            "visibility" in c.name.lower() or "body" in c.name.lower()
            for c in failed
        )
