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
