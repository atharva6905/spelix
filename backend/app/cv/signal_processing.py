"""
Signal processing utilities for the Phase 0 CV pipeline (FR-CVPL-14).

All functions are pure — no side effects, no DB, no IO.
Landmark arrays are (33, 5) per frame: [x, y, z, visibility, presence].
Phase 0 is sagittal (side) view only — angles use x, y coordinates only.

Landmark indices are resolved per-analysis via
``landmark_indices_for_side(lifter_side)`` (Session 2,
ADR-LIFTER-SIDE-DETECTION). The default ``"right"`` matches the
pre-refactor hardcoded subject-right indices, so existing test
assertions remain green without modification.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy.signal import savgol_filter

from app.cv.lifter_side import landmark_indices_for_side

# ---------------------------------------------------------------------------
# Column indices within a (33, 5) landmark array
# ---------------------------------------------------------------------------

_COL_X = 0
_COL_Y = 1


# ---------------------------------------------------------------------------
# smooth_signal
# ---------------------------------------------------------------------------


def smooth_signal(
    values: np.ndarray,
    window: int = 7,
    polyorder: int = 3,
) -> np.ndarray:
    """
    Apply a Savitzky-Golay filter to a 1-D signal.

    Parameters
    ----------
    values:
        Input signal as a 1-D numpy array.
    window:
        Length of the filter window (must be a positive odd integer).
        Default: 7.
    polyorder:
        Order of the polynomial used to fit the samples.
        Must be less than *window*.  Default: 3.

    Returns
    -------
    np.ndarray
        Smoothed signal of the same shape as *values*.
        If ``len(values) < window``, *values* is returned unmodified.
    """
    if len(values) < window:
        return values

    return savgol_filter(values, window_length=window, polyorder=polyorder)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# calculate_angle
# ---------------------------------------------------------------------------


def calculate_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """
    Calculate the angle at point *b* formed by vectors ba and bc.

    Only the x and y components are used (Phase 0 sagittal view).

    Parameters
    ----------
    a, b, c:
        2-D or 3-D points.  Only the first two components (x, y) are used.

    Returns
    -------
    float
        Angle in degrees in the range [0, 180].
    """
    # Extract only x, y
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])

    # Vectors from b to a, and from b to c
    ba_x = ax - bx
    ba_y = ay - by
    bc_x = cx - bx
    bc_y = cy - by

    # Use arctan2 for robust angle computation
    angle_ba = np.arctan2(ba_y, ba_x)
    angle_bc = np.arctan2(bc_y, bc_x)

    angle_rad = abs(angle_ba - angle_bc)

    # Fold to [0, π]
    if angle_rad > np.pi:
        angle_rad = 2.0 * np.pi - angle_rad

    return float(np.degrees(angle_rad))


# ---------------------------------------------------------------------------
# calculate_joint_angles
# ---------------------------------------------------------------------------


def calculate_joint_angles(
    landmarks: np.ndarray,
    exercise_type: str,
    lifter_side: Literal["left", "right"] = "right",
) -> dict[str, float]:
    """
    Compute relevant joint angles for a single frame.

    Parameters
    ----------
    landmarks:
        Shape (33, 5) array for one frame.
    exercise_type:
        One of ``"squat"``, ``"deadlift"``, ``"bench"`` (case-insensitive).
    lifter_side:
        ``"left"`` or ``"right"`` (subject-perspective). Defaults to
        ``"right"`` to preserve pre-refactor behaviour.

    Returns
    -------
    dict[str, float]
        Mapping of joint name to angle in degrees.

    Raises
    ------
    ValueError
        If *exercise_type* is not recognised.
    """
    ex = exercise_type.lower()
    side_idx = landmark_indices_for_side(lifter_side)

    def xy(idx: int) -> np.ndarray:
        """Extract (x, y) for landmark *idx*."""
        return landmarks[idx, :2]

    if ex in ("squat", "deadlift"):
        hip_angle = calculate_angle(
            xy(side_idx.shoulder),
            xy(side_idx.hip),
            xy(side_idx.knee),
        )
        knee_angle = calculate_angle(
            xy(side_idx.hip),
            xy(side_idx.knee),
            xy(side_idx.ankle),
        )
        return {
            "hip_angle": hip_angle,
            "knee_angle": knee_angle,
        }

    if ex == "bench":
        elbow_angle = calculate_angle(
            xy(side_idx.shoulder),
            xy(side_idx.elbow),
            xy(side_idx.wrist),
        )
        shoulder_angle = calculate_angle(
            xy(side_idx.elbow),
            xy(side_idx.shoulder),
            xy(side_idx.hip),
        )
        return {
            "elbow_angle": elbow_angle,
            "shoulder_angle": shoulder_angle,
        }

    raise ValueError(
        f"Unknown exercise type: {exercise_type!r}. "
        "Expected one of: 'squat', 'deadlift', 'bench'."
    )


# ---------------------------------------------------------------------------
# compute_angle_timeseries
# ---------------------------------------------------------------------------


def compute_angle_timeseries(
    landmarks_per_frame: list[np.ndarray],
    exercise_type: str,
    lifter_side: Literal["left", "right"] = "right",
) -> dict[str, np.ndarray]:
    """
    Compute smoothed joint-angle time-series for an entire clip.

    For each frame the relevant joint angles are computed, then each
    per-joint series is smoothed with :func:`smooth_signal`.

    Parameters
    ----------
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame.
    exercise_type:
        One of ``"squat"``, ``"deadlift"``, ``"bench"`` (case-insensitive).
    lifter_side:
        ``"left"`` or ``"right"`` (subject-perspective). Defaults to
        ``"right"`` to preserve pre-refactor behaviour.

    Returns
    -------
    dict[str, np.ndarray]
        Mapping of joint name → 1-D array of smoothed angles (degrees),
        one value per input frame.
    """
    # Accumulate raw angle series keyed by joint name
    raw: dict[str, list[float]] = {}

    for frame in landmarks_per_frame:
        angles = calculate_joint_angles(frame, exercise_type, lifter_side)
        for joint, angle in angles.items():
            raw.setdefault(joint, []).append(angle)

    # Smooth each series and convert to ndarray
    return {
        joint: smooth_signal(np.array(series, dtype=float))
        for joint, series in raw.items()
    }
