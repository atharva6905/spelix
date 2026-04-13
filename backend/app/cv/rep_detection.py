"""
Rep detection state machine for Phase 0 CV pipeline.

Implements FR-CVPL-15, FR-REPM-01, FR-REPM-05.
State machine: STANDING → DESCENDING → BOTTOM → ASCENDING → STANDING.
All functions are pure — no side effects, no DB, no IO.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class RepState(Enum):
    STANDING = "standing"
    DESCENDING = "descending"
    BOTTOM = "bottom"
    ASCENDING = "ascending"


@dataclass
class DetectedRep:
    rep_index: int
    start_frame: int
    end_frame: int
    confidence_score: float
    min_angle: float


# ---------------------------------------------------------------------------
# Per-exercise thresholds
# ---------------------------------------------------------------------------

# Standing threshold: angle must be above this to be considered "standing".
# Squat uses 150° (FR-CVPL-07): tolerates athletes who do not fully lock out
# between reps.  Bench and deadlift keep 160° — different joint geometry.
_STANDING_THRESHOLD: dict[str, float] = {
    "squat": 150.0,
    "bench": 160.0,
    "deadlift": 160.0,
}

# Depth threshold: angle must be below this to register "bottom".
# Squat uses 110° (FR-CVPL-07): catches parallel-depth squats (~90–110° hip).
# Old value was 90° (effective 85° with hysteresis), which silently skipped
# reps where the athlete stopped at parallel rather than going below it.
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

_HYSTERESIS_DEG = 5.0
_MIN_REP_DURATION_S = 0.5


# ---------------------------------------------------------------------------
# Threshold helpers
# ---------------------------------------------------------------------------


def _get_standing_threshold(exercise_type: str) -> float:
    return _STANDING_THRESHOLD.get(exercise_type.lower(), 160.0)


def _get_depth_threshold(exercise_type: str, exercise_variant: str) -> float:
    ex = exercise_type.lower()
    var = exercise_variant.lower()
    depth_map = _DEPTH_THRESHOLD.get(ex, {"default": 90.0})
    return depth_map.get(var, depth_map.get("default", 90.0))


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------


def detect_reps(
    angle_timeseries: np.ndarray,
    landmarks_per_frame: list[np.ndarray],
    exercise_type: str,
    exercise_variant: str,
    fps: float,
) -> list[DetectedRep]:
    """
    Detect reps from smoothed angle time-series using a state machine.

    Parameters
    ----------
    angle_timeseries:
        1-D array of smoothed primary angle per frame (degrees).
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame. Retained for API compat;
        confidence is now computed by pipeline Step 7 (Tier 5).
    exercise_type:
        One of "squat", "bench", "deadlift".
    exercise_variant:
        Exercise variant (e.g. "conventional", "sumo", "rdl", "standard").
    fps:
        Frames per second — used for min rep duration check.

    Returns
    -------
    list[DetectedRep]
        Detected reps with frame ranges, confidence, and min angle.
    """
    if len(angle_timeseries) == 0:
        return []

    standing_thresh = _get_standing_threshold(exercise_type)
    depth_thresh = _get_depth_threshold(exercise_type, exercise_variant)
    min_rep_frames = int(_MIN_REP_DURATION_S * fps)

    state = RepState.STANDING
    reps: list[DetectedRep] = []
    rep_start_frame = 0
    min_angle_in_rep = float("inf")

    for i, angle in enumerate(angle_timeseries):
        angle_f = float(angle)

        if state == RepState.STANDING:
            # Transition to DESCENDING when angle drops below standing - hysteresis
            if angle_f < standing_thresh - _HYSTERESIS_DEG:
                state = RepState.DESCENDING
                rep_start_frame = i
                min_angle_in_rep = angle_f

        elif state == RepState.DESCENDING:
            min_angle_in_rep = min(min_angle_in_rep, angle_f)
            # Transition to BOTTOM when angle drops below depth + hysteresis
            if angle_f < depth_thresh - _HYSTERESIS_DEG:
                state = RepState.BOTTOM
                min_angle_in_rep = min(min_angle_in_rep, angle_f)

            # If angle goes back above standing threshold, abort this rep attempt
            elif angle_f > standing_thresh + _HYSTERESIS_DEG:
                state = RepState.STANDING

        elif state == RepState.BOTTOM:
            min_angle_in_rep = min(min_angle_in_rep, angle_f)
            # Transition to ASCENDING when angle rises above depth + hysteresis
            if angle_f > depth_thresh + _HYSTERESIS_DEG:
                state = RepState.ASCENDING

        elif state == RepState.ASCENDING:
            min_angle_in_rep = min(min_angle_in_rep, angle_f)
            # Transition to STANDING when angle rises above standing - hysteresis
            if angle_f > standing_thresh - _HYSTERESIS_DEG:
                rep_end_frame = i
                rep_duration_frames = rep_end_frame - rep_start_frame

                # Check min rep duration
                if rep_duration_frames >= min_rep_frames:
                    # Confidence placeholder — pipeline Step 7 backfills
                    # with Tier 5 value (FR-CVPL-20–25)
                    reps.append(
                        DetectedRep(
                            rep_index=len(reps),
                            start_frame=rep_start_frame,
                            end_frame=rep_end_frame,
                            confidence_score=0.0,
                            min_angle=min_angle_in_rep,
                        )
                    )

                state = RepState.STANDING
                min_angle_in_rep = float("inf")

    return reps
