"""
Per-rep biomechanical metric extraction for Phase 0 CV pipeline.

Implements FR-REPM-02, FR-REPM-03, SRS Sec 3.7.
All functions are pure — no side effects, no DB, no IO.

Phase 0: sagittal (side) view only. Angles use x, y coordinates.
Landmark layout (33, 5) per frame: [x, y, z, visibility, presence].

Landmark indices are resolved per-analysis via
``landmark_indices_for_side(lifter_side)`` (Session 2,
ADR-LIFTER-SIDE-DETECTION). The default ``"right"`` matches the
pre-refactor hardcoded subject-right indices, so existing test
assertions remain green without modification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.cv.lifter_side import SideIndices, landmark_indices_for_side
from app.cv.rep_detection import DetectedRep

# Column indices within a landmark row
_COL_X = 0
_COL_Y = 1


# ---------------------------------------------------------------------------
# Data type
# ---------------------------------------------------------------------------


# Categorical strings, dict-valued phase-frame maps, and None (Session 7
# #2/#16 cannot-compute sentinel — stored as JSON null, NOT a 0.0 sentinel,
# because 0.0 is a valid biomechanical outcome for a delta / std).
RepMetricValue = float | str | dict[str, float | None] | None


@dataclass
class RepMetrics:
    """Per-rep biomechanical metrics for a single detected repetition."""

    rep_index: int
    start_frame: int
    end_frame: int
    metrics: dict[str, RepMetricValue]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _xy(landmarks: np.ndarray, idx: int) -> np.ndarray:
    """Return (x, y) for landmark *idx* from a (33, 5) frame array."""
    return landmarks[idx, :2]


def _facing_sign(side: Literal["left", "right"]) -> float:
    """Return +1.0 if the lifter faces right in the image, -1.0 if left.

    Multiplies x-direction signed metrics (wrist_alignment_deg, shin_angle_deg,
    setup_shoulder_x_offset, arch_deg) so the same pose filmed from either side
    produces the same signed output. Without this, swapping side indices alone
    flips the sign of every x-derived value because anterior-posterior direction
    in image coordinates depends on which way the subject faces.

    See ADR-LIFTER-SIDE-DETECTION (Session 2) and design Section 5 mirror tests.
    """
    return 1.0 if side == "right" else -1.0


def _torso_lean_deg(landmarks: np.ndarray, side_idx: SideIndices) -> float:
    """
    Compute torso lean — the angle between the shoulder–hip line and vertical.

    Vertical is defined as the downward y-axis direction (0, 1) in image
    coordinates (y increases downward in normalised MediaPipe space).

    Returns angle in [0, 90] degrees.
    """
    shoulder = _xy(landmarks, side_idx.shoulder)
    hip = _xy(landmarks, side_idx.hip)

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


def _classify_depth(depth_angle: float, parallel_angle: float) -> str:
    """Categorical relabel of squat depth (Session 4, design Section-4 #7).

    Returns one of ``above_parallel``, ``at_parallel``, ``below_parallel``
    based on a ±5° band around ``parallel_angle``. ``depth_angle`` is the
    minimum hip angle for the rep (lower = deeper).

    Boundaries are inclusive on both sides of the ±5° band so a value
    exactly equal to ``parallel_angle - 5.0`` or ``parallel_angle + 5.0``
    is classified ``at_parallel``.
    """
    upper = parallel_angle + 5.0
    lower = parallel_angle - 5.0
    if depth_angle > upper:
        return "above_parallel"
    if depth_angle < lower:
        return "below_parallel"
    return "at_parallel"


def _default_parallel_angle() -> float:
    """Load ``squat.depth_parallel_hip_angle_deg`` from ThresholdConfig.

    Lazy import + lazy load so tests with no ThresholdConfig available
    still work (returns 90.0 fallback, matching the Phase-0 default).
    """
    try:
        from app.config import ThresholdConfig
        return float(ThresholdConfig().get("squat", "depth_parallel_hip_angle_deg"))
    except Exception:
        return 90.0


def _find_depth_frame(
    angle_series: np.ndarray,
    start: int,
    end: int,
    valid_mask: np.ndarray | None = None,
) -> int:
    """
    Return the frame index (within [start, end]) with the minimum angle value.

    This is the "depth" or "bottom" frame of the rep.

    When *valid_mask* is provided and at least one frame in [start, end] is
    marked valid (True), the argmin is computed only over those valid frames.
    This prevents MediaPipe VIDEO-mode dropout frames (zero-filled, garbage
    angles) from being selected as the rep bottom (L2-CV-DEPTHFRAME-DROPOUT).

    When *valid_mask* is None, or no valid frame exists in [start, end],
    the function falls back to the original plain argmin — preserving
    backward-compatible behaviour for callers that pass no mask.
    """
    segment = angle_series[start : end + 1]

    if valid_mask is not None:
        seg_valid = valid_mask[start : end + 1]
        if np.any(seg_valid):
            # Replace invalid positions with +inf so argmin ignores them.
            masked = np.where(seg_valid, segment, np.inf)
            local_idx = int(np.argmin(masked))
            return start + local_idx
        # Fall through: all invalid — use plain argmin below.

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


def _pause_duration_s(
    primary_series: np.ndarray,
    start: int,
    end: int,
    depth_frame: int,
    fps: float,
    band_deg: float = 2.0,
) -> float:
    """Time spent within ``band_deg`` of the rep-bottom angle (Session 4 #9).

    Counts frames in ``primary_series[start:end+1]`` whose value is within
    ``band_deg`` of ``primary_series[depth_frame]`` and divides by ``fps``.

    Returns ``0.0`` on degenerate input (``end <= start`` or ``fps <= 0``).
    """
    if end <= start or fps <= 0.0:
        return 0.0
    if depth_frame < start or depth_frame > end:
        return 0.0
    if depth_frame >= primary_series.shape[0]:
        return 0.0

    bottom_angle = float(primary_series[depth_frame])
    segment = primary_series[start : end + 1]
    in_band = np.abs(segment - bottom_angle) <= band_deg
    n_frames = int(np.sum(in_band))
    return float(n_frames) / float(fps)


def _lockout_torso_lean_deg(
    landmarks_per_frame: list[np.ndarray],
    end_frame: int,
    side_idx: SideIndices,
) -> float:
    """Torso-vertical angle at rep peak-angle (lockout) frame (Session 4 #12).

    Thin wrapper over ``_torso_lean_deg`` that picks the rep's last frame.
    Returns ``0.0`` on out-of-bounds ``end_frame`` (degenerate-input safety).
    """
    if end_frame < 0 or end_frame >= len(landmarks_per_frame):
        return 0.0
    return _torso_lean_deg(landmarks_per_frame[end_frame], side_idx)


# ---------------------------------------------------------------------------
# FR-REPM-08: Lockout quality assessment
# ---------------------------------------------------------------------------


def _assess_lockout_quality(
    exercise_type: str,
    end_frame: int,
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
    side_idx: SideIndices,
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
        vis = float(np.mean([frame[side_idx.hip, 3], frame[side_idx.knee, 3]]))
        return (bool(hip_ok and knee_ok), vis)
    if exercise_type == "bench":
        elbow_ok = angle_timeseries["elbow_angle"][end_frame] >= 165.0
        vis = float(frame[side_idx.elbow, 3])
        return (bool(elbow_ok), vis)
    if exercise_type == "deadlift":
        hip_ok = angle_timeseries["hip_angle"][end_frame] >= 165.0
        # Shoulders behind bar: shoulder x should be at or behind hip x
        # (sagittal view, right-facing = x increases forward)
        shoulder_behind = bool(
            frame[side_idx.shoulder, 0] <= frame[side_idx.hip, 0] + 0.02
        )
        vis = float(np.mean([frame[side_idx.hip, 3], frame[side_idx.shoulder, 3]]))
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
    side_idx: SideIndices,
    lifter_side: Literal["left", "right"] = "right",
    all_reps: list[DetectedRep] | None = None,
    rep_position: int = 0,
) -> dict[str, RepMetricValue]:
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

    # Depth frame = frame with minimum hip angle within the rep.
    # Build a per-frame validity mask: a frame is valid iff shoulder, hip, and
    # knee are all above _S5_MIN_VIS.  This gates out VIDEO-mode dropout frames
    # (zero-filled landmarks) that inject garbage hip angles (L2-CV-DEPTHFRAME-DROPOUT).
    squat_valid_mask = np.array(
        [_vis_ok(f, side_idx.shoulder, side_idx.hip, side_idx.knee)
         for f in landmarks_per_frame],
        dtype=bool,
    )
    depth_frame = _find_depth_frame(hip_series, start, end, valid_mask=squat_valid_mask)

    depth_angle = float(hip_series[depth_frame])
    knee_angle_at_depth = float(knee_series[depth_frame])
    torso_lean = _torso_lean_deg(landmarks_per_frame[depth_frame], side_idx)

    rep_duration_s = float(end - start) / fps
    descent_frames, ascent_frames = _find_descent_end_ascent_start(
        hip_series, start, end, depth_frame
    )
    descent_duration_s = descent_frames / fps
    ascent_duration_s = ascent_frames / fps

    lockout_passed, lockout_conf = _assess_lockout_quality(
        "squat", end, landmarks_per_frame, angle_timeseries, side_idx,
    )
    max_dev_phase = _phase_of_max_deviation(
        hip_series, start, end, depth_frame, threshold_angle=90.0,
    )

    # Session 4: four refinement metrics derived from already-computed inputs.
    parallel_angle = _default_parallel_angle()
    depth_classification = _classify_depth(depth_angle, parallel_angle)
    if ascent_duration_s > 0.0:
        ecc_con_ratio = float(descent_duration_s / ascent_duration_s)
    else:
        ecc_con_ratio = 0.0
    pause_duration = _pause_duration_s(
        hip_series, start, end, depth_frame, fps,
    )
    lockout_torso_lean = _lockout_torso_lean_deg(
        landmarks_per_frame, end, side_idx,
    )

    # Session 5 squat extractors
    ankle_dorsiflexion = _ankle_dorsiflexion_deg(landmarks_per_frame[depth_frame], side_idx)
    heel_rise = _heel_rise_flag(landmarks_per_frame, start, depth_frame, side_idx)
    shin_angle = _shin_angle_deg(landmarks_per_frame[depth_frame], side_idx, lifter_side)

    # Session 7 #2 — lumbar flexion proxy delta vs standing baseline.
    baseline = identify_standing_baseline_frame(
        "squat", rep, rep_position, all_reps, bar_y_series=None,
    )
    lumbar_delta = extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame, depth_frame, baseline, side_idx, lifter_side,
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
        "depth_classification": depth_classification,  # type: ignore[dict-item]
        "ecc_con_ratio": ecc_con_ratio,
        "pause_duration_s": pause_duration,
        "lockout_torso_lean_deg": lockout_torso_lean,
        "ankle_dorsiflexion_deg": (
            float(ankle_dorsiflexion) if ankle_dorsiflexion is not None else None
        ),
        "heel_rise_flag": float(heel_rise),
        "shin_angle_deg": float(shin_angle) if shin_angle is not None else None,
        "lumbar_flexion_proxy_delta_deg": lumbar_delta,  # None or float
    }


def _bench_metrics(
    rep: DetectedRep,
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
    fps: float,
    side_idx: SideIndices,
    lifter_side: Literal["left", "right"] = "right",
    all_reps: list[DetectedRep] | None = None,
    rep_position: int = 0,
) -> dict[str, RepMetricValue]:
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

    # Bottom frame = frame with minimum elbow angle within the rep.
    # Bench bottom-frame robustness deferred to R3 — wrist proxy unreliable.
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
        "bench", end, landmarks_per_frame, angle_timeseries, side_idx,
    )
    max_dev_phase = _phase_of_max_deviation(
        elbow_series, start, end, bottom_frame, threshold_angle=90.0,
    )

    # Session 4: ecc_con_ratio + pause_duration_s (bench-applicable subset).
    if ascent_duration_s > 0.0:
        ecc_con_ratio = float(descent_duration_s / ascent_duration_s)
    else:
        ecc_con_ratio = 0.0
    pause_duration = _pause_duration_s(
        elbow_series, start, end, bottom_frame, fps,
    )

    # Session 5 bench extractors
    wrist_alignment = _wrist_alignment_deg(
        landmarks_per_frame[bottom_frame], side_idx, lifter_side,
    )
    bar_touch_height = _bar_touch_height_pct(landmarks_per_frame[bottom_frame], side_idx)
    # Session 6 #14 — shoulder protraction proxy (setup → bottom drift).
    shoulder_protraction = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=landmarks_per_frame[start],
        bottom_frame_landmarks=landmarks_per_frame[bottom_frame],
        side_idx=side_idx,
        side=lifter_side,
    )
    # Build the non-rep mask. For bench, every frame outside the current rep is
    # "non-rep" for arch purposes. Multi-rep analyses where we'd want to also
    # exclude OTHER reps' frames are out-of-scope for Session 5: the analyzer
    # is invoked per rep and doesn't have cross-rep state. For a per-rep call,
    # treat frames OUTSIDE this rep as non-rep.
    n_total = len(landmarks_per_frame)
    non_rep_mask = [not (start <= i <= end) for i in range(n_total)]
    arch_value = _arch_deg(landmarks_per_frame, non_rep_mask, side_idx, lifter_side)

    # Session 7 #6 — bar-path classification using wrist-midpoint x trajectory.
    bar_x_series, _ = _wrist_midpoint_trajectory(landmarks_per_frame)
    span = end - start
    if span < 2:
        bar_path: str | None = None
    else:
        bar_path = _classify_bar_path(
            descent_start_x=float(bar_x_series[start]),
            bottom_x=float(bar_x_series[bottom_frame]),
            ascent_end_x=float(bar_x_series[end]),
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
        "ecc_con_ratio": ecc_con_ratio,
        "pause_duration_s": pause_duration,
        "wrist_alignment_deg": (
            float(wrist_alignment) if wrist_alignment is not None else 0.0
        ),
        "bar_touch_height_pct": (
            float(bar_touch_height) if bar_touch_height is not None else 0.0
        ),
        "arch_deg": float(arch_value) if arch_value is not None else 0.0,
        "shoulder_protraction_proxy_px": (
            float(shoulder_protraction) if shoulder_protraction is not None else 0.0
        ),
        "bar_path_classification": bar_path,  # None or str
    }


def _deadlift_metrics(
    rep: DetectedRep,
    landmarks_per_frame: list[np.ndarray],
    angle_timeseries: dict[str, np.ndarray],
    fps: float,
    side_idx: SideIndices,
    lifter_side: Literal["left", "right"] = "right",
    all_reps: list[DetectedRep] | None = None,
    rep_position: int = 0,
) -> dict[str, RepMetricValue]:
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

    # Bottom frame = frame with minimum hip angle within the rep.
    # Build a per-frame validity mask: a frame is valid iff shoulder, hip, and
    # knee are all above _S5_MIN_VIS (L2-CV-DEPTHFRAME-DROPOUT).
    dl_valid_mask = np.array(
        [_vis_ok(f, side_idx.shoulder, side_idx.hip, side_idx.knee)
         for f in landmarks_per_frame],
        dtype=bool,
    )
    bottom_frame = _find_depth_frame(hip_series, start, end, valid_mask=dl_valid_mask)

    hip_angle_at_bottom = float(hip_series[bottom_frame])

    # Lockout = end frame (rep completion)
    knee_angle_at_lockout = float(knee_series[end])

    # Torso lean at start of pull (start frame)
    torso_lean_at_start = _torso_lean_deg(landmarks_per_frame[start], side_idx)

    rep_duration_s = float(end - start) / fps
    descent_frames, ascent_frames = _find_descent_end_ascent_start(
        hip_series, start, end, bottom_frame
    )
    descent_duration_s = descent_frames / fps
    ascent_duration_s = ascent_frames / fps

    lockout_passed, lockout_conf = _assess_lockout_quality(
        "deadlift", end, landmarks_per_frame, angle_timeseries, side_idx,
    )
    max_dev_phase = _phase_of_max_deviation(
        hip_series, start, end, bottom_frame, threshold_angle=90.0,
    )

    # Session 4: ecc_con_ratio + pause_duration_s + lockout_torso_lean_deg.
    if ascent_duration_s > 0.0:
        ecc_con_ratio = float(descent_duration_s / ascent_duration_s)
    else:
        ecc_con_ratio = 0.0
    pause_duration = _pause_duration_s(
        hip_series, start, end, bottom_frame, fps,
    )
    lockout_torso_lean = _lockout_torso_lean_deg(
        landmarks_per_frame, end, side_idx,
    )

    # Session 5 deadlift extractors
    setup_shoulder_offset = _setup_shoulder_x_offset(
        landmarks_per_frame[start], side_idx, lifter_side,
    )
    setup_knee_angle = _setup_knee_angle_deg(landmarks_per_frame[start], side_idx)

    # Session 6 #4 — bar-to-hip distance at four phase frames. Uses the
    # wrist-midpoint (lm 15+16 mean) as the bar-trajectory proxy — same
    # fallback compute_bar_path_from_landmarks uses when HoughCircles fails.
    bar_x_series, bar_y_series = _wrist_midpoint_trajectory(landmarks_per_frame)
    hip_x_series = np.array(
        [float(lm[side_idx.hip, 0]) for lm in landmarks_per_frame],
        dtype=float,
    )
    knee_y_series = np.array(
        [float(lm[side_idx.knee, 1]) for lm in landmarks_per_frame],
        dtype=float,
    )
    bar_to_hip = _bar_to_hip_distance_dict(
        bar_x_series=bar_x_series,
        bar_y_series=bar_y_series,
        hip_x_series=hip_x_series,
        knee_y_series=knee_y_series,
        shoulder_x_setup=float(landmarks_per_frame[start][side_idx.shoulder, 0]),
        shoulder_y_setup=float(landmarks_per_frame[start][side_idx.shoulder, 1]),
        hip_y_setup=float(landmarks_per_frame[start][side_idx.hip, 1]),
        setup_frame=start,
        end_frame=end,
        side=lifter_side,
    )

    # Session 7 #2 — lumbar flexion proxy delta vs standing baseline.
    # bar_y_series is already computed above for bar_to_hip_distance.
    dl_baseline = identify_standing_baseline_frame(
        "deadlift", rep, rep_position, all_reps, bar_y_series=bar_y_series,
    )
    dl_lumbar_delta = extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame, bottom_frame, dl_baseline, side_idx, lifter_side,
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
        "ecc_con_ratio": ecc_con_ratio,
        "pause_duration_s": pause_duration,
        "lockout_torso_lean_deg": lockout_torso_lean,
        "setup_shoulder_x_offset": (
            float(setup_shoulder_offset) if setup_shoulder_offset is not None else 0.0
        ),
        "setup_knee_angle_deg": (
            float(setup_knee_angle) if setup_knee_angle is not None else 0.0
        ),
        "bar_to_hip_distance": bar_to_hip,
        "lumbar_flexion_proxy_delta_deg": dl_lumbar_delta,  # None or float
    }


# ---------------------------------------------------------------------------
# Session 5 helpers — sagittal-view single-frame landmark math
# ---------------------------------------------------------------------------

# Visibility threshold for required landmarks (matches the registry's
# "return None on missing landmark" convention).
_S5_MIN_VIS = 0.30
_S5_DEGENERATE_MAGNITUDE = 1e-6

# Anatomical-plausibility envelopes for squat metrics (L2-CV-DEPTHFRAME-DROPOUT-R1b).
# Values outside these bounds indicate MediaPipe mis-tracking even when visibility
# passes and y-ordering holds.  Expert refines the clinically meaningful sub-range
# via FR-EXPV-08; these are the outer anatomical limits only.
#
# ankle_dorsiflexion_deg: joint angle at ankle (knee-ankle-foot_index triangle).
#   Full squat ROM spans ~45–110 deg. Anatomical ceiling ~120 deg (maximum
#   plantarflexion, toes pointing straight down); values at or above 120 mean the
#   foot_index vector points backward relative to the tibia — impossible in a squat.
#   Lower bound 10 deg (extreme dorsiflexion with heel-elevated technique; below 10
#   would require >80 deg passive ROM which exceeds bony-joint limits).
_ANKLE_DORSIFLEXION_MIN_DEG = 10.0
_ANKLE_DORSIFLEXION_MAX_DEG = 120.0  # exclusive upper bound

# shin_angle_deg: shin deviation from vertical (positive = knee forward).
#   Maximum forward knee travel is ~45 deg; extreme heel-elevated cases reach
#   ~60–70 deg; absolute upper bound 80 deg.  Backward shin (negative) of more
#   than ~30–45 deg is impossible in any standing or squatting posture; bound -45.
_SHIN_ANGLE_MIN_DEG = -45.0
_SHIN_ANGLE_MAX_DEG = 80.0


def _vis_ok(landmarks: np.ndarray, *indices: int) -> bool:
    """Return True iff every named landmark has visibility >= _S5_MIN_VIS."""
    return all(float(landmarks[i, 3]) >= _S5_MIN_VIS for i in indices)


def _ankle_dorsiflexion_deg(
    landmarks: np.ndarray,
    side_idx: SideIndices,
) -> float | None:
    """Session 5 #1 — joint angle at S_ankle between S_knee and S_foot_index.

    Stored as the raw joint angle (registry description: "90 minus this is
    dorsiflexion magnitude"). Returns None on missing landmark, degenerate
    zero-length vector, or failed geometric plausibility check.

    Geometric plausibility (L2-CV-DEPTHFRAME-DROPOUT-R1): in a valid sagittal
    squat pose (MediaPipe normalised coords, y increases downward):
      • knee_y < ankle_y  — knee is above ankle in image
      • ankle_y <= foot_y — ankle is at or above toe in image
    Violations indicate MediaPipe mis-tracking (visibility > 0.30 but
    coordinates inverted) — return None rather than an impossible angle.
    """
    if not _vis_ok(landmarks, side_idx.knee, side_idx.ankle, side_idx.foot_index):
        return None
    knee = _xy(landmarks, side_idx.knee)
    ankle = _xy(landmarks, side_idx.ankle)
    foot = _xy(landmarks, side_idx.foot_index)
    # Geometric plausibility guard — rejects mis-tracked frames.
    if float(knee[1]) >= float(ankle[1]):  # knee at or below ankle in image
        return None
    if float(ankle[1]) > float(foot[1]):   # ankle below toe in image
        return None
    v_kn = knee - ankle
    v_ft = foot - ankle
    mag_kn = float(np.linalg.norm(v_kn))
    mag_ft = float(np.linalg.norm(v_ft))
    if mag_kn < _S5_DEGENERATE_MAGNITUDE or mag_ft < _S5_DEGENERATE_MAGNITUDE:
        return None
    cos_t = float(np.clip(np.dot(v_kn, v_ft) / (mag_kn * mag_ft), -1.0, 1.0))
    angle = float(np.degrees(np.arccos(cos_t)))
    # Anatomical-plausibility envelope — rejects values outside the achievable
    # squat ROM even when visibility and y-ordering guards pass (L2-CV-DEPTHFRAME-DROPOUT-R1b).
    if angle < _ANKLE_DORSIFLEXION_MIN_DEG or angle >= _ANKLE_DORSIFLEXION_MAX_DEG:
        return None
    return angle


def _heel_rise_flag(
    landmarks_per_frame: list[np.ndarray],
    start: int,
    depth_frame: int,
    side_idx: SideIndices,
    baseline_frames: int = 5,
    rise_threshold: float = 0.02,
    consecutive_frames: int = 3,
) -> bool:
    """Session 5 #1 companion — True if S_heel-y stays below baseline by more
    than ``rise_threshold`` for ``consecutive_frames`` or more during descent.

    Baseline is the mean S_heel-y over the first ``baseline_frames`` of the rep
    (frames ``start`` .. ``start + baseline_frames - 1``). Descent is
    ``start + baseline_frames`` .. ``depth_frame`` inclusive. Frame height is
    1.0 in MediaPipe normalised space, so the threshold is literally
    ``baseline - rise_threshold`` (a heel rising in image = heel_y decreasing).

    Degenerate input (rep too short to span baseline + a descent window,
    out-of-bounds frames) returns False with no exception.
    """
    n = len(landmarks_per_frame)
    if start < 0 or depth_frame >= n or depth_frame <= start + baseline_frames:
        return False
    heel_idx = side_idx.heel
    baseline_ys: list[float] = []
    for k in range(start, start + baseline_frames):
        f = landmarks_per_frame[k]
        if float(f[heel_idx, 3]) < _S5_MIN_VIS:
            continue
        baseline_ys.append(float(f[heel_idx, 1]))
    if len(baseline_ys) == 0:
        return False
    baseline_y = float(np.mean(baseline_ys))
    triggered = 0
    for k in range(start + baseline_frames, depth_frame + 1):
        f = landmarks_per_frame[k]
        if float(f[heel_idx, 3]) < _S5_MIN_VIS:
            triggered = 0
            continue
        if float(f[heel_idx, 1]) < baseline_y - rise_threshold:
            triggered += 1
            if triggered >= consecutive_frames:
                return True
        else:
            triggered = 0
    return False


def _wrist_alignment_deg(
    landmarks: np.ndarray,
    side_idx: SideIndices,
    side: Literal["left", "right"],
) -> float | None:
    """Session 5 #3 — sagittal-plane wrist-elbow stacking angle at bench bottom.

    ``atan2((wrist_x - elbow_x) * facing_sign, elbow_y - wrist_y)`` in degrees.
    0° = wrist stacked vertically over elbow. Positive = wrist anterior to
    elbow (regardless of which side filmed the lifter). Returns None on missing
    landmark or degenerate (coincident wrist/elbow) input.
    """
    if not _vis_ok(landmarks, side_idx.wrist, side_idx.elbow):
        return None
    wrist = _xy(landmarks, side_idx.wrist)
    elbow = _xy(landmarks, side_idx.elbow)
    dx = (float(wrist[0]) - float(elbow[0])) * _facing_sign(side)
    dy = float(elbow[1]) - float(wrist[1])
    if abs(dx) < _S5_DEGENERATE_MAGNITUDE and abs(dy) < _S5_DEGENERATE_MAGNITUDE:
        return None
    return float(np.degrees(np.arctan2(dx, dy)))


def _bar_touch_height_pct(
    landmarks: np.ndarray,
    side_idx: SideIndices,
) -> float | None:
    """Session 5 #5 — bench bar-touch y relative to shoulder-hip span.

    ``(wrist_y - shoulder_y) / (hip_y - shoulder_y)``. 0.0 = touching at
    shoulder, 1.0 = at hip. Returns None on missing landmark or zero-span
    (``shoulder_y == hip_y``). Y-only math → side-agnostic.
    """
    if not _vis_ok(landmarks, side_idx.wrist, side_idx.shoulder, side_idx.hip):
        return None
    wrist_y = float(landmarks[side_idx.wrist, 1])
    shoulder_y = float(landmarks[side_idx.shoulder, 1])
    hip_y = float(landmarks[side_idx.hip, 1])
    span = hip_y - shoulder_y
    if abs(span) < _S5_DEGENERATE_MAGNITUDE:
        return None
    return float((wrist_y - shoulder_y) / span)


def _setup_shoulder_x_offset(
    landmarks: np.ndarray,
    side_idx: SideIndices,
    side: Literal["left", "right"],
) -> float | None:
    """Session 5 #10 — deadlift shoulder-x offset from wrist-x at the first
    lift frame, normalised by forearm length.

    ``((shoulder_x - wrist_x) * facing_sign) / forearm_length`` where forearm
    length is ``hypot(wrist_x - elbow_x, wrist_y - elbow_y)``. Positive =
    shoulders over the bar (anterior of the wrist) regardless of filmed side.
    Returns None on missing landmark or zero-length forearm.
    """
    if not _vis_ok(landmarks, side_idx.shoulder, side_idx.wrist, side_idx.elbow):
        return None
    shoulder = _xy(landmarks, side_idx.shoulder)
    wrist = _xy(landmarks, side_idx.wrist)
    elbow = _xy(landmarks, side_idx.elbow)
    forearm_len = float(np.hypot(wrist[0] - elbow[0], wrist[1] - elbow[1]))
    if forearm_len < _S5_DEGENERATE_MAGNITUDE:
        return None
    raw_offset = float(shoulder[0]) - float(wrist[0])
    return (raw_offset * _facing_sign(side)) / forearm_len


def _shin_angle_deg(
    landmarks: np.ndarray,
    side_idx: SideIndices,
    side: Literal["left", "right"],
) -> float | None:
    """Session 5 #11 — sagittal-plane shin-vertical angle at squat rep bottom.

    ``atan2((knee_x - ankle_x) * facing_sign, ankle_y - knee_y)``. 0° = vertical
    shin. Positive = knee forward of ankle (forward shin lean) regardless of
    filmed side. Returns None on missing landmark, zero-magnitude vector, or
    failed geometric plausibility check.

    Geometric plausibility (L2-CV-DEPTHFRAME-DROPOUT-R1): knee_y < ankle_y
    (knee above ankle in image; y increases downward in MediaPipe normalised
    coords). Violations indicate mis-tracking → return None.
    """
    if not _vis_ok(landmarks, side_idx.knee, side_idx.ankle):
        return None
    knee = _xy(landmarks, side_idx.knee)
    ankle = _xy(landmarks, side_idx.ankle)
    # Geometric plausibility guard — rejects mis-tracked frames.
    if float(knee[1]) >= float(ankle[1]):  # knee at or below ankle in image
        return None
    dx = (float(knee[0]) - float(ankle[0])) * _facing_sign(side)
    dy = float(ankle[1]) - float(knee[1])
    if abs(dx) < _S5_DEGENERATE_MAGNITUDE and abs(dy) < _S5_DEGENERATE_MAGNITUDE:
        return None
    angle = float(np.degrees(np.arctan2(dx, dy)))
    # Anatomical-plausibility envelope — rejects values outside achievable squat
    # shin-lean ROM (L2-CV-DEPTHFRAME-DROPOUT-R1b).
    if angle < _SHIN_ANGLE_MIN_DEG or angle > _SHIN_ANGLE_MAX_DEG:
        return None
    return angle


def _setup_knee_angle_deg(
    landmarks: np.ndarray,
    side_idx: SideIndices,
) -> float | None:
    """Session 5 #13 — deadlift joint angle at S_knee (hip-knee-ankle) at the
    first lift frame. Unsigned → side-agnostic. Returns None on missing
    landmark or degenerate (zero-length) vector.
    """
    if not _vis_ok(landmarks, side_idx.hip, side_idx.knee, side_idx.ankle):
        return None
    hip = _xy(landmarks, side_idx.hip)
    knee = _xy(landmarks, side_idx.knee)
    ankle = _xy(landmarks, side_idx.ankle)
    v_hk = hip - knee
    v_ak = ankle - knee
    m_hk = float(np.linalg.norm(v_hk))
    m_ak = float(np.linalg.norm(v_ak))
    if m_hk < _S5_DEGENERATE_MAGNITUDE or m_ak < _S5_DEGENERATE_MAGNITUDE:
        return None
    cos_t = float(np.clip(np.dot(v_hk, v_ak) / (m_hk * m_ak), -1.0, 1.0))
    return float(np.degrees(np.arccos(cos_t)))


def _arch_deg(
    landmarks_per_frame: list[np.ndarray],
    non_rep_frame_mask: list[bool],
    side_idx: SideIndices,
    side: Literal["left", "right"],
) -> float | None:
    """Session 5 #15 — bench arch angle averaged across non-rep frames.

    For each frame where ``non_rep_frame_mask[i]`` is True AND both S_shoulder
    and S_hip are visible, compute the shoulder→hip vector with facing-sign
    applied to dx, then take the mean (dx_mean, dy_mean) and reduce via
    ``atan2(dy_mean, dx_mean)``. Positive = hips higher than shoulders. Single
    value per session.

    Returns None when no qualifying frame exists.
    """
    if len(landmarks_per_frame) != len(non_rep_frame_mask):
        return None
    sign = _facing_sign(side)
    dxs: list[float] = []
    dys: list[float] = []
    for include, frame in zip(non_rep_frame_mask, landmarks_per_frame):
        if not include:
            continue
        if not _vis_ok(frame, side_idx.shoulder, side_idx.hip):
            continue
        shoulder_x = float(frame[side_idx.shoulder, 0])
        shoulder_y = float(frame[side_idx.shoulder, 1])
        hip_x = float(frame[side_idx.hip, 0])
        hip_y = float(frame[side_idx.hip, 1])
        dxs.append((hip_x - shoulder_x) * sign)
        # In image coords y increases downward → "hips higher than shoulders"
        # = hip_y < shoulder_y → (shoulder_y - hip_y) > 0 = positive dy.
        dys.append(shoulder_y - hip_y)
    if not dxs:
        return None
    dx_mean = float(np.mean(dxs))
    dy_mean = float(np.mean(dys))
    if abs(dx_mean) < _S5_DEGENERATE_MAGNITUDE and abs(dy_mean) < _S5_DEGENERATE_MAGNITUDE:
        return None
    return float(np.degrees(np.arctan2(dy_mean, dx_mean)))


# ---------------------------------------------------------------------------
# Session 6 — Bar-coordinate math helpers
# ---------------------------------------------------------------------------

# Liftoff: bar y must drop (rise in image) by at least this fraction of the
# frame height. MediaPipe normalises y to [0, 1] so the threshold is
# dimensionally the same as the design Section-4 "≥2% of frame height".
_S6_LIFTOFF_THRESHOLD_PCT = 0.02

_S6_BAR_TO_HIP_PHASES = ("setup", "liftoff", "knee_pass", "lockout")


def identify_liftoff_frame(
    bar_y_series: np.ndarray,
    setup_frame: int,
    end_frame: int,
    threshold_pct: float = _S6_LIFTOFF_THRESHOLD_PCT,
) -> int | None:
    """Session 6 — first frame after ``setup_frame`` where the bar rises in
    image (y decreases) by at least ``threshold_pct`` of the frame height.

    Returns ``None`` when:
    - ``setup_frame`` or ``end_frame`` is out of bounds,
    - ``end_frame <= setup_frame``,
    - the bar never rises far enough across ``(setup_frame, end_frame]``.

    Frame height is 1.0 in MediaPipe normalised coords, so the absolute
    threshold equals ``threshold_pct``.
    """
    n = bar_y_series.shape[0] if bar_y_series.ndim == 1 else 0
    if n == 0:
        return None
    if setup_frame < 0 or end_frame >= n or end_frame <= setup_frame:
        return None
    baseline = float(bar_y_series[setup_frame])
    cutoff = baseline - threshold_pct
    for k in range(setup_frame + 1, end_frame + 1):
        if float(bar_y_series[k]) < cutoff:
            return k
    return None


def identify_knee_pass_frame(
    bar_y_series: np.ndarray,
    knee_y_series: np.ndarray,
    liftoff_frame: int,
    end_frame: int,
) -> int | None:
    """Session 6 — first frame on ascent where ``bar_y <= knee_y`` (bar
    reaches at-or-above knee height in image coordinates).

    Returns ``None`` on degenerate input (out-of-bounds frames, end <
    liftoff, empty arrays, or bar never crosses).
    """
    n_bar = bar_y_series.shape[0] if bar_y_series.ndim == 1 else 0
    n_knee = knee_y_series.shape[0] if knee_y_series.ndim == 1 else 0
    n = min(n_bar, n_knee)
    if n == 0:
        return None
    if liftoff_frame < 0 or end_frame >= n or end_frame < liftoff_frame:
        return None
    for k in range(liftoff_frame, end_frame + 1):
        if float(bar_y_series[k]) <= float(knee_y_series[k]):
            return k
    return None


def identify_standing_baseline_frame(
    exercise_type: str,
    rep: DetectedRep,
    rep_position: int,
    all_reps: list[DetectedRep] | None,
    bar_y_series: np.ndarray | None,
) -> int | None:
    """Session 7 #2 — index of the standing-baseline frame for the lumbar
    flexion proxy delta.

    Squat: one global baseline = ``all_reps[0].start_frame`` (the cleanest
    upright posture in the clip — see ADR-LUMBAR-FLEXION-PROXY-NAMING).
    Deadlift: previous rep's ``end_frame`` (lockout). First rep has no
    previous rep, so use the last frame before liftoff
    (``identify_liftoff_frame - 1``), falling back to ``rep.start_frame``
    when liftoff is undetectable.

    Returns ``None`` when no reps are available.
    """
    ex = exercise_type.lower()
    if ex == "squat":
        if not all_reps:
            return None
        return all_reps[0].start_frame
    if ex == "deadlift":
        if all_reps and rep_position > 0:
            return all_reps[rep_position - 1].end_frame
        # First rep: pre-liftoff frame, fallback to start.
        if bar_y_series is not None:
            liftoff = identify_liftoff_frame(
                bar_y_series, rep.start_frame, rep.end_frame,
            )
            if liftoff is not None:
                return max(rep.start_frame, liftoff - 1)
        return rep.start_frame
    return None


def _lumbar_proxy_angle(
    landmarks: np.ndarray, side_idx: SideIndices, side: Literal["left", "right"],
) -> float | None:
    """Composite trunk-flexion proxy angle at one frame:
    ``degrees(atan2((shoulder_x - hip_x)*facing_sign, hip_y - shoulder_y))``.
    NOT lumbar-isolated (ADR-LUMBAR-FLEXION-PROXY-NAMING). Returns None on
    low visibility, a degenerate (zero-length) torso vector, OR a non-physical
    shoulder-below-hip pose.

    The shoulder-below-hip guard (``dy <= 0``) is load-bearing: for squat and
    deadlift the shoulder always sits above the hip in image space
    (``hip_y > shoulder_y`` -> ``dy > 0``). A deep-squat hip-fold occlusion (a
    known high-occlusion phase) can mis-place a landmark so the shoulder appears
    below the hip; ``atan2`` would then wrap toward +/-180 deg, producing an
    implausible delta (-165 deg was observed on the squat fixture). Guarding
    ``dy <= 0`` returns None on that artifact and bounds the proxy to
    (-90, 90) deg."""
    if not _vis_ok(landmarks, side_idx.shoulder, side_idx.hip):
        return None
    shoulder = _xy(landmarks, side_idx.shoulder)
    hip = _xy(landmarks, side_idx.hip)
    dx = (float(shoulder[0]) - float(hip[0])) * _facing_sign(side)
    dy = float(hip[1]) - float(shoulder[1])  # +ve: hip below shoulder (normal)
    if dy <= _S5_DEGENERATE_MAGNITUDE:
        return None
    return float(np.degrees(np.arctan2(dx, dy)))


def extract_lumbar_flexion_proxy_delta_deg(
    landmarks_per_frame: list[np.ndarray],
    bottom_frame: int,
    baseline_frame: int | None,
    side_idx: SideIndices,
    lifter_side: Literal["left", "right"] = "right",
) -> float | None:
    """Session 7 #2 — composite trunk-flexion proxy delta (NOT lumbar-isolated).
    ``proxy(bottom) - proxy(baseline)``. Returns None if baseline is None,
    a frame is out of bounds, or either proxy angle is None."""
    n = len(landmarks_per_frame)
    if baseline_frame is None or not (0 <= baseline_frame < n) or not (0 <= bottom_frame < n):
        return None
    base = _lumbar_proxy_angle(landmarks_per_frame[baseline_frame], side_idx, lifter_side)
    bot = _lumbar_proxy_angle(landmarks_per_frame[bottom_frame], side_idx, lifter_side)
    if base is None or bot is None:
        return None
    return bot - base


_S7_JCURVE_THRESHOLD = 0.03
_S7_VERTICAL_DEADBAND = 0.02


def _classify_bar_path(
    descent_start_x: float | None,
    bottom_x: float | None,
    ascent_end_x: float | None,
) -> str | None:
    """Session 7 #6 — bar-path shape from three x anchors (wrist-midpoint).
    Side-agnostic: uses ``abs()`` so a left-facing lifter's j-curve (which
    sweeps toward higher x) classifies identically to a right-facing one
    (v0 heuristic — design R5; expect post-onboarding refinement)."""
    if descent_start_x is None or bottom_x is None or ascent_end_x is None:
        return None
    if abs(ascent_end_x - bottom_x) > _S7_JCURVE_THRESHOLD:
        return "j_curve"
    if abs(descent_start_x - ascent_end_x) < _S7_VERTICAL_DEADBAND:
        return "vertical"
    return "drift"


_S7_CONSISTENCY_KEY = {
    "squat": "depth_angle",
    "deadlift": "lockout_torso_lean_deg",
}


def _inject_technique_consistency_std(
    result: list[RepMetrics], exercise_type: str,
) -> None:
    """Session 7 #16 — population std (ddof=0) of the chosen technique metric
    across reps, written into EVERY rep's dict. Single-rep -> None (one
    observation has no measurable consistency). In-place mutation."""
    key = _S7_CONSISTENCY_KEY.get(exercise_type.lower())
    if key is None:
        return
    values: list[float] = []
    for r in result:
        v = r.metrics.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            values.append(float(v))
    std: float | None = float(np.std(values)) if len(values) >= 2 else None
    for r in result:
        r.metrics["technique_consistency_std"] = std


def session_modal_bar_path_classification(
    rep_metrics_list: list[RepMetrics],
) -> str | None:
    """Most common non-None bar_path_classification across reps (smoke/
    calibration only — NOT persisted to JSONB)."""
    from collections import Counter
    labels: list[str] = []
    for rm in rep_metrics_list:
        v = rm.metrics.get("bar_path_classification")
        if isinstance(v, str):
            labels.append(v)
    if not labels:
        return None
    return Counter(labels).most_common(1)[0][0]


def _wrist_midpoint_trajectory(
    landmarks_per_frame: list[np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """Return (wrist_x_series, wrist_y_series) using MediaPipe landmarks 15
    and 16 (bilateral wrist midpoint). Same proxy used by
    ``compute_bar_path_from_landmarks`` when HoughCircles detection fails.

    Side-agnostic by construction (always averages both wrists).
    """
    n = len(landmarks_per_frame)
    xs = np.zeros(n, dtype=float)
    ys = np.zeros(n, dtype=float)
    for i, lm in enumerate(landmarks_per_frame):
        xs[i] = (float(lm[15, 0]) + float(lm[16, 0])) / 2.0
        ys[i] = (float(lm[15, 1]) + float(lm[16, 1])) / 2.0
    return xs, ys


def _bar_to_hip_distance_dict(
    bar_x_series: np.ndarray,
    bar_y_series: np.ndarray,
    hip_x_series: np.ndarray,
    knee_y_series: np.ndarray,
    shoulder_x_setup: float,
    shoulder_y_setup: float,
    hip_y_setup: float,
    setup_frame: int,
    end_frame: int,
    side: Literal["left", "right"],
) -> dict[str, float | None]:
    """Session 6 #4 — bar-x to hip-x signed distance at four phase frames,
    normalised by shoulder-to-hip distance at setup.

    Output dict keys: ``setup``, ``liftoff``, ``knee_pass``, ``lockout``.
    A phase's value is ``None`` when that phase frame cannot be identified
    (e.g. bar never lifts, never passes knee) OR when the normaliser is
    degenerate (zero shoulder-to-hip distance at setup).

    Side handling: the raw ``bar_x - hip_x`` delta is multiplied by
    ``_facing_sign(side)`` so positive always means "bar in front of the
    lifter" regardless of which body-side was filmed.
    """
    empty: dict[str, float | None] = {k: None for k in _S6_BAR_TO_HIP_PHASES}
    n = min(
        bar_x_series.shape[0], bar_y_series.shape[0],
        hip_x_series.shape[0], knee_y_series.shape[0],
    )
    if n == 0:
        return empty
    if setup_frame < 0 or end_frame >= n or end_frame < setup_frame:
        return empty
    norm = float(np.hypot(
        shoulder_x_setup - float(hip_x_series[setup_frame]),
        shoulder_y_setup - hip_y_setup,
    ))
    if norm < _S5_DEGENERATE_MAGNITUDE:
        return empty
    sign = _facing_sign(side)

    def _signed_norm(frame: int) -> float:
        return ((float(bar_x_series[frame]) - float(hip_x_series[frame])) * sign) / norm

    out: dict[str, float | None] = dict(empty)
    out["setup"] = _signed_norm(setup_frame)
    out["lockout"] = _signed_norm(end_frame)

    liftoff = identify_liftoff_frame(bar_y_series, setup_frame, end_frame)
    if liftoff is not None:
        out["liftoff"] = _signed_norm(liftoff)
        knee_pass = identify_knee_pass_frame(
            bar_y_series, knee_y_series, liftoff, end_frame,
        )
        if knee_pass is not None:
            out["knee_pass"] = _signed_norm(knee_pass)
    return out


def _shoulder_protraction_proxy_px(
    setup_frame_landmarks: np.ndarray,
    bottom_frame_landmarks: np.ndarray,
    side_idx: SideIndices,
    side: Literal["left", "right"],
) -> float | None:
    """Session 6 #14 — bench shoulder-x drift from setup to rep bottom,
    normalised by setup shoulder-to-hip distance.

    ``((shoulder_x_bottom - shoulder_x_setup) * facing_sign) /
    hypot(shoulder_x_setup - hip_x_setup, shoulder_y_setup - hip_y_setup)``.
    Positive = shoulders move anteriorly during the press. Returns ``None``
    on missing landmark visibility (either frame) or degenerate
    (zero-length) setup torso vector.
    """
    if not _vis_ok(setup_frame_landmarks, side_idx.shoulder, side_idx.hip):
        return None
    if not _vis_ok(bottom_frame_landmarks, side_idx.shoulder):
        return None
    shoulder_setup = _xy(setup_frame_landmarks, side_idx.shoulder)
    hip_setup = _xy(setup_frame_landmarks, side_idx.hip)
    shoulder_bottom = _xy(bottom_frame_landmarks, side_idx.shoulder)
    span = float(np.hypot(
        shoulder_setup[0] - hip_setup[0],
        shoulder_setup[1] - hip_setup[1],
    ))
    if span < _S5_DEGENERATE_MAGNITUDE:
        return None
    raw = float(shoulder_bottom[0]) - float(shoulder_setup[0])
    return (raw * _facing_sign(side)) / span


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
    lifter_side: Literal["left", "right"] = "right",
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
    lifter_side:
        ``"left"`` or ``"right"`` (subject-perspective). Defaults to
        ``"right"`` to preserve pre-refactor behaviour. Resolved to
        MediaPipe landmark indices via ``landmark_indices_for_side``.

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

    side_idx = landmark_indices_for_side(lifter_side)

    result: list[RepMetrics] = []
    for i, rep in enumerate(reps):
        if ex in ("squat", "deadlift"):
            metrics = analyzer(
                rep, landmarks_per_frame, angle_timeseries, fps, side_idx,
                lifter_side, all_reps=reps, rep_position=i,
            )
        else:
            metrics = analyzer(
                rep, landmarks_per_frame, angle_timeseries, fps, side_idx, lifter_side,
            )
        result.append(
            RepMetrics(
                rep_index=rep.rep_index,
                start_frame=rep.start_frame,
                end_frame=rep.end_frame,
                metrics=metrics,
            )
        )

    # Session 7 #16 — session-level consistency std injected into every rep.
    _inject_technique_consistency_std(result, ex)
    return result
