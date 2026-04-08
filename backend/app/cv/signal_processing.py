"""
Signal processing utilities for the Phase 0 CV pipeline (FR-CVPL-14).

All functions are pure — no side effects, no DB, no IO.
Landmark arrays are (33, 5) per frame: [x, y, z, visibility, presence].
Phase 0 is sagittal (side) view only — angles use x, y coordinates only.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import savgol_filter

# ---------------------------------------------------------------------------
# Column indices within a (33, 5) landmark array
# ---------------------------------------------------------------------------

_COL_X = 0
_COL_Y = 1

# ---------------------------------------------------------------------------
# Landmark index definitions
# MediaPipe BlazePose (33 landmarks):
#   LEFT side (primary for Phase 0 sagittal view):
#     11 = left_shoulder,  12 = right_shoulder  (confusingly, "left" in
#          MediaPipe means the subject's left, which appears on the RIGHT side
#          of the image in a mirrored camera.  For the LEFT body side in a
#          true sagittal view the convention varies.  The task spec uses
#          "LEFT side landmarks (even indices: 12,14,16,24,26,28)" so we
#          follow that exactly.)
#
#   RIGHT side (odd indices): 11,13,15,23,25,27
#   LEFT  side (even in task spec): 12,14,16,24,26,28
# ---------------------------------------------------------------------------

# Squat / Deadlift — left side (as per task spec: even indices)
_SQUAT_SHOULDER_L = 12
_SQUAT_HIP_L = 24
_SQUAT_KNEE_L = 26
_SQUAT_ANKLE_L = 28

# Bench — left side (as per task spec: even indices)
_BENCH_SHOULDER_L = 12
_BENCH_ELBOW_L = 14
_BENCH_WRIST_L = 16
_BENCH_HIP_L = 24  # for shoulder_angle: shoulder–hip vector


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

    return savgol_filter(values, window_length=window, polyorder=polyorder)


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
) -> dict[str, float]:
    """
    Compute relevant joint angles for a single frame.

    Parameters
    ----------
    landmarks:
        Shape (33, 5) array for one frame.
    exercise_type:
        One of ``"squat"``, ``"deadlift"``, ``"bench"`` (case-insensitive).

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

    def xy(idx: int) -> np.ndarray:
        """Extract (x, y) for landmark *idx*."""
        return landmarks[idx, :2]

    if ex in ("squat", "deadlift"):
        hip_angle = calculate_angle(
            xy(_SQUAT_SHOULDER_L),
            xy(_SQUAT_HIP_L),
            xy(_SQUAT_KNEE_L),
        )
        knee_angle = calculate_angle(
            xy(_SQUAT_HIP_L),
            xy(_SQUAT_KNEE_L),
            xy(_SQUAT_ANKLE_L),
        )
        return {
            "hip_angle": hip_angle,
            "knee_angle": knee_angle,
        }

    if ex == "bench":
        elbow_angle = calculate_angle(
            xy(_BENCH_SHOULDER_L),
            xy(_BENCH_ELBOW_L),
            xy(_BENCH_WRIST_L),
        )
        shoulder_angle = calculate_angle(
            xy(_BENCH_ELBOW_L),
            xy(_BENCH_SHOULDER_L),
            xy(_BENCH_HIP_L),
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

    Returns
    -------
    dict[str, np.ndarray]
        Mapping of joint name → 1-D array of smoothed angles (degrees),
        one value per input frame.
    """
    # Accumulate raw angle series keyed by joint name
    raw: dict[str, list[float]] = {}

    for frame in landmarks_per_frame:
        angles = calculate_joint_angles(frame, exercise_type)
        for joint, angle in angles.items():
            raw.setdefault(joint, []).append(angle)

    # Smooth each series and convert to ndarray
    return {
        joint: smooth_signal(np.array(series, dtype=float))
        for joint, series in raw.items()
    }
