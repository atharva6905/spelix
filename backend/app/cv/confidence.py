"""
Confidence scoring for Phase 0 CV pipeline.

Implements FR-CVPL-16 (per-rep confidence), FR-RESL-08 (session confidence),
FR-REPM-04 (rep-level confidence stored in rep_metrics), and FR-SCOR-10
(confidence label and guidance text shown to user).

All functions are pure — no side effects, no DB, no IO.
Landmark arrays: shape (33, 5) per frame — [x, y, z, visibility, presence].

MediaPipe gotcha: visibility values may be pre-sigmoid logits (outside [0, 1]).
Always apply sigmoid() before computing the mean.  See GitHub #4411, #4462.
"""

from __future__ import annotations

import numpy as np

from app.cv.quality_gates import sigmoid

# ---------------------------------------------------------------------------
# Exercise-specific landmark sets
# ---------------------------------------------------------------------------

# Squat and Deadlift: hips (23,24), knees (25,26), ankles (27,28)
_SQUAT_DEADLIFT_LANDMARKS: frozenset[int] = frozenset({23, 24, 25, 26, 27, 28})

# Bench: shoulders (11,12), elbows (13,14), wrists (15,16)
_BENCH_LANDMARKS: frozenset[int] = frozenset({11, 12, 13, 14, 15, 16})

_EXERCISE_LANDMARK_MAP: dict[str, frozenset[int]] = {
    "squat": _SQUAT_DEADLIFT_LANDMARKS,
    "deadlift": _SQUAT_DEADLIFT_LANDMARKS,
    "bench": _BENCH_LANDMARKS,
}

# Column index for visibility within a (33, 5) landmark row
_COL_VISIBILITY = 3

# ---------------------------------------------------------------------------
# Confidence label thresholds
# ---------------------------------------------------------------------------

_LABEL_HIGH = "High"
_LABEL_MODERATE = "Moderate"
_LABEL_LOW = "Low"
_LABEL_VERY_LOW = "Very Low"

_GUIDANCE: dict[str, str] = {
    _LABEL_HIGH: (
        "Landmark visibility is strong — high confidence in analysis accuracy."
    ),
    _LABEL_MODERATE: (
        "Moderate landmark visibility — results are generally reliable but may have minor inaccuracies."
    ),
    _LABEL_LOW: (
        "Low landmark visibility — results should be interpreted with caution. "
        "Consider re-recording with better lighting or camera angle."
    ),
    _LABEL_VERY_LOW: (
        "Very low landmark visibility — analysis accuracy is significantly reduced. "
        "We strongly recommend re-recording."
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_rep_confidence(
    landmarks_per_frame: list[np.ndarray],
    start_frame: int,
    end_frame: int,
    exercise_type: str,
) -> float:
    """
    Compute per-rep confidence for a single repetition (FR-CVPL-16).

    Extracts the visibility column (index 3) for exercise-specific landmarks
    across all frames in [start_frame, end_frame].  Applies sigmoid to handle
    pre-sigmoid logit values from MediaPipe (GitHub #4411, #4462), then
    returns the mean of all visibility values across the landmark set and
    frame range.

    Parameters
    ----------
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame, for the entire clip.
    start_frame:
        Inclusive start index of the rep within landmarks_per_frame.
    end_frame:
        Inclusive end index of the rep within landmarks_per_frame.
    exercise_type:
        One of "squat", "deadlift", "bench" (case-sensitive).

    Returns
    -------
    float
        Mean sigmoid-visibility in [0, 1].

    Raises
    ------
    ValueError
        If exercise_type is not a recognised exercise.
    """
    exercise_key = exercise_type.lower()
    if exercise_key not in _EXERCISE_LANDMARK_MAP:
        raise ValueError(
            f"Unknown exercise type {exercise_type!r}. "
            f"Expected one of: {sorted(_EXERCISE_LANDMARK_MAP.keys())}"
        )

    landmark_indices = _EXERCISE_LANDMARK_MAP[exercise_key]

    vis_values: list[float] = []
    for frame_idx in range(start_frame, end_frame + 1):
        frame = landmarks_per_frame[frame_idx]
        for lm_idx in landmark_indices:
            raw_vis = float(frame[lm_idx, _COL_VISIBILITY])
            vis_values.append(sigmoid(raw_vis))

    if not vis_values:
        return 0.0

    return float(np.mean(vis_values))


def compute_session_confidence(rep_confidences: list[float]) -> float:
    """
    Compute overall session confidence as the mean of per-rep scores (FR-RESL-08).

    Parameters
    ----------
    rep_confidences:
        List of per-rep confidence values in [0, 1].

    Returns
    -------
    float
        Mean confidence in [0, 1], or 0.0 for an empty list.
    """
    if not rep_confidences:
        return 0.0
    return float(np.mean(rep_confidences))


def confidence_label(score: float) -> str:
    """
    Map a confidence score to a human-readable label (FR-SCOR-10).

    Thresholds:
        ≥ 0.80        → "High"
        0.65 – 0.79   → "Moderate"
        0.50 – 0.64   → "Low"
        < 0.50        → "Very Low"

    Parameters
    ----------
    score:
        Confidence score in [0, 1].

    Returns
    -------
    str
        One of "High", "Moderate", "Low", "Very Low".
    """
    if score >= 0.80:
        return _LABEL_HIGH
    if score >= 0.65:
        return _LABEL_MODERATE
    if score >= 0.50:
        return _LABEL_LOW
    return _LABEL_VERY_LOW


def confidence_guidance(label: str) -> str:
    """
    Return user-facing guidance text for a confidence label (FR-SCOR-10).

    Parameters
    ----------
    label:
        One of "High", "Moderate", "Low", "Very Low".

    Returns
    -------
    str
        Guidance string explaining what the label means and suggesting
        corrective action where appropriate.

    Raises
    ------
    ValueError
        If label is not a recognised confidence label.
    """
    if label not in _GUIDANCE:
        raise ValueError(
            f"Unknown confidence label {label!r}. "
            f"Expected one of: {sorted(_GUIDANCE.keys())}"
        )
    return _GUIDANCE[label]
