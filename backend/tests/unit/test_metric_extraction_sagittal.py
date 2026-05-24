"""Session 4 — synthetic-landmark unit tests for the four trivial extractors.

Per design Session-4 and Section-5:
- Each extractor has a happy path, a boundary/edge case, and a
  side-agnosticism mirror test asserting equal output across left/right
  input with x mirrored (x' = 1 - x).
- _classify_depth and _pause_duration_s operate on 1-D angle signals and
  are side-agnostic by construction (sanity-checked).
- _lockout_torso_lean_deg consumes landmarks and is mirror-tested across
  five lean values.
- Analyzer integration tests assert each exercise's analyzer emits exactly
  its applicable Session 4 keys.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pytest

# Wire ThresholdConfig to v1 before any app.* imports so the lazy
# _default_parallel_angle() helper finds the squat config.
_V1_PATH = (
    Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
)
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.cv.lifter_side import landmark_indices_for_side  # noqa: E402
from app.cv.metric_extraction import (  # noqa: E402
    _classify_depth,
    _lockout_torso_lean_deg,
    _pause_duration_s,
    extract_rep_metrics,
)
from app.cv.rep_detection import DetectedRep  # noqa: E402


# ---------------------------------------------------------------------------
# #7 depth_classification (categorical relabel of existing depth_angle)
# ---------------------------------------------------------------------------


def test_session4_depth_classification_above_parallel() -> None:
    """depth_angle > parallel + 5° → 'above_parallel'."""
    assert _classify_depth(depth_angle=100.0, parallel_angle=90.0) == "above_parallel"


def test_session4_depth_classification_at_parallel_upper_band() -> None:
    """depth_angle within ±5° of parallel → 'at_parallel'."""
    assert _classify_depth(depth_angle=95.0, parallel_angle=90.0) == "at_parallel"


def test_session4_depth_classification_at_parallel_lower_band() -> None:
    assert _classify_depth(depth_angle=85.0, parallel_angle=90.0) == "at_parallel"


def test_session4_depth_classification_below_parallel() -> None:
    """depth_angle < parallel - 5° → 'below_parallel'."""
    assert _classify_depth(depth_angle=80.0, parallel_angle=90.0) == "below_parallel"


def test_session4_depth_classification_boundary_exact_parallel() -> None:
    """At exactly parallel - 5° = 85°, classification is 'at_parallel' (inclusive lower band)."""
    assert _classify_depth(depth_angle=85.0, parallel_angle=90.0) == "at_parallel"


# ---------------------------------------------------------------------------
# #9 pause_duration_s (frames within ±2° of rep bottom, divided by fps)
# ---------------------------------------------------------------------------


def test_session4_pause_duration_synthetic_pause() -> None:
    """A rep with an explicit 15-frame pause at the depth angle, fps=30 → 0.5s."""
    n = 60
    angles = np.full(n, 170.0)
    angles[10:20] = np.linspace(170.0, 80.0, 10)  # descent
    angles[20:35] = 80.0                          # plateau 15 frames
    angles[35:60] = np.linspace(80.0, 170.0, 25)  # ascent
    pause = _pause_duration_s(
        primary_series=angles, start=0, end=59, depth_frame=27, fps=30.0
    )
    # Plateau is 15 frames; boundary descent/ascent frames also fall within
    # the ±2° band geometrically (e.g. the last descent frame is exactly 80°,
    # and the first ascent frame is 80°). Use a 0.1s tolerance to allow for
    # these legitimate boundary frames without imposing artificial hysteresis.
    assert pause == pytest.approx(15.0 / 30.0, abs=0.10)
    # Hard upper bound: never more than ~75% above the plateau frame count.
    assert pause <= 0.75


def test_session4_pause_duration_touch_and_go() -> None:
    """Touch-and-go rep with no plateau → bounded above by a small fraction."""
    n = 60
    angles = np.full(n, 170.0)
    angles[10:30] = np.linspace(170.0, 80.0, 20)
    angles[30:60] = np.linspace(80.0, 170.0, 30)
    pause = _pause_duration_s(
        primary_series=angles, start=0, end=59, depth_frame=29, fps=30.0
    )
    # The ±2° band catches a few adjacent ramping samples on each side; bound
    # loosely (no pause requested = under 0.20s).
    assert pause <= 0.20


def test_session4_pause_duration_degenerate_zero_length_rep() -> None:
    """Degenerate input (start == end) returns 0.0, no exception."""
    angles = np.full(10, 90.0)
    pause = _pause_duration_s(
        primary_series=angles, start=5, end=5, depth_frame=5, fps=30.0
    )
    assert pause == 0.0


# ---------------------------------------------------------------------------
# #12 lockout_torso_lean_deg (torso-vertical angle at rep peak-angle frame)
# ---------------------------------------------------------------------------


def _make_landmark_frame_right_side(
    shoulder_xy: tuple[float, float], hip_xy: tuple[float, float]
) -> np.ndarray:
    """Build a (33, 5) frame with right-side shoulder/hip set + visibility=0.9."""
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9   # visibility
    lm[:, 4] = 5.0   # presence pre-sigmoid → ~1.0 (avoids the col-4 gotcha)
    lm[12, :2] = shoulder_xy  # right shoulder
    lm[24, :2] = hip_xy       # right hip
    return lm


def _make_landmark_frame_left_side(
    shoulder_xy: tuple[float, float], hip_xy: tuple[float, float]
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    lm[11, :2] = shoulder_xy
    lm[23, :2] = hip_xy
    return lm


def test_session4_lockout_torso_lean_upright() -> None:
    """Shoulder directly above hip → 0° lean."""
    right_idx = landmark_indices_for_side("right")
    frame = _make_landmark_frame_right_side(
        shoulder_xy=(0.5, 0.1), hip_xy=(0.5, 0.5)
    )
    lean = _lockout_torso_lean_deg(
        landmarks_per_frame=[frame], end_frame=0, side_idx=right_idx
    )
    assert lean == pytest.approx(0.0, abs=0.5)


def test_session4_lockout_torso_lean_forward_15deg() -> None:
    """Shoulder forward of hip by tan(15°)·Δy → ~15° lean."""
    right_idx = landmark_indices_for_side("right")
    dy = 0.4
    dx = dy * math.tan(math.radians(15.0))
    frame = _make_landmark_frame_right_side(
        shoulder_xy=(0.5 + dx, 0.1), hip_xy=(0.5, 0.5)
    )
    lean = _lockout_torso_lean_deg(
        landmarks_per_frame=[frame], end_frame=0, side_idx=right_idx
    )
    assert lean == pytest.approx(15.0, abs=0.5)


def test_session4_lockout_torso_lean_backward_5deg() -> None:
    """Shoulder behind hip by tan(5°)·Δy → ~5° lean magnitude (unsigned)."""
    right_idx = landmark_indices_for_side("right")
    dy = 0.4
    dx = dy * math.tan(math.radians(5.0))
    frame = _make_landmark_frame_right_side(
        shoulder_xy=(0.5 - dx, 0.1), hip_xy=(0.5, 0.5)
    )
    lean = _lockout_torso_lean_deg(
        landmarks_per_frame=[frame], end_frame=0, side_idx=right_idx
    )
    assert lean == pytest.approx(5.0, abs=0.5)


def test_session4_lockout_torso_lean_out_of_bounds_returns_zero() -> None:
    """Degenerate end_frame returns 0.0, no exception."""
    right_idx = landmark_indices_for_side("right")
    frames = [_make_landmark_frame_right_side((0.5, 0.1), (0.5, 0.5))]
    assert _lockout_torso_lean_deg(frames, end_frame=99, side_idx=right_idx) == 0.0
    assert _lockout_torso_lean_deg(frames, end_frame=-1, side_idx=right_idx) == 0.0


# ---------------------------------------------------------------------------
# Side-agnosticism mirror tests per design Section-5 line 410
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lean_deg",
    [0.0, 5.0, 10.0, 15.0, 20.0],
)
def test_session4_lockout_torso_lean_side_agnostic(lean_deg: float) -> None:
    """Same pose populated on either side (x mirrored on left) → same lean."""
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    dy = 0.4
    dx = dy * math.tan(math.radians(lean_deg))

    right_frame = _make_landmark_frame_right_side(
        shoulder_xy=(0.5 + dx, 0.1), hip_xy=(0.5, 0.5)
    )
    # Mirror convention: x' = 1.0 - x (normalised), pose remains the same.
    left_frame = _make_landmark_frame_left_side(
        shoulder_xy=(1.0 - (0.5 + dx), 0.1),
        hip_xy=(1.0 - 0.5, 0.5),
    )

    right_lean = _lockout_torso_lean_deg(
        landmarks_per_frame=[right_frame], end_frame=0, side_idx=right_idx
    )
    left_lean = _lockout_torso_lean_deg(
        landmarks_per_frame=[left_frame], end_frame=0, side_idx=left_idx
    )
    assert right_lean == pytest.approx(left_lean, abs=0.5)


def test_session4_classify_depth_is_signal_only_so_side_agnostic_by_construction() -> None:
    """_classify_depth operates only on the depth_angle scalar, which is
    itself computed via side-aware indices upstream."""
    assert _classify_depth(85.0, 90.0) == "at_parallel"


def test_session4_pause_duration_is_signal_only_so_side_agnostic_by_construction() -> None:
    """_pause_duration_s consumes only a 1-D angle signal."""
    angles = np.full(60, 90.0)
    pause = _pause_duration_s(angles, start=0, end=59, depth_frame=30, fps=30.0)
    assert pause == pytest.approx(60.0 / 30.0, abs=1e-2)


# ---------------------------------------------------------------------------
# Analyzer integration — extract_rep_metrics emits exactly applicable keys
# ---------------------------------------------------------------------------


def _make_squat_session(n_frames: int = 60) -> tuple[list, dict[str, np.ndarray], DetectedRep]:
    frames = []
    for _ in range(n_frames):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[12, :2] = [0.5, 0.1]   # shoulder
        lm[24, :2] = [0.5, 0.5]   # hip
        lm[26, :2] = [0.5, 0.75]  # knee
        lm[28, :2] = [0.5, 0.95]  # ankle
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    hip = 125.0 + 45.0 * np.cos(t)
    knee = 110.0 + 40.0 * np.cos(t)
    ts = {"hip_angle": hip, "knee_angle": knee}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=n_frames - 1,
        confidence_score=0.9, min_angle=80.0,
    )
    return frames, ts, rep


def test_session4_squat_analyzer_emits_all_four_new_keys() -> None:
    frames, ts, rep = _make_squat_session(60)
    out = extract_rep_metrics(
        reps=[rep],
        landmarks_per_frame=frames,
        angle_timeseries=ts,
        exercise_type="squat",
        exercise_variant="standard",
        fps=30.0,
        lifter_side="right",
    )
    metrics = out[0].metrics
    assert "depth_classification" in metrics
    assert metrics["depth_classification"] in {"above_parallel", "at_parallel", "below_parallel"}
    assert "ecc_con_ratio" in metrics
    assert isinstance(metrics["ecc_con_ratio"], float)
    assert "pause_duration_s" in metrics
    assert isinstance(metrics["pause_duration_s"], float)
    assert "lockout_torso_lean_deg" in metrics
    assert isinstance(metrics["lockout_torso_lean_deg"], float)


def test_session4_bench_analyzer_emits_applicable_keys() -> None:
    """Bench: ecc_con_ratio + pause_duration_s.
    NOT depth_classification (squat only).
    NOT lockout_torso_lean_deg (squat + DL only — bench torso is supine)."""
    frames = []
    for _ in range(60):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[12, :2] = [0.5, 0.1]
        lm[14, :2] = [0.3, 0.35]
        lm[16, :2] = [0.2, 0.35]
        lm[24, :2] = [0.5, 0.5]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, 60)
    ts = {"elbow_angle": 115.0 + 50.0 * np.cos(t), "shoulder_angle": 70.0 + 20.0 * np.cos(t)}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=59,
        confidence_score=0.9, min_angle=65.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="bench", exercise_variant="flat", fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "ecc_con_ratio" in metrics
    assert "pause_duration_s" in metrics
    assert "depth_classification" not in metrics
    assert "lockout_torso_lean_deg" not in metrics


def test_session4_deadlift_analyzer_emits_applicable_keys() -> None:
    """Deadlift: ecc_con_ratio + pause_duration_s + lockout_torso_lean_deg.
    NOT depth_classification."""
    frames = []
    for _ in range(60):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[12, :2] = [0.5, 0.1]
        lm[24, :2] = [0.5, 0.5]
        lm[26, :2] = [0.5, 0.75]
        lm[28, :2] = [0.5, 0.95]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, 60)
    ts = {"hip_angle": 100.0 + 60.0 * np.cos(t), "knee_angle": 120.0 + 40.0 * np.cos(t)}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=59,
        confidence_score=0.9, min_angle=40.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="deadlift", exercise_variant="conventional",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "ecc_con_ratio" in metrics
    assert "pause_duration_s" in metrics
    assert "lockout_torso_lean_deg" in metrics
    assert "depth_classification" not in metrics


def test_session4_ecc_con_ratio_value_correct() -> None:
    """Synthetic balanced rep (descent ≈ ascent) → ratio ≈ 1.0."""
    frames, ts, rep = _make_squat_session(60)
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="squat", exercise_variant="standard", fps=30.0,
        lifter_side="right",
    )
    # Cosine signal: bottom is near the midpoint (frame 29 or 30). For a
    # balanced rep the ratio is close to 1.0; assert within ±0.10 tolerance
    # to cover the off-by-one between np.argmin tiebreaks.
    ratio = out[0].metrics["ecc_con_ratio"]
    assert isinstance(ratio, float)
    assert ratio == pytest.approx(1.0, abs=0.10)


# ---------------------------------------------------------------------------
# Pipeline aggregator forwarding (Task 10)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Session 5 — facing-sign helper
# ---------------------------------------------------------------------------


def test_session5_facing_sign_right_is_positive_one() -> None:
    from app.cv.metric_extraction import _facing_sign
    assert _facing_sign("right") == 1.0


def test_session5_facing_sign_left_is_negative_one() -> None:
    from app.cv.metric_extraction import _facing_sign
    assert _facing_sign("left") == -1.0


# ---------------------------------------------------------------------------
# Session 5 #1 — ankle_dorsiflexion_deg + heel_rise_flag (squat)
# ---------------------------------------------------------------------------


def _make_squat_bottom_frame(
    *,
    knee_xy: tuple[float, float],
    ankle_xy: tuple[float, float],
    foot_index_xy: tuple[float, float],
    heel_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    """Build a single (33, 5) frame with the four squat-bottom landmarks set."""
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9    # visibility
    lm[:, 4] = 5.0    # presence pre-sigmoid → ~1.0 (col-4 gotcha)
    idx = landmark_indices_for_side(side)
    lm[idx.knee, :2] = knee_xy
    lm[idx.ankle, :2] = ankle_xy
    lm[idx.foot_index, :2] = foot_index_xy
    lm[idx.heel, :2] = heel_xy
    return lm


def test_session5_ankle_dorsiflexion_textbook_squat() -> None:
    """Vertical shin + horizontal foot → ankle joint angle ≈ 90°."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_squat_bottom_frame(
        knee_xy=(0.5, 0.55),         # knee directly above ankle
        ankle_xy=(0.5, 0.90),
        foot_index_xy=(0.65, 0.90),  # foot forward at same y
        heel_xy=(0.42, 0.90),
    )
    angle = _ankle_dorsiflexion_deg(frame, right_idx)
    assert angle == pytest.approx(90.0, abs=2.0)


