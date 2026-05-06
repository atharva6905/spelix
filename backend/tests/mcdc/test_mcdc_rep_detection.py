"""MC/DC truth-table tests for rep_detection.py.

State machine thresholds (squat, from thresholds_v1.json):
  standing_thresh = 150.0°  (DESCENDING triggered below 145°; ASCENDING exit above 145°)
  depth_thresh    = 110.0°  (BOTTOM entered below 105°; exits ASCENDING above 115°)
  hysteresis      =   5.0°  (module constant _HYSTERESIS_DEG)
  min_rep_duration_s = 0.5s → min_rep_frames = 15 at 30 fps

Conditions exercised:
  C1: angle > standing_thresh - hysteresis  (> 145°)   -- ASCENDING exit gate
  C2: duration >= min_rep_frames            (>= 15)     -- ASCENDING duration gate
  C3: angle < depth_thresh - hysteresis     (< 105°)    -- DESCENDING → BOTTOM gate
  C4: state_machine_reps >= 1              -- fallback trigger
  C5: valley_duration >= min_rep_frames     (>= 15)     -- peak/valley duration filter

Note on isolation strategy:
  TestStateMachineAscendingExit and TestStateMachineDescendingAbort use the
  internal _detect_reps_state_machine function directly. This isolates C1/C2/C3
  from the fallback path: if we used detect_reps(), a signal that tricks the
  state machine into returning 0 reps would then invoke the fallback, which
  could detect a rep for a different reason, masking the state-machine condition
  under test. TestPeakValleyFallbackTrigger and TestPeakValleyMinDuration use
  detect_reps() because the C4/C5 conditions are about the hybrid's routing
  logic and the fallback's own duration filter respectively.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.config import ThresholdConfig
from app.cv.rep_detection import (
    _detect_reps_peak_valley,
    _detect_reps_state_machine,
    detect_reps,
)

_V1_PATH = Path(__file__).parent.parent.parent.parent / "config" / "thresholds_v1.json"

FPS = 30.0

# ---------------------------------------------------------------------------
# Exact threshold values read from config (squat exercise)
# ---------------------------------------------------------------------------
# standing_thresh = 150.0  →  effective entry: <145° desc, >145° asc-exit
# depth_thresh    = 110.0  →  effective entry: <105° bottom
# min_rep_frames  = int(0.5 * 30) = 15

_STANDING = 150.0
_DEPTH = 110.0
_HYSTERESIS = 5.0
_MIN_FRAMES = int(0.5 * FPS)  # 15

# Angles that clearly satisfy / clearly violate each gate
_ABOVE_STANDING_EXIT = _STANDING - _HYSTERESIS + 5.0   # 150° — safely above exit threshold (>145)
_BELOW_DEPTH = _DEPTH - _HYSTERESIS - 5.0              # 100° — safely below depth entry (<105)
_BETWEEN = (_STANDING + _DEPTH) / 2.0                  # 130° — mid-range, neither threshold


@pytest.fixture()
def cfg() -> ThresholdConfig:
    return ThresholdConfig(_V1_PATH)


def _make_landmarks(n_frames: int) -> list[np.ndarray]:
    """Minimal landmarks array — detect_reps doesn't use them for logic."""
    frame = np.zeros((33, 5), dtype=float)
    frame[:, 3] = 0.9  # visibility
    frame[:, 4] = 0.9  # presence (required by Tier 1–5 confidence formula)
    return [frame.copy() for _ in range(n_frames)]


# ===========================================================================
# TestStateMachineAscendingExit
#
# Compound condition: C1 AND C2 where
#   C1 = angle > standing_thresh - hysteresis  (> 145°)
#   C2 = rep_duration_frames >= min_rep_frames  (>= 15)
#
# MC/DC truth table:
#   Row 1: C1=F, C2=?  → no rep  (never returns to standing; C1 is the killing condition)
#   Row 2: C1=T, C2=F  → no rep  (C2 is the killing condition)
#   Row 3: C1=T, C2=T  → rep counted
#
# Uses _detect_reps_state_machine directly to isolate from the fallback path.
# ===========================================================================


