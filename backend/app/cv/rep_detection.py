"""
Hybrid rep detection for the Spelix CV pipeline.

Implements FR-CVPL-15, FR-REPM-01, FR-REPM-05.

Approach: state-machine detector first (the legacy Phase 0 algorithm,
reliable for clean-lockout lifts that cross absolute standing + depth
thresholds). If it returns zero reps — typical for partial-lockout lifts
like bodyweight bench or fatigued final reps that never reach the
STANDING threshold — fall back to signal-relative peak/valley detection
via `scipy.signal.find_peaks`. Session 44 ADR-REPDET-01 motivated the
fallback path; session 45 fixture calibration proved that peak/valley
alone over-counts on noisy real-video signals, hence the hybrid.

All numeric knobs (standing/depth/prominence angles + global
min_rep_duration_s) flow through `ThresholdConfig` per FR-SCOR-11
(D-042, ADR-REPDET-03) so Expert Reviewers can tune them via PR.
Hysteresis remains a module constant — it's a detector-internal
numerical stability knob, not an expert-tunable kinesiology threshold.

All functions are pure — no side effects, no DB, no IO.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy.signal import find_peaks

from app.config import ThresholdConfig


# ---------------------------------------------------------------------------
# Public types (unchanged API)
# ---------------------------------------------------------------------------


@dataclass
class DetectedRep:
    rep_index: int
    start_frame: int
    end_frame: int
    confidence_score: float
    min_angle: float


class _RepState(Enum):
    STANDING = "standing"
    DESCENDING = "descending"
    BOTTOM = "bottom"
    ASCENDING = "ascending"


# ---------------------------------------------------------------------------
# Constants & cfg-reading helpers (FR-SCOR-11 — D-042)
# ---------------------------------------------------------------------------

# Hysteresis is a detector-internal numerical stability knob — not an
# expert-tunable kinesiology threshold. Kept as a module constant.
_HYSTERESIS_DEG = 5.0


def _get_standing_threshold_from_cfg(
    cfg: ThresholdConfig, exercise_type: str
) -> float:
    """Standing-angle threshold for the state-machine STANDING state."""
    return float(
        cfg.get(exercise_type.lower(), "rep_detection_standing_angle_deg")
    )


def _get_depth_threshold_from_cfg(
    cfg: ThresholdConfig, exercise_type: str, exercise_variant: str
) -> float:
    """Depth-angle threshold for the state-machine BOTTOM state.

    For exercises with variant-specific depths (deadlift: romanian/rdl
    deeper than conventional/sumo), prefer the variant-specific key
    ``rep_detection_depth_angle_{variant}_deg``. Fall back to the
    exercise default ``rep_detection_depth_angle_deg``.
    """
    ex = exercise_type.lower()
    var = exercise_variant.lower()
    variant_key = f"rep_detection_depth_angle_{var}_deg"
    try:
        return float(cfg.get(ex, variant_key))
    except KeyError:
        return float(cfg.get(ex, "rep_detection_depth_angle_deg"))


def _get_prominence_from_cfg(
    cfg: ThresholdConfig, exercise_type: str
) -> float:
    """Minimum valley prominence for the peak/valley fallback detector."""
    return float(
        cfg.get(exercise_type.lower(), "rep_detection_prominence_deg")
    )


def _get_min_rep_duration_s_from_cfg(cfg: ThresholdConfig) -> float:
    """Global minimum rep duration in seconds (exercise-agnostic)."""
    return float(cfg.get("rep_detection", "min_rep_duration_s"))


# ---------------------------------------------------------------------------
# State-machine primary path
# ---------------------------------------------------------------------------


def _detect_reps_state_machine(
    angle_timeseries: np.ndarray,
    exercise_type: str,
    exercise_variant: str,
    fps: float,
    cfg: ThresholdConfig,
) -> list[DetectedRep]:
    """
    Primary detector: STANDING -> DESCENDING -> BOTTOM -> ASCENDING -> STANDING.

    Requires the signal to cross both the STANDING threshold (full lockout)
    and the DEPTH threshold (rep bottom) within a min_rep_duration window.
    Robust to signal noise in the mid-range because state transitions
    require full up-and-down cycles through absolute thresholds.

    All numeric knobs (STANDING/DEPTH/min rep duration) flow through
    ``cfg`` per FR-SCOR-11 (D-042). Hysteresis remains a module constant.
    """
    if len(angle_timeseries) == 0:
        return []

    standing_thresh = _get_standing_threshold_from_cfg(cfg, exercise_type)
    depth_thresh = _get_depth_threshold_from_cfg(
        cfg, exercise_type, exercise_variant
    )
    min_rep_duration_s = _get_min_rep_duration_s_from_cfg(cfg)
    min_rep_frames = int(min_rep_duration_s * fps)

    state = _RepState.STANDING
    reps: list[DetectedRep] = []
    rep_start_frame = 0
    min_angle_in_rep = float("inf")

    for i, angle in enumerate(angle_timeseries):
        angle_f = float(angle)

        if state == _RepState.STANDING:
            if angle_f < standing_thresh - _HYSTERESIS_DEG:
                state = _RepState.DESCENDING
                rep_start_frame = i
                min_angle_in_rep = angle_f

        elif state == _RepState.DESCENDING:
            min_angle_in_rep = min(min_angle_in_rep, angle_f)
            if angle_f < depth_thresh - _HYSTERESIS_DEG:
                state = _RepState.BOTTOM
                min_angle_in_rep = min(min_angle_in_rep, angle_f)
            elif angle_f > standing_thresh + _HYSTERESIS_DEG:
                state = _RepState.STANDING

        elif state == _RepState.BOTTOM:
            min_angle_in_rep = min(min_angle_in_rep, angle_f)
            if angle_f > depth_thresh + _HYSTERESIS_DEG:
                state = _RepState.ASCENDING

        elif state == _RepState.ASCENDING:
            min_angle_in_rep = min(min_angle_in_rep, angle_f)
            # Intentional asymmetry: ASCENDING re-enters STANDING at
            # `standing - hysteresis` (lenient re-entry), while DESCENDING
            # aborts back to STANDING at `standing + hysteresis` (strict
            # abort). Per ADR-REPDET-01.
            if angle_f > standing_thresh - _HYSTERESIS_DEG:
                rep_end_frame = i
                rep_duration_frames = rep_end_frame - rep_start_frame
                if rep_duration_frames >= min_rep_frames:
                    reps.append(
                        DetectedRep(
                            rep_index=len(reps),
                            start_frame=rep_start_frame,
                            end_frame=rep_end_frame,
                            confidence_score=0.0,
                            min_angle=min_angle_in_rep,
                        )
                    )
                state = _RepState.STANDING
                min_angle_in_rep = float("inf")

    return reps


# ---------------------------------------------------------------------------
# Peak/valley fallback path (D-040 — for partial-lockout lifts)
# ---------------------------------------------------------------------------


def _detect_reps_peak_valley(
    angle_timeseries: np.ndarray,
    exercise_type: str,
    fps: float,
    cfg: ThresholdConfig,
) -> list[DetectedRep]:
    """
    Fallback detector: valleys via `find_peaks` on the inverted signal.

    Used only when the state-machine detector returns 0 reps — typical of
    partial-lockout lifts (bodyweight bench, fatigued reps, RDLs) whose
    signal peaks never exceed the STANDING threshold.

    Prominence threshold and minimum rep duration flow through ``cfg`` per
    FR-SCOR-11 (D-042).
    """
    n = len(angle_timeseries)
    if n < 3:
        return []

    prominence = _get_prominence_from_cfg(cfg, exercise_type)
    min_rep_duration_s = _get_min_rep_duration_s_from_cfg(cfg)
    min_rep_frames = max(1, int(min_rep_duration_s * fps))

    inverted = -np.asarray(angle_timeseries, dtype=float)
    valley_indices, _ = find_peaks(
        inverted,
        prominence=prominence,
        distance=min_rep_frames,
    )
    if len(valley_indices) == 0:
        return []

    reps: list[DetectedRep] = []
    prev_end = 0
    for i, v_idx in enumerate(valley_indices):
        v_idx_int = int(v_idx)

        start_lo = prev_end
        start_hi = v_idx_int
        if start_hi <= start_lo:
            start_frame = start_lo
        else:
            start_frame = start_lo + int(
                np.argmax(angle_timeseries[start_lo : start_hi + 1])
            )

        if i + 1 < len(valley_indices):
            end_hi = int(valley_indices[i + 1])
        else:
            end_hi = n - 1
        if end_hi <= v_idx_int:
            end_frame = v_idx_int
        else:
            end_frame = v_idx_int + int(
                np.argmax(angle_timeseries[v_idx_int : end_hi + 1])
            )

        # Min-duration post-filter; advance prev_end only on kept reps.
        if end_frame - start_frame >= min_rep_frames:
            reps.append(
                DetectedRep(
                    rep_index=len(reps),
                    start_frame=start_frame,
                    end_frame=end_frame,
                    confidence_score=0.0,
                    min_angle=float(angle_timeseries[v_idx_int]),
                )
            )
            prev_end = end_frame

    return reps


# ---------------------------------------------------------------------------
# Public hybrid entry point
# ---------------------------------------------------------------------------


def detect_reps(
    angle_timeseries: np.ndarray,
    landmarks_per_frame: list[np.ndarray],
    exercise_type: str,
    exercise_variant: str,
    fps: float,
    cfg: ThresholdConfig,
) -> list[DetectedRep]:
    """
    Detect reps using a hybrid state-machine + peak/valley detector.

    Primary path: state machine with absolute STANDING + DEPTH thresholds
    (robust to signal noise, preserves Phase 0 prod behavior).

    Fallback path: `scipy.signal.find_peaks` when state machine returns 0
    (catches partial-lockout lifts whose signal peaks never reach STANDING
    threshold — bodyweight bench, fatigued final reps, RDLs).

    Parameters
    ----------
    angle_timeseries:
        1-D array of smoothed primary angle per frame (degrees).
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame. Retained for API compat.
    exercise_type:
        One of "squat", "bench", "deadlift" (case-insensitive).
    exercise_variant:
        Variant (e.g. "conventional", "sumo", "rdl", "standard") —
        only consulted by the state-machine path for per-variant depth.
    fps:
        Frames per second.
    cfg:
        ``ThresholdConfig`` carrying rep-detection knobs
        (standing/depth/prominence angles + global min_rep_duration_s).
        Required per FR-SCOR-11 (D-042) so Expert Reviewers can tune via PR.

    Returns
    -------
    list[DetectedRep]
        Detected reps (state-machine result if >=1 rep found;
        peak/valley result otherwise).
    """
    sm_reps = _detect_reps_state_machine(
        angle_timeseries, exercise_type, exercise_variant, fps, cfg
    )
    if len(sm_reps) >= 1:
        return sm_reps
    return _detect_reps_peak_valley(angle_timeseries, exercise_type, fps, cfg)
