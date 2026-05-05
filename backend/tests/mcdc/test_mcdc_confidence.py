"""MC/DC truth-table tests for confidence.py Tier 4.

Decision: _tier4_phase_adjusted branch logic

3-way branch:
  A: abs(frame_offset - depth_frame_offset) <= bottom_window  → high_occlusion multiplier
  B: frame_offset == 0 OR frame_offset == rep_frame_count - 1  → static_peak multiplier (1.0)
  else                                                          → transition multiplier (0.90)

MC/DC rows for the OR in elif (condition A false):
  Row 1: offset=15, depth=0, count=30 → neither 0 nor 29, not near depth → transition
  Row 2: offset=0,  depth=0, count=30 → IS 0 (A_or independently true)  → static_peak
  Row 3: offset=29, depth=0, count=30 → IS last (B_or independently true) → static_peak

Priority: if depth_frame == first frame (offset=0, depth=0), high_occlusion wins.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"
os.environ.setdefault("THRESHOLD_CONFIG_PATH", str(_V1_PATH))

from app.config import ThresholdConfig
from app.cv.confidence import _tier4_phase_adjusted


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


# ---------------------------------------------------------------------------
# TestTier4StaticPeakOR
# MC/DC for the OR condition: frame_offset==0 OR frame_offset==rep_frame_count-1
# Setup: tier3_score=0.9, rep_frame_count=30, depth_frame_offset=0
# bottom_window = max(1, 30//10) = 3
# To avoid proximity branch: use depth_frame_offset far from test offsets
# ---------------------------------------------------------------------------


class TestTier4StaticPeakOR:
    """MC/DC rows for the static_peak OR condition (elif branch)."""

    # Use depth_frame_offset=14 so bottom_window=3 keeps the depth window
    # around frames 11..17. Offsets 0, 15, 29 are all far enough.
    # Wait — frame 15 is inside 14±3=11..17, so let's use depth_frame_offset=0
    # and test offsets that are out of window [0-3].
    # Actually depth=0, bottom_window=3, window=[0..3].
    # offset=0 is INSIDE window → would hit high_occlusion (priority test below).
    # We need depth far enough so test offsets 0 AND 29 are outside window.
    # depth_frame_offset=14, bottom_window=3 → window=[11,17]
    # offset=0: |0-14|=14 > 3 → not in window ✓
    # offset=15: |15-14|=1 ≤ 3 → in window (bad for middle test)
    # Use depth_frame_offset=20, bottom_window=3 → window=[17,23]
    # offset=0:  |0-20|=20 > 3 → not in window ✓
    # offset=15: |15-20|=5 > 3 → not in window ✓
    # offset=29: |29-20|=9 > 3 → not in window ✓

    _TIER3 = 0.9
    _COUNT = 30
    _DEPTH = 20  # depth_frame_offset kept far from all test offsets

    def test_middle_frame_gives_transition(self, cfg: ThresholdConfig) -> None:
        """Row 1: frame_offset=15 — not 0, not last, not near depth → transition.

        MC/DC: both OR sub-conditions are False → else branch fires.
        Changing either sub-condition independently to True would flip the outcome.
        """
        transition_mult = cfg.get("phase_multipliers", "transition")
        result = _tier4_phase_adjusted(
            tier3_score=self._TIER3,
            frame_offset=15,
            depth_frame_offset=self._DEPTH,
            rep_frame_count=self._COUNT,
            exercise_type="squat",
            cfg=cfg,
        )
        assert result == pytest.approx(self._TIER3 * transition_mult)

    def test_first_frame_gives_static_peak(self, cfg: ThresholdConfig) -> None:
        """Row 2: frame_offset=0 — (A_or=True, B_or=False) → static_peak.

        MC/DC: left sub-condition (==0) independently causes the elif to fire.
        """
        static_peak_mult = cfg.get("phase_multipliers", "static_peak")
        result = _tier4_phase_adjusted(
            tier3_score=self._TIER3,
            frame_offset=0,
            depth_frame_offset=self._DEPTH,
            rep_frame_count=self._COUNT,
            exercise_type="squat",
            cfg=cfg,
        )
        assert result == pytest.approx(self._TIER3 * static_peak_mult)

    def test_last_frame_gives_static_peak(self, cfg: ThresholdConfig) -> None:
        """Row 3: frame_offset=29 (count-1) — (A_or=False, B_or=True) → static_peak.

        MC/DC: right sub-condition (==count-1) independently causes elif to fire.
        """
        static_peak_mult = cfg.get("phase_multipliers", "static_peak")
        result = _tier4_phase_adjusted(
            tier3_score=self._TIER3,
            frame_offset=self._COUNT - 1,
            depth_frame_offset=self._DEPTH,
            rep_frame_count=self._COUNT,
            exercise_type="squat",
            cfg=cfg,
        )
        assert result == pytest.approx(self._TIER3 * static_peak_mult)


# ---------------------------------------------------------------------------
# TestTier4ProximityPriority
# The proximity (if) branch has higher priority than the static_peak (elif).
# When depth_frame coincides with first/last frame, high_occlusion wins.
# ---------------------------------------------------------------------------


class TestTier4ProximityPriority:
    """MC/DC priority rows — proximity branch overrides static_peak branch."""

    _TIER3 = 0.9
    _COUNT = 30

    def test_near_depth_overrides_static_peak(self, cfg: ThresholdConfig) -> None:
        """Priority: depth_frame=0, frame_offset=0 → high_occlusion, NOT static_peak.

        bottom_window=max(1,30//10)=3. |0-0|=0 ≤ 3 → first branch fires.
        This row demonstrates that the if-branch has lexical priority over elif.
        """
        occlusion_map = cfg.get("phase_multipliers", "high_occlusion")
        expected_mult = occlusion_map.get("squat_deep_hip_fold")
        result = _tier4_phase_adjusted(
            tier3_score=self._TIER3,
            frame_offset=0,
            depth_frame_offset=0,
            rep_frame_count=self._COUNT,
            exercise_type="squat",
            cfg=cfg,
        )
        assert result == pytest.approx(self._TIER3 * expected_mult)

    def test_far_from_depth_at_start_gives_static_peak(
        self, cfg: ThresholdConfig
    ) -> None:
        """Contrast: frame_offset=0 but depth=20 → static_peak (proximity not met).

        |0-20|=20 > 3 → if-branch skipped → elif fires (offset==0 is True).
        """
        static_peak_mult = cfg.get("phase_multipliers", "static_peak")
        result = _tier4_phase_adjusted(
            tier3_score=self._TIER3,
            frame_offset=0,
            depth_frame_offset=20,
            rep_frame_count=self._COUNT,
            exercise_type="squat",
            cfg=cfg,
        )
        assert result == pytest.approx(self._TIER3 * static_peak_mult)

    def test_far_middle_gives_transition(self, cfg: ThresholdConfig) -> None:
        """Contrast: frame_offset=15, depth=20 → transition (neither branch fires).

        |15-20|=5 > 3 → if skipped; 15 ≠ 0 and 15 ≠ 29 → elif skipped → else.
        """
        transition_mult = cfg.get("phase_multipliers", "transition")
        result = _tier4_phase_adjusted(
            tier3_score=self._TIER3,
            frame_offset=15,
            depth_frame_offset=20,
            rep_frame_count=self._COUNT,
            exercise_type="squat",
            cfg=cfg,
        )
        assert result == pytest.approx(self._TIER3 * transition_mult)
