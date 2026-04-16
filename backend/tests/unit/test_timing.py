"""Unit tests for app.services.timing.StageTimer (D-035)."""
from __future__ import annotations

import time

import pytest

from app.services.timing import StageTimer


class TestStageTimerBasics:
    def test_records_named_stage(self):
        timer = StageTimer()
        with timer.stage("download"):
            time.sleep(0.01)
        assert "download" in timer.as_dict()

    def test_elapsed_ms_is_positive_float(self):
        timer = StageTimer()
        with timer.stage("pose_extraction"):
            time.sleep(0.005)
        d = timer.as_dict()
        assert isinstance(d["pose_extraction"], float)
        assert d["pose_extraction"] >= 5.0  # 5ms sleep, allow some slop
        assert d["pose_extraction"] < 500.0  # not absurdly large

    def test_multiple_stages_each_recorded(self):
        timer = StageTimer()
        with timer.stage("a"):
            pass
        with timer.stage("b"):
            pass
        with timer.stage("c"):
            pass
        d = timer.as_dict()
        assert set(d.keys()) == {"a", "b", "c"}

    def test_same_stage_called_twice_overwrites_with_last(self):
        """Same stage called twice records the LAST elapsed (last write wins)."""
        timer = StageTimer()
        with timer.stage("stage_x"):
            time.sleep(0.001)
        first_value = timer.as_dict()["stage_x"]
        with timer.stage("stage_x"):
            time.sleep(0.02)
        second_value = timer.as_dict()["stage_x"]
        assert second_value > first_value

    def test_exception_inside_stage_still_records_elapsed(self):
        """Failure inside the stage block must still record elapsed for triage."""
        timer = StageTimer()
        with pytest.raises(ValueError):
            with timer.stage("failing_stage"):
                time.sleep(0.005)
                raise ValueError("synthetic failure")
        d = timer.as_dict()
        assert "failing_stage" in d
        assert d["failing_stage"] >= 5.0


class TestStageTimerSnapshot:
    def test_as_dict_returns_copy(self):
        """Mutating the returned dict must NOT mutate the timer's internal state."""
        timer = StageTimer()
        with timer.stage("a"):
            pass
        d = timer.as_dict()
        d["mutation"] = 999.0
        assert "mutation" not in timer.as_dict()

    def test_as_dict_empty_when_nothing_recorded(self):
        timer = StageTimer()
        assert timer.as_dict() == {}
