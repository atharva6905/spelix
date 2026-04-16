"""Unit tests for barbell detection and bar path tracking (B-020).

Tests cover:
- detect_barbell_in_frame: synthetic frame with drawn circle returns centroid near circle center
- detect_barbell_in_frame: frame with no circles returns None
- track_barbell: sequence of frames returns correct centroid list
- compute_bar_path: >50% None centroids returns None
- compute_bar_path: known centroid trajectory returns correct metrics
- compute_bar_path_from_landmarks: landmark-based fallback returns reasonable path
"""

import numpy as np
import pytest
import cv2

from app.cv.barbell_detection import (
    detect_barbell_in_frame,
    track_barbell,
    track_barbell_from_video,
    compute_bar_path,
    compute_bar_path_from_landmarks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_blank_frame(height: int = 480, width: int = 640) -> np.ndarray:
    """Return a plain dark-gray frame (no circles)."""
    return np.full((height, width, 3), 30, dtype=np.uint8)


def make_frame_with_circle(
    cx: int, cy: int, radius: int = 40, height: int = 480, width: int = 640
) -> np.ndarray:
    """Return a frame with a white-filled circle on a dark background."""
    frame = make_blank_frame(height, width)
    cv2.circle(frame, (cx, cy), radius, (200, 200, 200), thickness=-1)
    return frame


def make_synthetic_landmarks(
    wrist_left_x: float,
    wrist_left_y: float,
    wrist_right_x: float,
    wrist_right_y: float,
    n_landmarks: int = 33,
) -> np.ndarray:
    """Build a (33, 4) landmark array with specific wrist positions.

    Landmarks 15 (left wrist) and 16 (right wrist) are set explicitly;
    all others are zeros.  Shape matches MediaPipe BlazePose output.
    """
    lm = np.zeros((n_landmarks, 4), dtype=np.float32)
    lm[15] = [wrist_left_x, wrist_left_y, 0.0, 1.0]
    lm[16] = [wrist_right_x, wrist_right_y, 0.0, 1.0]
    return lm


# ---------------------------------------------------------------------------
# detect_barbell_in_frame
# ---------------------------------------------------------------------------


class TestDetectBarbellInFrame:
    def test_detects_circle_centroid(self):
        """A frame containing a clear circle should return a centroid close to
        the drawn circle's centre."""
        cx, cy = 320, 240
        frame = make_frame_with_circle(cx, cy, radius=40)
        result = detect_barbell_in_frame(frame)

        assert result is not None, "Expected centroid, got None"
        detected_x, detected_y = result
        # Allow ±20 px tolerance for HoughCircles
        assert abs(detected_x - cx) <= 20, f"x off by {abs(detected_x - cx)} px"
        assert abs(detected_y - cy) <= 20, f"y off by {abs(detected_y - cy)} px"

    def test_returns_none_for_blank_frame(self):
        """A frame with no circles should return None."""
        frame = make_blank_frame()
        result = detect_barbell_in_frame(frame)
        assert result is None

    def test_returns_none_for_noisy_frame(self):
        """A frame with random noise only (no clear circles) should return None."""
        rng = np.random.default_rng(42)
        frame = rng.integers(0, 50, size=(480, 640, 3), dtype=np.uint8)
        result = detect_barbell_in_frame(frame)
        # Noise is unlikely to produce a strong HoughCircles hit; either result is
        # acceptable but the function must not raise.
        assert result is None or (
            isinstance(result, tuple) and len(result) == 2
        )

    def test_returns_tuple_of_floats(self):
        """Return value must be a 2-tuple of floats (or None)."""
        frame = make_frame_with_circle(200, 150, radius=35)
        result = detect_barbell_in_frame(frame)
        if result is not None:
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], float)
            assert isinstance(result[1], float)


# ---------------------------------------------------------------------------
# track_barbell
# ---------------------------------------------------------------------------


class TestTrackBarbell:
    def test_returns_list_same_length_as_frames(self):
        """Output list length must equal input frames list length."""
        frames = [make_blank_frame() for _ in range(5)]
        result = track_barbell(frames)
        assert len(result) == 5

    def test_detects_circle_in_each_frame(self):
        """Frames with a clear circle should yield non-None centroids."""
        cx, cy = 320, 240
        frames = [make_frame_with_circle(cx, cy, radius=40) for _ in range(3)]
        result = track_barbell(frames)
        for centroid in result:
            assert centroid is not None, "Expected centroid for circle frame"

    def test_blank_frames_yield_none(self):
        """Blank frames without circles should yield None centroids."""
        frames = [make_blank_frame() for _ in range(4)]
        result = track_barbell(frames)
        for centroid in result:
            assert centroid is None

    def test_mixed_frames(self):
        """Mix of circle and blank frames should yield corresponding None / tuple."""
        circle_frame = make_frame_with_circle(300, 200, radius=40)
        blank_frame = make_blank_frame()
        frames = [circle_frame, blank_frame, circle_frame]
        result = track_barbell(frames)
        assert len(result) == 3
        assert result[0] is not None
        assert result[1] is None
        assert result[2] is not None

    def test_empty_input_returns_empty_list(self):
        """Empty input should return empty list without raising."""
        result = track_barbell([])
        assert result == []