class TestStateMachineAscendingExit:
    """MC/DC for the compound C1 AND C2 gate in the ASCENDING → STANDING transition."""

    def test_row1_c1_false_never_returns_to_standing(self, cfg: ThresholdConfig) -> None:
        """C1=F: signal descends and touches BOTTOM but never rises back past 145°.

        State machine stays in ASCENDING indefinitely → returns 0 reps.
        We call _detect_reps_state_machine directly to isolate from the fallback.
        """
        # Descend from 170° past both threshold gates, then park at 130° (below 145°)
        n_desc = 30
        n_park = 30
        descend = np.linspace(170.0, _BELOW_DEPTH, n_desc)   # 170→100, clears both thresholds
        park = np.full(n_park, _BETWEEN)                       # 130° — above BOTTOM exit (115°)
                                                               # but below ASCENDING exit (145°)

        # 130 > depth_thresh + hysteresis (115) → exits BOTTOM → enters ASCENDING ✓
        # 130 < standing_thresh - hysteresis (145) → C1=False, never exits ASCENDING
        signal = np.concatenate([descend, park])

        reps = _detect_reps_state_machine(signal, "squat", "standard", FPS, cfg)
        assert reps == [], f"Expected no reps from state machine (C1=F), got {len(reps)}"

    def test_row2_c1_true_c2_false_duration_too_short(self, cfg: ThresholdConfig) -> None:
        """C1=T, C2=F: signal completes the full angle cycle but total duration < min_rep_frames.

        Rep is discarded by the duration guard (C2 is the killing condition).
        Uses _detect_reps_state_machine directly to prevent the fallback from
        picking up the same short signal for a different reason.
        """
        # Full cycle in fewer than 15 frames:
        # standing_prefix (1 frame at 170°) → descent (3 frames 170→100°) →
        # ascent (6 frames 100→150°) — total 10 frames, rep_duration = 9 < 15
        standing_prefix = np.array([170.0])
        descent = np.linspace(170.0, _BELOW_DEPTH, 3)   # crosses 145° then 105°
        ascent = np.linspace(_BELOW_DEPTH, _ABOVE_STANDING_EXIT, 6)   # returns above 145°

        signal = np.concatenate([standing_prefix, descent, ascent])

        reps = _detect_reps_state_machine(signal, "squat", "standard", FPS, cfg)
        assert reps == [], (
            f"Expected 0 reps from state machine (C2=F, duration={len(signal) - 1} < {_MIN_FRAMES}), "
            f"got {len(reps)}"
        )

    def test_row3_c1_true_c2_true_full_valid_rep(self, cfg: ThresholdConfig) -> None:
        """C1=T, C2=T: full cycle with sufficient duration → exactly 1 rep counted.

        Uses _detect_reps_state_machine directly so the assertion is unambiguously
        about the state machine's C1 AND C2 both being True.
        """
        # 30-frame descent + 30-frame ascent = 60-frame rep (well above 15-frame minimum)
        n_half = 30
        descend = np.linspace(170.0, _BELOW_DEPTH, n_half)
        ascend = np.linspace(_BELOW_DEPTH, _ABOVE_STANDING_EXIT, n_half)

        signal = np.concatenate([descend, ascend])

        reps = _detect_reps_state_machine(signal, "squat", "standard", FPS, cfg)
        assert len(reps) == 1, f"Expected 1 rep (C1=T, C2=T), got {len(reps)}"
        assert reps[0].min_angle < _DEPTH - _HYSTERESIS, (
            f"min_angle={reps[0].min_angle:.1f}° should be below BOTTOM threshold "
            f"({_DEPTH - _HYSTERESIS}°) — confirming BOTTOM state was entered"
        )


# ===========================================================================
# TestStateMachineDescendingAbort
#
# Condition: C3 = angle < depth_thresh - hysteresis  (< 105°)
#
# During DESCENDING state:
#   C3=T  →  enters BOTTOM (rep will complete)
#   C3=F  →  may abort back to STANDING without ever entering BOTTOM (no rep)
#
# MC/DC truth table:
#   Row 1: C3=T  → enters BOTTOM, full rep counted
#   Row 2: C3=F  → dips but aborts, no rep
# ===========================================================================


class TestStateMachineDescendingAbort:
    """MC/DC for the C3 gate that distinguishes DESCENDING → BOTTOM from DESCENDING → abort."""

    def test_row1_c3_true_enters_bottom_completes_rep(self, cfg: ThresholdConfig) -> None:
        """C3=T: signal crosses depth threshold — BOTTOM entered, rep completes.

        Uses _detect_reps_state_machine to pin the assertion to the state machine's
        C3 gate (DESCENDING → BOTTOM) unambiguously.
        """
        n_half = 30
        descend = np.linspace(170.0, _BELOW_DEPTH, n_half)   # reaches 100° < 105° (C3=T)
        ascend = np.linspace(_BELOW_DEPTH, _ABOVE_STANDING_EXIT, n_half)

        signal = np.concatenate([descend, ascend])

        reps = _detect_reps_state_machine(signal, "squat", "standard", FPS, cfg)
        assert len(reps) == 1, f"Expected 1 rep (C3=T, depth crossed), got {len(reps)}"

    def test_row2_c3_false_aborts_without_reaching_depth(self, cfg: ThresholdConfig) -> None:
        """C3=F: signal dips below STANDING threshold but stays above DEPTH threshold.

        Minimum angle = 120° which is above depth_thresh - hysteresis (105°).
        After the dip, signal recovers above standing + hysteresis (155°) → DESCENDING aborts.
        Uses _detect_reps_state_machine directly to isolate from the fallback (which
        could otherwise detect the shallow dip as a valley via prominence).
        """
        _shallow_min = 120.0   # above 105°, so C3=False throughout

        # 1. Start at 170° (STANDING)
        # 2. Descend to 120° (crosses 145° → enters DESCENDING; 120 > 105 so C3=F)
        # 3. Return to 170° (crosses 155° → abort back to STANDING, no rep)
        n = 20
        standing_start = np.array([170.0])
        dip = np.linspace(170.0, _shallow_min, n)
        recover = np.linspace(_shallow_min, 170.0, n)

        signal = np.concatenate([standing_start, dip, recover])

        reps = _detect_reps_state_machine(signal, "squat", "standard", FPS, cfg)
        assert reps == [], (
            f"Expected 0 reps from state machine (C3=F, depth not reached), got {len(reps)} — "
            f"min angle in signal: {signal.min():.1f}°, depth gate: {_DEPTH - _HYSTERESIS}°"
        )


