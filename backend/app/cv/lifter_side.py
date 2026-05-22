"""Lifter-side detection for sagittal-view CV pipeline (Session 2).

Provides a single source of truth for "which side of the lifter is facing
the camera" and the corresponding MediaPipe BlazePose landmark indices.

Replaces hardcoded even-index constants in metric_extraction.py and
signal_processing.py. See ADR-LIFTER-SIDE-DETECTION.

MediaPipe BlazePose 33-landmark naming (subject perspective):
  Left  (subject's left):  11, 13, 15, 23, 25, 27, 29, 31
  Right (subject's right): 12, 14, 16, 24, 26, 28, 30, 32

All functions are pure — no IO, no DB, no side effects.
"""
from __future__ import annotations

import logging
from typing import Literal, NamedTuple

import numpy as np

logger = logging.getLogger(__name__)

# MediaPipe BlazePose 33-landmark indices.
_LEFT_LANDMARKS: tuple[int, ...] = (11, 13, 15, 23, 25, 27, 29, 31)
_RIGHT_LANDMARKS: tuple[int, ...] = (12, 14, 16, 24, 26, 28, 30, 32)

# Anchor-based robustness (R1 mitigation, ADR-QGATE-COMMERCIAL-GYM analogue).
_ANCHOR_FROM_FIRST_N_SAMPLES = 3
_OFF_ANCHOR_DISTANCE_FRAC = 0.25

# Ambiguous-detection threshold (relative difference between side visibilities).
_AMBIGUOUS_RELATIVE_DIFF = 0.05

# Default window for visibility comparison.
_DEFAULT_WINDOW_SECONDS = 3.0


class SideIndices(NamedTuple):
    """MediaPipe landmark indices for one side of the body."""

    shoulder: int
    elbow: int
    wrist: int
    hip: int
    knee: int
    ankle: int
    heel: int
    foot_index: int


_RIGHT_SIDE = SideIndices(
    shoulder=12, elbow=14, wrist=16, hip=24,
    knee=26, ankle=28, heel=30, foot_index=32,
)
_LEFT_SIDE = SideIndices(
    shoulder=11, elbow=13, wrist=15, hip=23,
    knee=25, ankle=27, heel=29, foot_index=31,
)


def landmark_indices_for_side(side: Literal["left", "right"]) -> SideIndices:
    """Return MediaPipe landmark indices for the lifter's filmed side.

    Parameters
    ----------
    side:
        Either ``"left"`` or ``"right"`` (subject-perspective).

    Returns
    -------
    SideIndices
        NamedTuple with fields shoulder/elbow/wrist/hip/knee/ankle/heel/foot_index.

    Raises
    ------
    ValueError
        If ``side`` is not one of ``"left"`` or ``"right"``.
    """
    if side == "right":
        return _RIGHT_SIDE
    if side == "left":
        return _LEFT_SIDE
    raise ValueError(
        f"side must be 'left' or 'right'; got {side!r}"
    )


def _compute_anchor_centroid(
    landmarks_session: np.ndarray,
) -> tuple[float, float] | None:
    """Compute lifter-centroid (x, y) from the first N high-visibility hip
    samples.

    Mirrors the ``check_single_person`` anchor pattern in
    ``backend/app/cv/quality_gates.py``: take the first
    ``_ANCHOR_FROM_FIRST_N_SAMPLES`` frames where BOTH hips have
    visibility >= 0.5, and use the median hip-midpoint (x, y) as the anchor.

    Returns ``None`` if no qualifying frames are found.
    """
    if landmarks_session.shape[0] == 0:
        return None
    midpoints: list[tuple[float, float]] = []
    for frame in landmarks_session:
        hip_l = frame[23]
        hip_r = frame[24]
        if hip_l[3] >= 0.5 and hip_r[3] >= 0.5:
            mid_x = float((hip_l[0] + hip_r[0]) / 2.0)
            mid_y = float((hip_l[1] + hip_r[1]) / 2.0)
            midpoints.append((mid_x, mid_y))
            if len(midpoints) >= _ANCHOR_FROM_FIRST_N_SAMPLES:
                break
    if not midpoints:
        return None
    xs = np.array([m[0] for m in midpoints])
    ys = np.array([m[1] for m in midpoints])
    return float(np.median(xs)), float(np.median(ys))


