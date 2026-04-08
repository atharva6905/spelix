"""
Quality gates for Phase 0 CV pipeline (FR-CVPL-03 through FR-CVPL-11).

All functions are pure — no side effects, no DB, no IO.
Landmark arrays: shape (33, 5) per frame — [x, y, z, visibility, presence].

MediaPipe gotcha: visibility/presence values may be pre-sigmoid logits
(outside [0, 1]).  Always apply sigmoid() before thresholding.
See GitHub #4411, #4462.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Body-visibility gate — landmark indices (shoulders, elbows, hips, knees)
_VISIBILITY_LANDMARK_INDICES: list[int] = [11, 12, 13, 14, 23, 24, 25, 26]

_BODY_VISIBILITY_THRESHOLD: float = 0.30

# Framing gate — fraction of total frame area
_FRAMING_MIN_FRACTION: float = 0.30
_FRAMING_MAX_FRACTION: float = 0.80

# Visibility threshold (post-sigmoid) for a landmark to count as "visible"
# when computing the bounding box for the framing gate.
_LANDMARK_VISIBLE_THRESHOLD: float = 0.50

# Column indices within a (33, 5) landmark array
_COL_X = 0
_COL_Y = 1
_COL_VISIBILITY = 3


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class GateCheckResult:
    """Result of a single quality-gate check."""

    passed: bool
    name: str
    level: str  # "error" | "warning"
    metric_value: float
    threshold: float
    user_message: str


@dataclass
class QualityGateResult:
    """Aggregated result of all quality-gate checks for one analysis."""

    passed: bool
    status: str  # "passed" | "rejected"
    checks: list[GateCheckResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def sigmoid(x: float) -> float:
    """Numerically stable logistic sigmoid: 1 / (1 + exp(-x))."""
    return 1.0 / (1.0 + math.exp(-float(x)))


# ---------------------------------------------------------------------------
# Gate 1: Body Visibility
# ---------------------------------------------------------------------------

_BODY_VISIBILITY_REJECT_MSG: str = (
    "Your body is not clearly visible. Please ensure good lighting and that "
    "your full body (shoulders to feet) is in the camera frame."
)
_BODY_VISIBILITY_PASS_MSG: str = "Body visibility is sufficient."


def check_body_visibility(landmarks_per_frame: list[np.ndarray]) -> GateCheckResult:
    """
    Gate P0-01: body visibility.

    Reject if mean sigmoid-visibility of key landmarks across the first 5
    frames is below 0.30.

    Parameters
    ----------
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame.  Only the first 5 are used.

    Returns
    -------
    GateCheckResult
    """
    frames = landmarks_per_frame[:5]

    # Collect visibility values for target landmarks across all used frames
    vis_values: list[float] = []
    for frame in frames:
        for idx in _VISIBILITY_LANDMARK_INDICES:
            raw_vis = float(frame[idx, _COL_VISIBILITY])
            vis_values.append(sigmoid(raw_vis))

    mean_vis = float(np.mean(vis_values)) if vis_values else 0.0
    passed = mean_vis >= _BODY_VISIBILITY_THRESHOLD

    return GateCheckResult(
        passed=passed,
        name="body_visibility",
        level="error",
        metric_value=mean_vis,
        threshold=_BODY_VISIBILITY_THRESHOLD,
        user_message=_BODY_VISIBILITY_PASS_MSG if passed else _BODY_VISIBILITY_REJECT_MSG,
    )


# ---------------------------------------------------------------------------
# Gate 2: Framing
# ---------------------------------------------------------------------------

_FRAMING_TOO_SMALL_MSG: str = (
    "You appear too far from the camera. Please move closer so your body "
    "fills at least 30% of the frame."
)
_FRAMING_TOO_LARGE_MSG: str = (
    "You are too close to the camera. Please step back so your full body "
    "is visible."
)
_FRAMING_PASS_MSG: str = "Framing is good."


def check_framing(
    landmarks_per_frame: list[np.ndarray],
    frame_width: int,
    frame_height: int,
) -> GateCheckResult:
    """
    Gate P0-02: subject framing.

    Reject if the mean bounding-box area (over the first 5 frames) is
    outside [30%, 80%] of the total frame area.

    The bounding box is derived from landmarks whose sigmoid-visibility
    exceeds 0.50.  Coordinates are normalised [0, 1]; multiply by
    frame_width / frame_height to get pixel space — but since we work
    entirely in normalised coordinates, the absolute pixel dimensions
    only matter for computing the *ratio*, and they cancel out when both
    the box and the frame are expressed in the same normalised space.

    Parameters
    ----------
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame.  Only the first 5 are used.
    frame_width, frame_height:
        Pixel dimensions of the source video frame (unused in ratio
        computation but accepted for API consistency and future use).

    Returns
    -------
    GateCheckResult
    """
    frames = landmarks_per_frame[:5]

    fractions: list[float] = []
    for frame in frames:
        # Identify landmarks visible enough to contribute to the bounding box
        vis_col = frame[:, _COL_VISIBILITY]
        sig_vis = np.array([sigmoid(v) for v in vis_col], dtype=np.float64)
        visible_mask = sig_vis > _LANDMARK_VISIBLE_THRESHOLD

        if not np.any(visible_mask):
            # No visible landmarks — treat bounding box as zero area
            fractions.append(0.0)
            continue

        xs = frame[visible_mask, _COL_X]
        ys = frame[visible_mask, _COL_Y]

        bbox_width = float(np.max(xs) - np.min(xs))
        bbox_height = float(np.max(ys) - np.min(ys))

        # Normalised coordinates → fraction of frame area is simply
        # bbox_width * bbox_height (both already in [0, 1]).
        fraction = bbox_width * bbox_height
        fractions.append(fraction)

    mean_fraction = float(np.mean(fractions)) if fractions else 0.0

    if mean_fraction < _FRAMING_MIN_FRACTION:
        passed = False
        user_message = _FRAMING_TOO_SMALL_MSG
    elif mean_fraction > _FRAMING_MAX_FRACTION:
        passed = False
        user_message = _FRAMING_TOO_LARGE_MSG
    else:
        passed = True
        user_message = _FRAMING_PASS_MSG

    # threshold reported as the violated bound (or the min bound when passing)
    threshold = (
        _FRAMING_MIN_FRACTION if mean_fraction <= _FRAMING_MIN_FRACTION
        else _FRAMING_MAX_FRACTION
    )

    return GateCheckResult(
        passed=passed,
        name="framing",
        level="error",
        metric_value=mean_fraction,
        threshold=threshold,
        user_message=user_message,
    )


# ---------------------------------------------------------------------------
# Combined runner
# ---------------------------------------------------------------------------


def run_quality_gates(
    landmarks_per_frame: list[np.ndarray],
    frame_width: int,
    frame_height: int,
) -> QualityGateResult:
    """
    Run all Phase 0 quality gates and return an aggregated result.

    Parameters
    ----------
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame.
    frame_width, frame_height:
        Pixel dimensions of the source video frame.

    Returns
    -------
    QualityGateResult
        passed=True only if every gate with level="error" passed.
        status is "passed" or "rejected".
    """
    visibility_check = check_body_visibility(landmarks_per_frame)
    framing_check = check_framing(landmarks_per_frame, frame_width, frame_height)

    checks = [visibility_check, framing_check]

    # Overall pass only if no error-level gate failed
    overall_passed = all(c.passed for c in checks if c.level == "error")
    status = "passed" if overall_passed else "rejected"

    return QualityGateResult(
        passed=overall_passed,
        status=status,
        checks=checks,
    )