def test_session5_ankle_dorsiflexion_forward_knee_travel() -> None:
    """Knee forward of ankle (deep squat dorsiflexion) → ankle angle < 90°."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_squat_bottom_frame(
        knee_xy=(0.65, 0.55),        # knee 0.15 forward of ankle
        ankle_xy=(0.5, 0.90),
        foot_index_xy=(0.65, 0.90),
        heel_xy=(0.42, 0.90),
    )
    angle = _ankle_dorsiflexion_deg(frame, right_idx)
    # Knee vector (0.15, -0.35) and foot vector (0.15, 0). Dot product positive,
    # smaller angle than the vertical-shin case.
    assert angle < 90.0
    assert angle > 0.0


def test_session5_ankle_dorsiflexion_low_visibility_returns_none() -> None:
    """Any required landmark below visibility 0.30 → None."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_squat_bottom_frame(
        knee_xy=(0.5, 0.55), ankle_xy=(0.5, 0.90),
        foot_index_xy=(0.65, 0.90), heel_xy=(0.42, 0.90),
    )
    frame[right_idx.ankle, 3] = 0.10  # ankle visibility crashed
    assert _ankle_dorsiflexion_deg(frame, right_idx) is None


def test_session5_ankle_dorsiflexion_degenerate_zero_vector_returns_none() -> None:
    """Zero-length knee vector (knee == ankle) → None, no exception."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_squat_bottom_frame(
        knee_xy=(0.5, 0.90),         # coincident with ankle
        ankle_xy=(0.5, 0.90),
        foot_index_xy=(0.65, 0.90),
        heel_xy=(0.42, 0.90),
    )
    assert _ankle_dorsiflexion_deg(frame, right_idx) is None


@pytest.mark.parametrize("knee_dx", [0.0, 0.10, 0.15, 0.20])
def test_session5_ankle_dorsiflexion_side_agnostic(knee_dx: float) -> None:
    """Same pose populated on either side (x mirrored on left) → same angle."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frame = _make_squat_bottom_frame(
        knee_xy=(0.5 + knee_dx, 0.55),
        ankle_xy=(0.5, 0.90),
        foot_index_xy=(0.65, 0.90),
        heel_xy=(0.42, 0.90),
        side="right",
    )
    left_frame = _make_squat_bottom_frame(
        knee_xy=(1.0 - (0.5 + knee_dx), 0.55),
        ankle_xy=(1.0 - 0.5, 0.90),
        foot_index_xy=(1.0 - 0.65, 0.90),
        heel_xy=(1.0 - 0.42, 0.90),
        side="left",
    )
    right_angle = _ankle_dorsiflexion_deg(right_frame, right_idx)
    left_angle = _ankle_dorsiflexion_deg(left_frame, left_idx)
    assert right_angle is not None and left_angle is not None
    assert right_angle == pytest.approx(left_angle, abs=0.5)


# heel_rise_flag tests ------------------------------------------------------


def _make_heel_y_series(
    n_frames: int,
    *,
    baseline_y: float = 0.90,
    rise_start: int | None = None,
    rise_amount: float = 0.05,
    rise_frames: int = 5,
) -> list[np.ndarray]:
    """Build n_frames worth of (33,5) arrays with right-heel y populated."""
    right_idx = landmark_indices_for_side("right")
    frames: list[np.ndarray] = []
    for i in range(n_frames):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        y = baseline_y
        if rise_start is not None and rise_start <= i < rise_start + rise_frames:
            y = baseline_y - rise_amount  # heel moved up in image
        lm[right_idx.heel, :2] = (0.42, y)
        frames.append(lm)
    return frames


def test_session5_heel_rise_textbook_squat_no_rise() -> None:
    """Heel stays at baseline → flag False."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    frames = _make_heel_y_series(20)
    assert _heel_rise_flag(frames, start=0, depth_frame=15, side_idx=right_idx) is False


def test_session5_heel_rise_sustained_rise_above_threshold() -> None:
    """Heel rises by 0.05 (> 0.02 threshold) for 5 consecutive frames → True."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    frames = _make_heel_y_series(
        20, rise_start=8, rise_amount=0.05, rise_frames=5,
    )
    assert _heel_rise_flag(frames, start=0, depth_frame=15, side_idx=right_idx) is True


def test_session5_heel_rise_noise_spike_under_three_frames() -> None:
    """Heel rises by 0.05 but for only 2 consecutive frames → False (noise)."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    frames = _make_heel_y_series(
        20, rise_start=8, rise_amount=0.05, rise_frames=2,
    )
    assert _heel_rise_flag(frames, start=0, depth_frame=15, side_idx=right_idx) is False


def test_session5_heel_rise_below_threshold_returns_false() -> None:
    """Heel rises by 0.01 (< 0.02 threshold) for many frames → False."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    frames = _make_heel_y_series(
        20, rise_start=8, rise_amount=0.01, rise_frames=6,
    )
    assert _heel_rise_flag(frames, start=0, depth_frame=15, side_idx=right_idx) is False


def test_session5_heel_rise_degenerate_short_rep() -> None:
    """start == depth_frame (rep too short for baseline) → False, no exception."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    frames = _make_heel_y_series(10)
    assert _heel_rise_flag(frames, start=5, depth_frame=5, side_idx=right_idx) is False


def test_session5_heel_rise_side_agnostic() -> None:
    """Same rise pattern on right-heel vs mirrored left-heel → same flag."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frames = _make_heel_y_series(
        20, rise_start=8, rise_amount=0.05, rise_frames=5,
    )
    # Build a mirrored left-side variant: same y dynamic, mirrored x, populated
    # at the left-heel index.
    left_frames: list[np.ndarray] = []
    for i, rf in enumerate(right_frames):
        lf = np.zeros((33, 5), dtype=float)
        lf[:, 3] = 0.9
        lf[:, 4] = 5.0
        rx, ry = rf[right_idx.heel, 0], rf[right_idx.heel, 1]
        lf[left_idx.heel, :2] = (1.0 - rx, ry)
        left_frames.append(lf)
    right_flag = _heel_rise_flag(right_frames, start=0, depth_frame=15, side_idx=right_idx)
    left_flag = _heel_rise_flag(left_frames, start=0, depth_frame=15, side_idx=left_idx)
    assert right_flag == left_flag is True


# ---------------------------------------------------------------------------
# Session 5 #3 — wrist_alignment_deg (bench)
# ---------------------------------------------------------------------------


def _make_bench_bottom_frame(
    *,
    wrist_xy: tuple[float, float],
    elbow_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.wrist, :2] = wrist_xy
    lm[idx.elbow, :2] = elbow_xy
    return lm


def test_session5_wrist_alignment_stacked() -> None:
    """Wrist directly above elbow → 0°."""
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_bottom_frame(wrist_xy=(0.50, 0.40), elbow_xy=(0.50, 0.55))
    assert _wrist_alignment_deg(frame, right_idx, "right") == pytest.approx(0.0, abs=0.5)


def test_session5_wrist_alignment_anterior() -> None:
    """Wrist forward of elbow (right-facing) → positive angle."""
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    dy = 0.15
    dx = dy * math.tan(math.radians(20.0))
    frame = _make_bench_bottom_frame(
        wrist_xy=(0.50 + dx, 0.40), elbow_xy=(0.50, 0.55),
    )
    assert _wrist_alignment_deg(frame, right_idx, "right") == pytest.approx(20.0, abs=0.5)


def test_session5_wrist_alignment_posterior_negative() -> None:
    """Wrist behind elbow (right-facing) → negative angle."""
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    dy = 0.15
    dx = dy * math.tan(math.radians(10.0))
    frame = _make_bench_bottom_frame(
        wrist_xy=(0.50 - dx, 0.40), elbow_xy=(0.50, 0.55),
    )
    assert _wrist_alignment_deg(frame, right_idx, "right") == pytest.approx(-10.0, abs=0.5)


def test_session5_wrist_alignment_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_bottom_frame(wrist_xy=(0.50, 0.40), elbow_xy=(0.50, 0.55))
    frame[right_idx.wrist, 3] = 0.05
    assert _wrist_alignment_deg(frame, right_idx, "right") is None


def test_session5_wrist_alignment_degenerate_coincident_returns_none() -> None:
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_bottom_frame(wrist_xy=(0.50, 0.55), elbow_xy=(0.50, 0.55))
    assert _wrist_alignment_deg(frame, right_idx, "right") is None


@pytest.mark.parametrize("anterior_deg", [-20.0, -5.0, 0.0, 5.0, 20.0])
def test_session5_wrist_alignment_side_agnostic(anterior_deg: float) -> None:
    """Same pose right-vs-mirrored-left → same signed angle (facing-sign applied)."""
    from app.cv.metric_extraction import _wrist_alignment_deg
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    dy = 0.15
    dx = dy * math.tan(math.radians(anterior_deg))
    right_frame = _make_bench_bottom_frame(
        wrist_xy=(0.50 + dx, 0.40), elbow_xy=(0.50, 0.55), side="right",
    )
    left_frame = _make_bench_bottom_frame(
        wrist_xy=(1.0 - (0.50 + dx), 0.40),
        elbow_xy=(1.0 - 0.50, 0.55),
        side="left",
    )
    r = _wrist_alignment_deg(right_frame, right_idx, "right")
    L = _wrist_alignment_deg(left_frame, left_idx, "left")
    assert r is not None and L is not None
    assert r == pytest.approx(L, abs=0.5)


# ---------------------------------------------------------------------------
# Session 5 #5 — bar_touch_height_pct (bench)
# ---------------------------------------------------------------------------


def _make_bench_touch_frame(
    *,
    wrist_y: float,
    shoulder_y: float,
    hip_y: float,
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.wrist, :2] = (0.30, wrist_y)
    lm[idx.shoulder, :2] = (0.50, shoulder_y)
    lm[idx.hip, :2] = (0.55, hip_y)
    return lm


def test_session5_bar_touch_height_at_shoulder() -> None:
    """wrist_y == shoulder_y → 0.0."""
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_touch_frame(wrist_y=0.40, shoulder_y=0.40, hip_y=0.60)
    assert _bar_touch_height_pct(frame, right_idx) == pytest.approx(0.0, abs=1e-6)


def test_session5_bar_touch_height_midway() -> None:
    """wrist halfway between shoulder and hip → 0.5."""
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_touch_frame(wrist_y=0.50, shoulder_y=0.40, hip_y=0.60)
    assert _bar_touch_height_pct(frame, right_idx) == pytest.approx(0.5, abs=1e-6)


def test_session5_bar_touch_height_at_hip() -> None:
    """wrist at hip level → 1.0."""
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_touch_frame(wrist_y=0.60, shoulder_y=0.40, hip_y=0.60)
    assert _bar_touch_height_pct(frame, right_idx) == pytest.approx(1.0, abs=1e-6)


def test_session5_bar_touch_height_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_touch_frame(wrist_y=0.50, shoulder_y=0.40, hip_y=0.60)
    frame[right_idx.hip, 3] = 0.10
    assert _bar_touch_height_pct(frame, right_idx) is None


