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

# Visibility floor below which a landmark is treated as untracked. Mirrors
# ``metric_extraction._S5_MIN_VIS`` (kept in sync — same physical threshold)
# so the angle-series validity gate (R2, L2-CV-DEPTHFRAME-R2) and the
# depth-frame validity mask (R1, L2-CV-DEPTHFRAME-DROPOUT) agree on what
# counts as a dropout frame. Raw MediaPipe visibility (column 3), not sigmoid.
_MIN_VIS = 0.30

# Landmark dependencies per joint angle, used to gate dropout / low-visibility
# frames out of the angle series before smoothing (R2). A joint's angle for a
# given frame is trusted only when ALL of its defining landmarks clear
# ``_MIN_VIS`` — the same "minimum landmark" principle as Tier-2 confidence
# (FR-CVPL-21) and ``metric_extraction._vis_ok``. Keys mirror the joint names
# returned by :func:`calculate_joint_angles`; values are ``SideIndices`` attrs.
#
# BENCH IS DELIBERATELY EXCLUDED (no key). On supine bench the wrists are
# *systematically* near-invisible (~0.008 median visibility, <_MIN_VIS on ~100%
# of frames), so gating ``elbow_angle`` on the wrist would NaN the whole series
# and collapse rep detection (it cut detected reps 13→3 and pushed
# ``bar_touch_height_pct`` to the spurious 76.4 the investigation flagged). This
# mirrors R1 (ADR-DEPTHFRAME-DROPOUT-GATE) excluding bench from its depth-frame
# mask: bench bar-path/wrist robustness is R3/R3b (barbell detection), not R2.
# An exercise absent from this map is simply not gated (its series is computed,
# interpolated-where-already-finite = no-op, smoothed, and clamped as before).
_JOINT_LANDMARK_DEPS: dict[str, dict[str, tuple[str, str, str]]] = {
    "squat": {
        "hip_angle": ("shoulder", "hip", "knee"),
        "knee_angle": ("hip", "knee", "ankle"),
    },
    "deadlift": {
        "hip_angle": ("shoulder", "hip", "knee"),
        "knee_angle": ("hip", "knee", "ankle"),
    },
}


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
# Validity gating helpers (R2, L2-CV-DEPTHFRAME-R2)
# ---------------------------------------------------------------------------


def _landmarks_visible(frame: np.ndarray, indices: tuple[int, ...]) -> bool:
    """Return True iff every named landmark clears ``_MIN_VIS`` (column 3)."""
    return all(float(frame[i, 3]) >= _MIN_VIS for i in indices)


def _interpolate_invalid(series: np.ndarray) -> np.ndarray:
    """
    Linear-interpolate NaN entries, holding endpoints for leading/trailing NaNs.

    Invalid (dropout / low-visibility) frames are marked NaN upstream. This
    fills each interior NaN run by drawing a straight line between the nearest
    valid frames on either side (``np.interp``), and holds the first/last valid
    value across leading/trailing NaN runs. Linear interpolation is
    deliberately conservative: between two valid endpoints it can only
    *under*-read a peak/valley, never fabricate a deeper-than-observed
    extremum — so it removes the spurious 0° dropout spikes without inventing
    motion that wasn't seen (ADR-ANGLE-SERIES-VALIDITY-GATE).

    If the series has no valid frame at all (fully-occluded clip — rejected
    upstream by the quality gate), it is returned unchanged (all NaN).
    """
    s = np.asarray(series, dtype=float)
    valid = ~np.isnan(s)
    if not valid.any() or valid.all():
        return s
    idx = np.arange(len(s))
    out = s.copy()
    out[~valid] = np.interp(idx[~valid], idx[valid], s[valid])
    return out


# ---------------------------------------------------------------------------
# compute_angle_timeseries
# ---------------------------------------------------------------------------


def compute_angle_timeseries(
    landmarks_per_frame: list[np.ndarray],
    exercise_type: str,
    lifter_side: Literal["left", "right"] = "right",
) -> dict[str, np.ndarray]:
    """
    Compute smoothed, validity-gated joint-angle time-series for a clip.

    For each frame the relevant joint angles are computed. Frames whose
    defining landmarks fall below ``_MIN_VIS`` (MediaPipe VIDEO-mode dropout
    or confident mis-tracking) are treated as **missing** rather than letting
    their garbage angle — a zero-filled frame yields a spurious 0° — enter the
    series. Each per-joint series is then linear-interpolated across the gaps
    (:func:`_interpolate_invalid`), smoothed with :func:`smooth_signal`, and
    clamped to ``[0, 180]`` to kill any residual Savitzky-Golay over/undershoot.

    This is R2 (L2-CV-DEPTHFRAME-R2): cleaning the series here de-noises every
    downstream consumer at the source — rep detection (``detect_reps``), the
    confidence-scoring depth argmin in ``pipeline.py``, and the metric
    depth-frame selection — see ADR-ANGLE-SERIES-VALIDITY-GATE.

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
        Mapping of joint name → 1-D array of smoothed angles (degrees) in
        ``[0, 180]``, one value per input frame. A joint with no valid frame
        anywhere yields an all-NaN array (fully-occluded clip).
    """
    side_idx = landmark_indices_for_side(lifter_side)
    joint_deps = _JOINT_LANDMARK_DEPS.get(exercise_type.lower(), {})
    joint_indices = {
        joint: tuple(getattr(side_idx, attr) for attr in attrs)
        for joint, attrs in joint_deps.items()
    }

    # Accumulate raw angle series keyed by joint name; NaN out invalid frames
    # so dropout spikes never enter the signal that gets smoothed.
    raw: dict[str, list[float]] = {}
    for frame in landmarks_per_frame:
        angles = calculate_joint_angles(frame, exercise_type, lifter_side)
        for joint, angle in angles.items():
            indices = joint_indices.get(joint)
            if indices is not None and not _landmarks_visible(frame, indices):
                angle = float("nan")
            raw.setdefault(joint, []).append(angle)

    result: dict[str, np.ndarray] = {}
    for joint, series in raw.items():
        arr = _interpolate_invalid(np.array(series, dtype=float))
        if np.isnan(arr).any():
            # No valid frame for this joint anywhere — nothing reliable to
            # smooth. Leave as NaN (quality gate rejects such clips upstream).
            result[joint] = arr
            continue
        result[joint] = np.clip(smooth_signal(arr), 0.0, 180.0)
    return result
