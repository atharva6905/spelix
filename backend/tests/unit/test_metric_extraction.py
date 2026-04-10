"""
Unit tests for per-rep metric extraction (B-018).

Implements TDD gate for FR-REPM-02–03, Sec 3.7.
All tests use synthetic numpy arrays — no real video, no IO.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.cv.rep_detection import DetectedRep
from app.cv.metric_extraction import RepMetrics, extract_rep_metrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_landmarks(n_frames: int = 60) -> list[np.ndarray]:
    """
    Create synthetic (33, 5) landmark arrays for n_frames.

    Positions are placed so that:
    - shoulder (12): (0.5, 0.1)
    - hip     (24): (0.5, 0.5)
    - knee    (26): (0.5, 0.75)
    - ankle   (28): (0.5, 0.95)
    - elbow   (14): (0.3, 0.35)
    - wrist   (16): (0.2, 0.35)

    These produce non-degenerate angles.
    """
    frames: list[np.ndarray] = []
    for i in range(n_frames):
        lm = np.zeros((33, 5), dtype=float)
        lm[:, 3] = 0.9  # visibility

        # Sagittal side positions (x, y)
        lm[12, :2] = [0.5, 0.1]   # shoulder
        lm[24, :2] = [0.5, 0.5]   # hip
        lm[26, :2] = [0.5, 0.75]  # knee
        lm[28, :2] = [0.5, 0.95]  # ankle
        lm[14, :2] = [0.3, 0.35]  # elbow
        lm[16, :2] = [0.2, 0.35]  # wrist

        frames.append(lm)
    return frames


def make_squat_timeseries(n_frames: int = 60) -> dict[str, np.ndarray]:
    """Synthetic squat angle timeseries with a single dip to ~80°."""
    t = np.linspace(0, 2 * np.pi, n_frames)
    # Hip angle: starts ~170°, dips to ~80° at midpoint
    hip = 125.0 + 45.0 * np.cos(t)   # range [80, 170]
    # Knee angle: mirrors hip roughly (bends more at depth)
    knee = 110.0 + 40.0 * np.cos(t)  # range [70, 150]
    return {
        "hip_angle": hip,
        "knee_angle": knee,
    }


def make_bench_timeseries(n_frames: int = 60) -> dict[str, np.ndarray]:
    """Synthetic bench angle timeseries with a single press."""
    t = np.linspace(0, 2 * np.pi, n_frames)
    elbow = 115.0 + 50.0 * np.cos(t)   # range [65, 165]
    shoulder = 70.0 + 20.0 * np.cos(t)  # range [50, 90]
    return {
        "elbow_angle": elbow,
        "shoulder_angle": shoulder,
    }


def make_deadlift_timeseries(n_frames: int = 60) -> dict[str, np.ndarray]:
    """Synthetic deadlift angle timeseries."""
    t = np.linspace(0, 2 * np.pi, n_frames)
    hip = 100.0 + 60.0 * np.cos(t)   # range [40, 160]
    knee = 120.0 + 40.0 * np.cos(t)  # range [80, 160]
    return {
        "hip_angle": hip,
        "knee_angle": knee,
    }


def make_detected_rep(
    rep_index: int = 0,
    start_frame: int = 0,
    end_frame: int = 59,
    min_angle: float = 80.0,
) -> DetectedRep:
    return DetectedRep(
        rep_index=rep_index,
        start_frame=start_frame,
        end_frame=end_frame,
        confidence_score=0.9,
        min_angle=min_angle,
    )


# ---------------------------------------------------------------------------
# Empty reps
# ---------------------------------------------------------------------------


def test_empty_reps_returns_empty_list():
    landmarks = make_landmarks(30)
    ts = make_squat_timeseries(30)
    result = extract_rep_metrics(
        reps=[],
        landmarks_per_frame=landmarks,
        angle_timeseries=ts,
        exercise_type="squat",
        exercise_variant="standard",
        fps=30.0,
    )
    assert result == []


# ---------------------------------------------------------------------------
# Squat
# ---------------------------------------------------------------------------


class TestSquatMetrics:
    def _run(
        self,
        n_frames: int = 60,
        fps: float = 30.0,
        start: int = 0,
        end: int | None = None,
    ) -> RepMetrics:
        end = end if end is not None else n_frames - 1
        landmarks = make_landmarks(n_frames)
        ts = make_squat_timeseries(n_frames)
        rep = make_detected_rep(start_frame=start, end_frame=end, min_angle=ts["hip_angle"][ts["hip_angle"].argmin()])
        result = extract_rep_metrics(
            reps=[rep],
            landmarks_per_frame=landmarks,
            angle_timeseries=ts,
            exercise_type="squat",
            exercise_variant="standard",
            fps=fps,
        )
        assert len(result) == 1
        return result[0]

    def test_squat_has_all_metrics(self):
        rm = self._run()
        expected_keys = {
            "depth_angle",
            "knee_angle_at_depth",
            "torso_lean",
            "rep_duration_s",
            "descent_duration_s",
            "eccentric_duration_s",
            "ascent_duration_s",
            "lockout_passed",
            "lockout_confidence",
            "phase_of_max_deviation",
        }
        assert expected_keys == set(rm.metrics.keys())

    def test_squat_rep_index(self):
        rm = self._run()
        assert rm.rep_index == 0

    def test_squat_frame_range(self):
        rm = self._run(start=5, end=54)
        assert rm.start_frame == 5
        assert rm.end_frame == 54

    def test_squat_rep_duration_s(self):
        n = 60
        fps = 30.0
        rm = self._run(n_frames=n, fps=fps, start=0, end=59)
        expected = (59 - 0) / fps
        assert rm.metrics["rep_duration_s"] == pytest.approx(expected, rel=1e-3)

    def test_squat_depth_angle_is_min_hip_angle(self):
        n = 60
        ts = make_squat_timeseries(n)
        rm = self._run(n_frames=n)
        # depth_angle should equal min_angle of the rep (min hip angle)
        min_hip = float(np.min(ts["hip_angle"][0:59]))
        assert rm.metrics["depth_angle"] == pytest.approx(min_hip, abs=1.0)

    def test_squat_descent_ascent_sum_approx_rep(self):
        rm = self._run()
        total = rm.metrics["descent_duration_s"] + rm.metrics["ascent_duration_s"]
        # Both must be > 0
        assert rm.metrics["descent_duration_s"] > 0
        assert rm.metrics["ascent_duration_s"] > 0
        # Together they should approximately span rep duration
        assert total == pytest.approx(rm.metrics["rep_duration_s"], rel=0.2)

    def test_squat_knee_angle_at_depth_in_range(self):
        rm = self._run()
        # Knee angle should be positive and reasonable (0–180°)
        assert 0 < rm.metrics["knee_angle_at_depth"] < 180

    def test_squat_torso_lean_in_range(self):
        rm = self._run()
        # Torso lean (angle vs vertical) should be in [0, 90]
        assert 0 <= rm.metrics["torso_lean"] <= 90


# ---------------------------------------------------------------------------
# Bench
# ---------------------------------------------------------------------------


class TestBenchMetrics:
    def _run(
        self,
        n_frames: int = 60,
        fps: float = 30.0,
        start: int = 0,
        end: int | None = None,
    ) -> RepMetrics:
        end = end if end is not None else n_frames - 1
        landmarks = make_landmarks(n_frames)
        ts = make_bench_timeseries(n_frames)
        min_elbow = float(np.min(ts["elbow_angle"][start:end+1]))
        rep = make_detected_rep(start_frame=start, end_frame=end, min_angle=min_elbow)
        result = extract_rep_metrics(
            reps=[rep],
            landmarks_per_frame=landmarks,
            angle_timeseries=ts,
            exercise_type="bench",
            exercise_variant="standard",
            fps=fps,
        )
        assert len(result) == 1
        return result[0]

    def test_bench_has_all_metrics(self):
        rm = self._run()
        expected_keys = {
            "elbow_angle_at_bottom",
            "shoulder_angle_at_bottom",
            "rep_duration_s",
            "descent_duration_s",
            "eccentric_duration_s",
            "ascent_duration_s",
            "lockout_passed",
            "lockout_confidence",
            "phase_of_max_deviation",
        }
        assert expected_keys == set(rm.metrics.keys())

    def test_bench_rep_duration_s(self):
        rm = self._run(fps=25.0, start=0, end=49)
        expected = 49 / 25.0
        assert rm.metrics["rep_duration_s"] == pytest.approx(expected, rel=1e-3)

    def test_bench_elbow_angle_at_bottom_in_range(self):
        rm = self._run()
        assert 0 < rm.metrics["elbow_angle_at_bottom"] < 180

    def test_bench_shoulder_angle_at_bottom_in_range(self):
        rm = self._run()
        assert 0 < rm.metrics["shoulder_angle_at_bottom"] < 180

    def test_bench_descent_ascent_positive(self):
        rm = self._run()
        assert rm.metrics["descent_duration_s"] > 0
        assert rm.metrics["ascent_duration_s"] > 0


# ---------------------------------------------------------------------------
# Deadlift
# ---------------------------------------------------------------------------


class TestDeadliftMetrics:
    def _run(
        self,
        n_frames: int = 60,
        fps: float = 30.0,
        start: int = 0,
        end: int | None = None,
    ) -> RepMetrics:
        end = end if end is not None else n_frames - 1
        landmarks = make_landmarks(n_frames)
        ts = make_deadlift_timeseries(n_frames)
        min_hip = float(np.min(ts["hip_angle"][start:end+1]))
        rep = make_detected_rep(start_frame=start, end_frame=end, min_angle=min_hip)
        result = extract_rep_metrics(
            reps=[rep],
            landmarks_per_frame=landmarks,
            angle_timeseries=ts,
            exercise_type="deadlift",
            exercise_variant="conventional",
            fps=fps,
        )
        assert len(result) == 1
        return result[0]

    def test_deadlift_has_all_metrics(self):
        rm = self._run()
        expected_keys = {
            "hip_angle_at_bottom",
            "knee_angle_at_lockout",
            "torso_lean_at_start",
            "rep_duration_s",
            "descent_duration_s",
            "eccentric_duration_s",
            "ascent_duration_s",
            "lockout_passed",
            "lockout_confidence",
            "phase_of_max_deviation",
        }
        assert expected_keys == set(rm.metrics.keys())

    def test_deadlift_rep_duration_s(self):
        rm = self._run(fps=30.0, start=0, end=59)
        assert rm.metrics["rep_duration_s"] == pytest.approx(59 / 30.0, rel=1e-3)

    def test_deadlift_hip_angle_at_bottom_in_range(self):
        rm = self._run()
        assert 0 < rm.metrics["hip_angle_at_bottom"] < 180

    def test_deadlift_knee_angle_at_lockout_in_range(self):
        rm = self._run()
        # At lockout knee should tend toward 180° for deadlift
        assert 0 < rm.metrics["knee_angle_at_lockout"] < 180

    def test_deadlift_torso_lean_at_start_in_range(self):
        rm = self._run()
        assert 0 <= rm.metrics["torso_lean_at_start"] <= 90

    def test_deadlift_descent_ascent_positive(self):
        rm = self._run()
        assert rm.metrics["descent_duration_s"] > 0
        assert rm.metrics["ascent_duration_s"] > 0


# ---------------------------------------------------------------------------
# FR-REPM-07: Eccentric duration alias
# ---------------------------------------------------------------------------


class TestEccentricDuration:
    """FR-REPM-07: eccentric_duration_s mirrors descent duration for all exercises."""

    def test_squat_eccentric_equals_descent(self):
        from app.cv.metric_extraction import extract_rep_metrics
        landmarks = make_landmarks(60)
        ts = make_squat_timeseries(60)
        rep = make_detected_rep(start_frame=0, end_frame=59, min_angle=80.0)
        rm = extract_rep_metrics([rep], landmarks, ts, "squat", "high_bar", 30.0)[0]
        assert rm.metrics["eccentric_duration_s"] == rm.metrics["descent_duration_s"]

    def test_bench_eccentric_equals_descent(self):
        from app.cv.metric_extraction import extract_rep_metrics
        landmarks = make_landmarks(60)
        ts = make_bench_timeseries(60)
        rep = make_detected_rep(start_frame=0, end_frame=59, min_angle=85.0)
        rm = extract_rep_metrics([rep], landmarks, ts, "bench", "flat", 30.0)[0]
        assert rm.metrics["eccentric_duration_s"] == rm.metrics["descent_duration_s"]

    def test_deadlift_eccentric_equals_descent(self):
        from app.cv.metric_extraction import extract_rep_metrics
        landmarks = make_landmarks(60)
        ts = make_deadlift_timeseries(60)
        rep = make_detected_rep(start_frame=0, end_frame=59, min_angle=75.0)
        rm = extract_rep_metrics([rep], landmarks, ts, "deadlift", "conventional", 30.0)[0]
        assert rm.metrics["eccentric_duration_s"] == rm.metrics["descent_duration_s"]


# ---------------------------------------------------------------------------
# FR-REPM-08: Lockout quality
# ---------------------------------------------------------------------------


class TestLockoutQuality:
    def test_squat_lockout_fields_present(self):
        from app.cv.metric_extraction import extract_rep_metrics
        landmarks = make_landmarks(60)
        ts = make_squat_timeseries(60)
        rep = make_detected_rep(start_frame=0, end_frame=59, min_angle=80.0)
        rm = extract_rep_metrics([rep], landmarks, ts, "squat", "high_bar", 30.0)[0]
        assert "lockout_passed" in rm.metrics
        assert "lockout_confidence" in rm.metrics
        assert rm.metrics["lockout_passed"] in (0.0, 1.0)
        assert 0.0 <= rm.metrics["lockout_confidence"] <= 1.0

    def test_squat_lockout_passed_when_end_angle_high(self):
        """Synthetic timeseries ends at 170° → lockout should pass."""
        landmarks = make_landmarks(60)
        # Override hip and knee to end at 170°
        ts = make_squat_timeseries(60)
        ts["hip_angle"][59] = 170.0
        ts["knee_angle"][59] = 170.0
        from app.cv.metric_extraction import extract_rep_metrics
        rep = make_detected_rep(start_frame=0, end_frame=59, min_angle=80.0)
        rm = extract_rep_metrics([rep], landmarks, ts, "squat", "high_bar", 30.0)[0]
        assert rm.metrics["lockout_passed"] == 1.0


# ---------------------------------------------------------------------------
# FR-REPM-09: Phase of max deviation
# ---------------------------------------------------------------------------


class TestPhaseOfMaxDeviation:
    def test_phase_field_is_valid_phase_name(self):
        from app.cv.metric_extraction import extract_rep_metrics
        landmarks = make_landmarks(60)
        ts = make_squat_timeseries(60)
        rep = make_detected_rep(start_frame=0, end_frame=59, min_angle=80.0)
        rm = extract_rep_metrics([rep], landmarks, ts, "squat", "high_bar", 30.0)[0]
        assert rm.metrics["phase_of_max_deviation"] in {
            "setup", "descent", "bottom", "ascent", "lockout",
        }


# ---------------------------------------------------------------------------
# Multiple reps
# ---------------------------------------------------------------------------


class TestMultipleReps:
    def test_multiple_reps_produce_separate_metric_sets(self):
        n_frames = 120
        fps = 30.0
        landmarks = make_landmarks(n_frames)
        ts = make_squat_timeseries(n_frames)
        reps = [
            make_detected_rep(rep_index=0, start_frame=0, end_frame=49, min_angle=80.0),
            make_detected_rep(rep_index=1, start_frame=60, end_frame=109, min_angle=85.0),
        ]
        result = extract_rep_metrics(
            reps=reps,
            landmarks_per_frame=landmarks,
            angle_timeseries=ts,
            exercise_type="squat",
            exercise_variant="standard",
            fps=fps,
        )
        assert len(result) == 2
        assert result[0].rep_index == 0
        assert result[1].rep_index == 1

    def test_multiple_reps_have_correct_frames(self):
        n_frames = 120
        fps = 30.0
        landmarks = make_landmarks(n_frames)
        ts = make_squat_timeseries(n_frames)
        reps = [
            make_detected_rep(rep_index=0, start_frame=5, end_frame=40),
            make_detected_rep(rep_index=1, start_frame=65, end_frame=100),
        ]
        result = extract_rep_metrics(
            reps=reps,
            landmarks_per_frame=landmarks,
            angle_timeseries=ts,
            exercise_type="squat",
            exercise_variant="standard",
            fps=fps,
        )
        assert result[0].start_frame == 5
        assert result[0].end_frame == 40
        assert result[1].start_frame == 65
        assert result[1].end_frame == 100

    def test_multiple_reps_durations_differ(self):
        n_frames = 120
        fps = 30.0
        landmarks = make_landmarks(n_frames)
        ts = make_squat_timeseries(n_frames)
        reps = [
            make_detected_rep(rep_index=0, start_frame=0, end_frame=29),   # 1s
            make_detected_rep(rep_index=1, start_frame=60, end_frame=119), # 2s
        ]
        result = extract_rep_metrics(
            reps=reps,
            landmarks_per_frame=landmarks,
            angle_timeseries=ts,
            exercise_type="squat",
            exercise_variant="standard",
            fps=fps,
        )
        assert result[0].metrics["rep_duration_s"] == pytest.approx(29 / 30.0, rel=1e-3)
        assert result[1].metrics["rep_duration_s"] == pytest.approx(59 / 30.0, rel=1e-3)


# ---------------------------------------------------------------------------
# Metrics value ranges for synthetic data
# ---------------------------------------------------------------------------


class TestMetricValueRanges:
    def test_rep_duration_matches_frames_and_fps(self):
        """Duration = (end - start) / fps — checked across fps values."""
        for fps in [24.0, 30.0, 60.0]:
            landmarks = make_landmarks(60)
            ts = make_squat_timeseries(60)
            rep = make_detected_rep(start_frame=0, end_frame=59, min_angle=80.0)
            result = extract_rep_metrics(
                reps=[rep],
                landmarks_per_frame=landmarks,
                angle_timeseries=ts,
                exercise_type="squat",
                exercise_variant="standard",
                fps=fps,
            )
            expected = 59 / fps
            assert result[0].metrics["rep_duration_s"] == pytest.approx(expected, rel=1e-3)

    def test_all_squat_metric_values_are_floats(self):
        landmarks = make_landmarks(60)
        ts = make_squat_timeseries(60)
        rep = make_detected_rep(start_frame=0, end_frame=59, min_angle=80.0)
        result = extract_rep_metrics(
            reps=[rep],
            landmarks_per_frame=landmarks,
            angle_timeseries=ts,
            exercise_type="squat",
            exercise_variant="standard",
            fps=30.0,
        )
        for key, val in result[0].metrics.items():
            # phase_of_max_deviation is a string (phase name); all others are floats
            if key == "phase_of_max_deviation":
                assert isinstance(val, str)
            else:
                assert isinstance(val, float), f"metric {key} is not a float"

    def test_all_bench_metric_values_are_floats(self):
        landmarks = make_landmarks(60)
        ts = make_bench_timeseries(60)
        rep = make_detected_rep(start_frame=0, end_frame=59, min_angle=70.0)
        result = extract_rep_metrics(
            reps=[rep],
            landmarks_per_frame=landmarks,
            angle_timeseries=ts,
            exercise_type="bench",
            exercise_variant="standard",
            fps=30.0,
        )
        for key, val in result[0].metrics.items():
            # phase_of_max_deviation is a string (phase name); all others are floats
            if key == "phase_of_max_deviation":
                assert isinstance(val, str)
            else:
                assert isinstance(val, float), f"metric {key} is not a float"

    def test_all_deadlift_metric_values_are_floats(self):
        landmarks = make_landmarks(60)
        ts = make_deadlift_timeseries(60)
        rep = make_detected_rep(start_frame=0, end_frame=59, min_angle=50.0)
        result = extract_rep_metrics(
            reps=[rep],
            landmarks_per_frame=landmarks,
            angle_timeseries=ts,
            exercise_type="deadlift",
            exercise_variant="conventional",
            fps=30.0,
        )
        for key, val in result[0].metrics.items():
            # phase_of_max_deviation is a string (phase name); all others are floats
            if key == "phase_of_max_deviation":
                assert isinstance(val, str)
            else:
                assert isinstance(val, float), f"metric {key} is not a float"
