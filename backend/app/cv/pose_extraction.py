"""
MediaPipe BlazePose landmark extraction (FR-CVPL-01, FR-CVPL-02, FR-CVPL-12, FR-CVPL-13).

This module is pure — no side effects, no DB, no IO beyond reading the video file.
Designed to be called via ``loop.run_in_executor(None, extract_landmarks, path)``
from the ARQ worker so the async event loop is never blocked.

MediaPipe gotcha: visibility/presence may be pre-sigmoid logits (outside [0, 1]).
Always guard with sigmoid before storing.  See GitHub #4411, #4462.
"""

from __future__ import annotations


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
    * MediaPipe config is fixed per CLAUDE.md gotchas — do NOT change.
    * Visibility/presence values outside ``[0, 1]`` are treated as pre-sigmoid
      logits and clamped via ``sigmoid()`` before storage.
    * This function is synchronous (blocking).  Call it from an executor thread.
    """
    cap = cv2.VideoCapture(video_path)

    fps: float = cap.get(cv2.CAP_PROP_FPS)
    width: int = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height: int = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    landmarks_per_frame: list[np.ndarray] = []

    import mediapipe as mp

    with mp.solutions.pose.Pose(  # type: ignore[attr-defined]
        model_complexity=2,
        static_image_mode=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        num_threads=1,
    ) as pose:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_frame)

            if results.pose_landmarks is None:
                landmarks_per_frame.append(
                    np.zeros((_NUM_LANDMARKS, _NUM_COLS), dtype=np.float64)
                )
                continue

            arr = np.zeros((_NUM_LANDMARKS, _NUM_COLS), dtype=np.float64)
            for i, lm in enumerate(results.pose_landmarks.landmark):
                arr[i, 0] = lm.x
                arr[i, 1] = lm.y
                arr[i, 2] = lm.z
                arr[i, _COL_VISIBILITY] = _guard_sigmoid(lm.visibility)
                arr[i, _COL_PRESENCE] = _guard_sigmoid(lm.presence)

            landmarks_per_frame.append(arr)

    cap.release()
    return landmarks_per_frame, fps, width, height


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
