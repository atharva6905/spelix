"""
Per-rep biomechanical metric extraction for Phase 0 CV pipeline.

Implements FR-REPM-02, FR-REPM-03, SRS Sec 3.7.
All functions are pure — no side effects, no DB, no IO.

Phase 0: sagittal (side) view only. Angles use x, y coordinates.
Landmark layout (33, 5) per frame: [x, y, z, visibility, presence].

Landmark indices used (left/even side per task spec):
  Squat/Deadlift: shoulder=12, hip=24, knee=26, ankle=28
  Bench:          shoulder=12, elbow=14, wrist=16, hip=24
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass

from app.cv.rep_detection import DetectedRep

# ---------------------------------------------------------------------------
# Landmark index constants
# ---------------------------------------------------------------------------

_SHOULDER = 12
_HIP = 24
_KNEE = 26
_ANKLE = 28
_ELBOW = 14
_WRIST = 16

# Column indices within a landmark row
_COL_X = 0
_COL_Y = 1


# ---------------------------------------------------------------------------
# Data type
# ---------------------------------------------------------------------------


@dataclass
class RepMetrics:
    """Per-rep biomechanical metrics for a single detected repetition."""

    rep_index: int
    start_frame: int
    end_frame: int
    metrics: dict[str, float | str]  # exercise-specific metrics (may include phase labels)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _xy(landmarks: np.ndarray, idx: int) -> np.ndarray:
    """Return (x, y) for landmark *idx* from a (33, 5) frame array."""
    return landmarks[idx, :2]


def _torso_lean_deg(landmarks: np.ndarray) -> float:
    """
    Compute torso lean — the angle between the shoulder–hip line and vertical.

    Vertical is defined as the downward y-axis direction (0, 1) in image
    coordinates (y increases downward in normalised MediaPipe space).

    Returns angle in [0, 90] degrees.
    """
    shoulder = _xy(landmarks, _SHOULDER)
    hip = _xy(landmarks, _HIP)

    # Vector from hip to shoulder
    dx = float(shoulder[0] - hip[0])
    dy = float(shoulder[1] - hip[1])

    # Vertical reference vector pointing "up" in image coords: (0, -1)
    # Angle between (dx, dy) and (0, -1):
    #   cos θ = dot / (|v1| * |v2|)
    # |vertical| = 1, |torso_vec| = sqrt(dx²+dy²)
    magnitude = np.sqrt(dx * dx + dy * dy)
    if magnitude < 1e-9:
        return 0.0

    # Dot product with (0, -1): -dy
    cos_theta = -dy / magnitude
    # Clamp for numerical safety
    cos_theta = float(np.clip(cos_theta, -1.0, 1.0))
    return float(np.degrees(np.arccos(cos_theta)))


def _find_depth_frame(angle_series: np.ndarray, start: int, end: int) -> int:
    """
    Return the frame index (within [start, end]) with the minimum angle value.

    This is the "depth" or "bottom" frame of the rep.
    """
    segment = angle_series[start : end + 1]
    local_idx = int(np.argmin(segment))
    return start + local_idx


def _find_descent_end_ascent_start(
    primary_series: np.ndarray,
    start: int,
    end: int,
    depth_frame: int,
) -> tuple[float, float]:
    """
    Compute descent and ascent durations in frames.

    Descent: start_frame → depth_frame
    Ascent:  depth_frame → end_frame

    Returns (descent_frames, ascent_frames) as floats.
    """
    descent_frames = float(depth_frame - start)
    ascent_frames = float(end - depth_frame)
    return descent_frames, ascent_frames


# ---------------------------------------------------------------------------
# FR-REPM-08: Lockout quality assessment
# ---------------------------------------------------------------------------


def _assess_lockout_quality(
    exercise_type: str,
    end_frame: int,
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
) -> tuple[bool, float]:
    """
    Assess lockout quality at rep end for squat, bench, or deadlift (FR-REPM-08).

    Returns
    -------
    (passed, confidence) tuple.
    - squat: full hip AND knee extension (both >= 165°)
    - bench: full elbow extension (>= 165°)
    - deadlift: full hip extension (>= 165°) + shoulders behind bar
    Confidence is the mean visibility of the joints inspected.
    """
    if end_frame >= len(landmarks_per_frame):
        return (False, 0.0)
    frame = landmarks_per_frame[end_frame]

    if exercise_type == "squat":
        hip_ok = angle_timeseries["hip_angle"][end_frame] >= 165.0
        knee_ok = angle_timeseries["knee_angle"][end_frame] >= 165.0
        vis = float(np.mean([frame[_HIP, 3], frame[_KNEE, 3]]))
        return (bool(hip_ok and knee_ok), vis)
    if exercise_type == "bench":
        elbow_ok = angle_timeseries["elbow_angle"][end_frame] >= 165.0
        vis = float(frame[_ELBOW, 3])
        return (bool(elbow_ok), vis)
    if exercise_type == "deadlift":
        hip_ok = angle_timeseries["hip_angle"][end_frame] >= 165.0
        # Shoulders behind bar: shoulder x should be at or behind hip x
        # (sagittal view, right-facing = x increases forward)
        shoulder_behind = bool(frame[_SHOULDER, 0] <= frame[_HIP, 0] + 0.02)
        vis = float(np.mean([frame[_HIP, 3], frame[_SHOULDER, 3]]))
        return (bool(hip_ok and shoulder_behind), vis)
    return (False, 0.0)


# ---------------------------------------------------------------------------
# FR-REPM-09: Phase of maximum deviation
# ---------------------------------------------------------------------------


def _phase_of_max_deviation(
    primary_series: np.ndarray,
    start: int,
    end: int,
    depth_frame: int,
    threshold_angle: float,
) -> str:
    """
    Identify which lift phase shows the greatest deviation from threshold_angle.

    Phases: setup | descent | bottom | ascent | lockout
    Returns the phase name with maximum |angle - threshold| within its frames.
    """
    if end <= start:
        return "bottom"

    # Phase segmentation:
    # - setup: first ~10% of rep
    # - descent: setup_end → just before depth (within 5% window)
    # - bottom: ±5% window around depth_frame
    # - ascent: after bottom window → just before lockout
    # - lockout: last ~10% of rep
    rep_len = end - start
    setup_end = start + max(1, int(0.10 * rep_len))
    lockout_start = end - max(1, int(0.10 * rep_len))
    bottom_half = max(1, int(0.05 * rep_len))
    bottom_start = max(setup_end, depth_frame - bottom_half)
    bottom_end = min(lockout_start, depth_frame + bottom_half)

    phase_ranges = {
        "setup": (start, setup_end),
        "descent": (setup_end, bottom_start),
        "bottom": (bottom_start, bottom_end + 1),
        "ascent": (bottom_end + 1, lockout_start),
        "lockout": (lockout_start, end + 1),
    }

    best_phase = "bottom"
    best_dev = -1.0
    for phase, (a, b) in phase_ranges.items():
        if b <= a or a >= len(primary_series):
            continue
        segment = primary_series[a : min(b, len(primary_series))]
        if segment.size == 0:
            continue
        dev = float(np.max(np.abs(segment - threshold_angle)))
        if dev > best_dev:
            best_dev = dev
            best_phase = phase
    return best_phase


# ---------------------------------------------------------------------------
# Exercise-specific analyzers
# ---------------------------------------------------------------------------


def _squat_metrics(
    rep: DetectedRep,
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
    fps: float,
) -> dict[str, float | str]:
    """
    Extract squat metrics for one rep.

    Metrics:
      depth_angle         — min hip angle during rep
      knee_angle_at_depth — knee angle at frame of min hip angle
      torso_lean          — torso-to-vertical angle at depth
      rep_duration_s      — total rep duration in seconds
      descent_duration_s  — standing to depth duration in seconds
      ascent_duration_s   — depth to standing duration in seconds
    """
    start = rep.start_frame
    end = rep.end_frame
    hip_series = angle_timeseries["hip_angle"]
    knee_series = angle_timeseries["knee_angle"]

    # Depth frame = frame with minimum hip angle within the rep
    depth_frame = _find_depth_frame(hip_series, start, end)

    depth_angle = float(hip_series[depth_frame])
    knee_angle_at_depth = float(knee_series[depth_frame])
    torso_lean = _torso_lean_deg(landmarks_per_frame[depth_frame])

    rep_duration_s = float(end - start) / fps
    descent_frames, ascent_frames = _find_descent_end_ascent_start(
        hip_series, start, end, depth_frame
    )
    descent_duration_s = descent_frames / fps
    ascent_duration_s = ascent_frames / fps

    lockout_passed, lockout_conf = _assess_lockout_quality(
        "squat", end, landmarks_per_frame, angle_timeseries,
    )
    max_dev_phase = _phase_of_max_deviation(
        hip_series, start, end, depth_frame, threshold_angle=90.0,
    )

    return {
        "depth_angle": depth_angle,
        "knee_angle_at_depth": knee_angle_at_depth,
        "torso_lean": torso_lean,
        "rep_duration_s": rep_duration_s,
        "descent_duration_s": descent_duration_s,
        "eccentric_duration_s": descent_duration_s,  # FR-REPM-07
        "ascent_duration_s": ascent_duration_s,
        "lockout_passed": float(lockout_passed),
        "lockout_confidence": lockout_conf,
        "phase_of_max_deviation": max_dev_phase,  # type: ignore[dict-item]
    }


def _bench_metrics(
    rep: DetectedRep,
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
    fps: float,
) -> dict[str, float | str]:
    """
    Extract bench press metrics for one rep.

    Metrics:
      elbow_angle_at_bottom   — min elbow angle during rep
      shoulder_angle_at_bottom — shoulder angle at frame of min elbow angle
      rep_duration_s
      descent_duration_s
      ascent_duration_s
    """
    start = rep.start_frame
    end = rep.end_frame
    elbow_series = angle_timeseries["elbow_angle"]
    shoulder_series = angle_timeseries["shoulder_angle"]

    # Bottom frame = frame with minimum elbow angle within the rep
    bottom_frame = _find_depth_frame(elbow_series, start, end)

    elbow_angle_at_bottom = float(elbow_series[bottom_frame])
    shoulder_angle_at_bottom = float(shoulder_series[bottom_frame])

    rep_duration_s = float(end - start) / fps
    descent_frames, ascent_frames = _find_descent_end_ascent_start(
        elbow_series, start, end, bottom_frame
    )
    descent_duration_s = descent_frames / fps
    ascent_duration_s = ascent_frames / fps

    lockout_passed, lockout_conf = _assess_lockout_quality(
        "bench", end, landmarks_per_frame, angle_timeseries,
    )
    max_dev_phase = _phase_of_max_deviation(
        elbow_series, start, end, bottom_frame, threshold_angle=90.0,
    )

    return {
        "elbow_angle_at_bottom": elbow_angle_at_bottom,
        "shoulder_angle_at_bottom": shoulder_angle_at_bottom,
        "rep_duration_s": rep_duration_s,
        "descent_duration_s": descent_duration_s,
        "eccentric_duration_s": descent_duration_s,  # FR-REPM-07
        "ascent_duration_s": ascent_duration_s,
        "lockout_passed": float(lockout_passed),
        "lockout_confidence": lockout_conf,
        "phase_of_max_deviation": max_dev_phase,
    }


def _deadlift_metrics(
    rep: DetectedRep,
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
    fps: float,
) -> dict[str, float | str]:
    """
    Extract deadlift metrics for one rep.

    Metrics:
      hip_angle_at_bottom   — min hip angle during rep (bottom of pull)
      knee_angle_at_lockout — knee angle at rep end (lockout)
      torso_lean_at_start   — torso angle at beginning of the pull
      rep_duration_s
      descent_duration_s    — lockout to bottom (lowering phase)
      ascent_duration_s     — bottom to lockout (pulling phase)
    """
    start = rep.start_frame
    end = rep.end_frame
    hip_series = angle_timeseries["hip_angle"]
    knee_series = angle_timeseries["knee_angle"]

    # Bottom frame = frame with minimum hip angle within the rep
    bottom_frame = _find_depth_frame(hip_series, start, end)

    hip_angle_at_bottom = float(hip_series[bottom_frame])

    # Lockout = end frame (rep completion)
    knee_angle_at_lockout = float(knee_series[end])

    # Torso lean at start of pull (start frame)
    torso_lean_at_start = _torso_lean_deg(landmarks_per_frame[start])

    rep_duration_s = float(end - start) / fps
    descent_frames, ascent_frames = _find_descent_end_ascent_start(
        hip_series, start, end, bottom_frame
    )
    descent_duration_s = descent_frames / fps
    ascent_duration_s = ascent_frames / fps

    lockout_passed, lockout_conf = _assess_lockout_quality(
        "deadlift", end, landmarks_per_frame, angle_timeseries,
    )
    max_dev_phase = _phase_of_max_deviation(
        hip_series, start, end, bottom_frame, threshold_angle=90.0,
    )

    return {
        "hip_angle_at_bottom": hip_angle_at_bottom,
        "knee_angle_at_lockout": knee_angle_at_lockout,
        "torso_lean_at_start": torso_lean_at_start,
        "rep_duration_s": rep_duration_s,
        "descent_duration_s": descent_duration_s,
        "eccentric_duration_s": descent_duration_s,  # FR-REPM-07
        "ascent_duration_s": ascent_duration_s,
        "lockout_passed": float(lockout_passed),
        "lockout_confidence": lockout_conf,
        "phase_of_max_deviation": max_dev_phase,
    }


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_ANALYZER_MAP = {
    "squat": _squat_metrics,
    "bench": _bench_metrics,
    "deadlift": _deadlift_metrics,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_rep_metrics(
    reps: list[DetectedRep],
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
    exercise_type: str,
    exercise_variant: str,
    fps: float,
) -> list[RepMetrics]:
    """
    Extract per-rep biomechanical metrics for each detected rep.

    Implements FR-REPM-02, FR-REPM-03.

    Parameters
    ----------
    reps:
        Output of ``detect_reps()`` — list of DetectedRep objects.
    landmarks_per_frame:
        List of (33, 5) numpy arrays, one per frame (full clip).
    angle_timeseries:
        Dict of joint-name → smoothed 1-D angle array (from
        ``compute_angle_timeseries()``).  Keys depend on exercise:
        squat/deadlift: "hip_angle", "knee_angle";
        bench: "elbow_angle", "shoulder_angle".
    exercise_type:
        One of "squat", "bench", "deadlift" (case-insensitive).
    exercise_variant:
        Exercise variant string (e.g. "standard", "conventional", "sumo",
        "rdl") — reserved for future variant-specific logic.
    fps:
        Frames per second of the source video.

    Returns
    -------
    list[RepMetrics]
        One RepMetrics entry per detected rep, in input order.

    Raises
    ------
    ValueError
        If exercise_type is not recognised.
    """
    if not reps:
        return []

    ex = exercise_type.lower()
    analyzer = _ANALYZER_MAP.get(ex)
    if analyzer is None:
        raise ValueError(
            f"Unknown exercise type {exercise_type!r}. "
            f"Expected one of: {sorted(_ANALYZER_MAP.keys())}"
        )

    result: list[RepMetrics] = []
    for rep in reps:
        metrics = analyzer(rep, landmarks_per_frame, angle_timeseries, fps)
        result.append(
            RepMetrics(
                rep_index=rep.rep_index,
                start_frame=rep.start_frame,
                end_frame=rep.end_frame,
                metrics=metrics,
            )
        )

    return result
