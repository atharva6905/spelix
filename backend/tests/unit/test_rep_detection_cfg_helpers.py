"""
Unit tests for private cfg-reading helpers in rep_detection.py (D-042).

Proves each helper returns the expected value for every exercise and variant
supported by the production config.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.config import ThresholdConfig
from app.cv.rep_detection import (
    _detect_reps_peak_valley,
    _detect_reps_state_machine,
    _get_depth_threshold_from_cfg,
    _get_min_rep_duration_s_from_cfg,
    _get_prominence_from_cfg,
    _get_standing_threshold_from_cfg,
    detect_reps,
)


@pytest.fixture(scope="module")
def cfg() -> ThresholdConfig:
    return ThresholdConfig()


class TestStandingThreshold:
    def test_squat(self, cfg: ThresholdConfig) -> None:
        assert _get_standing_threshold_from_cfg(cfg, "squat") == 150.0

    def test_bench(self, cfg: ThresholdConfig) -> None:
        assert _get_standing_threshold_from_cfg(cfg, "bench") == 160.0

    def test_deadlift(self, cfg: ThresholdConfig) -> None:
        assert _get_standing_threshold_from_cfg(cfg, "deadlift") == 160.0

    def test_case_insensitive(self, cfg: ThresholdConfig) -> None:
        assert _get_standing_threshold_from_cfg(cfg, "SQUAT") == 150.0


class TestDepthThreshold:
    def test_squat_standard(self, cfg: ThresholdConfig) -> None:
        assert _get_depth_threshold_from_cfg(cfg, "squat", "standard") == 110.0

    def test_bench_standard(self, cfg: ThresholdConfig) -> None:
        assert _get_depth_threshold_from_cfg(cfg, "bench", "flat") == 90.0

    def test_deadlift_conventional_uses_default(
        self, cfg: ThresholdConfig
    ) -> None:
        assert (
            _get_depth_threshold_from_cfg(cfg, "deadlift", "conventional")
            == 70.0
        )

    def test_deadlift_sumo_uses_default(self, cfg: ThresholdConfig) -> None:
        assert _get_depth_threshold_from_cfg(cfg, "deadlift", "sumo") == 70.0

    def test_deadlift_romanian_uses_variant_key(
        self, cfg: ThresholdConfig
    ) -> None:
        assert (
            _get_depth_threshold_from_cfg(cfg, "deadlift", "romanian") == 90.0
        )

    def test_deadlift_rdl_uses_variant_key(self, cfg: ThresholdConfig) -> None:
        assert _get_depth_threshold_from_cfg(cfg, "deadlift", "rdl") == 90.0

    def test_unknown_variant_falls_back_to_default(
        self, cfg: ThresholdConfig
    ) -> None:
        """An unrecognised variant string must fall back to the exercise's
        `rep_detection_depth_angle_deg` default key, not raise."""
        assert (
            _get_depth_threshold_from_cfg(cfg, "deadlift", "unrecognised")
            == 70.0
        )


class TestProminence:
    def test_squat(self, cfg: ThresholdConfig) -> None:
        assert _get_prominence_from_cfg(cfg, "squat") == 20.0

    def test_bench(self, cfg: ThresholdConfig) -> None:
        assert _get_prominence_from_cfg(cfg, "bench") == 20.0

    def test_deadlift(self, cfg: ThresholdConfig) -> None:
        assert _get_prominence_from_cfg(cfg, "deadlift") == 20.0


class TestMinRepDuration:
    def test_returns_half_second(self, cfg: ThresholdConfig) -> None:
        assert _get_min_rep_duration_s_from_cfg(cfg) == 0.5





def _make_angle_series(
    standing: float, bottom: float, frames_per_phase: int = 10
) -> np.ndarray:
    """Single-rep squat-style signal: stand → descend → bottom → ascend → stand."""
    return np.concatenate(
        [
            np.full(frames_per_phase, standing),
            np.linspace(standing, bottom, frames_per_phase),
            np.full(frames_per_phase, bottom),
            np.linspace(bottom, standing, frames_per_phase),
            np.full(frames_per_phase, standing),
        ]
    )


class TestStateMachineReadsFromCfg:
    def test_cfg_standing_threshold_changes_behavior(
        self, cfg: ThresholdConfig
    ) -> None:
        """
        With production cfg: signal 170°→75°→170° yields 1 rep.
        With a mocked cfg raising standing to 200°, the signal never enters
        STANDING → never transitions to DESCENDING → 0 reps.
        """
        angles = _make_angle_series(standing=170.0, bottom=75.0)

        class _FakeCfg:
            def get(self, section: str, key: str) -> float:
                if key == "rep_detection_standing_angle_deg":
                    return 200.0
                return cfg.get(section, key)

        reps_default = _detect_reps_state_machine(
            angles, "squat", "standard", 30.0, cfg
        )
        reps_override = _detect_reps_state_machine(
            angles, "squat", "standard", 30.0, _FakeCfg()  # type: ignore[arg-type]
        )

        assert len(reps_default) == 1
        assert reps_override == []

    def test_cfg_depth_threshold_changes_behavior(
        self, cfg: ThresholdConfig
    ) -> None:
        """
        Signal dips to 95° (parallel depth).
        Default cfg (depth=110, effective 105) → rep counts.
        Override cfg (depth=60, effective 55) → rep does NOT count.
        """
        angles = _make_angle_series(standing=170.0, bottom=95.0)

        class _FakeCfg:
            def get(self, section: str, key: str) -> float:
                if key == "rep_detection_depth_angle_deg":
                    return 60.0
                return cfg.get(section, key)

        reps_default = _detect_reps_state_machine(
            angles, "squat", "standard", 30.0, cfg
        )
        reps_override = _detect_reps_state_machine(
            angles, "squat", "standard", 30.0, _FakeCfg()  # type: ignore[arg-type]
        )

        assert len(reps_default) == 1
        assert reps_override == []

    def test_cfg_min_rep_duration_changes_behavior(
        self, cfg: ThresholdConfig
    ) -> None:
        """
        Rep spanning ~0.67s counts under default cfg (min 0.5s)
        but is filtered under override (min 1.5s).

        frames_per_phase=8 at 30fps: squat standing threshold is 150°
        (effective DESCENDING entry at 145°), so the actual counted
        window is ~20 frames (0.67s) — above 0.5s default but below
        1.5s override.
        """
        angles = _make_angle_series(
            standing=170.0, bottom=75.0, frames_per_phase=8
        )

        class _FakeCfg:
            def get(self, section: str, key: str) -> float:
                if key == "min_rep_duration_s":
                    return 1.5
                return cfg.get(section, key)

        reps_default = _detect_reps_state_machine(
            angles, "squat", "standard", 30.0, cfg
        )
        reps_override = _detect_reps_state_machine(
            angles, "squat", "standard", 30.0, _FakeCfg()  # type: ignore[arg-type]
        )

        assert len(reps_default) == 1
        assert reps_override == []




class TestPeakValleyReadsFromCfg:
    def test_cfg_prominence_changes_behavior(
        self, cfg: ThresholdConfig
    ) -> None:
        """
        Partial-lockout bench signal (peak 153°, valley 37°, ~116° prominence)
        counts under default (prominence=20). Under an override raising
        prominence to 200° (impossibly high), 0 reps.
        """
        stand1 = np.full(45, 153.0)
        descend = np.linspace(153.0, 37.0, 30)
        ascend = np.linspace(37.0, 153.0, 30)
        stand2 = np.full(45, 153.0)
        angles = np.concatenate([stand1, descend, ascend, stand2])

        class _FakeCfg:
            def get(self, section: str, key: str) -> float:
                if key == "rep_detection_prominence_deg":
                    return 200.0
                return cfg.get(section, key)

        reps_default = _detect_reps_peak_valley(angles, "bench", 30.0, cfg)
        reps_override = _detect_reps_peak_valley(
            angles, "bench", 30.0, _FakeCfg()  # type: ignore[arg-type]
        )

        assert len(reps_default) == 1
        assert reps_override == []


class TestPublicDetectRepsAcceptsCfg:
    def test_public_api_accepts_cfg(self, cfg: ThresholdConfig) -> None:
        """Public detect_reps must accept cfg as its 6th positional argument."""
        angles = _make_angle_series(standing=170.0, bottom=75.0)
        frame = np.zeros((33, 5), dtype=float)
        frame[:, 3] = 0.9
        landmarks = [frame.copy() for _ in range(len(angles))]

        reps = detect_reps(angles, landmarks, "squat", "standard", 30.0, cfg)

        assert len(reps) == 1
