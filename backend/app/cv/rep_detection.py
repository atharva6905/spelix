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

All functions are pure — no side effects, no DB, no IO.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy.signal import find_peaks


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
# Shared constants
# ---------------------------------------------------------------------------

_MIN_REP_DURATION_S = 0.5
_HYSTERESIS_DEG = 5.0


# ---------------------------------------------------------------------------
# State-machine primary path (FR-CVPL-07 thresholds)
# ---------------------------------------------------------------------------

# Standing threshold: angle must be above this to be considered "standing".
# Squat 150° tolerates athletes who do not fully lock out between reps.
# Bench and deadlift keep 160° (different joint geometry).
_STANDING_THRESHOLD: dict[str, float] = {
    "squat": 150.0,
    "bench": 160.0,
    "deadlift": 160.0,
}

# Depth threshold: angle must be below this to register "bottom".
# Squat 110° catches parallel-depth squats (~90-110° hip).
# Deadlift variants differ (conventional/sumo deeper than RDL/romanian).
_DEPTH_THRESHOLD: dict[str, dict[str, float]] = {
    "squat": {"default": 110.0},
    "bench": {"default": 90.0},
    "deadlift": {
        "conventional": 70.0,
        "sumo": 70.0,
        "romanian": 90.0,
        "rdl": 90.0,
    },
}


def _get_standing_threshold(exercise_type: str) -> float:
    return _STANDING_THRESHOLD.get(exercise_type.lower(), 160.0)


def _get_depth_threshold(exercise_type: str, exercise_variant: str) -> float:
    ex = exercise_type.lower()
    var = exercise_variant.lower()
    depth_map = _DEPTH_THRESHOLD.get(ex, {"default": 90.0})
    return depth_map.get(var, depth_map.get("default", 90.0))


def _detect_reps_state_machine(
    angle_timeseries: np.ndarray,
    exercise_type: str,
    exercise_variant: str,
    fps: float,
) -> list[DetectedRep]:
    """
    Primary detector: STANDING -> DESCENDING -> BOTTOM -> ASCENDING -> STANDING.

    Requires the signal to cross both the STANDING threshold (full lockout)
    and the DEPTH threshold (rep bottom) within a min_rep_duration window.
    Robust to signal noise in the mid-range because state transitions
    require full up-and-down cycles through absolute thresholds.
    """
    if len(angle_timeseries) == 0:
        return []

    standing_thresh = _get_standing_threshold(exercise_type)
    depth_thresh = _get_depth_threshold(exercise_type, exercise_variant)
    min_rep_frames = int(_MIN_REP_DURATION_S * fps)

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
            # abort). The lenient ASCENDING side tolerates athletes who
            # don't fully lock out between reps (squat 150° standing →
            # 145° effective re-entry). Per ADR-REPDET-01.
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

# Signal-relative minimum valley prominence (degrees). Only used when the
# state machine returns 0 reps; keeps partial-lockout detection working.
_PROMINENCE_DEG: dict[str, float] = {
    "squat": 20.0,
    "bench": 20.0,
    "deadlift": 20.0,
}


def _detect_reps_peak_valley(
    angle_timeseries: np.ndarray,
    exercise_type: str,
    fps: float,
) -> list[DetectedRep]:
    """
    Fallback detector: valleys via `find_peaks` on the inverted signal.

    Used only when the state-machine detector returns 0 reps — typical of
    partial-lockout lifts (bodyweight bench, fatigued reps, RDLs) whose
    signal peaks never exceed the STANDING threshold.
    """
    n = len(angle_timeseries)
    if n < 3:
        return []

    prominence = _PROMINENCE_DEG.get(exercise_type.lower(), 20.0)
    min_rep_frames = max(1, int(_MIN_REP_DURATION_S * fps))

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
            start_frame = start_lo + int(np.argmax(angle_timeseries[start_lo : start_hi + 1]))

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

    Returns
    -------
    list[DetectedRep]
        Detected reps (state-machine result if >=1 rep found;
        peak/valley result otherwise).
    """
    sm_reps = _detect_reps_state_machine(
        angle_timeseries, exercise_type, exercise_variant, fps
    )
    if len(sm_reps) >= 1:
        return sm_reps
    return _detect_reps_peak_valley(angle_timeseries, exercise_type, fps)