def test_session5_bar_touch_height_degenerate_shoulder_eq_hip_returns_none() -> None:
    """shoulder_y == hip_y (zero span) → None, no division by zero."""
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    frame = _make_bench_touch_frame(wrist_y=0.50, shoulder_y=0.50, hip_y=0.50)
    assert _bar_touch_height_pct(frame, right_idx) is None


def test_session5_bar_touch_height_side_agnostic() -> None:
    """Same y-coordinates on either side → same ratio (y-only math)."""
    from app.cv.metric_extraction import _bar_touch_height_pct
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frame = _make_bench_touch_frame(
        wrist_y=0.50, shoulder_y=0.40, hip_y=0.60, side="right",
    )
    left_frame = _make_bench_touch_frame(
        wrist_y=0.50, shoulder_y=0.40, hip_y=0.60, side="left",
    )
    r = _bar_touch_height_pct(right_frame, right_idx)
    L = _bar_touch_height_pct(left_frame, left_idx)
    assert r == pytest.approx(L, abs=1e-9)


# ---------------------------------------------------------------------------
# Session 5 #10 — setup_shoulder_x_offset (deadlift)
# ---------------------------------------------------------------------------


def _make_dl_setup_frame(
    *,
    shoulder_xy: tuple[float, float],
    wrist_xy: tuple[float, float],
    elbow_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.shoulder, :2] = shoulder_xy
    lm[idx.wrist, :2] = wrist_xy
    lm[idx.elbow, :2] = elbow_xy
    return lm


def test_session5_setup_shoulder_offset_over_bar() -> None:
    """Shoulders directly above wrist → offset ≈ 0."""
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_setup_frame(
        shoulder_xy=(0.50, 0.30),
        wrist_xy=(0.50, 0.85),
        elbow_xy=(0.50, 0.60),  # forearm length ~0.25, vertical
    )
    val = _setup_shoulder_x_offset(frame, right_idx, "right")
    assert val == pytest.approx(0.0, abs=0.02)


def test_session5_setup_shoulder_offset_shoulders_ahead() -> None:
    """Shoulders 0.05 forward of wrist, forearm ≈ 0.25 → +0.20 normalised."""
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_setup_frame(
        shoulder_xy=(0.55, 0.30),     # 0.05 forward of wrist
        wrist_xy=(0.50, 0.85),
        elbow_xy=(0.50, 0.60),         # forearm length 0.25
    )
    val = _setup_shoulder_x_offset(frame, right_idx, "right")
    assert val == pytest.approx(0.05 / 0.25, abs=0.02)


def test_session5_setup_shoulder_offset_shoulders_behind_negative() -> None:
    """Shoulders behind wrist (right-facing) → negative offset."""
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_setup_frame(
        shoulder_xy=(0.45, 0.30),
        wrist_xy=(0.50, 0.85),
        elbow_xy=(0.50, 0.60),
    )
    val = _setup_shoulder_x_offset(frame, right_idx, "right")
    assert val < 0.0
    assert val == pytest.approx(-0.05 / 0.25, abs=0.02)


def test_session5_setup_shoulder_offset_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_setup_frame(
        shoulder_xy=(0.55, 0.30), wrist_xy=(0.50, 0.85), elbow_xy=(0.50, 0.60),
    )
    frame[right_idx.elbow, 3] = 0.10
    assert _setup_shoulder_x_offset(frame, right_idx, "right") is None


def test_session5_setup_shoulder_offset_zero_forearm_returns_none() -> None:
    """elbow == wrist → forearm length 0 → None."""
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_setup_frame(
        shoulder_xy=(0.55, 0.30),
        wrist_xy=(0.50, 0.85),
        elbow_xy=(0.50, 0.85),  # coincident with wrist
    )
    assert _setup_shoulder_x_offset(frame, right_idx, "right") is None


@pytest.mark.parametrize("shoulder_dx", [-0.05, -0.02, 0.0, 0.02, 0.05])
def test_session5_setup_shoulder_offset_side_agnostic(shoulder_dx: float) -> None:
    from app.cv.metric_extraction import _setup_shoulder_x_offset
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frame = _make_dl_setup_frame(
        shoulder_xy=(0.50 + shoulder_dx, 0.30),
        wrist_xy=(0.50, 0.85),
        elbow_xy=(0.50, 0.60),
        side="right",
    )
    left_frame = _make_dl_setup_frame(
        shoulder_xy=(1.0 - (0.50 + shoulder_dx), 0.30),
        wrist_xy=(1.0 - 0.50, 0.85),
        elbow_xy=(1.0 - 0.50, 0.60),
        side="left",
    )
    r = _setup_shoulder_x_offset(right_frame, right_idx, "right")
    L = _setup_shoulder_x_offset(left_frame, left_idx, "left")
    assert r is not None and L is not None
    assert r == pytest.approx(L, abs=0.02)


# ---------------------------------------------------------------------------
# Session 5 #11 — shin_angle_deg (squat)
# ---------------------------------------------------------------------------


def _make_shin_frame(
    *,
    knee_xy: tuple[float, float],
    ankle_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.knee, :2] = knee_xy
    lm[idx.ankle, :2] = ankle_xy
    return lm


def test_session5_shin_angle_vertical() -> None:
    """Knee directly above ankle → 0°."""
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_shin_frame(knee_xy=(0.50, 0.55), ankle_xy=(0.50, 0.90))
    assert _shin_angle_deg(frame, right_idx, "right") == pytest.approx(0.0, abs=0.5)


def test_session5_shin_angle_forward_lean_20deg() -> None:
    """Knee 0.35 * tan(20°) forward of ankle → +20° forward."""
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    dy = 0.35
    dx = dy * math.tan(math.radians(20.0))
    frame = _make_shin_frame(knee_xy=(0.50 + dx, 0.55), ankle_xy=(0.50, 0.90))
    assert _shin_angle_deg(frame, right_idx, "right") == pytest.approx(20.0, abs=0.5)


def test_session5_shin_angle_backward_lean_negative() -> None:
    """Knee behind ankle (rare/wrong technique) → negative angle."""
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    dy = 0.35
    dx = dy * math.tan(math.radians(5.0))
    frame = _make_shin_frame(knee_xy=(0.50 - dx, 0.55), ankle_xy=(0.50, 0.90))
    assert _shin_angle_deg(frame, right_idx, "right") == pytest.approx(-5.0, abs=0.5)


def test_session5_shin_angle_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_shin_frame(knee_xy=(0.50, 0.55), ankle_xy=(0.50, 0.90))
    frame[right_idx.knee, 3] = 0.05
    assert _shin_angle_deg(frame, right_idx, "right") is None


def test_session5_shin_angle_degenerate_coincident_returns_none() -> None:
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_shin_frame(knee_xy=(0.50, 0.90), ankle_xy=(0.50, 0.90))
    assert _shin_angle_deg(frame, right_idx, "right") is None


@pytest.mark.parametrize("lean_deg", [-10.0, -2.0, 0.0, 2.0, 10.0, 25.0])
def test_session5_shin_angle_side_agnostic(lean_deg: float) -> None:
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    dy = 0.35
    dx = dy * math.tan(math.radians(lean_deg))
    right_frame = _make_shin_frame(
        knee_xy=(0.50 + dx, 0.55), ankle_xy=(0.50, 0.90), side="right",
    )
    left_frame = _make_shin_frame(
        knee_xy=(1.0 - (0.50 + dx), 0.55), ankle_xy=(1.0 - 0.50, 0.90), side="left",
    )
    r = _shin_angle_deg(right_frame, right_idx, "right")
    L = _shin_angle_deg(left_frame, left_idx, "left")
    assert r is not None and L is not None
    assert r == pytest.approx(L, abs=0.5)


# ---------------------------------------------------------------------------
# Session 5 #13 — setup_knee_angle_deg (deadlift)
# ---------------------------------------------------------------------------


def _make_dl_knee_frame(
    *,
    hip_xy: tuple[float, float],
    knee_xy: tuple[float, float],
    ankle_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.hip, :2] = hip_xy
    lm[idx.knee, :2] = knee_xy
    lm[idx.ankle, :2] = ankle_xy
    return lm


def test_session5_setup_knee_angle_straight_leg() -> None:
    """Hip, knee, ankle collinear → 180°."""
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_knee_frame(
        hip_xy=(0.50, 0.30), knee_xy=(0.50, 0.60), ankle_xy=(0.50, 0.90),
    )
    assert _setup_knee_angle_deg(frame, right_idx) == pytest.approx(180.0, abs=1.0)


def test_session5_setup_knee_angle_right_angle_squat_pull() -> None:
    """Hip directly above knee, knee directly above ankle, both at right
    angle → 90°."""
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_knee_frame(
        hip_xy=(0.30, 0.60),    # hip 0.20 behind knee, same y
        knee_xy=(0.50, 0.60),
        ankle_xy=(0.50, 0.80),  # ankle 0.20 below knee, same x
    )
    assert _setup_knee_angle_deg(frame, right_idx) == pytest.approx(90.0, abs=1.0)


def test_session5_setup_knee_angle_hip_hinge_140() -> None:
    """Typical deadlift hip-hinge setup → 130-150° range."""
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_knee_frame(
        hip_xy=(0.35, 0.45),
        knee_xy=(0.50, 0.65),
        ankle_xy=(0.50, 0.95),
    )
    val = _setup_knee_angle_deg(frame, right_idx)
    assert val is not None
    assert 120.0 <= val <= 160.0


def test_session5_setup_knee_angle_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_knee_frame(
        hip_xy=(0.50, 0.30), knee_xy=(0.50, 0.60), ankle_xy=(0.50, 0.90),
    )
    frame[right_idx.knee, 3] = 0.05
    assert _setup_knee_angle_deg(frame, right_idx) is None


def test_session5_setup_knee_angle_degenerate_coincident_returns_none() -> None:
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    frame = _make_dl_knee_frame(
        hip_xy=(0.50, 0.60), knee_xy=(0.50, 0.60), ankle_xy=(0.50, 0.90),
    )
    assert _setup_knee_angle_deg(frame, right_idx) is None


def test_session5_setup_knee_angle_side_agnostic() -> None:
    from app.cv.metric_extraction import _setup_knee_angle_deg
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frame = _make_dl_knee_frame(
        hip_xy=(0.35, 0.45), knee_xy=(0.50, 0.65), ankle_xy=(0.50, 0.95),
        side="right",
    )
    left_frame = _make_dl_knee_frame(
        hip_xy=(1.0 - 0.35, 0.45), knee_xy=(1.0 - 0.50, 0.65),
        ankle_xy=(1.0 - 0.50, 0.95), side="left",
    )
    r = _setup_knee_angle_deg(right_frame, right_idx)
    L = _setup_knee_angle_deg(left_frame, left_idx)
    assert r is not None and L is not None
    assert r == pytest.approx(L, abs=0.5)


# ---------------------------------------------------------------------------
# Session 5 #15 — arch_deg (bench)
# ---------------------------------------------------------------------------


def _make_bench_arch_frame(
    *,
    shoulder_xy: tuple[float, float],
    hip_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.shoulder, :2] = shoulder_xy
    lm[idx.hip, :2] = hip_xy
    return lm


def test_session5_arch_deg_flat_back() -> None:
    """Shoulder and hip at the same y, hip 0.30 anterior → 0° arch
    (flat horizontal supine body)."""
    from app.cv.metric_extraction import _arch_deg
    frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.50), hip_xy=(0.60, 0.50))
        for _ in range(20)
    ]
    right_idx = landmark_indices_for_side("right")
    val = _arch_deg(frames, non_rep_frame_mask=[True] * 20,
                    side_idx=right_idx, side="right")
    assert val == pytest.approx(0.0, abs=0.5)


def test_session5_arch_deg_pronounced_arch() -> None:
    """Hips 0.05 above shoulders (smaller y = higher in image) with 0.30
    horizontal separation → positive arch around 9-10°."""
    from app.cv.metric_extraction import _arch_deg
    frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.55), hip_xy=(0.60, 0.50))
        for _ in range(20)
    ]
    right_idx = landmark_indices_for_side("right")
    val = _arch_deg(frames, non_rep_frame_mask=[True] * 20,
                    side_idx=right_idx, side="right")
    assert val is not None
    # atan2(0.05, 0.30) ≈ 9.46°
    assert val == pytest.approx(9.46, abs=0.5)


def test_session5_arch_deg_low_arch() -> None:
    """Hips marginally above shoulders → small positive angle."""
    from app.cv.metric_extraction import _arch_deg
    frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.51), hip_xy=(0.60, 0.50))
        for _ in range(20)
    ]
    right_idx = landmark_indices_for_side("right")
    val = _arch_deg(frames, non_rep_frame_mask=[True] * 20,
                    side_idx=right_idx, side="right")
    assert val is not None
    assert 0.5 <= val <= 5.0


def test_session5_arch_deg_no_non_rep_frames_returns_none() -> None:
    """Empty non-rep window → None."""
    from app.cv.metric_extraction import _arch_deg
    frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.55), hip_xy=(0.60, 0.50))
        for _ in range(10)
    ]
    right_idx = landmark_indices_for_side("right")
    val = _arch_deg(frames, non_rep_frame_mask=[False] * 10,
                    side_idx=right_idx, side="right")
    assert val is None


