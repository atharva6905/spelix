"""
Confidence scoring for CV pipeline.

Phase 0: FR-CVPL-16 (simple mean visibility) — retained for backward compat.
Phase 1: FR-CVPL-20–25 (Tier 1–5 composite confidence) — replaces Phase 0.

Also: FR-RESL-08 (session confidence), FR-REPM-04 (per-rep storage),
FR-SCOR-10 (labels), FR-CVPL-25 (categorical labels only).

All functions are pure — no side effects, no DB, no IO.
Landmark arrays: shape (33, 5) per frame — [x, y, z, visibility, presence].

MediaPipe gotcha: visibility/presence values may be pre-sigmoid logits.
pose_extraction._guard_sigmoid handles this at ingestion time — stored values
are in [0, 1]. Phase 1 Tier 1 multiplies stored values directly (no second sigmoid).
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


# ---------------------------------------------------------------------------
# Phase 1: Tier 1–5 composite confidence (FR-CVPL-20 through FR-CVPL-25)
# ---------------------------------------------------------------------------

# Column indices within a (33, 5) landmark row
_COL_PRESENCE = 4


def _tier1_landmark_conf(frame: np.ndarray, lm_idx: int) -> float:
    """Tier 1 (FR-CVPL-20): landmark_conf = visibility × presence.

    Values are already sigmoid-guarded at ingestion by pose_extraction.
    DO NOT apply sigmoid again — just multiply the stored [0,1] values.
    """
    return float(frame[lm_idx, _COL_VISIBILITY] * frame[lm_idx, _COL_PRESENCE])


def _tier2_angle_conf(
    frame: np.ndarray, lm_a: int, lm_b: int, lm_c: int,
) -> float:
    """Tier 2 (FR-CVPL-21): min confidence of an angle's three landmarks.

    Minimum, not mean — one unreliable landmark invalidates the entire
    angle estimate.
    """
    return min(
        _tier1_landmark_conf(frame, lm_a),
        _tier1_landmark_conf(frame, lm_b),
        _tier1_landmark_conf(frame, lm_c),
    )


def _tier3_frame_conf(frame: np.ndarray, weights: dict[int, float]) -> float:
    """Tier 3 (FR-CVPL-22): weighted mean of landmark confidences per frame.

    Parameters
    ----------
    frame:
        Single (33, 5) landmark array.
    weights:
        {landmark_index: weight} — exercise-specific from ThresholdConfig
        ``confidence_landmark_weights``.
    """
    total_w = sum(weights.values())
    if total_w == 0.0:
        return 0.0
    return sum(
        _tier1_landmark_conf(frame, idx) * w for idx, w in weights.items()
    ) / total_w


def _tier4_phase_adjusted(
    tier3_score: float,
    frame_offset: int,
    depth_frame_offset: int,
    rep_frame_count: int,
    exercise_type: str,
    cfg: "ThresholdConfig",
) -> float:
    """Tier 4 (FR-CVPL-23): frame_conf × phase_multiplier.

    Phase classification:
      - Frames within ±10% of depth frame → high_occlusion
      - First/last frame of rep → static_peak (1.0)
      - All others → transition (0.90)
    """

    bottom_window = max(1, rep_frame_count // 10)

    if abs(frame_offset - depth_frame_offset) <= bottom_window:
        occlusion_map = cfg.get("phase_multipliers", "high_occlusion")
        key_map = {
            "squat": "squat_deep_hip_fold",
            "deadlift": "squat_deep_hip_fold",
            "bench": "bench_supine",
        }
        key = key_map.get(exercise_type.lower(), "squat_deep_hip_fold")
        multiplier = occlusion_map.get(
            key, cfg.get("phase_multipliers", "transition"),
        )
    elif frame_offset == 0 or frame_offset == rep_frame_count - 1:
        multiplier = cfg.get("phase_multipliers", "static_peak")
    else:
        multiplier = cfg.get("phase_multipliers", "transition")

    return tier3_score * multiplier


def _tier5_rep_confidence(tier4_scores: list[float]) -> float:
    """Tier 5 (FR-CVPL-24): 10th percentile of phase-adjusted frame confidences.

    Pessimistic bound — uses percentile, not mean — so a few bad frames
    pull the confidence down appropriately.
    """
    if not tier4_scores:
        return 0.0
    return float(np.percentile(tier4_scores, 10))


def compute_confidence_result(
    landmarks_per_frame: list[np.ndarray],
    start_frame: int,
    end_frame: int,
    exercise_type: str,
    depth_frame_idx: int,
    cfg: "ThresholdConfig",
    rep_index: int = 0,
) -> "ConfidenceResult":
    """Compute all 5 tiers for a single rep.

    Parameters
    ----------
    landmarks_per_frame:
        Full clip's landmark arrays (list of (33,5) ndarrays).
    start_frame, end_frame:
        Inclusive frame range for this rep.
    exercise_type:
        "squat", "deadlift", or "bench".
    depth_frame_idx:
        Absolute frame index of the rep's bottom position (for Tier 4
        phase classification). Passed by the pipeline from metric_extraction.
    cfg:
        ThresholdConfig instance (v1) with confidence_landmark_weights and
        phase_multipliers sections.
    rep_index:
        0-based rep index (stored in the result for identification).

    Returns
    -------
    ConfidenceResult
        Per-rep confidence breakdown across all five tiers.
    """
    from app.cv.types import ConfidenceResult as _CR

    exercise_key = exercise_type.lower()

    # Load exercise-specific landmark weights from ThresholdConfig
    lm_weights_section = cfg.get_section("confidence_landmark_weights")
    raw_weights = lm_weights_section.get(exercise_key, {})
    # Keys are strings in JSON — convert to int for numpy indexing
    weights: dict[int, float] = {int(k): v for k, v in raw_weights.items()}

    rep_frame_count = end_frame - start_frame + 1
    depth_offset = depth_frame_idx - start_frame

    tier3_scores: list[float] = []
    tier4_scores: list[float] = []

    for abs_frame in range(start_frame, end_frame + 1):
        frame = landmarks_per_frame[abs_frame]
        frame_offset = abs_frame - start_frame

        # Tier 3: weighted mean of landmark confs
        t3 = _tier3_frame_conf(frame, weights)
        tier3_scores.append(t3)

        # Tier 4: phase-adjusted
        t4 = _tier4_phase_adjusted(
            tier3_score=t3,
            frame_offset=frame_offset,
            depth_frame_offset=depth_offset,
            rep_frame_count=rep_frame_count,
            exercise_type=exercise_key,
            cfg=cfg,
        )
        tier4_scores.append(t4)

    # Tier 5: 10th percentile
    tier5 = _tier5_rep_confidence(tier4_scores)
    label = confidence_label(tier5)

    return _CR(
        rep_index=rep_index,
        tier3_frame_scores=tier3_scores,
        tier4_frame_scores=tier4_scores,
        tier5=tier5,
        label=label,
    )