# ===========================================================================
# TestPeakValleyFallbackTrigger
#
# Condition: C4 = len(state_machine_reps) >= 1
#
# MC/DC truth table:
#   C4=T → state machine result returned; fallback not invoked
#   C4=F → peak/valley fallback fires and (for a suitable signal) detects reps
# ===========================================================================


class TestPeakValleyFallbackTrigger:
    """MC/DC for the C4 gate that decides whether fallback fires."""

    def test_row1_c4_true_state_machine_handles_clean_lockout(self, cfg: ThresholdConfig) -> None:
        """C4=T: clean full-lockout signal → state machine detects 2 reps, fallback not needed."""
        n_half = 30
        rep_down = np.linspace(170.0, _BELOW_DEPTH, n_half)
        rep_up = np.linspace(_BELOW_DEPTH, _ABOVE_STANDING_EXIT, n_half)
        one_rep = np.concatenate([rep_down, rep_up])

        signal = np.concatenate([one_rep, one_rep])  # 2 clean reps
        landmarks = _make_landmarks(len(signal))

        reps = detect_reps(signal, landmarks, "squat", "standard", FPS, cfg)
        # State machine must handle this; result must be ≥ 1 rep (C4=T path taken)
        assert len(reps) >= 1, f"Expected ≥1 rep from state machine, got {len(reps)}"

    def test_row2_c4_false_partial_lockout_triggers_fallback(self, cfg: ThresholdConfig) -> None:
        """C4=F: partial-lockout signal (80°–130°) never reaches standing threshold (150°).

        State machine returns 0 → fallback peak/valley fires and detects valleys.

        Signal oscillates between 80° and 130° with enough prominence (50°) and
        slow enough oscillation (30 frames per half-cycle = 1.0 s) to clear
        the prominence (20°) and min-duration (15 frames) filters.
        """
        prominence = 50.0   # 130 - 80 = 50° > 20° threshold ✓
        n_half = 30         # 30 frames each direction → 60 frames per valley-to-valley

        # Build 2 full valleys: high-low-high-low-high
        high = 130.0
        low = 80.0

        seg1 = np.linspace(high, low, n_half)   # valley 1
        seg2 = np.linspace(low, high, n_half)
        seg3 = np.linspace(high, low, n_half)   # valley 2
        seg4 = np.linspace(low, high, n_half)

        signal = np.concatenate([seg1, seg2, seg3, seg4])
        landmarks = _make_landmarks(len(signal))

        # Confirm state machine sees 0 reps first (C4=F condition)
        sm_reps = _detect_reps_state_machine(signal, "squat", "standard", FPS, cfg)
        assert sm_reps == [], (
            f"Signal should not reach standing threshold ({_STANDING}°) — "
            f"max signal: {signal.max():.1f}°. State machine must return 0 for fallback to fire."
        )

        # Now confirm the full hybrid detect_reps fires the fallback and finds reps
        reps = detect_reps(signal, landmarks, "squat", "standard", FPS, cfg)
        assert len(reps) >= 1, (
            f"Expected ≥1 rep from fallback path, got {len(reps)} — "
            f"signal range: {signal.min():.1f}°–{signal.max():.1f}°, prominence={prominence}°"
        )


# ===========================================================================
# TestPeakValleyMinDuration
#
# Condition: C5 = (end_frame - start_frame) >= min_rep_frames  (>= 15)
#
# Both rows start with C4=F (partial lockout) so fallback fires.
# MC/DC truth table:
#   C5=T → slow oscillation, valleys kept
#   C5=F → rapid noise, valleys discarded
# ===========================================================================


