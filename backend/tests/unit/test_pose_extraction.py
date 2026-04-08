"""
Unit tests for pose_extraction.py (B-015).

Requirements: FR-CVPL-01, FR-CVPL-02, FR-CVPL-12, FR-CVPL-13.

All tests use synthetic data — no real video file or MediaPipe installation required.
cv2.VideoCapture and mediapipe are fully mocked via sys.modules.
"""

from __future__ import annotations

import importlib
import math
import sys
from unittest.mock import MagicMock, patch

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    """Reference sigmoid for test assertions."""
    return 1.0 / (1.0 + math.exp(-float(x)))


def _make_landmark(x=0.5, y=0.5, z=0.0, visibility=0.9, presence=0.9):
    """Create a mock MediaPipe landmark object."""
    lm = MagicMock()
    lm.x = x
    lm.y = y
    lm.z = z
    lm.visibility = visibility
    lm.presence = presence
    return lm


def _make_pose_landmarks(
    visibility=0.9,
    presence=0.9,
    x=0.5,
    y=0.5,
    z=0.0,
):
    """Create a mock MediaPipe pose_landmarks with 33 landmarks."""
    landmarks = MagicMock()
    lm_list = [_make_landmark(x, y, z, visibility, presence) for _ in range(33)]
    landmarks.landmark = lm_list
    return landmarks


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


def _make_mock_pose(pose_landmarks):
    """Create a mock mediapipe Pose context manager."""
    pose = MagicMock()
    result = MagicMock()
    result.pose_landmarks = pose_landmarks
    pose.__enter__ = MagicMock(return_value=pose)
    pose.__exit__ = MagicMock(return_value=False)
    pose.process.return_value = result
    return pose