def _mean_visibility_for_indices(
    frames: np.ndarray,
    indices: tuple[int, ...],
    anchor: tuple[float, float] | None,
) -> float:
    """Mean visibility of ``indices`` across ``frames``, restricted to
    landmarks near the lifter anchor when an anchor is available.

    Restriction (R1 mitigation): a landmark is included only if its x is
    within ``_OFF_ANCHOR_DISTANCE_FRAC`` of the anchor x in normalised
    [0, 1] space. This prevents bystander landmarks (which MediaPipe may
    re-acquire) from flipping the visibility tally.
    """
    if frames.shape[0] == 0:
        return 0.0
    selection = frames[:, list(indices), :]  # (n_frames, len(indices), 5)
    visibilities = selection[..., 3]
    if anchor is not None:
        anchor_x = anchor[0]
        xs = selection[..., 0]
        mask = np.abs(xs - anchor_x) <= _OFF_ANCHOR_DISTANCE_FRAC
        if not bool(np.any(mask)):
            return float(np.mean(visibilities))
        return float(np.mean(visibilities[mask]))
    return float(np.mean(visibilities))


def detect_lifter_side(
    landmarks_session: np.ndarray,
    fps: float | None = None,
) -> Literal["left", "right"]:
    """Detect which side of the lifter is facing the camera.

    Algorithm:
      1. Compute the lifter anchor centroid from the first 3 high-visibility
         hip-midpoint samples (R1 mitigation against bystander interference).
      2. Restrict comparison to the first ``fps * _DEFAULT_WINDOW_SECONDS``
         frames when ``fps`` is given; else use the full session.
      3. For each side, compute the mean visibility, excluding landmarks
         whose x is more than ``_OFF_ANCHOR_DISTANCE_FRAC`` from the anchor x.
      4. Whichever side has the higher mean wins. On exact tie, return
         ``"right"`` (matches the pre-refactor hardcoded default).
      5. When relative difference is below ``_AMBIGUOUS_RELATIVE_DIFF``,
         log WARNING and default to ``"right"``.

    Parameters
    ----------
    landmarks_session:
        ``(n_frames, 33, 5)`` ndarray. Column 3 is visibility, column 4
        is presence; both may be pre-sigmoid logits per MediaPipe.
    fps:
        Optional frames-per-second. When given, restricts the analysis
        window to the first ``fps * _DEFAULT_WINDOW_SECONDS`` frames.

    Returns
    -------
    Literal["left", "right"]
        Detected subject-side. Always returns a concrete string; never None.
    """
    if landmarks_session.ndim != 3 or landmarks_session.shape[0] == 0:
        return "right"

    if fps is not None and fps > 0:
        max_frames = int(fps * _DEFAULT_WINDOW_SECONDS)
        frames = landmarks_session[:max_frames]
    else:
        frames = landmarks_session

    if frames.shape[0] == 0:
        return "right"

    anchor = _compute_anchor_centroid(landmarks_session)
    left_vis = _mean_visibility_for_indices(frames, _LEFT_LANDMARKS, anchor)
    right_vis = _mean_visibility_for_indices(frames, _RIGHT_LANDMARKS, anchor)

    higher = max(left_vis, right_vis)
    if higher <= 0.0:
        return "right"

    rel_diff = abs(left_vis - right_vis) / higher
    if rel_diff < _AMBIGUOUS_RELATIVE_DIFF:
        logger.warning(
            "Ambiguous lifter-side detection: left_vis=%.3f right_vis=%.3f "
            "(relative diff %.3f < %.3f); defaulting to 'right'",
            left_vis, right_vis, rel_diff, _AMBIGUOUS_RELATIVE_DIFF,
        )
        return "right"

    return "left" if left_vis > right_vis else "right"


__all__ = [
    "SideIndices",
    "detect_lifter_side",
    "landmark_indices_for_side",
]
