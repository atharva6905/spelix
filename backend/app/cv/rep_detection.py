"""
Rep detection via peak/valley extraction for the Spelix CV pipeline.

Implements FR-CVPL-15, FR-REPM-01, FR-REPM-05.

Approach: `scipy.signal.find_peaks` on the inverted primary angle
time-series. Valleys (rep bottoms) are located by a signal-relative
prominence threshold; `start_frame` and `end_frame` are the surrounding
local maxima. No absolute angle thresholds are used — this correctly
handles partial-lockout lifts (bodyweight bench, fatigued reps, RDLs)
that the previous fixed-threshold state machine silently failed on.

All functions are pure — no side effects, no DB, no IO.
"""

from __future__ import annotations

from dataclasses import dataclass

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


# ---------------------------------------------------------------------------
# Tuning knobs
# ---------------------------------------------------------------------------

# Minimum peak prominence (degrees) on the inverted signal — i.e. the
# minimum depth of a valley below its bracketing peaks. Tuned against the
# in-repo fixture library (see plan Task 5 Step 6). Signal-relative, so
# it handles partial-lockout lifts that never reach absolute standing.
# Unknown exercise_type values fall back to 20.0 via dict.get default.
_PROMINENCE_DEG: dict[str, float] = {
    "squat": 20.0,
    "bench": 20.0,
    "deadlift": 20.0,
}

# Minimum rep duration in seconds — applied after peak/valley extraction
# as `end_frame - start_frame >= min_rep_frames`. Prevents spurious
# reps from single-frame noise spikes that slipped through prominence.
_MIN_REP_DURATION_S = 0.5


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
    Detect reps from smoothed angle time-series via peak/valley extraction.

    Parameters
    ----------
    angle_timeseries:
        1-D array of smoothed primary angle per frame (degrees).
        For squat/deadlift this is the hip angle; for bench it is the
        elbow angle.
    landmarks_per_frame:
        List of (33, 5) arrays, one per frame. Retained for API compat;
        confidence is computed by pipeline Step 7 (Tier 5).
    exercise_type:
        One of "squat", "bench", "deadlift". Selects the prominence knob.
    exercise_variant:
        Retained for API compat — the peak/valley approach is variant-
        agnostic (old per-variant depth thresholds are gone). Kept in
        the signature so callers in `app/services/pipeline.py` need no
        change.
    fps:
        Frames per second — used for min rep duration filter.

    Returns
    -------
    list[DetectedRep]
        Detected reps with frame ranges, 0.0 placeholder confidence
        (pipeline Step 7 backfills Tier 5), and min_angle at the valley.
    """
    n = len(angle_timeseries)
    if n < 3:
        return []

    prominence = _PROMINENCE_DEG.get(exercise_type.lower(), 20.0)
    min_rep_frames = max(1, int(_MIN_REP_DURATION_S * fps))

    # find_peaks on -angle: peaks of inverted signal = valleys of original
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

        # start_frame: argmax in [prev_end, valley]
        start_lo = prev_end
        start_hi = v_idx_int
        if start_hi <= start_lo:
            start_frame = start_lo
        else:
            start_frame = start_lo + int(np.argmax(angle_timeseries[start_lo : start_hi + 1]))

        # end_frame: argmax in [valley, next_valley_or_signal_end]
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

        # Min-duration post-filter. Advance prev_end ONLY on kept reps —
        # if a valley is filtered here, the next rep's start-frame search
        # window correctly extends back across the filtered region and
        # argmax still lands on the highest intermediate peak (or earlier).
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