def test_session5_arch_deg_all_low_visibility_returns_none() -> None:
    from app.cv.metric_extraction import _arch_deg
    right_idx = landmark_indices_for_side("right")
    frames = []
    for _ in range(10):
        f = _make_bench_arch_frame(shoulder_xy=(0.30, 0.55), hip_xy=(0.60, 0.50))
        f[right_idx.shoulder, 3] = 0.05
        f[right_idx.hip, 3] = 0.05
        frames.append(f)
    val = _arch_deg(frames, non_rep_frame_mask=[True] * 10,
                    side_idx=right_idx, side="right")
    assert val is None


def test_session5_arch_deg_side_agnostic() -> None:
    """Same arch on right-vs-mirrored-left → same signed value."""
    from app.cv.metric_extraction import _arch_deg
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.55), hip_xy=(0.60, 0.50),
                               side="right")
        for _ in range(20)
    ]
    left_frames = [
        _make_bench_arch_frame(shoulder_xy=(1.0 - 0.30, 0.55),
                               hip_xy=(1.0 - 0.60, 0.50), side="left")
        for _ in range(20)
    ]
    r = _arch_deg(right_frames, non_rep_frame_mask=[True] * 20,
                  side_idx=right_idx, side="right")
    L = _arch_deg(left_frames, non_rep_frame_mask=[True] * 20,
                  side_idx=left_idx, side="left")
    assert r is not None and L is not None
    assert r == pytest.approx(L, abs=0.5)


# ---------------------------------------------------------------------------
# Session 5 — per-exercise analyzer key emission
# ---------------------------------------------------------------------------


def _make_full_squat_session_with_landmarks(n_frames: int = 60):
    """Squat session helper populated for Session 5 squat extractors."""
    frames = []
    right_idx = landmark_indices_for_side("right")
    for _ in range(n_frames):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[right_idx.shoulder, :2] = [0.50, 0.10]
        lm[right_idx.hip, :2] = [0.50, 0.50]
        lm[right_idx.knee, :2] = [0.55, 0.70]   # slight forward knee travel
        lm[right_idx.ankle, :2] = [0.50, 0.92]
        lm[right_idx.foot_index, :2] = [0.65, 0.92]
        lm[right_idx.heel, :2] = [0.42, 0.92]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    hip = 125.0 + 45.0 * np.cos(t)
    knee = 110.0 + 40.0 * np.cos(t)
    ts = {"hip_angle": hip, "knee_angle": knee}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=n_frames - 1,
        confidence_score=0.9, min_angle=80.0,
    )
    return frames, ts, rep


def test_session5_squat_analyzer_emits_session5_keys() -> None:
    frames, ts, rep = _make_full_squat_session_with_landmarks(60)
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="squat", exercise_variant="standard",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "ankle_dorsiflexion_deg" in metrics
    assert "heel_rise_flag" in metrics
    assert "shin_angle_deg" in metrics
    # Bench-only / DL-only keys must NOT appear on squat output.
    assert "wrist_alignment_deg" not in metrics
    assert "bar_touch_height_pct" not in metrics
    assert "arch_deg" not in metrics
    assert "setup_shoulder_x_offset" not in metrics
    assert "setup_knee_angle_deg" not in metrics


def test_session5_bench_analyzer_emits_session5_keys() -> None:
    frames = []
    right_idx = landmark_indices_for_side("right")
    for _ in range(60):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[right_idx.shoulder, :2] = [0.30, 0.55]   # arch pose
        lm[right_idx.elbow, :2] = [0.40, 0.42]
        lm[right_idx.wrist, :2] = [0.42, 0.30]
        lm[right_idx.hip, :2] = [0.60, 0.50]        # hips higher → arch +
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, 60)
    ts = {"elbow_angle": 115.0 + 50.0 * np.cos(t),
          "shoulder_angle": 70.0 + 20.0 * np.cos(t)}
    rep = DetectedRep(
        rep_index=0, start_frame=10, end_frame=49,
        confidence_score=0.9, min_angle=65.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="bench", exercise_variant="flat",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "wrist_alignment_deg" in metrics
    assert "bar_touch_height_pct" in metrics
    assert "arch_deg" in metrics
    assert "ankle_dorsiflexion_deg" not in metrics
    assert "heel_rise_flag" not in metrics
    assert "shin_angle_deg" not in metrics
    assert "setup_shoulder_x_offset" not in metrics
    assert "setup_knee_angle_deg" not in metrics


def test_session5_deadlift_analyzer_emits_session5_keys() -> None:
    frames = []
    right_idx = landmark_indices_for_side("right")
    for _ in range(60):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[right_idx.shoulder, :2] = [0.55, 0.45]   # shoulders over bar
        lm[right_idx.elbow, :2] = [0.50, 0.70]
        lm[right_idx.wrist, :2] = [0.50, 0.85]
        lm[right_idx.hip, :2] = [0.40, 0.55]
        lm[right_idx.knee, :2] = [0.50, 0.70]
        lm[right_idx.ankle, :2] = [0.50, 0.92]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, 60)
    ts = {"hip_angle": 100.0 + 60.0 * np.cos(t),
          "knee_angle": 120.0 + 40.0 * np.cos(t)}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=59,
        confidence_score=0.9, min_angle=40.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="deadlift", exercise_variant="conventional",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "setup_shoulder_x_offset" in metrics
    assert "setup_knee_angle_deg" in metrics
    assert "ankle_dorsiflexion_deg" not in metrics
    assert "heel_rise_flag" not in metrics
    assert "shin_angle_deg" not in metrics
    assert "wrist_alignment_deg" not in metrics
    assert "bar_touch_height_pct" not in metrics
    assert "arch_deg" not in metrics


def test_session4_pipeline_aggregate_passes_through_session4_keys() -> None:
    """The aggregator that feeds OverallFormScore must propagate
    depth_classification (modal string) and ecc_con_ratio (mean float)."""
    from app.cv.metric_extraction import RepMetrics
    from app.services.pipeline import _aggregate_rep_metrics

    rep_metrics = [
        RepMetrics(
            rep_index=0, start_frame=0, end_frame=29,
            metrics={
                "depth_classification": "above_parallel",
                "ecc_con_ratio": 0.6,
                "depth_angle": 95.0,
            },
        ),
        RepMetrics(
            rep_index=1, start_frame=30, end_frame=59,
            metrics={
                "depth_classification": "above_parallel",
                "ecc_con_ratio": 0.8,
                "depth_angle": 95.0,
            },
        ),
        RepMetrics(
            rep_index=2, start_frame=60, end_frame=89,
            metrics={
                "depth_classification": "at_parallel",
                "ecc_con_ratio": 1.0,
                "depth_angle": 90.0,
            },
        ),
    ]
    reps = [
        DetectedRep(
            rep_index=r.rep_index, start_frame=r.start_frame, end_frame=r.end_frame,
            confidence_score=0.9, min_angle=80.0,
        )
        for r in rep_metrics
    ]
    agg = _aggregate_rep_metrics(rep_metrics, reps, session_confidence=0.9)
    # ecc_con_ratio is the mean across reps (0.6, 0.8, 1.0 → 0.8).
    assert agg["ecc_con_ratio"] == pytest.approx(0.8, abs=0.01)
    # depth_classification is the modal label (2× above_parallel → above_parallel).
    assert agg["depth_classification"] == "above_parallel"


# ---------------------------------------------------------------------------
# Session 5 — defensive guard coverage (Task 14 Step 4)
# These tests target specific lines reported as uncovered by coverage tooling.
# ---------------------------------------------------------------------------


# --- _heel_rise_flag defensive guards (lines 653, 656, 662-663) ---