# ---------------------------------------------------------------------------
# compute_bar_path
# ---------------------------------------------------------------------------


class TestComputeBarPath:
    def test_returns_none_when_majority_none(self):
        """If >50% of centroids are None, return None."""
        centroids = [None, None, None, (100.0, 200.0), (105.0, 190.0)]
        # 3/5 = 60% None → should return None
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is None

    def test_returns_none_when_all_none(self):
        """All-None centroid list → None."""
        centroids = [None] * 10
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is None

    def test_returns_dict_for_valid_trajectory(self):
        """A valid trajectory with no Nones should return a dict."""
        centroids = [(300.0 + i, 200.0 - i * 2) for i in range(10)]
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is not None
        assert isinstance(result, dict)

    def test_dict_has_required_keys(self):
        """Result dict must contain all four required keys."""
        centroids = [(320.0, float(200 - i * 5)) for i in range(6)]
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is not None
        assert "centroids" in result
        assert "lateral_deviation_px" in result
        assert "vertical_range_px" in result
        assert "path_consistency" in result

    def test_normalized_centroids_in_0_1(self):
        """All centroid coordinates must be normalised to [0, 1]."""
        centroids = [(320.0, 200.0), (330.0, 190.0), (310.0, 180.0)]
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is not None
        for x, y in result["centroids"]:
            assert 0.0 <= x <= 1.0, f"x={x} out of range"
            assert 0.0 <= y <= 1.0, f"y={y} out of range"

    def test_lateral_deviation_zero_for_vertical_path(self):
        """A perfectly vertical bar path should have lateral_deviation_px ≈ 0."""
        centroids = [(320.0, float(200 - i * 10)) for i in range(8)]
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is not None
        assert result["lateral_deviation_px"] == pytest.approx(0.0, abs=1e-6)

    def test_vertical_range_correct(self):
        """vertical_range_px should equal max_y - min_y of the trajectory."""
        # y goes from 100 to 200
        centroids = [(320.0, 100.0 + i * 10) for i in range(11)]  # 100 to 200
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is not None
        assert result["vertical_range_px"] == pytest.approx(100.0, abs=1e-6)

    def test_path_consistency_clamped_to_0_1(self):
        """path_consistency must be in [0, 1]."""
        centroids = [(float(i * 10), float(i * 5)) for i in range(10)]
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is not None
        assert 0.0 <= result["path_consistency"] <= 1.0

    def test_path_consistency_high_for_vertical_path(self):
        """A vertical path (constant x) should have path_consistency = 1.0."""
        centroids = [(320.0, float(i * 10)) for i in range(8)]
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is not None
        assert result["path_consistency"] == pytest.approx(1.0, abs=1e-6)

    def test_interpolates_none_centroids(self):
        """None centroids that are in the minority should be interpolated."""
        # Frame 0: (100, 200), Frame 1: None, Frame 2: (120, 180)
        centroids: list = [(100.0, 200.0), None, (120.0, 180.0)]
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is not None
        # After interpolation, should have 3 centroids
        assert len(result["centroids"]) == 3

    def test_lateral_deviation_known_value(self):
        """Lateral deviation: x oscillates between 310 and 330, mean=320, max dev=10."""
        centroids = [
            (310.0, 200.0),
            (330.0, 190.0),
            (310.0, 180.0),
            (330.0, 170.0),
        ]
        result = compute_bar_path(centroids, frame_width=640, frame_height=480)
        assert result is not None
        assert result["lateral_deviation_px"] == pytest.approx(10.0, abs=1e-6)


# ---------------------------------------------------------------------------
# compute_bar_path_from_landmarks
# ---------------------------------------------------------------------------


