"""
MediaPipe BlazePose landmark extraction (FR-CVPL-01, FR-CVPL-02, FR-CVPL-12, FR-CVPL-13).

This module is pure — no side effects, no DB, no IO beyond reading the video
file and the model file. Designed to be called via
``loop.run_in_executor(None, extract_landmarks, path)`` from the ARQ worker
so the async event loop is never blocked.

Uses the **MediaPipe Tasks API** (``mediapipe.tasks.python.vision.PoseLandmarker``),
NOT the legacy ``mediapipe.solutions.pose.Pose`` API. The Linux x86_64 wheel
for ``mediapipe`` 0.10.x has never shipped the legacy ``solutions`` submodule
(verified across 0.10.9–0.10.33), even though Mac and Windows wheels still
include it. Production crashed with ``AttributeError: module 'mediapipe' has
no attribute 'solutions'`` on the very first real pose extraction call. The
Tasks API is the recommended replacement and is available on every platform.

MediaPipe gotcha: visibility/presence may be pre-sigmoid logits (outside
``[0, 1]``). Always guard with sigmoid before storing. See GitHub #4411, #4462.
"""

from __future__ import annotations

import os

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NUM_LANDMARKS = 33
_NUM_COLS = 5  # [x, y, z, visibility, presence]

# Column indices
_COL_VISIBILITY = 3
_COL_PRESENCE = 4

# Path to the BlazePose Heavy model file. Baked into the Docker image at
# build time via ``RUN curl ... -o /app/models/pose_landmarker_heavy.task``
# in the Dockerfile. Override with the ``POSE_LANDMARKER_MODEL_PATH`` env
# var for local-dev or alternative deployment layouts.
_DEFAULT_MODEL_PATH = "/app/models/pose_landmarker_heavy.task"


def _resolve_model_path() -> str:
    """Locate the pose landmarker .task model file.

    Resolution order:
    1. ``POSE_LANDMARKER_MODEL_PATH`` env var (explicit override)
    2. ``/app/models/pose_landmarker_heavy.task`` (Docker default)
    3. ``<repo>/models/pose_landmarker_heavy.task`` via three-parent walk
       from this file (local-dev convenience)

    Returns the first existing path. Raises ``FileNotFoundError`` listing
    every candidate that was tried so deploy issues are diagnosable from
    worker logs alone (same pattern as ``app/config.py::_resolve_threshold_path``).
    """
    env_path = os.environ.get("POSE_LANDMARKER_MODEL_PATH")
    if env_path:
        return env_path

    from pathlib import Path

    candidates = [
        Path(_DEFAULT_MODEL_PATH),
        # Local dev: <repo>/models/pose_landmarker_heavy.task — three .parent
        # walks from backend/app/cv/pose_extraction.py reach the repo root.
        Path(__file__).parent.parent.parent.parent / "models" / "pose_landmarker_heavy.task",
        Path.cwd() / "models" / "pose_landmarker_heavy.task",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError(
        "pose_landmarker_heavy.task not found. Tried: "
        + ", ".join(str(c) for c in candidates)
        + ". Set POSE_LANDMARKER_MODEL_PATH env var to override, or ensure "
        "the Dockerfile downloads the model into /app/models/."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_landmarks(
    video_path: str,
) -> tuple[list[np.ndarray], float, int, int]:
    """Extract MediaPipe BlazePose landmarks from every frame of a video.

    Parameters
    ----------
    video_path:
        Absolute path to the MP4 (or any OpenCV-readable) video file.

    Returns
    -------
    landmarks_per_frame:
        List of ``(33, 5)`` float64 arrays, one per frame.
        Columns: ``[x, y, z, visibility, presence]``.
        For frames where no pose is detected, a zero-filled array is stored.
    fps:
        Frames per second reported by the container.
    width:
        Frame width in pixels (int).
    height:
        Frame height in pixels (int).

    Notes
    -----
    * Uses the MediaPipe Tasks API ``PoseLandmarker`` with the BlazePose
      Heavy model (``pose_landmarker_heavy.task``). The legacy
      ``mediapipe.solutions.pose.Pose`` API is intentionally NOT used —
      see the module docstring.
    * Configured for ``RunningMode.IMAGE`` (each frame processed
      independently — no inter-frame tracking), matching the legacy
      ``static_image_mode=True`` behaviour.
    * Visibility/presence values outside ``[0, 1]`` are treated as
      pre-sigmoid logits and clamped via ``sigmoid()`` before storage.
    * This function is synchronous (blocking). Call it from an executor
      thread (e.g. ``loop.run_in_executor(None, extract_landmarks, path)``).
    """
    cap = cv2.VideoCapture(video_path)

    fps: float = cap.get(cv2.CAP_PROP_FPS)
    width: int = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height: int = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    landmarks_per_frame: list[np.ndarray] = []

    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import (
        PoseLandmarker,
        PoseLandmarkerOptions,
        RunningMode,
    )

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=_resolve_model_path()),
        running_mode=RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    with PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = landmarker.detect(mp_image)

            # result.pose_landmarks is a list of detected poses; each entry
            # is a list of 33 NormalizedLandmark objects. With num_poses=1
            # the outer list has length 0 (no pose) or 1 (one pose).
            if not result.pose_landmarks:
                landmarks_per_frame.append(
                    np.zeros((_NUM_LANDMARKS, _NUM_COLS), dtype=np.float64)
                )
                continue

            arr = np.zeros((_NUM_LANDMARKS, _NUM_COLS), dtype=np.float64)
            for i, lm in enumerate(result.pose_landmarks[0]):
                arr[i, 0] = lm.x
                arr[i, 1] = lm.y
                arr[i, 2] = lm.z
                arr[i, _COL_VISIBILITY] = _guard_sigmoid(lm.visibility)
                arr[i, _COL_PRESENCE] = _guard_sigmoid(lm.presence)

            landmarks_per_frame.append(arr)

    cap.release()
    return landmarks_per_frame, fps, width, height


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------


def extract_frames(video_path: str) -> list[np.ndarray]:
    """Read all frames from a video file.

    Parameters
    ----------
    video_path:
        Absolute path to the video file (any OpenCV-readable format).

    Returns
    -------
    list[np.ndarray]
        Ordered list of BGR frames as uint8 arrays.
    """
    cap = cv2.VideoCapture(video_path)
    frames: list[np.ndarray] = []
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    return frames


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sigmoid(x: float) -> float:
    """Numerically stable logistic sigmoid: 1 / (1 + exp(-x))."""
    import math

    return 1.0 / (1.0 + math.exp(-float(x)))


def _guard_sigmoid(value: float) -> float:
    """Return ``value`` unchanged if already in [0, 1]; otherwise apply sigmoid.

    MediaPipe may emit pre-logit values for visibility/presence — see
    GitHub issues #4411 and #4462.
    """
    v = float(value)
    if 0.0 <= v <= 1.0:
        return v
    return _sigmoid(v)