def test_session5_heel_rise_low_visibility_during_baseline_returns_false() -> None:
    """All baseline frames have heel visibility below _S5_MIN_VIS → no
    baseline_ys collected → return False (covers line 656)."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    # Build 20 frames; set heel visibility to 0.10 for the first 5 (baseline window).
    frames: list[np.ndarray] = []
    for i in range(20):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[right_idx.heel, :2] = (0.42, 0.90)
        # Baseline frames (0-4): crash heel visibility so they are skipped (line 653).
        if i < 5:
            lm[right_idx.heel, 3] = 0.10
        frames.append(lm)
    result = _heel_rise_flag(frames, start=0, depth_frame=15, side_idx=right_idx)
    assert result is False


def test_session5_heel_rise_low_visibility_during_detection_resets_triggered() -> None:
    """A low-visibility heel frame mid-detection resets the consecutive-frame
    counter (covers lines 662-663).  Pattern: 2 rising frames → invisible frame
    → 2 more rising frames → total consecutive never reaches 3 → False."""
    from app.cv.metric_extraction import _heel_rise_flag
    right_idx = landmark_indices_for_side("right")
    baseline_y = 0.90
    rise_y = baseline_y - 0.05  # above threshold (0.02)
    n = 20
    frames: list[np.ndarray] = []
    for i in range(n):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        # Baseline frames 0-4: heel at baseline_y, visible.
        y = baseline_y
        vis = 0.9
        if i == 7 or i == 8:
            # Two rising frames.
            y = rise_y
        elif i == 9:
            # Invisible frame mid-streak — resets triggered counter (lines 662-663).
            vis = 0.10
        elif i == 10 or i == 11:
            # Two more rising frames (counter restarts from 0, never reaches 3).
            y = rise_y
        lm[right_idx.heel, :2] = (0.42, y)
        lm[right_idx.heel, 3] = vis
        frames.append(lm)
    result = _heel_rise_flag(frames, start=0, depth_frame=15, side_idx=right_idx)
    assert result is False


# --- _arch_deg defensive guards (lines 804, 826) ---


def test_session5_arch_deg_mismatched_length_returns_none() -> None:
    """len(landmarks_per_frame) != len(non_rep_frame_mask) → return None (line 804)."""
    from app.cv.metric_extraction import _arch_deg
    right_idx = landmark_indices_for_side("right")
    frames = [
        _make_bench_arch_frame(shoulder_xy=(0.30, 0.55), hip_xy=(0.60, 0.50))
        for _ in range(10)
    ]
    # Mask length differs from frames length — triggers the guard.
    result = _arch_deg(frames, non_rep_frame_mask=[True] * 7,
                       side_idx=right_idx, side="right")
    assert result is None


def test_session5_arch_deg_degenerate_zero_mean_vector_returns_none() -> None:
    """After averaging, dx_mean and dy_mean are both < _S5_DEGENERATE_MAGNITUDE
    (shoulder and hip at identical position) → return None (line 826)."""
    from app.cv.metric_extraction import _arch_deg
    right_idx = landmark_indices_for_side("right")
    # shoulder_xy == hip_xy → dx=0, dy=0 → zero mean vector.
    frames = [
        _make_bench_arch_frame(shoulder_xy=(0.50, 0.50), hip_xy=(0.50, 0.50))
        for _ in range(10)
    ]
    result = _arch_deg(frames, non_rep_frame_mask=[True] * 10,
                       side_idx=right_idx, side="right")
    assert result is None


# --- extract_rep_metrics public API defensive guards (lines 894, 899) ---


def test_session5_extract_rep_metrics_empty_reps_returns_empty_list() -> None:
    """reps=[] → return [] without entering the exercise dispatch (line 894)."""
    out = extract_rep_metrics(
        reps=[],
        landmarks_per_frame=[np.zeros((33, 5))],
        angle_timeseries={"hip_angle": np.zeros(1)},
        exercise_type="squat",
        exercise_variant="standard",
        fps=30.0,
    )
    assert out == []


def test_session5_extract_rep_metrics_unknown_exercise_raises_value_error() -> None:
    """exercise_type not in ('squat','bench','deadlift') → ValueError (line 899)."""
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=9,
        confidence_score=0.9, min_angle=90.0,
    )
    frames = [np.zeros((33, 5)) for _ in range(10)]
    with pytest.raises(ValueError, match="overhead_press"):
        extract_rep_metrics(
            reps=[rep],
            landmarks_per_frame=frames,
            angle_timeseries={"elbow_angle": np.zeros(10)},
            exercise_type="overhead_press",
            exercise_variant="barbell",
            fps=30.0,
        )


# ---------------------------------------------------------------------------
# Session 6 — Bar-coordinate math
# ---------------------------------------------------------------------------


def test_session6_identify_liftoff_frame_happy_path() -> None:
    """Bar held still for 10 frames, then rises 5% over the next 10 → liftoff
    at the first frame strictly past the 2% threshold."""
    from app.cv.metric_extraction import identify_liftoff_frame
    n = 30
    bar_y = np.full(n, 0.80)
    bar_y[11:21] = np.linspace(0.80, 0.75, 10)  # rises (y decreases) starting frame 11
    bar_y[21:] = 0.75
    out = identify_liftoff_frame(bar_y, setup_frame=0, end_frame=n - 1, threshold_pct=0.02)
    assert out is not None
    assert 11 <= out <= 21
    assert bar_y[out] < 0.80 - 0.02 + 1e-9


def test_session6_identify_liftoff_frame_never_lifts_returns_none() -> None:
    """Bar drifts up <2% of frame height → no liftoff detected → None."""
    from app.cv.metric_extraction import identify_liftoff_frame
    n = 30
    bar_y = np.full(n, 0.80)
    bar_y[10:] = 0.795  # rises only 0.5% — below 2% threshold
    out = identify_liftoff_frame(bar_y, setup_frame=0, end_frame=n - 1, threshold_pct=0.02)
    assert out is None


def test_session6_identify_liftoff_frame_immediate_liftoff() -> None:
    """Bar already moving up at frame 1 → liftoff returned at the first qualifying frame."""
    from app.cv.metric_extraction import identify_liftoff_frame
    n = 10
    bar_y = np.array([0.80, 0.77, 0.74, 0.70, 0.66, 0.62, 0.58, 0.55, 0.55, 0.55])
    out = identify_liftoff_frame(bar_y, setup_frame=0, end_frame=n - 1, threshold_pct=0.02)
    assert out == 1


def test_session6_identify_liftoff_frame_out_of_bounds_returns_none() -> None:
    """end_frame past array length or setup_frame negative → None, no exception."""
    from app.cv.metric_extraction import identify_liftoff_frame
    bar_y = np.full(10, 0.80)
    assert identify_liftoff_frame(bar_y, setup_frame=-1, end_frame=5) is None
    assert identify_liftoff_frame(bar_y, setup_frame=0, end_frame=99) is None
    assert identify_liftoff_frame(bar_y, setup_frame=5, end_frame=3) is None


def test_session6_identify_liftoff_frame_empty_series_returns_none() -> None:
    from app.cv.metric_extraction import identify_liftoff_frame
    assert identify_liftoff_frame(np.array([]), setup_frame=0, end_frame=0) is None


def test_session6_identify_knee_pass_frame_happy_path() -> None:
    """Bar starts below knees (y > knee_y), rises past knees at frame 15."""
    from app.cv.metric_extraction import identify_knee_pass_frame
    n = 30
    knee_y = np.full(n, 0.70)
    bar_y = np.full(n, 0.80)
    bar_y[15:] = 0.65  # at frame 15, bar y (0.65) is above knee (0.70) in image
    out = identify_knee_pass_frame(
        bar_y, knee_y, liftoff_frame=5, end_frame=n - 1
    )
    assert out == 15


def test_session6_identify_knee_pass_frame_bar_starts_above_knee() -> None:
    """Bar already above knee at liftoff_frame → return liftoff_frame itself."""
    from app.cv.metric_extraction import identify_knee_pass_frame
    n = 20
    knee_y = np.full(n, 0.70)
    bar_y = np.full(n, 0.50)  # always above knee
    out = identify_knee_pass_frame(
        bar_y, knee_y, liftoff_frame=3, end_frame=n - 1
    )
    assert out == 3


def test_session6_identify_knee_pass_frame_never_reaches_knee() -> None:
    """Degenerate lift where bar stays below knee throughout → None."""
    from app.cv.metric_extraction import identify_knee_pass_frame
    n = 20
    knee_y = np.full(n, 0.70)
    bar_y = np.full(n, 0.85)  # always below knee
    out = identify_knee_pass_frame(
        bar_y, knee_y, liftoff_frame=2, end_frame=n - 1
    )
    assert out is None


def test_session6_identify_knee_pass_frame_out_of_bounds_returns_none() -> None:
    from app.cv.metric_extraction import identify_knee_pass_frame
    knee_y = np.full(10, 0.70)
    bar_y = np.full(10, 0.65)
    assert identify_knee_pass_frame(bar_y, knee_y, liftoff_frame=-1, end_frame=5) is None
    assert identify_knee_pass_frame(bar_y, knee_y, liftoff_frame=0, end_frame=99) is None
    assert identify_knee_pass_frame(bar_y, knee_y, liftoff_frame=5, end_frame=3) is None


def test_session6_identify_knee_pass_frame_empty_series_returns_none() -> None:
    from app.cv.metric_extraction import identify_knee_pass_frame
    empty = np.array([])
    assert identify_knee_pass_frame(empty, empty, liftoff_frame=0, end_frame=0) is None


def test_session6_identify_knee_pass_frame_mismatched_length_returns_none_safely() -> None:
    """Mismatched series lengths must not raise."""
    from app.cv.metric_extraction import identify_knee_pass_frame
    out = identify_knee_pass_frame(
        bar_y_series=np.full(10, 0.65),
        knee_y_series=np.full(20, 0.70),
        liftoff_frame=0,
        end_frame=9,
    )
    assert out is None or 0 <= out <= 9


def test_session6_bar_to_hip_distance_textbook_deadlift() -> None:
    """Synthetic deadlift with all 4 phase frames identifiable. Bar moves
    from in-front-of-hip at setup, to closer at lockout."""
    from app.cv.metric_extraction import _bar_to_hip_distance_dict
    bar_x = np.array([0.50, 0.48, 0.46, 0.455])
    bar_y = np.array([0.80, 0.65, 0.55, 0.40])
    hip_x = np.array([0.45, 0.45, 0.45, 0.45])
    knee_y = np.array([0.70, 0.70, 0.70, 0.70])
    shoulder_y_setup = 0.20
    hip_y_setup = 0.45
    shoulder_x_setup = 0.45  # vertically above hip → unsigned distance ≈ 0.25
    out = _bar_to_hip_distance_dict(
        bar_x_series=bar_x,
        bar_y_series=bar_y,
        hip_x_series=hip_x,
        knee_y_series=knee_y,
        shoulder_x_setup=shoulder_x_setup,
        shoulder_y_setup=shoulder_y_setup,
        hip_y_setup=hip_y_setup,
        setup_frame=0,
        end_frame=3,
        side="right",
    )
    assert set(out.keys()) == {"setup", "liftoff", "knee_pass", "lockout"}
    for k in out:
        assert out[k] is not None, f"phase {k} unexpectedly None"
    # Normalised by ~0.25 → setup ≈ 0.05 / 0.25 = 0.20
    assert out["setup"] == pytest.approx(0.20, abs=0.02)
    # Lockout is smallest (bar moved toward hip)
    assert abs(out["lockout"]) < abs(out["setup"])


def test_session6_bar_to_hip_distance_missing_liftoff_returns_none_for_that_key() -> None:
    """Bar never rises far enough → liftoff is None; downstream knee_pass also None."""
    from app.cv.metric_extraction import _bar_to_hip_distance_dict
    bar_x = np.array([0.50, 0.50, 0.50, 0.50])
    bar_y = np.array([0.80, 0.80, 0.80, 0.80])  # never rises
    hip_x = np.array([0.45, 0.45, 0.45, 0.45])
    knee_y = np.array([0.70, 0.70, 0.70, 0.70])
    out = _bar_to_hip_distance_dict(
        bar_x_series=bar_x,
        bar_y_series=bar_y,
        hip_x_series=hip_x,
        knee_y_series=knee_y,
        shoulder_x_setup=0.45,
        shoulder_y_setup=0.20,
        hip_y_setup=0.45,
        setup_frame=0,
        end_frame=3,
        side="right",
    )
    assert out["setup"] is not None
    assert out["lockout"] is not None
    assert out["liftoff"] is None
    assert out["knee_pass"] is None


def test_session6_bar_to_hip_distance_degenerate_zero_torso_returns_all_none() -> None:
    """Setup-frame torso length = 0 → can't normalise → all four values None."""
    from app.cv.metric_extraction import _bar_to_hip_distance_dict
    bar_x = np.full(4, 0.50)
    bar_y = np.array([0.80, 0.70, 0.60, 0.50])
    hip_x = np.full(4, 0.45)
    knee_y = np.full(4, 0.65)
    out = _bar_to_hip_distance_dict(
        bar_x_series=bar_x,
        bar_y_series=bar_y,
        hip_x_series=hip_x,
        knee_y_series=knee_y,
        shoulder_x_setup=0.45,
        shoulder_y_setup=0.45,   # SAME as hip_y → zero shoulder-to-hip distance
        hip_y_setup=0.45,
        setup_frame=0,
        end_frame=3,
        side="right",
    )
    assert all(v is None for v in out.values()), out


def test_session6_bar_to_hip_distance_side_agnostic() -> None:
    """Same physical pose, sides mirrored (x' = 1 - x): output values match."""
    from app.cv.metric_extraction import _bar_to_hip_distance_dict
    bar_x_r = np.array([0.50, 0.48, 0.46, 0.455])
    hip_x_r = np.full(4, 0.45)
    bar_x_l = 1.0 - bar_x_r
    hip_x_l = 1.0 - hip_x_r
    bar_y = np.array([0.80, 0.65, 0.55, 0.40])
    knee_y = np.full(4, 0.70)
    common = dict(
        bar_y_series=bar_y,
        knee_y_series=knee_y,
        shoulder_y_setup=0.20,
        hip_y_setup=0.45,
        setup_frame=0,
        end_frame=3,
    )
    right = _bar_to_hip_distance_dict(
        bar_x_series=bar_x_r,
        hip_x_series=hip_x_r,
        shoulder_x_setup=0.45,
        side="right",
        **common,
    )
    left = _bar_to_hip_distance_dict(
        bar_x_series=bar_x_l,
        hip_x_series=hip_x_l,
        shoulder_x_setup=1.0 - 0.45,
        side="left",
        **common,
    )
    for phase in ("setup", "liftoff", "knee_pass", "lockout"):
        rv, lv = right[phase], left[phase]
        if rv is None or lv is None:
            assert rv is None and lv is None
        else:
            assert rv == pytest.approx(lv, abs=1e-6), (phase, rv, lv)


def test_session6_shoulder_protraction_stable_returns_zero() -> None:
    """Shoulder x identical at setup and bottom → ~0 protraction."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    setup = np.zeros((33, 5))
    setup[:, 3] = 0.9
    setup[:, 4] = 5.0
    setup[12, :2] = [0.50, 0.20]
    setup[24, :2] = [0.50, 0.50]
    bottom = setup.copy()
    out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=setup,
        bottom_frame_landmarks=bottom,
        side_idx=right_idx,
        side="right",
    )
    assert out == pytest.approx(0.0, abs=1e-6)


def test_session6_shoulder_protraction_anterior_drift_positive() -> None:
    """Shoulder moves forward by 0.06 normalised → positive normalised value."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    setup = np.zeros((33, 5))
    setup[:, 3] = 0.9
    setup[:, 4] = 5.0
    setup[12, :2] = [0.50, 0.20]
    setup[24, :2] = [0.50, 0.50]  # span = 0.30
    bottom = setup.copy()
    bottom[12, :2] = [0.56, 0.20]  # shoulder moved +0.06 in image
    out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=setup,
        bottom_frame_landmarks=bottom,
        side_idx=right_idx,
        side="right",
    )
    assert out == pytest.approx(0.20, abs=1e-3)


def test_session6_shoulder_protraction_posterior_drift_negative() -> None:
    """Shoulder moves backward → negative."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    setup = np.zeros((33, 5))
    setup[:, 3] = 0.9
    setup[:, 4] = 5.0
    setup[12, :2] = [0.50, 0.20]
    setup[24, :2] = [0.50, 0.50]
    bottom = setup.copy()
    bottom[12, :2] = [0.44, 0.20]
    out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=setup,
        bottom_frame_landmarks=bottom,
        side_idx=right_idx,
        side="right",
    )
    assert out == pytest.approx(-0.20, abs=1e-3)


def test_session6_shoulder_protraction_missing_landmark_returns_none() -> None:
    """Low-visibility shoulder → None."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    setup = np.zeros((33, 5))
    setup[:, 3] = 0.9
    setup[:, 4] = 5.0
    setup[12, :2] = [0.50, 0.20]
    setup[24, :2] = [0.50, 0.50]
    bottom = setup.copy()
    bottom[12, 3] = 0.10  # below threshold
    out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=setup,
        bottom_frame_landmarks=bottom,
        side_idx=right_idx,
        side="right",
    )
    assert out is None