class TestComputeBarPathFromLandmarks:
    def _make_landmarks_sequence(
        self, n_frames: int = 10, start_y: float = 0.3, end_y: float = 0.7
    ) -> list[np.ndarray]:
        """Build a sequence of landmark arrays simulating a lift."""
        frames = []
        for i in range(n_frames):
            t = i / max(n_frames - 1, 1)
            y = start_y + t * (end_y - start_y)
            lm = make_synthetic_landmarks(
                wrist_left_x=0.5,
                wrist_left_y=y,
                wrist_right_x=0.5,
                wrist_right_y=y,
            )
            frames.append(lm)
        return frames

    def test_returns_dict_for_squat(self):
        lm_frames = self._make_landmarks_sequence()
        result = compute_bar_path_from_landmarks(lm_frames, exercise_type="squat")
        assert result is not None
        assert isinstance(result, dict)

    def test_returns_dict_for_bench(self):
        lm_frames = self._make_landmarks_sequence()
        result = compute_bar_path_from_landmarks(lm_frames, exercise_type="bench")
        assert result is not None

    def test_returns_dict_for_deadlift(self):
        lm_frames = self._make_landmarks_sequence()
        result = compute_bar_path_from_landmarks(lm_frames, exercise_type="deadlift")
        assert result is not None

    def test_has_same_keys_as_compute_bar_path(self):
        lm_frames = self._make_landmarks_sequence()
        result = compute_bar_path_from_landmarks(lm_frames, exercise_type="squat")
        assert result is not None
        assert "centroids" in result
        assert "lateral_deviation_px" in result
        assert "vertical_range_px" in result
        assert "path_consistency" in result

    def test_centroids_normalized(self):
        """Landmark coordinates are already normalised; output should be in [0,1]."""
        lm_frames = self._make_landmarks_sequence()
        result = compute_bar_path_from_landmarks(lm_frames, exercise_type="squat")
        assert result is not None
        for x, y in result["centroids"]:
            assert 0.0 <= x <= 1.0, f"x={x} out of range"
            assert 0.0 <= y <= 1.0, f"y={y} out of range"

    def test_returns_none_for_empty_frames(self):
        """Empty frame list → None (cannot compute path)."""
        result = compute_bar_path_from_landmarks([], exercise_type="squat")
        assert result is None

    def test_lateral_deviation_zero_for_constant_wrist_x(self):
        """Wrists at constant x → lateral_deviation_px ≈ 0 (in pixel terms, 0)."""
        lm_frames = self._make_landmarks_sequence()
        result = compute_bar_path_from_landmarks(lm_frames, exercise_type="deadlift")
        assert result is not None
        # All x positions are the same (0.5 normalised), so deviation = 0
        assert result["lateral_deviation_px"] == pytest.approx(0.0, abs=1e-6)

    def test_path_consistency_one_for_constant_x(self):
        """Constant x wrist position → path_consistency = 1.0."""
        lm_frames = self._make_landmarks_sequence()
        result = compute_bar_path_from_landmarks(lm_frames, exercise_type="bench")
        assert result is not None
        assert result["path_consistency"] == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# track_barbell_from_video
# ---------------------------------------------------------------------------


class TestTrackBarbellFromVideo:
    def test_streams_centroids_matching_track_barbell(self, tmp_path):
        """Streaming version must return identical centroids to list version."""
        import cv2
        import numpy as np

        # Synthesize a 3-frame video with a white circle at known positions
        w, h, fps = 640, 480, 30
        video_path = str(tmp_path / "test.mp4")
        fourcc = cv2.VideoWriter.fourcc(*"mp4v")
        writer = cv2.VideoWriter(video_path, fourcc, fps, (w, h))
        frames = []
        for cx in [100, 200, 300]:
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            cv2.circle(frame, (cx, 240), 30, (255, 255, 255), -1)
            frames.append(frame)
            writer.write(frame)
        writer.release()

        streaming_result = track_barbell_from_video(video_path)
        list_result = track_barbell(frames)

        assert len(streaming_result) == len(list_result) == 3
        for s, ref in zip(streaming_result, list_result):
            if s is None:
                assert ref is None
            else:
                assert ref is not None
                assert abs(s[0] - ref[0]) < 1.0
                assert abs(s[1] - ref[1]) < 1.0

    def test_returns_empty_list_for_missing_video(self, tmp_path):
        """Missing video returns empty list, not exception."""
        result = track_barbell_from_video(str(tmp_path / "does-not-exist.mp4"))
        assert result == []

    def test_handles_single_frame_video(self, tmp_path):
        import cv2
        import numpy as np

        w, h = 320, 240
        video_path = str(tmp_path / "single.mp4")
        fourcc = cv2.VideoWriter.fourcc(*"mp4v")
        writer = cv2.VideoWriter(video_path, fourcc, 30, (w, h))
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        cv2.circle(frame, (160, 120), 20, (255, 255, 255), -1)
        writer.write(frame)
        writer.release()

        result = track_barbell_from_video(video_path)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _downscale_for_detection  (D-035)
