"""
Keyframe extraction for the CV pipeline (FR-AICP-01).

Extracts rep boundary frames (start, depth/bottom, end) from a video file
without loading all frames into memory — critical on the 2GB droplet.

Depth frame = argmin of primary_angle_series within the rep's frame range.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import cv2
import numpy as np

from app.cv.rep_detection import DetectedRep


@dataclass
class RepKeyframes:
    rep_index: int
    start_frame_idx: int
    depth_frame_idx: int  # argmin of primary angle within rep
    end_frame_idx: int
    start_image_b64: str  # JPEG base64
    depth_image_b64: str
    end_image_b64: str


def extract_keyframes(
    video_path: str,
    reps: list[DetectedRep],
    primary_angle_series: np.ndarray,
) -> list[RepKeyframes]:
    """Extract keyframe images at rep boundaries and depth position.

    Uses ``cv2.VideoCapture.set(CAP_PROP_POS_FRAMES, idx)`` to seek to
    specific frames — does NOT load all frames into memory.

    Parameters
    ----------
    video_path:
        Path to the source video file (local path).
    reps:
        Detected reps from the rep detection state machine.
    primary_angle_series:
        1-D array of the primary joint angle per frame (degrees).

    Returns
    -------
    list[RepKeyframes]
        One entry per rep, in rep order.
    """
    if not reps:
        return []

    cap = cv2.VideoCapture(video_path)
    try:
        keyframes: list[RepKeyframes] = []

        for rep in reps:
            start = rep.start_frame
            end = rep.end_frame

            # Clamp indices to valid range for the angle series
            series_len = len(primary_angle_series)
            clamped_start = max(0, min(start, series_len - 1))
            clamped_end = max(0, min(end, series_len - 1))

            # Depth = argmin of primary angle within [start, end] inclusive
            if clamped_start == clamped_end:
                depth = clamped_start
            else:
                slice_ = primary_angle_series[clamped_start : clamped_end + 1]
                depth = clamped_start + int(np.argmin(slice_))

            start_frame = _read_frame(cap, start)
            depth_frame = _read_frame(cap, depth)
            end_frame = _read_frame(cap, end)

            keyframes.append(
                RepKeyframes(
                    rep_index=rep.rep_index,
                    start_frame_idx=start,
                    depth_frame_idx=depth,
                    end_frame_idx=end,
                    start_image_b64=_encode_frame_b64(start_frame),
                    depth_image_b64=_encode_frame_b64(depth_frame),
                    end_image_b64=_encode_frame_b64(end_frame),
                )
            )

        return keyframes
    finally:
        cap.release()


def _read_frame(cap: cv2.VideoCapture, frame_idx: int) -> np.ndarray:
    """Seek to frame_idx and return the decoded BGR frame.

    If seek or decode fails, returns a 1x1 black frame so the pipeline
    does not crash — the JPEG will still be valid.
    """
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    if not ok or frame is None:
        return np.zeros((1, 1, 3), dtype=np.uint8)
    return frame


def _encode_frame_b64(frame: np.ndarray, quality: int = 85) -> str:
    """Encode a BGR frame as a JPEG base64 string."""
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        # Fallback: encode a 1x1 black pixel
        ok, buf = cv2.imencode(
            ".jpg",
            np.zeros((1, 1, 3), dtype=np.uint8),
            [cv2.IMWRITE_JPEG_QUALITY, quality],
        )
    return base64.b64encode(buf.tobytes()).decode("ascii")