def test_session6_shoulder_protraction_degenerate_zero_torso_returns_none() -> None:
    """Setup shoulder-hip distance = 0 → cannot normalise → None."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    setup = np.zeros((33, 5))
    setup[:, 3] = 0.9
    setup[:, 4] = 5.0
    setup[12, :2] = [0.50, 0.50]  # SAME as hip
    setup[24, :2] = [0.50, 0.50]
    bottom = setup.copy()
    bottom[12, :2] = [0.55, 0.50]
    out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=setup,
        bottom_frame_landmarks=bottom,
        side_idx=right_idx,
        side="right",
    )
    assert out is None


@pytest.mark.parametrize("delta_x", [-0.05, 0.0, 0.04, 0.08])
def test_session6_shoulder_protraction_side_agnostic(delta_x: float) -> None:
    """Same physical drift, sides mirrored → same signed output."""
    from app.cv.metric_extraction import _shoulder_protraction_proxy_px
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    r_setup = np.zeros((33, 5))
    r_setup[:, 3] = 0.9
    r_setup[:, 4] = 5.0
    r_setup[12, :2] = [0.50, 0.20]
    r_setup[24, :2] = [0.50, 0.50]
    r_bottom = r_setup.copy()
    r_bottom[12, :2] = [0.50 + delta_x, 0.20]
    l_setup = np.zeros((33, 5))
    l_setup[:, 3] = 0.9
    l_setup[:, 4] = 5.0
    l_setup[11, :2] = [1.0 - 0.50, 0.20]
    l_setup[23, :2] = [1.0 - 0.50, 0.50]
    l_bottom = l_setup.copy()
    l_bottom[11, :2] = [1.0 - (0.50 + delta_x), 0.20]

    r_out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=r_setup,
        bottom_frame_landmarks=r_bottom,
        side_idx=right_idx, side="right",
    )
    l_out = _shoulder_protraction_proxy_px(
        setup_frame_landmarks=l_setup,
        bottom_frame_landmarks=l_bottom,
        side_idx=left_idx, side="left",
    )
    assert r_out == pytest.approx(l_out, abs=1e-6)


def test_session6_deadlift_analyzer_emits_bar_to_hip_distance_dict() -> None:
    """Deadlift analyzer emits ``bar_to_hip_distance`` as a dict with all four
    phase-frame keys, where wrist-midpoint serves as the bar trajectory."""
    n_frames = 60
    frames = []
    for i in range(n_frames):
        lm = np.zeros((33, 5))
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        bar_y_t = 0.80 - 0.40 * (i / (n_frames - 1))
        lm[12, :2] = [0.45, 0.30]   # right shoulder
        lm[24, :2] = [0.45, 0.55]   # right hip — span ≈ 0.25
        lm[26, :2] = [0.45, 0.70]   # right knee
        lm[28, :2] = [0.45, 0.95]   # right ankle
        lm[15, :2] = [0.50, bar_y_t]
        lm[16, :2] = [0.50, bar_y_t]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    hip_ang = 110.0 + 60.0 * np.cos(t)
    knee_ang = 130.0 + 40.0 * np.cos(t)
    ts = {"hip_angle": hip_ang, "knee_angle": knee_ang}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=n_frames - 1,
        confidence_score=0.9, min_angle=50.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="deadlift", exercise_variant="conventional",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "bar_to_hip_distance" in metrics
    d = metrics["bar_to_hip_distance"]
    assert isinstance(d, dict)
    assert set(d.keys()) == {"setup", "liftoff", "knee_pass", "lockout"}
    for k, v in d.items():
        assert v is not None, f"phase {k} unexpectedly None"
        assert isinstance(v, float)


def test_session6_bench_analyzer_emits_shoulder_protraction() -> None:
    """Bench analyzer emits ``shoulder_protraction_proxy_px`` per rep."""
    n_frames = 60
    frames = []
    for i in range(n_frames):
        lm = np.zeros((33, 5))
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        drift = 0.04 * abs(np.sin(np.pi * i / (n_frames - 1)))
        lm[12, :2] = [0.50 + drift, 0.30]
        lm[14, :2] = [0.30, 0.55]
        lm[16, :2] = [0.20, 0.55]
        lm[24, :2] = [0.50, 0.60]   # span ≈ 0.30
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    elbow_ang = 115.0 + 50.0 * np.cos(t)
    shoulder_ang = 70.0 + 20.0 * np.cos(t)
    ts = {"elbow_angle": elbow_ang, "shoulder_angle": shoulder_ang}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=n_frames - 1,
        confidence_score=0.9, min_angle=65.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="bench", exercise_variant="flat",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "shoulder_protraction_proxy_px" in metrics
    val = metrics["shoulder_protraction_proxy_px"]
    assert isinstance(val, float)
    assert -1.0 <= val <= 1.0


def test_session6_squat_analyzer_does_not_emit_bar_or_shoulder_protraction() -> None:
    """Squat analyzer must NOT emit either Session 6 key."""
    n_frames = 60
    frames = []
    for _ in range(n_frames):
        lm = np.zeros((33, 5))
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[12, :2] = [0.50, 0.20]
        lm[24, :2] = [0.50, 0.55]
        lm[26, :2] = [0.50, 0.75]
        lm[28, :2] = [0.50, 0.95]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    ts = {"hip_angle": 125 + 45 * np.cos(t), "knee_angle": 110 + 40 * np.cos(t)}
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=n_frames - 1,
        confidence_score=0.9, min_angle=80.0,
    )
    out = extract_rep_metrics(
        reps=[rep], landmarks_per_frame=frames, angle_timeseries=ts,
        exercise_type="squat", exercise_variant="standard",
        fps=30.0, lifter_side="right",
    )
    metrics = out[0].metrics
    assert "bar_to_hip_distance" not in metrics
    assert "shoulder_protraction_proxy_px" not in metrics


# ---------------------------------------------------------------------------
# Session 7 #2 — standing baseline frame identification
# ---------------------------------------------------------------------------
from app.cv.metric_extraction import identify_standing_baseline_frame  # noqa: E402


def test_session7_baseline_squat_uses_first_rep_start() -> None:
    """Squat baseline is the global first-rep start frame, for every rep."""
    reps = [
        DetectedRep(rep_index=0, start_frame=5, end_frame=40, confidence_score=0.9, min_angle=80.0),
        DetectedRep(rep_index=1, start_frame=45, end_frame=80, confidence_score=0.9, min_angle=80.0),
    ]
    # rep_position is ignored for squat — always returns reps[0].start_frame
    assert identify_standing_baseline_frame(
        "squat", reps[1], rep_position=1, all_reps=reps, bar_y_series=None
    ) == 5


def test_session7_baseline_squat_no_reps_returns_none() -> None:
    assert identify_standing_baseline_frame(
        "squat",
        DetectedRep(rep_index=0, start_frame=0, end_frame=10, confidence_score=0.9, min_angle=80.0),
        rep_position=0, all_reps=None, bar_y_series=None,
    ) is None


def test_session7_baseline_deadlift_uses_prev_rep_lockout() -> None:
    """DL non-first rep baseline = previous rep's end_frame (lockout)."""
    reps = [
        DetectedRep(rep_index=0, start_frame=0, end_frame=30, confidence_score=0.9, min_angle=80.0),
        DetectedRep(rep_index=1, start_frame=35, end_frame=70, confidence_score=0.9, min_angle=80.0),
    ]
    bar_y = np.full(80, 0.5)
    assert identify_standing_baseline_frame(
        "deadlift", reps[1], rep_position=1, all_reps=reps, bar_y_series=bar_y
    ) == 30


def test_session7_baseline_deadlift_first_rep_uses_preliftoff() -> None:
    """DL first rep: liftoff detected at frame 10 -> baseline = 9."""
    rep = DetectedRep(rep_index=0, start_frame=2, end_frame=40, confidence_score=0.9, min_angle=80.0)
    bar_y = np.full(50, 0.80)          # set position, bar low (high y)
    bar_y[10:] = 0.50                  # bar rises (y drops) at frame 10 -> liftoff
    out = identify_standing_baseline_frame(
        "deadlift", rep, rep_position=0, all_reps=[rep], bar_y_series=bar_y
    )
    assert out == 9


def test_session7_baseline_deadlift_first_rep_no_liftoff_falls_back_to_start() -> None:
    """DL first rep, bar never lifts -> fall back to rep.start_frame."""
    rep = DetectedRep(rep_index=0, start_frame=3, end_frame=40, confidence_score=0.9, min_angle=80.0)
    bar_y = np.full(50, 0.80)  # never rises
    out = identify_standing_baseline_frame(
        "deadlift", rep, rep_position=0, all_reps=[rep], bar_y_series=bar_y
    )
    assert out == 3


# ---------------------------------------------------------------------------
# Session 7 #2 — lumbar_flexion_proxy_delta_deg extractor
# ---------------------------------------------------------------------------
from app.cv.metric_extraction import extract_lumbar_flexion_proxy_delta_deg  # noqa: E402


def _upright_then_flexed_frames(flex_dx: float) -> list[np.ndarray]:
    """Frame 0 = upright (shoulder over hip); frame 1 = trunk flexed forward
    by flex_dx (shoulder ahead of hip in +x for a right-facing lifter)."""
    upright = _make_landmark_frame_right_side(shoulder_xy=(0.50, 0.20), hip_xy=(0.50, 0.55))
    flexed = _make_landmark_frame_right_side(shoulder_xy=(0.50 + flex_dx, 0.20), hip_xy=(0.50, 0.55))
    return [upright, flexed]


def test_session7_lumbar_proxy_no_buttwink_near_zero() -> None:
    """Clean squat: trunk angle at bottom ~= trunk angle at baseline -> delta ~= 0."""
    frames = _upright_then_flexed_frames(flex_dx=0.0)
    right_idx = landmark_indices_for_side("right")
    delta = extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame=frames, bottom_frame=1, baseline_frame=0,
        side_idx=right_idx, lifter_side="right",
    )
    assert delta == pytest.approx(0.0, abs=0.5)


def test_session7_lumbar_proxy_buttwink_positive_delta() -> None:
    """Pronounced forward flexion at bottom -> delta > 15 degrees."""
    dy = 0.35
    flex_dx = dy * math.tan(math.radians(20.0))  # ~20 degrees of trunk flexion
    frames = _upright_then_flexed_frames(flex_dx=flex_dx)
    right_idx = landmark_indices_for_side("right")
    delta = extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame=frames, bottom_frame=1, baseline_frame=0,
        side_idx=right_idx, lifter_side="right",
    )
    assert delta is not None and delta > 15.0


def test_session7_lumbar_proxy_no_baseline_returns_none() -> None:
    frames = _upright_then_flexed_frames(flex_dx=0.1)
    right_idx = landmark_indices_for_side("right")
    assert extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame=frames, bottom_frame=1, baseline_frame=None,
        side_idx=right_idx, lifter_side="right",
    ) is None


def test_session7_lumbar_proxy_low_visibility_returns_none() -> None:
    frames = _upright_then_flexed_frames(flex_dx=0.1)
    frames[0][24, 3] = 0.1  # hip low-vis at baseline frame (right hip = lm 24)
    right_idx = landmark_indices_for_side("right")
    assert extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame=frames, bottom_frame=1, baseline_frame=0,
        side_idx=right_idx, lifter_side="right",
    ) is None


@pytest.mark.parametrize("flex_deg", [0.0, 10.0, 20.0])
def test_session7_lumbar_proxy_side_agnostic(flex_deg: float) -> None:
    """Same physical flexion filmed from either side -> equal delta."""
    dy = 0.35
    dx = dy * math.tan(math.radians(flex_deg))
    right_idx = landmark_indices_for_side("right")
    left_idx = landmark_indices_for_side("left")
    right_frames = [
        _make_landmark_frame_right_side((0.50, 0.20), (0.50, 0.55)),
        _make_landmark_frame_right_side((0.50 + dx, 0.20), (0.50, 0.55)),
    ]
    left_frames = [
        _make_landmark_frame_left_side((1.0 - 0.50, 0.20), (1.0 - 0.50, 0.55)),
        _make_landmark_frame_left_side((1.0 - (0.50 + dx), 0.20), (1.0 - 0.50, 0.55)),
    ]
    rd = extract_lumbar_flexion_proxy_delta_deg(right_frames, 1, 0, right_idx, "right")
    ld = extract_lumbar_flexion_proxy_delta_deg(left_frames, 1, 0, left_idx, "left")
    assert rd == pytest.approx(ld, abs=0.5)


# ---------------------------------------------------------------------------
# Session 7 #6 — _classify_bar_path
# ---------------------------------------------------------------------------
from app.cv.metric_extraction import _classify_bar_path  # noqa: E402


def test_session7_barpath_vertical() -> None:
    assert _classify_bar_path(descent_start_x=0.50, bottom_x=0.50, ascent_end_x=0.50) == "vertical"


def test_session7_barpath_jcurve() -> None:
    assert _classify_bar_path(descent_start_x=0.50, bottom_x=0.50, ascent_end_x=0.44) == "j_curve"


def test_session7_barpath_drift() -> None:
    assert _classify_bar_path(descent_start_x=0.50, bottom_x=0.52, ascent_end_x=0.54) == "drift"


def test_session7_barpath_jcurve_mirrored_left_facing() -> None:
    """Left-facing lifter's j-curve sweeps to higher x -- symmetrized abs() catches it."""
    assert _classify_bar_path(descent_start_x=0.50, bottom_x=0.50, ascent_end_x=0.56) == "j_curve"


def test_session7_barpath_jcurve_precedence_over_neardrift() -> None:
    assert _classify_bar_path(descent_start_x=0.50, bottom_x=0.50, ascent_end_x=0.46) == "j_curve"


def test_session7_barpath_degenerate_none() -> None:
    assert _classify_bar_path(None, None, None) is None


# ---------------------------------------------------------------------------
# Session 7 #16 — technique_consistency_std + session-modal bar-path
# ---------------------------------------------------------------------------
from app.cv.metric_extraction import (  # noqa: E402
    _inject_technique_consistency_std,
    session_modal_bar_path_classification,
)
from app.cv.metric_extraction import RepMetrics  # noqa: E402


def _rep_with(metrics: dict) -> RepMetrics:
    return RepMetrics(rep_index=0, start_frame=0, end_frame=1, metrics=dict(metrics))


def test_session7_consistency_identical_reps_zero() -> None:
    reps = [_rep_with({"depth_angle": 90.0}) for _ in range(3)]
    _inject_technique_consistency_std(reps, "squat")
    assert all(r.metrics["technique_consistency_std"] == pytest.approx(0.0) for r in reps)


def test_session7_consistency_fatigued_reps_positive() -> None:
    reps = [_rep_with({"depth_angle": v}) for v in (90.0, 95.0, 105.0)]
    _inject_technique_consistency_std(reps, "squat")
    std = reps[0].metrics["technique_consistency_std"]
    assert std == pytest.approx(float(np.std([90.0, 95.0, 105.0])))  # ddof=0
    assert std > 0.0


def test_session7_consistency_deadlift_uses_lockout_lean() -> None:
    reps = [_rep_with({"lockout_torso_lean_deg": v}) for v in (5.0, 9.0)]
    _inject_technique_consistency_std(reps, "deadlift")
    assert reps[0].metrics["technique_consistency_std"] == pytest.approx(2.0)