def _run_extract(mock_cap, mock_pose_cls, video_path="/fake/video.mp4"):
    """Import and run extract_landmarks with mocked cv2 and mediapipe."""
    # Create a mock mediapipe module hierarchy
    mock_mp = MagicMock()
    mock_mp.solutions.pose.Pose = mock_pose_cls

    with patch("cv2.VideoCapture", return_value=mock_cap):
        with patch.dict(sys.modules, {"mediapipe": mock_mp}):
            # Force reimport to pick up the patched mediapipe
            if "app.cv.pose_extraction" in sys.modules:
                mod = importlib.reload(sys.modules["app.cv.pose_extraction"])
            else:
                mod = importlib.import_module("app.cv.pose_extraction")
            return mod.extract_landmarks(video_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExtractLandmarksShape:
    """Verify output shape and types."""

    def test_returns_tuple_of_four(self):
        cap = _make_mock_cap(num_frames=2)
        pose = _make_mock_pose(_make_pose_landmarks())
        mock_cls = MagicMock(return_value=pose)

        result = _run_extract(cap, mock_cls)

        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_landmarks_per_frame_is_list(self):
        cap = _make_mock_cap(num_frames=2)
        pose = _make_mock_pose(_make_pose_landmarks())
        mock_cls = MagicMock(return_value=pose)

        landmarks_per_frame, fps, width, height = _run_extract(cap, mock_cls)

        assert isinstance(landmarks_per_frame, list)
        assert len(landmarks_per_frame) == 2

    def test_each_frame_array_shape_33_5(self):
        cap = _make_mock_cap(num_frames=2)
        pose = _make_mock_pose(_make_pose_landmarks())
        mock_cls = MagicMock(return_value=pose)

        landmarks_per_frame, _, _, _ = _run_extract(cap, mock_cls)

        for arr in landmarks_per_frame:
            assert isinstance(arr, np.ndarray)
            assert arr.shape == (33, 5)

    def test_fps_width_height_extracted_correctly(self):
        cap = _make_mock_cap(num_frames=1, fps=30.0, width=1280.0, height=720.0)
        pose = _make_mock_pose(_make_pose_landmarks())
        mock_cls = MagicMock(return_value=pose)

        _, fps, width, height = _run_extract(cap, mock_cls)

        assert fps == 30.0
        assert width == 1280
        assert height == 720

    def test_width_height_are_ints(self):
        cap = _make_mock_cap(num_frames=1)
        pose = _make_mock_pose(_make_pose_landmarks())
        mock_cls = MagicMock(return_value=pose)

        _, fps, width, height = _run_extract(cap, mock_cls)

        assert isinstance(width, int)
        assert isinstance(height, int)


class TestSigmoidGuard:
    """Verify sigmoid is applied to visibility/presence values outside [0, 1]."""

    def test_sigmoid_applied_to_visibility_outside_range(self):
        cap = _make_mock_cap(num_frames=1)
        pose = _make_mock_pose(_make_pose_landmarks(visibility=2.0, presence=0.9))
        mock_cls = MagicMock(return_value=pose)

        landmarks_per_frame, _, _, _ = _run_extract(cap, mock_cls)

        frame_arr = landmarks_per_frame[0]
        expected = _sigmoid(2.0)
        for i in range(33):
            assert abs(frame_arr[i, 3] - expected) < 1e-6

    def test_sigmoid_applied_to_presence_outside_range(self):
        cap = _make_mock_cap(num_frames=1)
        pose = _make_mock_pose(_make_pose_landmarks(visibility=0.9, presence=-3.0))
        mock_cls = MagicMock(return_value=pose)

        landmarks_per_frame, _, _, _ = _run_extract(cap, mock_cls)

        frame_arr = landmarks_per_frame[0]
        expected = _sigmoid(-3.0)
        for i in range(33):
            assert abs(frame_arr[i, 4] - expected) < 1e-6

    def test_sigmoid_not_applied_when_value_in_range(self):
        cap = _make_mock_cap(num_frames=1)
        pose = _make_mock_pose(_make_pose_landmarks(visibility=0.7, presence=0.6))
        mock_cls = MagicMock(return_value=pose)

        landmarks_per_frame, _, _, _ = _run_extract(cap, mock_cls)

        frame_arr = landmarks_per_frame[0]
        for i in range(33):
            assert abs(frame_arr[i, 3] - 0.7) < 1e-6
            assert abs(frame_arr[i, 4] - 0.6) < 1e-6

    def test_boundary_values_zero_and_one_not_sigmoided(self):
        cap = _make_mock_cap(num_frames=1)
        pose = _make_mock_pose(_make_pose_landmarks(visibility=0.0, presence=1.0))
        mock_cls = MagicMock(return_value=pose)

        landmarks_per_frame, _, _, _ = _run_extract(cap, mock_cls)

        frame_arr = landmarks_per_frame[0]
        for i in range(33):
            assert abs(frame_arr[i, 3] - 0.0) < 1e-6
            assert abs(frame_arr[i, 4] - 1.0) < 1e-6


class TestNoLandmarksDetected:
    """Verify zero-filled array when no pose detected."""

    def test_zero_array_returned_for_frames_with_no_landmarks(self):
        cap = _make_mock_cap(num_frames=1)
        pose = _make_mock_pose(None)  # No landmarks
        mock_cls = MagicMock(return_value=pose)

        landmarks_per_frame, _, _, _ = _run_extract(cap, mock_cls)

        assert len(landmarks_per_frame) == 1
        arr = landmarks_per_frame[0]
        assert arr.shape == (33, 5)
        assert np.all(arr == 0.0)

    def test_mixed_frames_detection_and_no_detection(self):
        cap = _make_mock_cap(num_frames=2, fps=25.0, width=640.0, height=480.0)

        # Pose returns landmarks for first call, None for second
        pose = MagicMock()
        result_ok = MagicMock()
        result_ok.pose_landmarks = _make_pose_landmarks(visibility=0.8, presence=0.8)
        result_none = MagicMock()
        result_none.pose_landmarks = None
        pose.__enter__ = MagicMock(return_value=pose)
        pose.__exit__ = MagicMock(return_value=False)
        pose.process.side_effect = [result_ok, result_none]
        mock_cls = MagicMock(return_value=pose)

        landmarks_per_frame, fps, width, height = _run_extract(cap, mock_cls)

        assert len(landmarks_per_frame) == 2
        assert not np.all(landmarks_per_frame[0] == 0.0)
        assert np.all(landmarks_per_frame[1] == 0.0)


class TestMediaPipeConfig:
    """Verify exact MediaPipe configuration is used."""

    def test_pose_initialized_with_exact_config(self):
        cap = _make_mock_cap(num_frames=1)
        pose = _make_mock_pose(_make_pose_landmarks())
        mock_cls = MagicMock(return_value=pose)

        _run_extract(cap, mock_cls)

        mock_cls.assert_called_once_with(
            model_complexity=2,
            static_image_mode=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            num_threads=1,
        )


class TestLandmarkColumnOrdering:
    """Verify landmark array columns are [x, y, z, visibility, presence]."""

    def test_landmark_columns_order(self):
        cap = _make_mock_cap(num_frames=1)
        pose = _make_mock_pose(
            _make_pose_landmarks(x=0.1, y=0.2, z=0.3, visibility=0.4, presence=0.5)
        )
        mock_cls = MagicMock(return_value=pose)

        landmarks_per_frame, _, _, _ = _run_extract(cap, mock_cls)

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
        pose = _make_mock_pose(_make_pose_landmarks())
        mock_cls = MagicMock(return_value=pose)

        _run_extract(cap, mock_cls)

        cap.release.assert_called_once()
