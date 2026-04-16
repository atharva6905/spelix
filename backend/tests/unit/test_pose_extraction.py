"""
Unit tests for pose_extraction.py (B-015).

Requirements: FR-CVPL-01, FR-CVPL-02, FR-CVPL-12, FR-CVPL-13.

All tests use synthetic data — no real video file, no real MediaPipe model
file. ``cv2.VideoCapture`` and the MediaPipe Tasks API
(``PoseLandmarker``, ``PoseLandmarkerOptions``, ``BaseOptions``,
``RunningMode``, ``mp.Image``) are mocked via ``unittest.mock.patch``
targeting the deferred imports inside ``extract_landmarks``.

Migration note: this test file was rewritten when ``pose_extraction.py``
moved from the legacy ``mediapipe.solutions.pose.Pose`` API (which
doesn't exist on Linux x86_64 wheels) to the modern
``mediapipe.tasks.python.vision.PoseLandmarker`` API.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    """Reference sigmoid for test assertions."""
    return 1.0 / (1.0 + math.exp(-float(x)))


def _make_landmark(x=0.5, y=0.5, z=0.0, visibility=0.9, presence=0.9):
    """Create a mock MediaPipe NormalizedLandmark object."""
    lm = MagicMock()
    lm.x = x
    lm.y = y
    lm.z = z
    lm.visibility = visibility
    lm.presence = presence
    return lm


def _make_pose_landmarks_list(
    visibility=0.9,
    presence=0.9,
    x=0.5,
    y=0.5,
    z=0.0,
):
    """Create the Tasks API pose_landmarks shape: list of poses, each a list of 33 landmarks."""
    return [[_make_landmark(x, y, z, visibility, presence) for _ in range(33)]]


def _make_mock_cap(num_frames=2, fps=30.0, width=1280.0, height=720.0):
    """Create a mock cv2.VideoCapture."""
    cap = MagicMock()

    props = {
        5: fps,    # CAP_PROP_FPS
        3: width,  # CAP_PROP_FRAME_WIDTH
        4: height, # CAP_PROP_FRAME_HEIGHT
    }
    cap.get.side_effect = lambda prop: props.get(prop, 0.0)

    frame = np.zeros((int(height), int(width), 3), dtype=np.uint8)
    reads = [(True, frame.copy()) for _ in range(num_frames)] + [(False, None)]
    cap.read.side_effect = reads
    cap.release = MagicMock()
    return cap


def _make_mock_landmarker(detect_results: list):
    """Create a mock PoseLandmarker context manager.

    ``detect_results`` is a list — one entry per call to ``detect()``.
    Each entry is the value to assign to the returned object's
    ``pose_landmarks`` attribute (the Tasks API's per-frame result shape:
    list-of-poses, each pose a list of 33 landmarks; or empty list if
    no pose detected).
    """
    landmarker = MagicMock()
    landmarker.__enter__ = MagicMock(return_value=landmarker)
    landmarker.__exit__ = MagicMock(return_value=False)

    detect_call_results = []
    for r in detect_results:
        result_obj = MagicMock()
        result_obj.pose_landmarks = r
        detect_call_results.append(result_obj)

    landmarker.detect.side_effect = detect_call_results
    return landmarker


# Capture-and-return helper so tests can assert on the constructor args.
_constructor_args: dict = {}

# Captures the shape of every ``data`` array passed to ``mp.Image`` during a
# single ``_run_extract`` call so tests can assert that resize happened (or
# didn't) before MediaPipe inference. Cleared at the start of each call.
_mp_image_call_shapes: list[tuple[int, ...]] = []


def _run_extract(
    mock_cap,
    detect_results: list,
    video_path: str = "/fake/video.mp4",
):
    """Import and run ``extract_landmarks`` with cv2 + Tasks API mocked.

    Patches the deferred imports inside ``extract_landmarks``:
        ``mediapipe.tasks.python.BaseOptions``
        ``mediapipe.tasks.python.vision.PoseLandmarker``
        ``mediapipe.tasks.python.vision.PoseLandmarkerOptions``
        ``mediapipe.tasks.python.vision.RunningMode``
        ``mediapipe.Image`` and ``mediapipe.ImageFormat``

    Also patches ``_resolve_model_path`` so the function doesn't
    actually need a real .task file on disk.
    """
    _constructor_args.clear()
    _mp_image_call_shapes.clear()

    landmarker = _make_mock_landmarker(detect_results)
    landmarker_cls = MagicMock(return_value=landmarker)
    landmarker_cls.create_from_options = MagicMock(return_value=landmarker)

    def options_capture(**kwargs):
        _constructor_args.update(kwargs)
        return MagicMock()

    options_cls = MagicMock(side_effect=options_capture)

    base_options_cls = MagicMock()
    running_mode = MagicMock()
    running_mode.IMAGE = "IMAGE"

    def _mp_image_side_effect(image_format, data):
        # ``data`` is the BGR→RGB-converted numpy frame passed into
        # MediaPipe's Image constructor. We record its shape so the
        # TestFrameDownsampling suite can assert resize behavior without
        # mocking cv2.resize itself.
        _mp_image_call_shapes.append(tuple(data.shape))
        return MagicMock()

    mp_image_cls = MagicMock(side_effect=_mp_image_side_effect)
    mp_image_format = MagicMock()
    mp_image_format.SRGB = "SRGB"

    with patch("cv2.VideoCapture", return_value=mock_cap), patch(
        "app.cv.pose_extraction._resolve_model_path",
        return_value="/fake/pose_landmarker_heavy.task",
    ), patch.dict(
        "sys.modules",
        {},
    ):
        # Patch the deferred Tasks API imports at their module of origin so
        # ``from mediapipe.tasks.python.vision import PoseLandmarker, ...``
        # picks up the mocks.
        with patch("mediapipe.tasks.python.vision.PoseLandmarker", landmarker_cls), patch(
            "mediapipe.tasks.python.vision.PoseLandmarkerOptions", options_cls
        ), patch(
            "mediapipe.tasks.python.vision.RunningMode", running_mode
        ), patch(
            "mediapipe.tasks.python.BaseOptions", base_options_cls
        ), patch(
            "mediapipe.Image", mp_image_cls
        ), patch(
            "mediapipe.ImageFormat", mp_image_format
        ):
            from app.cv.pose_extraction import extract_landmarks

            return extract_landmarks(video_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExtractLandmarksShape:
    """Verify output shape and types."""

    def test_returns_tuple_of_four(self):
        cap = _make_mock_cap(num_frames=2)
        result = _run_extract(cap, [_make_pose_landmarks_list(), _make_pose_landmarks_list()])

        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_landmarks_per_frame_is_list(self):
        cap = _make_mock_cap(num_frames=2)
        landmarks_per_frame, fps, width, height = _run_extract(
            cap, [_make_pose_landmarks_list(), _make_pose_landmarks_list()]
        )

        assert isinstance(landmarks_per_frame, list)
        assert len(landmarks_per_frame) == 2

    def test_each_frame_array_shape_33_5(self):
        cap = _make_mock_cap(num_frames=2)
        landmarks_per_frame, _, _, _ = _run_extract(
            cap, [_make_pose_landmarks_list(), _make_pose_landmarks_list()]
        )

        for arr in landmarks_per_frame:
            assert isinstance(arr, np.ndarray)
            assert arr.shape == (33, 5)

    def test_fps_width_height_extracted_correctly(self):
        cap = _make_mock_cap(num_frames=1, fps=30.0, width=1280.0, height=720.0)
        _, fps, width, height = _run_extract(cap, [_make_pose_landmarks_list()])

        assert fps == 30.0
        assert width == 1280
        assert height == 720

    def test_width_height_are_ints(self):
        cap = _make_mock_cap(num_frames=1)
        _, fps, width, height = _run_extract(cap, [_make_pose_landmarks_list()])

        assert isinstance(width, int)
        assert isinstance(height, int)


class TestSigmoidGuard:
    """Verify sigmoid is applied to visibility/presence values outside [0, 1]."""

    def test_sigmoid_applied_to_visibility_outside_range(self):
        cap = _make_mock_cap(num_frames=1)
        landmarks_per_frame, _, _, _ = _run_extract(
            cap, [_make_pose_landmarks_list(visibility=2.0, presence=0.9)]
        )

        frame_arr = landmarks_per_frame[0]
        expected = _sigmoid(2.0)
        for i in range(33):
            assert abs(frame_arr[i, 3] - expected) < 1e-6

    def test_sigmoid_applied_to_presence_outside_range(self):
        cap = _make_mock_cap(num_frames=1)
        landmarks_per_frame, _, _, _ = _run_extract(
            cap, [_make_pose_landmarks_list(visibility=0.9, presence=-3.0)]
        )

        frame_arr = landmarks_per_frame[0]
        expected = _sigmoid(-3.0)
        for i in range(33):
            assert abs(frame_arr[i, 4] - expected) < 1e-6

    def test_sigmoid_not_applied_when_value_in_range(self):
        cap = _make_mock_cap(num_frames=1)
        landmarks_per_frame, _, _, _ = _run_extract(
            cap, [_make_pose_landmarks_list(visibility=0.7, presence=0.6)]
        )

        frame_arr = landmarks_per_frame[0]
        for i in range(33):
            assert abs(frame_arr[i, 3] - 0.7) < 1e-6
            assert abs(frame_arr[i, 4] - 0.6) < 1e-6

    def test_boundary_values_zero_and_one_not_sigmoided(self):
        cap = _make_mock_cap(num_frames=1)
        landmarks_per_frame, _, _, _ = _run_extract(
            cap, [_make_pose_landmarks_list(visibility=0.0, presence=1.0)]
        )

        frame_arr = landmarks_per_frame[0]
        for i in range(33):
            assert abs(frame_arr[i, 3] - 0.0) < 1e-6
            assert abs(frame_arr[i, 4] - 1.0) < 1e-6


class TestNoLandmarksDetected:
    """Verify zero-filled array when no pose detected.

    The Tasks API returns ``result.pose_landmarks = []`` (empty list) when
    no pose is detected, NOT ``None`` like the legacy ``solutions`` API.
    """

    def test_zero_array_returned_for_frames_with_no_landmarks(self):
        cap = _make_mock_cap(num_frames=1)
        landmarks_per_frame, _, _, _ = _run_extract(cap, [[]])  # empty pose list

        assert len(landmarks_per_frame) == 1
        arr = landmarks_per_frame[0]
        assert arr.shape == (33, 5)
        assert np.all(arr == 0.0)

    def test_mixed_frames_detection_and_no_detection(self):
        cap = _make_mock_cap(num_frames=2, fps=25.0, width=640.0, height=480.0)

        landmarks_per_frame, fps, width, height = _run_extract(
            cap,
            [
                _make_pose_landmarks_list(visibility=0.8, presence=0.8),  # detected
                [],  # no pose
            ],
        )

        assert len(landmarks_per_frame) == 2
        assert not np.all(landmarks_per_frame[0] == 0.0)
        assert np.all(landmarks_per_frame[1] == 0.0)


class TestMediaPipeConfig:
    """Verify exact MediaPipe Tasks API configuration is used.

    The legacy ``solutions.pose.Pose`` ctor took ``model_complexity``,
    ``static_image_mode``, ``min_detection_confidence``,
    ``min_tracking_confidence``, ``num_threads``. The Tasks API uses
    ``base_options`` (with the model file path encoding the BlazePose
    Heavy choice), ``running_mode=IMAGE`` (equivalent to
    ``static_image_mode=True``), and three confidence thresholds.
    """

    def test_pose_initialized_with_correct_tasks_config(self):
        cap = _make_mock_cap(num_frames=1)
        _run_extract(cap, [_make_pose_landmarks_list()])

        # The PoseLandmarkerOptions constructor should have been called
        # with the canonical Spelix config.
        assert _constructor_args["running_mode"] == "IMAGE"
        assert _constructor_args["num_poses"] == 1
        assert _constructor_args["min_pose_detection_confidence"] == 0.5
        assert _constructor_args["min_pose_presence_confidence"] == 0.5
        assert _constructor_args["min_tracking_confidence"] == 0.5
        # base_options should have been constructed (we don't introspect
        # its model_asset_path here because that's covered by the
        # _resolve_model_path tests below).
        assert _constructor_args["base_options"] is not None


class TestLandmarkColumnOrdering:
    """Verify landmark array columns are [x, y, z, visibility, presence]."""

    def test_landmark_columns_order(self):
        cap = _make_mock_cap(num_frames=1)
        landmarks_per_frame, _, _, _ = _run_extract(
            cap,
            [
                _make_pose_landmarks_list(
                    x=0.1, y=0.2, z=0.3, visibility=0.4, presence=0.5
                )
            ],
        )

        arr = landmarks_per_frame[0]
        assert abs(arr[0, 0] - 0.1) < 1e-6  # x
        assert abs(arr[0, 1] - 0.2) < 1e-6  # y
        assert abs(arr[0, 2] - 0.3) < 1e-6  # z
        assert abs(arr[0, 3] - 0.4) < 1e-6  # visibility (in range, no sigmoid)
        assert abs(arr[0, 4] - 0.5) < 1e-6  # presence (in range, no sigmoid)


class TestVideoCapRelease:
    """VideoCapture is properly released after extraction."""

    def test_cap_released_on_success(self):
        cap = _make_mock_cap(num_frames=1)
        _run_extract(cap, [_make_pose_landmarks_list()])

        cap.release.assert_called_once()


class TestModelPathResolution:
    """Verify _resolve_model_path candidate fallback + actionable errors.

    Mirrors the pattern in app/config.py::_resolve_threshold_path which
    has its own dedicated test file (test_config_path_resolution.py).
    """

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("POSE_LANDMARKER_MODEL_PATH", "/custom/model.task")
        from app.cv.pose_extraction import _resolve_model_path

        assert _resolve_model_path() == "/custom/model.task"

    def test_raises_with_actionable_error_when_no_candidate_exists(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.delenv("POSE_LANDMARKER_MODEL_PATH", raising=False)
        # chdir to an empty tmp dir so Path.cwd() / "models" / ... misses,
        # and patch _DEFAULT_MODEL_PATH to a non-existent path.
        monkeypatch.chdir(tmp_path)

        from app.cv import pose_extraction as mod

        monkeypatch.setattr(
            mod, "_DEFAULT_MODEL_PATH", str(tmp_path / "nope" / "pose.task")
        )

        # The local-dev candidate uses Path(__file__).parent.parent.parent.parent
        # which resolves to the real spelix repo root — that file does NOT
        # exist locally yet (the model is only baked into the Docker image),
        # so all three candidates should miss.
        import pytest

        with pytest.raises(FileNotFoundError) as exc_info:
            mod._resolve_model_path()
        msg = str(exc_info.value)
        assert "pose_landmarker_heavy.task" in msg
        assert "POSE_LANDMARKER_MODEL_PATH" in msg


class TestPoseFrameDimensions:
    """`_pose_frame_dimensions` caps the long side at 1280, never upscales, rounds even.

    Mirrors `_annotation_dimensions` in artifact_generation.py. See D-035 / ADR-057.
    """

    def test_landscape_1080p_caps_to_1280x720(self):
        from app.cv.pose_extraction import _pose_frame_dimensions

        assert _pose_frame_dimensions(1920, 1080) == (1280, 720)

    def test_portrait_1080p_caps_to_720x1280(self):
        from app.cv.pose_extraction import _pose_frame_dimensions

        assert _pose_frame_dimensions(1080, 1920) == (720, 1280)

    def test_720p_source_unchanged(self):
        from app.cv.pose_extraction import _pose_frame_dimensions

        assert _pose_frame_dimensions(1280, 720) == (1280, 720)
        assert _pose_frame_dimensions(720, 1280) == (720, 1280)

    def test_sub_720p_not_upscaled(self):
        """Never upscale — scale is capped at 1.0."""
        from app.cv.pose_extraction import _pose_frame_dimensions

        assert _pose_frame_dimensions(640, 480) == (640, 480)
        assert _pose_frame_dimensions(320, 240) == (320, 240)

    def test_odd_source_dimensions_rounded_even(self):
        """Rounds to even dims so any downstream H.264 pipeline stays happy."""
        from app.cv.pose_extraction import _pose_frame_dimensions

        w, h = _pose_frame_dimensions(1921, 1081)
        assert w % 2 == 0
        assert h % 2 == 0
        # 1921 > 1280 so scale = 1280/1921 = 0.6663..., 1921 * 0.6663 ≈ 1280, 1081 * 0.6663 ≈ 720
        assert w == 1280
        assert h == 720

    def test_square_source_at_cap(self):
        from app.cv.pose_extraction import _pose_frame_dimensions

        # 2000×2000 → scale = 1280/2000 = 0.64 → (1280, 1280)
        assert _pose_frame_dimensions(2000, 2000) == (1280, 1280)


class TestFrameDownsampling:
    """`extract_landmarks` resizes frames above _MAX_POSE_DIM before inference (D-035)."""

    def test_1080p_landscape_source_resized_to_1280x720_for_mediapipe(self):
        cap = _make_mock_cap(num_frames=1, fps=30.0, width=1920.0, height=1080.0)
        _, fps, width, height = _run_extract(cap, [_make_pose_landmarks_list()])

        # extract_landmarks returns SOURCE dimensions — landmarks are
        # normalized [0,1] so downstream pixel math must use the original
        # frame size, not the downscaled one.
        assert width == 1920
        assert height == 1080
        assert fps == 30.0

        # But MediaPipe received a resized frame.
        assert len(_mp_image_call_shapes) == 1
        # cv2.cvtColor preserves shape → (h, w, 3). After resize to 1280×720:
        assert _mp_image_call_shapes[0] == (720, 1280, 3)

    def test_1080p_portrait_source_resized_to_720x1280_for_mediapipe(self):
        cap = _make_mock_cap(num_frames=1, fps=30.0, width=1080.0, height=1920.0)
        _, _, width, height = _run_extract(cap, [_make_pose_landmarks_list()])

        assert width == 1080
        assert height == 1920
        assert _mp_image_call_shapes[0] == (1280, 720, 3)

    def test_720p_source_not_resized(self):
        """Exactly at the cap — cv2.resize should NOT be called (no-op path)."""
        cap = _make_mock_cap(num_frames=1, fps=30.0, width=1280.0, height=720.0)
        _run_extract(cap, [_make_pose_landmarks_list()])

        assert _mp_image_call_shapes[0] == (720, 1280, 3)

    def test_sub_720p_source_not_upscaled(self):
        """480p → still 480p into MediaPipe; the cap never upscales."""
        cap = _make_mock_cap(num_frames=1, fps=30.0, width=640.0, height=480.0)
        _, _, width, height = _run_extract(cap, [_make_pose_landmarks_list()])

        assert width == 640
        assert height == 480
        assert _mp_image_call_shapes[0] == (480, 640, 3)

    def test_all_frames_downsampled_when_above_cap(self):
        """Multi-frame clip: every frame gets resized, not just the first."""
        cap = _make_mock_cap(num_frames=3, fps=30.0, width=1920.0, height=1080.0)
        _run_extract(
            cap,
            [
                _make_pose_landmarks_list(),
                _make_pose_landmarks_list(),
                _make_pose_landmarks_list(),
            ],
        )

        assert len(_mp_image_call_shapes) == 3
        for shape in _mp_image_call_shapes:
            assert shape == (720, 1280, 3)

    def test_landmark_shape_still_33x5_after_downsample(self):
        """Sanity — downsampling does not break the landmark output contract."""
        cap = _make_mock_cap(num_frames=2, fps=30.0, width=1920.0, height=1080.0)
        landmarks_per_frame, _, _, _ = _run_extract(
            cap, [_make_pose_landmarks_list(), _make_pose_landmarks_list()]
        )

        assert len(landmarks_per_frame) == 2
        for arr in landmarks_per_frame:
            assert arr.shape == (33, 5)

    def test_no_pose_frame_still_zero_filled_after_downsample(self):
        """NO_POSE handling is unchanged when downsampling is active."""
        cap = _make_mock_cap(num_frames=2, fps=30.0, width=1920.0, height=1080.0)
        landmarks_per_frame, _, _, _ = _run_extract(
            cap,
            [
                _make_pose_landmarks_list(visibility=0.8, presence=0.8),
                [],  # no pose detected on frame 2
            ],
        )

        import numpy as np

        assert not np.all(landmarks_per_frame[0] == 0.0)
        assert np.all(landmarks_per_frame[1] == 0.0)
        # Both frames were still handed to MediaPipe after resize
        assert len(_mp_image_call_shapes) == 2
        assert _mp_image_call_shapes[0] == (720, 1280, 3)
        assert _mp_image_call_shapes[1] == (720, 1280, 3)
