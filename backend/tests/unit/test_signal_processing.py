"""
Unit tests for signal_processing.py (FR-CVPL-14).

TDD: these tests are written before the implementation exists.
All functions under test are pure — no DB, no IO, no side effects.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.cv.lifter_side import landmark_indices_for_side
from app.cv.signal_processing import (
    calculate_angle,
    calculate_joint_angles,
    compute_angle_timeseries,
    compute_invalid_frame_mask,
    smooth_signal,
)


# ---------------------------------------------------------------------------
# smooth_signal
# ---------------------------------------------------------------------------


class TestSmoothSignal:
    def test_smooth_signal_polynomial_close_to_expected(self) -> None:
        """
        Smoothing a clean quadratic signal should reproduce it closely.
        A degree-3 polynomial is exactly reproduced by a window=7, polyorder=3
        Savitzky-Golay filter.
        """
        # y = x^2 sampled at integer points — polynomial of degree 2 ≤ polyorder=3
        x = np.arange(20, dtype=float)
        y = x**2

        smoothed = smooth_signal(y, window=7, polyorder=3)

        # For a polynomial signal the filter should reproduce it very tightly
        np.testing.assert_allclose(smoothed, y, atol=1e-6)

    def test_smooth_signal_short_signal_returned_unchanged(self) -> None:
        """
        When signal length < window, the original array is returned unmodified.
        """
        short = np.array([1.0, 2.0, 3.0])  # length 3 < default window 7

        result = smooth_signal(short)

        np.testing.assert_array_equal(result, short)

    def test_smooth_signal_short_signal_same_window_returned_unchanged(self) -> None:
        """
        Signal length equal to window — len == window < window is False, so it
        should NOT be skipped.  Verify the equal-length case proceeds through
        the filter (scipy handles this).
        """
        signal = np.arange(7, dtype=float)
        result = smooth_signal(signal, window=7, polyorder=3)
        # Just confirm it returns an array of the same shape without crashing
        assert result.shape == signal.shape

    def test_smooth_signal_reduces_high_frequency_noise(self) -> None:
        """
        Smoothing should reduce the std-dev of a noisy constant signal.
        """
        rng = np.random.default_rng(42)
        noisy = np.ones(50) + rng.normal(0, 0.5, 50)
        smoothed = smooth_signal(noisy, window=7, polyorder=3)

        assert float(np.std(smoothed)) < float(np.std(noisy))

    def test_smooth_signal_returns_ndarray(self) -> None:
        signal = np.linspace(0, 10, 20)
        result = smooth_signal(signal)
        assert isinstance(result, np.ndarray)
        assert result.shape == signal.shape

    def test_smooth_signal_length_one_returned_unchanged(self) -> None:
        """Single-element signal is shorter than any reasonable window."""
        single = np.array([42.0])
        result = smooth_signal(single)
        np.testing.assert_array_equal(result, single)


# ---------------------------------------------------------------------------
# calculate_angle
# ---------------------------------------------------------------------------


class TestCalculateAngle:
    def test_right_angle(self) -> None:
        """
        Three points forming a right angle at b.
        a=(0,1), b=(0,0), c=(1,0) → angle at b = 90°
        """
        a = np.array([0.0, 1.0])
        b = np.array([0.0, 0.0])
        c = np.array([1.0, 0.0])

        angle = calculate_angle(a, b, c)

        assert abs(angle - 90.0) < 1e-6

    def test_straight_line(self) -> None:
        """
        Collinear points → angle = 180°.
        a=(0,0), b=(1,0), c=(2,0)
        """
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 0.0])
        c = np.array([2.0, 0.0])

        angle = calculate_angle(a, b, c)

        assert abs(angle - 180.0) < 1e-6

    def test_45_degree_angle(self) -> None:
        """
        a=(1,0), b=(0,0), c=(1,1) → angle = 45°
        """
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 0.0])
        c = np.array([1.0, 1.0])

        angle = calculate_angle(a, b, c)

        assert abs(angle - 45.0) < 1e-6

    def test_angle_in_range(self) -> None:
        """Result is always in [0, 180]."""
        for _ in range(20):
            rng = np.random.default_rng()
            a = rng.random(2)
            b = rng.random(2)
            c = rng.random(2)
            angle = calculate_angle(a, b, c)
            assert 0.0 <= angle <= 180.0

    def test_3d_points_use_only_xy(self) -> None:
        """
        3D points: same x, y as the right-angle test but with z noise
        should still produce 90°.
        """
        a = np.array([0.0, 1.0, 99.0])
        b = np.array([0.0, 0.0, -5.0])
        c = np.array([1.0, 0.0, 42.0])

        angle = calculate_angle(a, b, c)

        assert abs(angle - 90.0) < 1e-6


# ---------------------------------------------------------------------------
# calculate_joint_angles
# ---------------------------------------------------------------------------


def _make_landmarks(positions: dict[int, tuple[float, float]]) -> np.ndarray:
    """
    Build a (33, 5) landmark array.

    Unspecified landmarks default to (0.5, 0.5, 0.0, 1.0, 1.0).
    positions maps landmark index → (x, y).
    """
    lm = np.zeros((33, 5), dtype=float)
    lm[:, 0] = 0.5  # x
    lm[:, 1] = 0.5  # y
    lm[:, 3] = 1.0  # visibility
    lm[:, 4] = 1.0  # presence

    for idx, (x, y) in positions.items():
        lm[idx, 0] = x
        lm[idx, 1] = y

    return lm


class TestCalculateJointAngles:
    def test_squat_hip_and_knee_keys_present(self) -> None:
        """calculate_joint_angles returns hip_angle and knee_angle for squat."""
        lm = _make_landmarks({})
        result = calculate_joint_angles(lm, "squat")
        assert "hip_angle" in result
        assert "knee_angle" in result

    def test_deadlift_hip_and_knee_keys_present(self) -> None:
        lm = _make_landmarks({})
        result = calculate_joint_angles(lm, "deadlift")
        assert "hip_angle" in result
        assert "knee_angle" in result

    def test_bench_elbow_and_shoulder_keys_present(self) -> None:
        lm = _make_landmarks({})
        result = calculate_joint_angles(lm, "bench")
        assert "elbow_angle" in result
        assert "shoulder_angle" in result

    def test_squat_known_hip_angle(self) -> None:
        """
        Place LEFT side landmarks (12=shoulder, 24=hip, 26=knee) so hip angle
        at 24 is exactly 90°:
          shoulder(12) directly above hip(24), knee(26) directly right of hip.
        """
        # 12 = LEFT shoulder, 24 = LEFT hip, 26 = LEFT knee
        # Sagittal left-side view: primary landmarks are 12, 24, 26
        lm = _make_landmarks(
            {
                12: (0.5, 0.0),  # shoulder — directly above hip
                24: (0.5, 0.5),  # hip (vertex)
                26: (1.0, 0.5),  # knee — directly right of hip
            }
        )
        result = calculate_joint_angles(lm, "squat")
        assert abs(result["hip_angle"] - 90.0) < 1e-4

    def test_squat_known_knee_angle(self) -> None:
        """
        knee at 26 (vertex), hip at 24 above, ankle at 28 below — straight line → 180°
        """
        lm = _make_landmarks(
            {
                24: (0.5, 0.0),  # hip
                26: (0.5, 0.5),  # knee (vertex)
                28: (0.5, 1.0),  # ankle
            }
        )
        result = calculate_joint_angles(lm, "squat")
        assert abs(result["knee_angle"] - 180.0) < 1e-4

    def test_bench_known_elbow_angle(self) -> None:
        """
        elbow at 14 (vertex), shoulder at 12 above, wrist at 16 right → 90°
        Landmarks: 12=shoulder, 14=elbow (vertex), 16=wrist
        """
        lm = _make_landmarks(
            {
                12: (0.5, 0.0),  # shoulder
                14: (0.5, 0.5),  # elbow (vertex)
                16: (1.0, 0.5),  # wrist
            }
        )
        result = calculate_joint_angles(lm, "bench")
        assert abs(result["elbow_angle"] - 90.0) < 1e-4

    def test_unknown_exercise_raises(self) -> None:
        lm = _make_landmarks({})
        with pytest.raises((ValueError, KeyError)):
            calculate_joint_angles(lm, "unknown_exercise")

    def test_angles_in_valid_range(self) -> None:
        lm = _make_landmarks({})
        for exercise in ("squat", "deadlift", "bench"):
            result = calculate_joint_angles(lm, exercise)
            for angle in result.values():
                assert 0.0 <= angle <= 180.0, f"{exercise}: angle {angle} out of range"


# ---------------------------------------------------------------------------
# compute_angle_timeseries
# ---------------------------------------------------------------------------


def _make_frame_sequence(n_frames: int = 10) -> list[np.ndarray]:
    """
    Build a sequence of n_frames (33, 5) landmark arrays.
    Landmarks are placed such that all angles are deterministic.
    """
    frames: list[np.ndarray] = []
    for _ in range(n_frames):
        lm = _make_landmarks(
            {
                # squat/deadlift left side
                12: (0.5, 0.0),  # shoulder
                24: (0.5, 0.5),  # hip
                26: (1.0, 0.5),  # knee
                28: (1.0, 1.0),  # ankle
                # bench
                14: (0.5, 0.5),  # elbow
                16: (1.0, 0.5),  # wrist
            }
        )
        frames.append(lm)
    return frames


class TestComputeAngleTimeseries:
    def test_squat_returns_correct_keys(self) -> None:
        frames = _make_frame_sequence(10)
        result = compute_angle_timeseries(frames, "squat")
        assert "hip_angle" in result
        assert "knee_angle" in result

    def test_bench_returns_correct_keys(self) -> None:
        frames = _make_frame_sequence(10)
        result = compute_angle_timeseries(frames, "bench")
        assert "elbow_angle" in result
        assert "shoulder_angle" in result

    def test_deadlift_returns_correct_keys(self) -> None:
        frames = _make_frame_sequence(10)
        result = compute_angle_timeseries(frames, "deadlift")
        assert "hip_angle" in result
        assert "knee_angle" in result

    def test_output_length_matches_input_frames(self) -> None:
        n = 15
        frames = _make_frame_sequence(n)
        result = compute_angle_timeseries(frames, "squat")
        for key, arr in result.items():
            assert len(arr) == n, f"key {key}: expected {n} values, got {len(arr)}"

    def test_output_values_are_ndarray(self) -> None:
        frames = _make_frame_sequence(10)
        result = compute_angle_timeseries(frames, "squat")
        for key, arr in result.items():
            assert isinstance(arr, np.ndarray), f"{key} is not ndarray"

    def test_constant_signal_unchanged_after_smoothing(self) -> None:
        """
        When every frame produces the same angles, smoothing must not change
        the values (SG filter preserves polynomial signals exactly).
        """
        frames = _make_frame_sequence(20)
        result = compute_angle_timeseries(frames, "squat")

        for key, arr in result.items():
            assert float(np.std(arr)) < 1e-3, (
                f"{key}: expected constant signal after smoothing, std={np.std(arr)}"
            )

    def test_short_sequence_still_works(self) -> None:
        """
        Fewer frames than the default smoothing window — should return results
        without error (smooth_signal handles len < window gracefully).
        """
        frames = _make_frame_sequence(3)  # 3 < default window 7
        result = compute_angle_timeseries(frames, "squat")
        assert "hip_angle" in result
        assert len(result["hip_angle"]) == 3


# ---------------------------------------------------------------------------
# compute_angle_timeseries — validity gating (R2, L2-CV-DEPTHFRAME-R2)
# ---------------------------------------------------------------------------


def _valid_squat_frame() -> np.ndarray:
    """A clean squat frame (subject-right indices): hip_angle == 90°.

    shoulder(12) directly above hip(24); knee(26) directly right of hip.
    All landmarks fully visible (visibility 1.0 from ``_make_landmarks``).
    """
    return _make_landmarks(
        {
            12: (0.5, 0.0),  # shoulder above hip
            24: (0.5, 0.5),  # hip (vertex)
            26: (1.0, 0.5),  # knee right of hip -> hip_angle 90°
            28: (1.0, 1.0),  # ankle
        }
    )


def _zero_filled_frame() -> np.ndarray:
    """Total MediaPipe VIDEO-mode dropout: all landmarks at origin, visibility 0.

    ``calculate_angle`` on origin points returns 0.0° — the spurious spike R2
    must gate out before smoothing.
    """
    return np.zeros((33, 5), dtype=float)


class TestComputeAngleTimeseriesValidityGating:
    """R2 (L2-CV-DEPTHFRAME-R2): gate dropout / low-visibility frames out of the
    angle series before smoothing so garbage angles (the 0° spikes and the
    Savitzky-Golay over/undershoot they cause) never reach rep detection or
    depth-frame selection. See ADR-ANGLE-SERIES-VALIDITY-GATE.
    """

    def test_interior_dropout_interpolated_not_zero_spike(self) -> None:
        # 8 valid (hip=90) | 3 zero-filled dropout | 8 valid (hip=90)
        frames = (
            [_valid_squat_frame() for _ in range(8)]
            + [_zero_filled_frame() for _ in range(3)]
            + [_valid_squat_frame() for _ in range(8)]
        )
        result = compute_angle_timeseries(frames, "squat")
        hip = result["hip_angle"]
        # Dropout frames (indices 8,9,10) must be linearly interpolated to ~90,
        # NOT the spurious 0° spike a zero-filled frame produces pre-fix.
        for i in (8, 9, 10):
            assert hip[i] > 45.0, f"frame {i}: expected interpolated ~90, got {hip[i]}"

    def test_output_clamped_to_valid_range(self) -> None:
        # Pre-fix, savgol undershoots below 0° near the 0-spike (the −32°
        # artifact from the investigation). Post-fix interp + clamp -> [0,180].
        frames = (
            [_valid_squat_frame() for _ in range(8)]
            + [_zero_filled_frame() for _ in range(3)]
            + [_valid_squat_frame() for _ in range(8)]
        )
        result = compute_angle_timeseries(frames, "squat")
        for key, arr in result.items():
            assert float(np.min(arr)) >= 0.0, f"{key}: min {float(np.min(arr))} < 0"
            assert float(np.max(arr)) <= 180.0, f"{key}: max {float(np.max(arr))} > 180"

    def test_leading_dropout_held_at_first_valid(self) -> None:
        frames = [_zero_filled_frame() for _ in range(3)] + [
            _valid_squat_frame() for _ in range(10)
        ]
        result = compute_angle_timeseries(frames, "squat")
        hip = result["hip_angle"]
        assert hip[0] > 45.0, f"leading dropout should hold ~90, got {hip[0]}"

    def test_trailing_dropout_held_at_last_valid(self) -> None:
        frames = [_valid_squat_frame() for _ in range(10)] + [
            _zero_filled_frame() for _ in range(3)
        ]
        result = compute_angle_timeseries(frames, "squat")
        hip = result["hip_angle"]
        assert hip[-1] > 45.0, f"trailing dropout should hold ~90, got {hip[-1]}"

    def test_low_visibility_frame_gated_even_if_pose_present(self) -> None:
        # Confident-mis-track mode (B): a frame whose knee is geometrically
        # valid (gives a 180° hip reading) but has visibility 0.10 < 0.30.
        # It must be gated (interpolated to ~90), not bias the series toward 180.
        bad = _valid_squat_frame()
        bad[26] = (0.5, 1.0, 0.0, 0.10, 1.0)  # knee collinear -> 180°, low vis
        frames = (
            [_valid_squat_frame() for _ in range(8)]
            + [bad]
            + [_valid_squat_frame() for _ in range(8)]
        )
        result = compute_angle_timeseries(frames, "squat")
        hip = result["hip_angle"]
        assert abs(hip[8] - 90.0) < 10.0, (
            f"low-vis frame should be gated to ~90, got {hip[8]}"
        )

    def test_all_frames_dropout_does_not_crash(self) -> None:
        # Fully-occluded clip (quality gate rejects these upstream in prod).
        # Must not raise; returns same-length arrays.
        frames = [_zero_filled_frame() for _ in range(12)]
        result = compute_angle_timeseries(frames, "squat")
        assert len(result["hip_angle"]) == 12

    def test_clean_signal_not_altered_by_gating(self) -> None:
        # Regression guard: a fully-valid clip is unchanged (interp + clamp are
        # both no-ops when nothing is invalid and all values are in-range).
        frames = [_valid_squat_frame() for _ in range(20)]
        result = compute_angle_timeseries(frames, "squat")
        assert float(np.std(result["hip_angle"])) < 1e-3

    def test_bench_not_gated_on_invisible_wrist(self) -> None:
        # Bench wrists are SYSTEMATICALLY near-invisible (supine occlusion —
        # ~0.008 median vis, <0.30 on 100% of frames on real footage). Gating
        # bench elbow_angle on wrist visibility would NaN the entire series and
        # collapse rep detection (the 76.4 bar_touch_height_pct artifact R1 also
        # avoided by excluding bench). Bench is deliberately NOT validity-gated
        # — its bar-path/wrist robustness is R3/R3b, not R2.
        f = _make_landmarks({12: (0.5, 0.0), 14: (0.5, 0.5), 16: (1.0, 0.5)})
        f[16, 3] = 0.10  # right wrist barely visible (realistic bench)
        frames = [f.copy() for _ in range(20)]
        result = compute_angle_timeseries(frames, "bench")
        elbow = result["elbow_angle"]
        assert not np.isnan(elbow).any(), (
            "bench elbow_angle must not be gated to NaN on low wrist visibility"
        )
        assert abs(float(np.mean(elbow)) - 90.0) < 1.0


# ---------------------------------------------------------------------------
# compute_invalid_frame_mask (R5, L2-CV-DEPTHFRAME-R5)
# ---------------------------------------------------------------------------


class TestComputeInvalidFrameMask:
    """compute_invalid_frame_mask — R5 per-rep interpolation-fraction source."""

    def test_clean_squat_clip_all_false(self):
        frames = [_valid_squat_frame() for _ in range(10)]
        mask = compute_invalid_frame_mask(frames, "squat", "right")
        assert mask.dtype == bool
        assert mask.shape == (10,)
        assert not mask.any()

    def test_zero_filled_frame_flagged(self):
        frames = [_valid_squat_frame() for _ in range(10)]
        frames[4] = _zero_filled_frame()  # dropout — hip landmarks vis 0.0
        mask = compute_invalid_frame_mask(frames, "squat", "right")
        assert mask[4]
        assert mask.sum() == 1

    def test_visibility_boundary_is_min_vis(self):
        # A defining-landmark visibility exactly at _MIN_VIS is VISIBLE (not gated);
        # just below is gated. Guards against threshold drift vs _landmarks_visible.
        from app.cv.signal_processing import _MIN_VIS

        at = _valid_squat_frame()
        below = _valid_squat_frame()
        side = landmark_indices_for_side("right")
        for f, v in ((at, _MIN_VIS), (below, _MIN_VIS - 0.01)):
            for idx in (side.shoulder, side.hip, side.knee, side.ankle):
                f[idx, 3] = v
        assert not compute_invalid_frame_mask([at], "squat", "right")[0]
        assert compute_invalid_frame_mask([below], "squat", "right")[0]

    def test_bench_never_gated(self):
        # Bench is excluded from _JOINT_LANDMARK_DEPS (wrists systematically
        # invisible) — mask is all False so its interpolation fraction is 0.0.
        frames = [_zero_filled_frame() for _ in range(8)]
        mask = compute_invalid_frame_mask(frames, "bench", "right")
        assert mask.shape == (8,)
        assert not mask.any()

    def test_empty_clip_returns_empty_bool_array(self):
        mask = compute_invalid_frame_mask([], "squat", "right")
        assert mask.shape == (0,)
        assert mask.dtype == bool
