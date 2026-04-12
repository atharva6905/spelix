"""
Unit tests for quality_gates.py (FR-CVPL-03 through FR-CVPL-11).

All tests use synthetic numpy arrays with known visibility values — no real video.
Landmark array shape per frame: (33, 5) — [x, y, z, visibility, presence].
"""

import math
import subprocess
from unittest.mock import MagicMock, patch

import numpy as np

from app.cv.quality_gates import (
    GateCheckResult,
    QualityGateResult,
    check_body_visibility,
    check_framing,
    check_minimum_resolution,
    check_occlusion,
    check_single_person,
    check_video_file,
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
        msg = result.user_message.lower()
        assert "visible" in msg, (
            f"Expected rejection message to mention visibility. Got: {result.user_message!r}"
        )

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
        msg = result.user_message.lower()
        assert "closer" in msg or "far" in msg, (
            f"Expected too-small framing message to mention moving closer or being too far. "
            f"Got: {result.user_message!r}"
        )

    def test_too_large_user_message_mentions_step_back(self):
        frames = _make_framing_frames(
            x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0, visibility=0.9
        )
        result = check_framing(frames, FRAME_WIDTH, FRAME_HEIGHT)
        msg = result.user_message.lower()
        assert "back" in msg or "close" in msg, (
            f"Expected too-large framing message to mention stepping back or being too close. "
            f"Got: {result.user_message!r}"
        )

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

    def test_portrait_video_passes_with_well_framed_subject(self):
        """Portrait (9:16) videos have smaller landmark width fractions.
        A body spanning 30% width × 70% height = 21% area should pass
        because the threshold scales by aspect ratio."""
        frames = _make_framing_frames(
            x_min=0.35, y_min=0.10, x_max=0.65, y_max=0.80, visibility=0.9
        )
        # 0.30 width × 0.70 height = 0.21 area — would fail old 0.30 threshold
        result = check_framing(frames, frame_width=1080, frame_height=1920)
        assert result.passed is True

    def test_portrait_video_still_rejects_truly_distant_subject(self):
        """Even in portrait, a very small bounding box should still reject."""
        frames = _make_framing_frames(
            x_min=0.40, y_min=0.35, x_max=0.60, y_max=0.65, visibility=0.9
        )
        # 0.20 width × 0.30 height = 0.06 area — too small for any aspect ratio
        result = check_framing(frames, frame_width=1080, frame_height=1920)
        assert result.passed is False

    def test_landscape_threshold_unchanged(self):
        """Landscape (16:9) framing threshold stays at 0.30 — no regression."""
        frames = _make_framing_frames(
            x_min=0.35, y_min=0.10, x_max=0.65, y_max=0.80, visibility=0.9
        )
        # 0.30 × 0.70 = 0.21 area — should still FAIL at 0.30 for landscape
        result = check_framing(frames, frame_width=1920, frame_height=1080)
        assert result.passed is False


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

    def test_checks_list_contains_all_gates(self):
        # resolution + body_visibility + framing + single_person = 4 error-level gates
        frames = _make_n_frames(visibility=0.9)
        result = run_quality_gates(frames, FRAME_WIDTH, FRAME_HEIGHT)
        assert len(result.checks) >= 4
        error_checks = [c for c in result.checks if c.level == "error"]
        assert len(error_checks) == 4

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


# ---------------------------------------------------------------------------
# check_video_file (B-051 — FFprobe gate)
# ---------------------------------------------------------------------------


class TestCheckVideoFile:
    def test_passes_when_duration_within_limit(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "30.0\n"
        with patch("app.cv.quality_gates.subprocess.run", return_value=mock_result):
            result = check_video_file("/fake/video.mp4")
        assert result.passed is True
        assert result.metric_value == 30.0

    def test_rejects_when_duration_exceeds_limit(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "150.0\n"
        with patch("app.cv.quality_gates.subprocess.run", return_value=mock_result):
            result = check_video_file("/fake/video.mp4")
        assert result.passed is False
        assert result.metric_value == 150.0
        assert "120" in result.user_message

    def test_rejects_when_ffprobe_returns_nonzero(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("app.cv.quality_gates.subprocess.run", return_value=mock_result):
            result = check_video_file("/fake/corrupt.mp4")
        assert result.passed is False
        assert "corrupt" in result.user_message.lower() or "unsupported" in result.user_message.lower()

    def test_rejects_when_ffprobe_not_found(self):
        with patch(
            "app.cv.quality_gates.subprocess.run",
            side_effect=FileNotFoundError("ffprobe not found"),
        ):
            result = check_video_file("/fake/video.mp4")
        assert result.passed is False

    def test_rejects_on_timeout(self):
        with patch(
            "app.cv.quality_gates.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=30),
        ):
            result = check_video_file("/fake/video.mp4")
        assert result.passed is False

    def test_level_is_error(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "30.0\n"
        with patch("app.cv.quality_gates.subprocess.run", return_value=mock_result):
            result = check_video_file("/fake/video.mp4")
        assert result.level == "error"


# ---------------------------------------------------------------------------
# check_single_person (B-061)
# ---------------------------------------------------------------------------


class TestCheckSinglePerson:
    def test_passes_with_stable_hip_positions(self):
        # Hip landmarks at consistent x positions — no large jumps
        frames = []
        for _ in range(10):
            frame = np.zeros((33, 5), dtype=np.float32)
            frame[:, 0] = 0.5  # x = 0.5 (normalised)
            frame[:, 3] = 0.9  # visibility
            frames.append(frame)
        result = check_single_person(frames, FRAME_WIDTH)
        assert result.passed is True

    def test_rejects_with_large_hip_jumps(self):
        # Alternating hip x positions jumping by 30% of frame width
        frames = []
        for i in range(10):
            frame = np.zeros((33, 5), dtype=np.float32)
            frame[:, 0] = 0.5
            frame[:, 3] = 0.9
            # Hip landmarks (23, 24) alternate between 0.1 and 0.5 normalised x
            hip_x = 0.1 if i % 2 == 0 else 0.5
            frame[23, 0] = hip_x
            frame[24, 0] = hip_x
            frames.append(frame)
        result = check_single_person(frames, FRAME_WIDTH)
        assert result.passed is False

    def test_level_is_error(self):
        frames = _make_n_frames(10)
        result = check_single_person(frames, FRAME_WIDTH)
        assert result.level == "error"

    def test_name_is_single_person(self):
        frames = _make_n_frames(5)
        result = check_single_person(frames, FRAME_WIDTH)
        assert result.name == "single_person"

    def test_handles_fewer_than_two_frames(self):
        frames = _make_n_frames(1)
        result = check_single_person(frames, FRAME_WIDTH)
        assert isinstance(result, GateCheckResult)


# ---------------------------------------------------------------------------
# check_minimum_resolution (B-062)
# ---------------------------------------------------------------------------


class TestCheckMinimumResolution:
    def test_rejects_640x480(self):
        result = check_minimum_resolution(640, 480)
        assert result.passed is False

    def test_passes_1280x720(self):
        result = check_minimum_resolution(1280, 720)
        assert result.passed is True

    def test_passes_720x1280_portrait(self):
        # Portrait 720p — min dimension is 720
        result = check_minimum_resolution(720, 1280)
        assert result.passed is True

    def test_passes_1920x1080(self):
        result = check_minimum_resolution(1920, 1080)
        assert result.passed is True

    def test_rejects_1280x480_mixed(self):
        # Min dimension is 480 — below threshold
        result = check_minimum_resolution(1280, 480)
        assert result.passed is False

    def test_metric_value_is_min_dimension(self):
        result = check_minimum_resolution(640, 480)
        assert result.metric_value == 480.0

    def test_threshold_is_720(self):
        result = check_minimum_resolution(1280, 720)
        assert result.threshold == 720.0

    def test_level_is_error(self):
        result = check_minimum_resolution(640, 480)
        assert result.level == "error"

    def test_name_is_resolution(self):
        result = check_minimum_resolution(1280, 720)
        assert result.name == "resolution"


# ---------------------------------------------------------------------------
# check_occlusion (B-063)
# ---------------------------------------------------------------------------


class TestCheckOcclusion:
    def _frames_with_low_knee_visibility(self, n: int = 10) -> list[np.ndarray]:
        """Frames where left knee (25) has very low visibility."""
        frames = []
        for _ in range(n):
            frame = np.zeros((33, 5), dtype=np.float32)
            frame[:, 3] = 5.0  # high visibility for all
            frame[25, 3] = -5.0  # left knee: sigmoid(-5) ≈ 0.007 < 0.30
            frames.append(frame)
        return frames

    def test_returns_warning_for_occluded_knee(self):
        frames = self._frames_with_low_knee_visibility()
        results = check_occlusion(frames, "squat")
        assert len(results) > 0
        names = [r.name for r in results]
        assert any("left_knee" in n for n in names)

    def test_no_warnings_when_all_visible(self):
        # All landmarks at high visibility
        frames = _make_n_frames(10, visibility=5.0)
        results = check_occlusion(frames, "squat")
        assert results == []

    def test_warnings_are_non_rejecting(self):
        frames = self._frames_with_low_knee_visibility()
        results = check_occlusion(frames, "squat")
        for r in results:
            assert r.passed is True
            assert r.level == "warning"

    def test_bench_uses_different_landmarks(self):
        # Make all squat landmarks invisible, bench landmarks visible
        frames = []
        for _ in range(5):
            frame = np.zeros((33, 5), dtype=np.float32)
            frame[:, 3] = 5.0
            # Make squat landmarks (hip/knee/ankle) invisible
            for idx in [23, 24, 25, 26, 27, 28]:
                frame[idx, 3] = -5.0
            frames.append(frame)
        # For bench, only shoulder/elbow/wrist matter — these are visible
        results = check_occlusion(frames, "bench")
        assert results == []

    def test_defaults_to_squat_for_unknown_exercise(self):
        frames = _make_n_frames(5, visibility=5.0)
        # Should not raise
        results = check_occlusion(frames, "unknown_exercise")
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Gate 6: Lighting (FR-CVPL-08)
# ---------------------------------------------------------------------------


class TestLightingGate:
    """Tests for check_lighting — warning-level only."""

    def test_dark_frames_produce_warning(self):
        from app.cv.quality_gates import check_lighting

        # Mean brightness ~30 (well below 60 threshold)
        dark_frames = [np.full((100, 100), 30, dtype=np.uint8) for _ in range(10)]
        result = check_lighting(dark_frames)
        assert result.name == "lighting"
        assert result.level == "warning"
        assert result.passed is True  # Warnings never reject
        assert result.metric_value < 60.0
        assert "lighting" in result.user_message.lower()

    def test_overexposed_frames_produce_warning(self):
        from app.cv.quality_gates import check_lighting

        # Mean brightness ~245 (above 240 threshold)
        bright_frames = [np.full((100, 100), 245, dtype=np.uint8) for _ in range(10)]
        result = check_lighting(bright_frames)
        assert result.name == "lighting"
        assert result.level == "warning"
        assert result.passed is True
        assert result.metric_value > 240.0
        assert "overexposed" in result.user_message.lower()

    def test_good_lighting_passes_silently(self):
        from app.cv.quality_gates import check_lighting

        # Mean brightness ~128 (well within 60–240 range)
        ok_frames = [np.full((100, 100), 128, dtype=np.uint8) for _ in range(10)]
        result = check_lighting(ok_frames)
        assert result.name == "lighting"
        assert result.passed is True
        assert result.user_message == ""

    def test_empty_frames_passes(self):
        from app.cv.quality_gates import check_lighting

        result = check_lighting([])
        assert result.passed is True
        assert result.user_message == ""

    def test_uses_only_first_10_frames(self):
        from app.cv.quality_gates import check_lighting

        # 15 frames: first 10 bright (ok), last 5 dark — should pass
        frames = [np.full((100, 100), 128, dtype=np.uint8) for _ in range(10)]
        frames += [np.full((100, 100), 10, dtype=np.uint8) for _ in range(5)]
        result = check_lighting(frames)
        assert result.passed is True
        assert result.user_message == ""


# ---------------------------------------------------------------------------
# Gate 7: Camera stability (FR-CVPL-09)
# ---------------------------------------------------------------------------


class TestCameraStabilityGate:
    """Tests for check_camera_stability — warning-level only."""

    def test_static_frames_pass(self):
        from app.cv.quality_gates import check_camera_stability

        # Identical frames → zero optical flow
        static = [np.full((100, 100), 128, dtype=np.uint8) for _ in range(6)]
        result = check_camera_stability(static)
        assert result.name == "camera_stability"
        assert result.passed is True
        assert result.metric_value < 3.0
        assert result.user_message == ""

    def test_moving_frames_produce_warning(self):
        from app.cv.quality_gates import check_camera_stability

        # Simulate large movement: create gradient frames shifted heavily
        # Use a textured pattern so optical flow has features to track
        np.random.seed(42)
        base = np.random.randint(0, 256, (200, 200), dtype=np.uint8)
        frames = []
        for i in range(6):
            # Roll the image by 30px each frame — big movement
            shifted = np.roll(base, i * 30, axis=1)
            frames.append(shifted)
        result = check_camera_stability(frames)
        assert result.name == "camera_stability"
        assert result.passed is True  # Warning only
        assert result.level == "warning"
        assert result.metric_value > 3.0
        assert "moving" in result.user_message.lower()

    def test_single_frame_passes(self):
        from app.cv.quality_gates import check_camera_stability

        # Need at least 2 frames for flow
        result = check_camera_stability([np.full((100, 100), 128, dtype=np.uint8)])
        assert result.passed is True
        assert result.user_message == ""

    def test_two_identical_frames_pass(self):
        from app.cv.quality_gates import check_camera_stability

        frame = np.full((100, 100), 100, dtype=np.uint8)
        result = check_camera_stability([frame, frame])
        assert result.passed is True
        assert result.metric_value < 3.0