def test_session7_consistency_single_rep_none() -> None:
    reps = [_rep_with({"depth_angle": 90.0})]
    _inject_technique_consistency_std(reps, "squat")
    assert reps[0].metrics["technique_consistency_std"] is None


def test_session7_session_modal_bar_path() -> None:
    reps = [
        _rep_with({"bar_path_classification": "vertical"}),
        _rep_with({"bar_path_classification": "vertical"}),
        _rep_with({"bar_path_classification": "drift"}),
    ]
    assert session_modal_bar_path_classification(reps) == "vertical"


def test_session7_session_modal_all_none() -> None:
    reps = [_rep_with({"bar_path_classification": None})]
    assert session_modal_bar_path_classification(reps) is None


# ---------------------------------------------------------------------------
# Session 7 Task 5 — wiring tests
# ---------------------------------------------------------------------------


def _make_full_bench_session_with_landmarks(n_frames: int = 60):
    """Bench session helper: full landmarks + elbow/shoulder timeseries + one rep."""
    frames = []
    right_idx = landmark_indices_for_side("right")
    for i in range(n_frames):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[right_idx.shoulder, :2] = [0.30, 0.55]
        lm[right_idx.elbow, :2] = [0.40, 0.42]
        lm[right_idx.wrist, :2] = [0.42, 0.30]
        lm[right_idx.hip, :2] = [0.60, 0.50]
        # Bilateral wrist midpoint for bar-x trajectory (landmarks 15 + 16)
        lm[15, :2] = [0.42, 0.30]
        lm[16, :2] = [0.42, 0.30]
        frames.append(lm)
    t = np.linspace(0, 2 * np.pi, n_frames)
    ts = {
        "elbow_angle": 115.0 + 50.0 * np.cos(t),
        "shoulder_angle": 70.0 + 20.0 * np.cos(t),
    }
    rep = DetectedRep(
        rep_index=0, start_frame=5, end_frame=n_frames - 5,
        confidence_score=0.9, min_angle=65.0,
    )
    return frames, ts, rep


def test_session7_squat_emits_lumbar_and_consistency_keys() -> None:
    frames, angles, _ = _make_full_squat_session_with_landmarks(80)
    reps = [
        DetectedRep(rep_index=0, start_frame=2, end_frame=38, confidence_score=0.9, min_angle=80.0),
        DetectedRep(rep_index=1, start_frame=42, end_frame=78, confidence_score=0.9, min_angle=80.0),
    ]
    out = extract_rep_metrics(reps, frames, angles, "squat", "standard", 30.0, "right")
    assert "lumbar_flexion_proxy_delta_deg" in out[0].metrics
    assert "technique_consistency_std" in out[0].metrics
    # consistency identical across reps
    assert out[0].metrics["technique_consistency_std"] == out[1].metrics["technique_consistency_std"]
    # bench-only key absent
    assert "bar_path_classification" not in out[0].metrics


def test_session7_bench_emits_bar_path_only() -> None:
    frames, angles, rep = _make_full_bench_session_with_landmarks(60)
    out = extract_rep_metrics([rep], frames, angles, "bench", "standard", 30.0, "right")
    assert "bar_path_classification" in out[0].metrics
    assert "lumbar_flexion_proxy_delta_deg" not in out[0].metrics
    assert "technique_consistency_std" not in out[0].metrics


def test_session7_squat_lumbar_none_when_baseline_frame_low_vis() -> None:
    """M-01: low visibility at the global baseline frame (rep0 start) → lumbar
    delta None for EVERY rep (visibility is enforced downstream in
    _lumbar_proxy_angle, per identify_standing_baseline_frame's contract)."""
    right_idx = landmark_indices_for_side("right")
    frames, angles, _ = _make_full_squat_session_with_landmarks(80)
    reps = [
        DetectedRep(rep_index=0, start_frame=2, end_frame=38, confidence_score=0.9, min_angle=80.0),
        DetectedRep(rep_index=1, start_frame=42, end_frame=78, confidence_score=0.9, min_angle=80.0),
    ]
    # Tank shoulder + hip visibility at the global baseline frame (rep0 start=2).
    frames[2][right_idx.shoulder, 3] = 0.1
    frames[2][right_idx.hip, 3] = 0.1
    out = extract_rep_metrics(reps, frames, angles, "squat", "standard", 30.0, "right")
    assert all(rm.metrics["lumbar_flexion_proxy_delta_deg"] is None for rm in out)


def test_session7_bench_bar_path_none_on_degenerate_short_rep() -> None:
    """M-03: a bench rep spanning fewer than 3 frames → bar_path_classification
    None (the span<2 caller-side gate in _bench_metrics)."""
    right_idx = landmark_indices_for_side("right")
    frames = []
    for _ in range(3):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0
        lm[right_idx.shoulder, :2] = [0.30, 0.55]
        lm[right_idx.elbow, :2] = [0.40, 0.42]
        lm[right_idx.wrist, :2] = [0.42, 0.30]
        lm[right_idx.hip, :2] = [0.60, 0.50]
        lm[15, :2] = [0.42, 0.30]
        lm[16, :2] = [0.42, 0.30]
        frames.append(lm)
    ts = {
        "elbow_angle": np.array([160.0, 90.0, 160.0]),
        "shoulder_angle": np.array([70.0, 60.0, 70.0]),
    }
    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=1,
        confidence_score=0.9, min_angle=90.0,
    )
    out = extract_rep_metrics([rep], frames, ts, "bench", "standard", 30.0, "right")
    assert out[0].metrics["bar_path_classification"] is None


def test_r3_bench_barpath_none_when_wrist_low_vis_at_anchor() -> None:
    """R3 (L2-CV-DEPTHFRAME-R3): bench bar_path_classification is None
    (cannot-classify) when a wrist landmark is below _S5_MIN_VIS at a bar-path
    anchor frame. The bilateral wrist-midpoint proxy is unreliable on the
    supine press (occluded/hallucinated wrists), so emit None rather than a
    misleading label. Pre-fix this returned 'vertical' from the garbage midpoint."""
    frames, angles, rep = _make_full_bench_session_with_landmarks(60)
    # Tank LEFT wrist (15) visibility at the descent-start anchor (rep.start_frame).
    frames[rep.start_frame][15, 3] = 0.1
    out = extract_rep_metrics([rep], frames, angles, "bench", "standard", 30.0, "right")
    assert out[0].metrics["bar_path_classification"] is None


def test_r3_bench_barpath_label_when_both_wrists_visible() -> None:
    """R3: the metric STILL classifies (no over-suppression) when BOTH wrists
    are reliably visible (>=_S5_MIN_VIS) at all three anchors — the gate only
    suppresses unreliable frames, not reliable ones."""
    frames, angles, rep = _make_full_bench_session_with_landmarks(60)
    # Shift the ascent-end wrist x well past the (constant) bottom x → j-curve.
    frames[rep.end_frame][15, 0] = 0.60
    frames[rep.end_frame][16, 0] = 0.60
    out = extract_rep_metrics([rep], frames, angles, "bench", "standard", 30.0, "right")
    assert out[0].metrics["bar_path_classification"] == "j_curve"


def test_session7_lumbar_proxy_none_when_shoulder_below_hip_occlusion() -> None:
    """Deep-squat hip-fold occlusion can mis-place a landmark so the shoulder
    appears BELOW the hip (dy = hip_y - shoulder_y <= 0), which is non-physical
    for squat/deadlift. atan2 would then wrap toward +/-180 deg and produce an
    implausible delta (observed -165 deg on the squat fixture). The dy<=0 guard
    returns None instead, bounding the proxy to (-90, 90) deg."""
    right_idx = landmark_indices_for_side("right")
    baseline = _make_landmark_frame_right_side(shoulder_xy=(0.50, 0.20), hip_xy=(0.50, 0.55))
    # Occluded bottom frame: shoulder-y (0.58) is BELOW hip-y (0.50) -> dy < 0.
    occluded = _make_landmark_frame_right_side(shoulder_xy=(0.48, 0.58), hip_xy=(0.50, 0.50))
    delta = extract_lumbar_flexion_proxy_delta_deg(
        landmarks_per_frame=[baseline, occluded], bottom_frame=1, baseline_frame=0,
        side_idx=right_idx, lifter_side="right",
    )
    assert delta is None


# ---------------------------------------------------------------------------
# L2-CV-DEPTHFRAME-DROPOUT: pipeline regression — squat dropout depth frame
# ---------------------------------------------------------------------------


def _make_squat_dropout_session():
    """Build a synthetic squat rep (20 frames) where the global-minimum
    hip-angle frame (index 10, hip_angle=-25.0) is a zero-vis dropout, but
    the adjacent frame (index 9, hip_angle=65.0) is fully valid.

    Rep spans frames 0-19. Standing baseline = frame 0 start (valid, upright).
    All frames use the 5-column convention with col4=presence.
    """
    right_idx = landmark_indices_for_side("right")
    n = 20

    # Build a realistic hip-angle series (standing→depth→standing) with
    # a garbage spike at the bottom imposed by zero-fill dropout.
    # Normal bottom of rep would be near frame 9-10 at ~65 deg.
    hip_angles = np.full(n, 170.0)
    # Descend from 170 deg to 65 deg between frames 1-9.
    hip_angles[1:10] = np.linspace(170.0, 65.0, 9)
    # Frame 10: dropout injects garbage angle (-25 deg).
    hip_angles[10] = -25.0
    # Ascend from 65 deg back to 170 deg between frames 11-19.
    hip_angles[11:20] = np.linspace(65.0, 170.0, 9)

    knee_angles = np.full(n, 170.0)
    knee_angles[1:10] = np.linspace(170.0, 80.0, 9)
    knee_angles[10] = -20.0  # also garbage at the dropout frame
    knee_angles[11:20] = np.linspace(80.0, 170.0, 9)

    angle_timeseries = {
        "hip_angle": hip_angles,
        "knee_angle": knee_angles,
    }

    # Build landmark frames.
    frames: list[np.ndarray] = []
    for i in range(n):
        lm = np.zeros((33, 5), dtype=float)
        if i == 10:
            # Dropout frame: zero-fill entire array (all vis=0).
            # This is the MediaPipe VIDEO-mode tracking-loss signature.
            frames.append(lm)
            continue

        # Valid frame: populate the right-side landmarks.
        # Visibility = 0.9, presence pre-sigmoid (col 4) = 5.0 -> ~1.0.
        lm[:, 3] = 0.9
        lm[:, 4] = 5.0  # col 4 = presence (required for Tier 1-5 confidence -- do not omit)

        # Standing posture at frames 0 and 19, squatting at frames 9/11.
        # We only need shoulder, hip, knee for the visibility gate.
        lm[right_idx.shoulder, :2] = [0.50, 0.15]
        lm[right_idx.hip, :2] = [0.50, 0.50]
        lm[right_idx.knee, :2] = [0.50, 0.75]
        lm[right_idx.ankle, :2] = [0.50, 0.92]
        frames.append(lm)

    rep = DetectedRep(
        rep_index=0, start_frame=0, end_frame=19,
        confidence_score=0.9, min_angle=65.0,
    )
    return frames, angle_timeseries, [rep]


def test_dropout_squat_depth_frame_uses_valid_frame_not_dropout() -> None:
    """RED-3: with the dropout-aware mask fix, _find_depth_frame must select
    the valid bottom frame (index 9, hip_angle=65.0) rather than the zero-vis
    dropout (index 10, hip_angle=-25.0).

    Asserts:
    - depth_angle == 65.0 (from valid frame 9), NOT -25.0 (dropout frame 10).
    - lumbar_flexion_proxy_delta_deg is not None (shoulder+hip both visible at
      the valid bottom frame).
    """
    frames, angle_timeseries, reps = _make_squat_dropout_session()
    out = extract_rep_metrics(
        reps=reps,
        landmarks_per_frame=frames,
        angle_timeseries=angle_timeseries,
        exercise_type="squat",
        exercise_variant="standard",
        fps=30.0,
        lifter_side="right",
    )
    assert len(out) == 1
    metrics = out[0].metrics

    # Pre-fix: depth_angle would be -25.0 (the dropout garbage).
    # Post-fix: depth_angle must be 65.0 (the valid minimum).
    assert metrics["depth_angle"] == pytest.approx(65.0, abs=0.5), (
        f"Expected depth_angle=65.0 (valid bottom), got {metrics['depth_angle']} "
        f"(likely still selecting dropout frame -25.0)"
    )

    # Pre-fix: lumbar_flexion_proxy_delta_deg is None because the dropout frame
    # has zero visibility and _vis_ok returns False.
    # Post-fix: the valid bottom frame has visible shoulder+hip, so it must
    # compute successfully.
    assert metrics["lumbar_flexion_proxy_delta_deg"] is not None, (
        "lumbar_flexion_proxy_delta_deg must be non-None when a valid bottom "
        "frame is selected (pre-fix: None because dropout frame was selected)"
    )


# ---------------------------------------------------------------------------
# L2-CV-DEPTHFRAME-DROPOUT-R1: geometric plausibility guards on ankle/shin
# ---------------------------------------------------------------------------
# Visibility threshold (0.30) does NOT cleanly separate good from garbage
# frames on real footage (knee vis 0.36→garbage, 0.43→good, 0.48→garbage).
# A geometric y-ordering invariant is more reliable:
#   • knee_y < ankle_y   (knee above ankle in image; y increases downward)
#   • ankle_y <= foot_y  (ankle above or at same level as toe; for dorsiflexion)
# Violations indicate MediaPipe mis-tracking → both functions return None.
#
# Pipeline wrapper in _squat_metrics must propagate None directly (not 0.0).