class TestPeakValleyMinDuration:
    """MC/DC for the C5 duration post-filter inside _detect_reps_peak_valley."""

    def test_row1_c5_true_slow_oscillation_kept(self, cfg: ThresholdConfig) -> None:
        """C5=T: half-cycle of 30 frames → valley-to-next-peak span well above 15 frames.

        Prominence = 50° > 20° threshold, distance already satisfied.
        Reps should be detected.
        """
        high = 130.0
        low = 80.0
        n_half = 30   # each half-cycle = 1.0 s at 30 fps

        seg1 = np.linspace(high, low, n_half)
        seg2 = np.linspace(low, high, n_half)
        seg3 = np.linspace(high, low, n_half)
        seg4 = np.linspace(low, high, n_half)

        signal = np.concatenate([seg1, seg2, seg3, seg4])
        landmarks = _make_landmarks(len(signal))

        reps = detect_reps(signal, landmarks, "squat", "standard", FPS, cfg)
        assert len(reps) >= 1, (
            f"Slow oscillation should produce ≥1 rep via fallback; got {len(reps)}"
        )

    def test_row2_c5_false_short_valley_span_filtered(self, cfg: ThresholdConfig) -> None:
        """C5=F: valley found by find_peaks but (end_frame - start_frame) < min_rep_frames.

        We call _detect_reps_peak_valley directly to isolate C5 from the hybrid
        routing logic. The signal has exactly one deep valley (prominence 50° > 20° ✓)
        so find_peaks locates it, but the surrounding peak-to-peak span is only 10
        frames (< 15), so the post-filter discards it.

        Signal layout (total 25 frames):
          frames 0–4   : flat 130° — preceding peak plateau; argmax = idx 0
          frames 5–9   : linspace(130→80, 6 pts)[1:] = 5 frames descending
          frame  10    : 80° — valley bottom (prominence = 50° ✓)
          frames 11–14 : linspace(80→130, 6 pts)[1:5] = 4 frames ascending to 130°
          frames 15–24 : flat 130° — long tail (end_hi = 24)

        Span calculation (mirrors _detect_reps_peak_valley logic):
          prev_end = 0, v_idx = 10, end_hi = 24 (next valley absent → n-1)
          start_frame = 0 + argmax(signal[0:11])  = 0   (plateau all equal → idx 0)
          end_frame   = 10 + argmax(signal[10:25]) = 10 + 4 = 14
          span = 14 − 0 = 14 < 15 → rep discarded. ✓
        """
        high = 130.0
        low = 80.0

        # Signal layout (24 frames total):
        #   frames 0–4  : flat 130° — preceding peak; argmax(signal[0:11]) → idx 0
        #   frames 5–9  : linspace(130,80,6)[1:] — 5-frame descent ending above low
        #   frame  10   : 80° valley  (prominence = 50° > 20° ✓)
        #   frames 11–13: linspace(80,130,5)[1:4] — 3-frame rise (doesn't reach 130°)
        #   frame  14   : 130° — first high frame after the rise
        #   frames 15–23: flat 130° — long tail
        #
        # argmax(signal[10:24]) → index 4 within slice = absolute frame 14
        # end_frame = 14, start_frame = 0, span = 14 < 15 ✓
        pre_plateau = np.full(5, high)               # frames 0–4
        descent = np.linspace(high, low, 6)[1:]      # frames 5–9 (5 pts, stops above low)
        valley_pt = np.array([low])                  # frame 10
        short_rise = np.linspace(low, high, 5)[1:4]  # frames 11–13 (3 pts, not yet at high)
        first_high = np.array([high])                # frame 14 — first 130° after rise
        post_plateau = np.full(9, high)              # frames 15–23

        signal = np.concatenate(
            [pre_plateau, descent, valley_pt, short_rise, first_high, post_plateau]
        )
        assert len(signal) == 24, f"Expected 24 frames, got {len(signal)}"

        # Sanity-check: valley is at index 10
        assert signal[10] == low, f"Valley should be at frame 10 = {low}°, got {signal[10]}"

        # Pre-verify the span mirrors what _detect_reps_peak_valley will compute
        v_idx = 10
        end_hi = len(signal) - 1  # 23
        end_frame = v_idx + int(np.argmax(signal[v_idx : end_hi + 1]))
        start_frame = int(np.argmax(signal[0 : v_idx + 1]))
        assert end_frame - start_frame < _MIN_FRAMES, (
            f"Test setup error: span={end_frame - start_frame}, expected < {_MIN_FRAMES}. "
            f"end_frame={end_frame}, start_frame={start_frame}"
        )

        reps = _detect_reps_peak_valley(signal, "squat", FPS, cfg)
        assert reps == [], (
            f"Valley with span {end_frame - start_frame} < {_MIN_FRAMES} frames should be "
            f"discarded by C5 post-filter; got {len(reps)} rep(s)"
        )