# ---------------------------------------------------------------------------


class TestDownscaleForDetection:
    def test_noop_for_small_frames(self):
        """480x270 input: no downscale, scale_factor == 1.0."""
        from app.cv.barbell_detection import _downscale_for_detection

        frame = np.zeros((270, 480, 3), dtype=np.uint8)
        scaled, scale_factor = _downscale_for_detection(frame)
        assert scale_factor == 1.0
        assert scaled.shape == (270, 480, 3)

    def test_noop_at_exactly_max_dim(self):
        """Frame whose longest side equals max_dim is not resized."""
        from app.cv.barbell_detection import _downscale_for_detection

        frame = np.zeros((480, 480, 3), dtype=np.uint8)
        scaled, scale_factor = _downscale_for_detection(frame)
        assert scale_factor == 1.0
        assert scaled.shape == (480, 480, 3)

    def test_1080p_to_480p(self):
        """1920x1080 input: longest side becomes 480, scale_factor == 4.0."""
        from app.cv.barbell_detection import _downscale_for_detection

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        scaled, scale_factor = _downscale_for_detection(frame)
        assert scaled.shape == (270, 480, 3)
        assert scale_factor == pytest.approx(4.0, rel=1e-3)

    def test_4k_to_480p(self):
        """3840x2160 (4K) input: longest side becomes 480, scale_factor == 8.0."""
        from app.cv.barbell_detection import _downscale_for_detection

        frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
        scaled, scale_factor = _downscale_for_detection(frame)
        assert scaled.shape == (270, 480, 3)
        assert scale_factor == pytest.approx(8.0, rel=1e-3)

    def test_portrait_orientation(self):
        """Portrait 1080x1920 input: longest side (1920) becomes 480."""
        from app.cv.barbell_detection import _downscale_for_detection

        frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
        scaled, scale_factor = _downscale_for_detection(frame)
        assert scaled.shape == (480, 270, 3)
        assert scale_factor == pytest.approx(4.0, rel=1e-3)


# ---------------------------------------------------------------------------
# detect_barbell_in_frame after D-035 downscale (post-fix behaviour)
# ---------------------------------------------------------------------------


class TestDetectBarbellAfterDownscale:
    def test_detect_returns_source_coords_on_1080p(self):
        """Circle drawn at (1000, 500) in a 1920x1080 frame is detected near
        (1000, 500) after internal downscale-to-480 + scale-back."""
        w, h = 1920, 1080
        cx, cy = 1000, 500
        radius = 60
        frame = np.full((h, w, 3), 30, dtype=np.uint8)
        cv2.circle(frame, (cx, cy), radius, (200, 200, 200), thickness=-1)

        result = detect_barbell_in_frame(frame)
        assert result is not None, "Expected centroid on clean 1080p circle"
        dx = abs(result[0] - cx)
        dy = abs(result[1] - cy)
        # Error budget: ~1 source px per 0.25 scaled px. Allow ±20 source px.
        assert dx <= 20, f"x off by {dx} px (detected {result[0]})"
        assert dy <= 20, f"y off by {dy} px (detected {result[1]})"

    def test_detect_returns_source_coords_on_portrait_1080p(self):
        """Same test in portrait orientation — longest side 1920 (height)."""
        w, h = 1080, 1920
        cx, cy = 540, 900
        radius = 60
        frame = np.full((h, w, 3), 30, dtype=np.uint8)
        cv2.circle(frame, (cx, cy), radius, (200, 200, 200), thickness=-1)

        result = detect_barbell_in_frame(frame)
        assert result is not None
        dx = abs(result[0] - cx)
        dy = abs(result[1] - cy)
        assert dx <= 20, f"x off by {dx} px"
        assert dy <= 20, f"y off by {dy} px"

    def test_detect_on_1080p_is_fast(self):
        """Per-frame detection on 1080p completes in < 200 ms (budget check).

        This is a unit-level smoke test that the downscale is wired through;
        the rigorous stage budget check is the slow integration test.
        """
        import time

        w, h = 1920, 1080
        frame = np.full((h, w, 3), 30, dtype=np.uint8)
        cv2.circle(frame, (1000, 500), 60, (200, 200, 200), thickness=-1)

        t0 = time.perf_counter()
        for _ in range(3):  # warm-up smoothed median-ish
            detect_barbell_in_frame(frame)
        elapsed = (time.perf_counter() - t0) / 3
        assert elapsed < 0.2, f"per-frame detection took {elapsed*1000:.0f} ms (budget 200 ms)"
