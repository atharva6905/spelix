"""
Sanity tests for D-042: new rep_detection threshold keys in thresholds_v1.json.

Proves every key needed by `rep_detection.py` resolves via ThresholdConfig.get()
and unwraps to the expected numeric value.
"""
from __future__ import annotations

import pytest

from app.config import ThresholdConfig


@pytest.fixture(scope="module")
def cfg() -> ThresholdConfig:
    return ThresholdConfig()


class TestSquatRepDetectionKeys:
    def test_standing_angle(self, cfg: ThresholdConfig) -> None:
        assert cfg.get("squat", "rep_detection_standing_angle_deg") == 150.0

    def test_depth_angle(self, cfg: ThresholdConfig) -> None:
        assert cfg.get("squat", "rep_detection_depth_angle_deg") == 110.0

    def test_prominence(self, cfg: ThresholdConfig) -> None:
        assert cfg.get("squat", "rep_detection_prominence_deg") == 20.0


class TestBenchRepDetectionKeys:
    def test_standing_angle(self, cfg: ThresholdConfig) -> None:
        assert cfg.get("bench", "rep_detection_standing_angle_deg") == 160.0

    def test_depth_angle(self, cfg: ThresholdConfig) -> None:
        assert cfg.get("bench", "rep_detection_depth_angle_deg") == 90.0

    def test_prominence(self, cfg: ThresholdConfig) -> None:
        assert cfg.get("bench", "rep_detection_prominence_deg") == 20.0


class TestDeadliftRepDetectionKeys:
    def test_standing_angle(self, cfg: ThresholdConfig) -> None:
        assert cfg.get("deadlift", "rep_detection_standing_angle_deg") == 160.0

    def test_depth_angle_default(self, cfg: ThresholdConfig) -> None:
        """Default depth (used by conventional, sumo)."""
        assert cfg.get("deadlift", "rep_detection_depth_angle_deg") == 70.0

    def test_depth_angle_romanian(self, cfg: ThresholdConfig) -> None:
        assert (
            cfg.get("deadlift", "rep_detection_depth_angle_romanian_deg")
            == 90.0
        )

    def test_depth_angle_rdl(self, cfg: ThresholdConfig) -> None:
        assert cfg.get("deadlift", "rep_detection_depth_angle_rdl_deg") == 90.0

    def test_prominence(self, cfg: ThresholdConfig) -> None:
        assert cfg.get("deadlift", "rep_detection_prominence_deg") == 20.0


class TestGlobalRepDetectionSection:
    def test_min_rep_duration_s(self, cfg: ThresholdConfig) -> None:
        assert cfg.get("rep_detection", "min_rep_duration_s") == 0.5