def _make_mistrack_ankle_frame(
    *,
    knee_xy: tuple[float, float],
    ankle_xy: tuple[float, float],
    foot_index_xy: tuple[float, float],
    side: str = "right",
) -> np.ndarray:
    """Build a (33, 5) frame for ankle/shin geometry tests.

    All named landmarks get vis=0.9 and presence=5.0 (pre-sigmoid ~1.0).
    """
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    idx = landmark_indices_for_side(side)
    lm[idx.knee, :2] = knee_xy
    lm[idx.ankle, :2] = ankle_xy
    lm[idx.foot_index, :2] = foot_index_xy
    lm[idx.heel, :2] = (ankle_xy[0] - 0.05, ankle_xy[1])  # plausible heel
    return lm


def test_geometric_guard_ankle_dorsiflexion_foot_above_ankle_returns_none() -> None:
    """RED-GEO-1: foot_index_y < ankle_y (foot appears above ankle in image —
    impossible in a squat). With only the vis-guard (current code) this returns
    a float. With the geometric guard it must return None.

    This is the mis-tracking signature observed on reps 0/2/5 in atharva-squat
    after R1 shifted the depth frame onto frames where lower-body landmarks
    are flipped (ankle_dorsiflexion_deg = 138-170 deg before this fix).
    """
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    # foot_index_y (0.50) < ankle_y (0.90): foot appears ABOVE ankle — impossible.
    frame = _make_mistrack_ankle_frame(
        knee_xy=(0.50, 0.55),
        ankle_xy=(0.50, 0.90),
        foot_index_xy=(0.50, 0.50),  # mis-tracked: above ankle
    )
    result = _ankle_dorsiflexion_deg(frame, right_idx)
    assert result is None, (
        f"Expected None for foot-above-ankle mis-tracking, got {result}. "
        "Geometric guard (ankle_y <= foot_y) not yet implemented."
    )


def test_geometric_guard_ankle_dorsiflexion_knee_below_ankle_returns_none() -> None:
    """RED-GEO-2: knee_y > ankle_y (knee appears below ankle in image —
    anatomically impossible for squat). Must return None.
    """
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    # knee_y (0.95) > ankle_y (0.55): knee appears BELOW ankle — impossible.
    frame = _make_mistrack_ankle_frame(
        knee_xy=(0.50, 0.95),   # mis-tracked: knee below ankle
        ankle_xy=(0.50, 0.55),
        foot_index_xy=(0.65, 0.70),
    )
    result = _ankle_dorsiflexion_deg(frame, right_idx)
    assert result is None, (
        f"Expected None for knee-below-ankle mis-tracking, got {result}. "
        "Geometric guard (knee_y < ankle_y) not yet implemented."
    )


def test_geometric_guard_shin_angle_knee_below_ankle_returns_none() -> None:
    """RED-GEO-3: knee_y > ankle_y (knee below ankle in image) — anatomically
    impossible. _shin_angle_deg must return None.
    """
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    lm[right_idx.knee, :2] = [0.50, 0.95]   # knee BELOW ankle — mis-tracked
    lm[right_idx.ankle, :2] = [0.50, 0.55]
    result = _shin_angle_deg(lm, right_idx, "right")
    assert result is None, (
        f"Expected None for knee-below-ankle mis-tracking, got {result}. "
        "Geometric guard (knee_y < ankle_y) not yet implemented."
    )


def test_geometric_guard_valid_squat_geometry_still_returns_float() -> None:
    """Sanity: a valid squat geometry (knee_y < ankle_y < foot_y) must still
    produce a float from both guards — no regression on the happy path."""
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg, _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    # knee(0.55) < ankle(0.90) < foot(0.92) — all valid
    frame = _make_mistrack_ankle_frame(
        knee_xy=(0.50, 0.55),
        ankle_xy=(0.50, 0.90),
        foot_index_xy=(0.65, 0.92),
    )
    ankle_result = _ankle_dorsiflexion_deg(frame, right_idx)
    shin_result = _shin_angle_deg(frame, right_idx, "right")
    assert ankle_result is not None, "Valid geometry should not return None for ankle_dorsiflexion"
    assert isinstance(ankle_result, float)
    assert shin_result is not None, "Valid geometry should not return None for shin_angle"
    assert isinstance(shin_result, float)


def test_geometric_guard_pipeline_propagates_none_not_zero() -> None:
    """RED-GEO-4: when _ankle_dorsiflexion_deg / _shin_angle_deg return None
    due to mis-tracking, the _squat_metrics pipeline wrapper must store None
    (not 0.0) in the output dict.

    Current code: float(ankle_dorsiflexion) if ... else 0.0 → stores 0.0.
    Required: None propagated directly so downstream can distinguish
    'could not compute' from 'no dorsiflexion observed'.
    """
    frames, angle_timeseries, reps = _make_squat_dropout_session()
    # Override frame 9 (the valid bottom after R1) so that the ankle landmark
    # has knee_y > ankle_y → geometric guard fires → None.
    right_idx = landmark_indices_for_side("right")
    # Depth frame is index 9 (hip_angle=65.0). Corrupt ankle/foot geometry there.
    frames[9][right_idx.knee, :2] = [0.50, 0.95]   # knee below ankle
    frames[9][right_idx.ankle, :2] = [0.50, 0.55]
    frames[9][right_idx.foot_index, :2] = [0.65, 0.70]

    out = extract_rep_metrics(
        reps=reps,
        landmarks_per_frame=frames,
        angle_timeseries=angle_timeseries,
        exercise_type="squat",
        exercise_variant="standard",
        fps=30.0,
        lifter_side="right",
    )
    metrics = out[0].metrics
    assert metrics["ankle_dorsiflexion_deg"] is None, (
        f"Expected None when geometric guard fires, got {metrics['ankle_dorsiflexion_deg']}. "
        "Pipeline must propagate None, not convert to 0.0."
    )
    assert metrics["shin_angle_deg"] is None, (
        f"Expected None when geometric guard fires, got {metrics['shin_angle_deg']}. "
        "Pipeline must propagate None, not convert to 0.0."
    )


# ---------------------------------------------------------------------------
# L2-CV-DEPTHFRAME-DROPOUT-R1b: anatomical-plausibility envelope guards
# ---------------------------------------------------------------------------
# The y-ordering guard catches gross spatial inversions but misses a second
# class of mis-tracking where the landmarks are y-ordered correctly yet the
# computed angle is anatomically impossible:
#
#   • rep 2 shin_angle_deg = -81.26° — landmark x-coordinates mis-placed
#     horizontally while y-ordering holds; atan2 wraps to ~-81°.
#   • rep 5 ankle_dorsiflexion_deg = 138.24° — foot_index nearly behind the
#     ankle (foot vector anti-parallel to knee vector); cos < 0 → >90°.
#
# Rationale for chosen bounds (anatomy-first; expert refines the clinically
# meaningful sub-range via FR-EXPV-08):
#
#   ankle_dorsiflexion_deg: joint angle at the ankle (knee-ankle-foot
#     triangle). Full squat ROM spans ~45°–110°. Absolute anatomical ceiling
#     ~120° (maximum plantarflexion, toes pointing straight down). Values at
#     or above 120° mean foot_index vector points backward relative to the
#     tibia — impossible in a squat. Lower bound ~10° (extreme dorsiflexion
#     with heel-elevated technique; <10° would require >80° dorsiflexion
#     which exceeds bony-joint ROM).
#     Guard: 10° <= value < 120°.
#
#   shin_angle_deg (shin deviation from vertical, positive = knee-forward):
#     Maximum forward knee travel is ~45°; extreme heel-elevated cases reach
#     ~60–70°. A backward shin (negative) of more than ~30–45° is impossible
#     in any standing or squatting posture. Guard: -45° <= value <= 80°.




def test_anatomical_envelope_ankle_above_120_returns_none() -> None:
    """RED-ENV-1: ankle_dorsiflexion_deg >= 120 is anatomically impossible
    in a squat (foot_index nearly behind ankle). Must return None even when
    y-ordering holds.

    Coordinates mirror rep-5 fixture frame (atharva-squat, left side, frame
    1087) which produced 138.24 deg. Mirrored to right side (x_prime = 1-x).
    """
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    # Original left-side: knee=(0.7989,0.5630) ankle=(0.8716,0.6087) foot=(0.8786,0.6329)
    # Mirrored to right (x_prime = 1 - x):
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    lm[right_idx.knee, :2]       = [1 - 0.7989, 0.5630]
    lm[right_idx.ankle, :2]      = [1 - 0.8716, 0.6087]
    lm[right_idx.foot_index, :2] = [1 - 0.8786, 0.6329]
    lm[right_idx.heel, :2]       = [1 - 0.8851, 0.6118]
    result = _ankle_dorsiflexion_deg(lm, right_idx)
    assert result is None, (
        f"Expected None for ankle_dorsiflexion_deg >= 120 (rep-5 garbage coords, "
        f"raw ~138 deg), got {result}. Anatomical-plausibility envelope not yet "
        f"implemented."
    )


def test_anatomical_envelope_ankle_below_10_returns_none() -> None:
    """RED-ENV-2: ankle_dorsiflexion_deg < 10 deg always co-occurs with
    foot_index above ankle (y-ordering guard fires first). This test
    confirms the combined guard (y-ordering + envelope) works together.
    """
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg
    right_idx = landmark_indices_for_side("right")
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    # Small angle: foot nearly co-directional with v_kn (upward), so foot_y < ankle_y.
    # y-ordering guard fires -> None. This is the anatomical lower-bound scenario.
    lm[right_idx.knee, :2]       = [0.50, 0.40]
    lm[right_idx.ankle, :2]      = [0.50, 0.70]
    lm[right_idx.foot_index, :2] = [0.50 + 0.01, 0.41]  # foot nearly at knee height
    lm[right_idx.heel, :2]       = [0.46, 0.71]
    result = _ankle_dorsiflexion_deg(lm, right_idx)
    assert result is None, (
        f"Expected None when foot is above ankle (y-ordering guard), got {result}"
    )


def test_anatomical_envelope_shin_below_neg45_returns_none() -> None:
    """RED-ENV-3: shin_angle_deg < -45 (knee far behind ankle) is
    anatomically impossible in a squat. Must return None.

    Coordinates mirror rep-2 fixture frame (atharva-squat, left side, frame
    423) which produced -81.26 deg. Mirrored to right side (x_prime = 1-x).
    """
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    # Original left-side: knee=(0.9532,0.5872) ankle=(0.9274,0.5912)
    # Mirrored to right (x_prime = 1 - x):
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    lm[right_idx.knee, :2]  = [1 - 0.9532, 0.5872]  # (0.0468, 0.5872)
    lm[right_idx.ankle, :2] = [1 - 0.9274, 0.5912]  # (0.0726, 0.5912)
    result = _shin_angle_deg(lm, right_idx, "right")
    assert result is None, (
        f"Expected None for shin_angle_deg < -45 (rep-2 garbage coords, "
        f"raw ~-81 deg), got {result}. Anatomical-plausibility envelope not yet "
        f"implemented."
    )


def test_anatomical_envelope_shin_above_80_returns_none() -> None:
    """RED-ENV-4: shin_angle_deg > 80 is beyond any recorded squat ROM.
    Must return None.

    Constructed: knee far forward of ankle (right-facing). atan2(dx, dy)
    with small dy and large dx gives > 80 deg.
    """
    from app.cv.metric_extraction import _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    # knee far forward (+x) with small dy: atan2(0.14, 0.02) ~ 82 deg
    lm[right_idx.knee, :2]  = [0.64, 0.68]
    lm[right_idx.ankle, :2] = [0.50, 0.70]
    result = _shin_angle_deg(lm, right_idx, "right")
    assert result is None, (
        f"Expected None for shin_angle_deg > 80 (extreme forward knee), "
        f"got {result}. Anatomical-plausibility envelope not yet implemented."
    )


def test_anatomical_envelope_valid_values_still_return_float() -> None:
    """Sanity: values well within the physiological range must be returned
    as floats. Uses realistic right-facing squat-bottom geometry.
    """
    from app.cv.metric_extraction import _ankle_dorsiflexion_deg, _shin_angle_deg
    right_idx = landmark_indices_for_side("right")
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 3] = 0.9
    lm[:, 4] = 5.0
    # Realistic right-facing squat bottom: knee forward-and-above ankle.
    lm[right_idx.knee, :2]       = [0.62, 0.55]
    lm[right_idx.ankle, :2]      = [0.50, 0.75]
    lm[right_idx.foot_index, :2] = [0.60, 0.80]
    lm[right_idx.heel, :2]       = [0.46, 0.77]
    r_ankle = _ankle_dorsiflexion_deg(lm, right_idx)
    assert r_ankle is not None and isinstance(r_ankle, float), (
        f"Expected float for valid squat geometry (dorsiflexion), got {r_ankle}"
    )
    assert 10.0 < r_ankle < 120.0, f"Expected within (10, 120), got {r_ankle}"
    r_shin = _shin_angle_deg(lm, right_idx, "right")
    assert r_shin is not None and isinstance(r_shin, float), (
        f"Expected float for valid squat geometry (shin angle), got {r_shin}"
    )
    assert -45.0 <= r_shin <= 80.0, f"Expected within [-45, 80], got {r_shin}"
