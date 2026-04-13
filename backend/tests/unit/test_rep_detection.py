"""
Unit tests for rep detection state machine (FR-CVPL-15, FR-REPM-01, FR-REPM-05).

All tests use synthetic numpy arrays — no real video required.
"""

from __future__ import annotations


import numpy as np

from app.cv.rep_detection import detect_reps

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FPS = 30.0


def _make_landmarks(n_frames: int, visibility: float = 0.9) -> list[np.ndarray]:
    """
    Return a list of (33, 5) landmark arrays with constant position and
    the given visibility value (pre-sigmoid space is not needed here since
    we pass values directly in [0,1] — the implementation applies sigmoid
    which is ~identity near 0.9).
    """
    frame = np.zeros((33, 5), dtype=float)
    frame[:, 3] = visibility  # visibility column
    return [frame.copy() for _ in range(n_frames)]


def _squat_rep_angles(
    n_reps: int,
    frames_per_phase: int = 10,
    standing_angle: float = 170.0,
    bottom_angle: float = 75.0,
    fps: float = FPS,
) -> np.ndarray:
    """
    Build a synthetic hip-angle time-series for *n_reps* squat reps.

    Each rep: stand → descend → bottom → ascend → stand
    Each phase takes *frames_per_phase* frames.
    """
    phases: list[np.ndarray] = []

    # Initial standing segment (half-phase to avoid immediate detection)
    phases.append(np.full(frames_per_phase, standing_angle))

    for _ in range(n_reps):
        descend = np.linspace(standing_angle, bottom_angle, frames_per_phase)
        bottom_hold = np.full(frames_per_phase, bottom_angle)
        ascend = np.linspace(bottom_angle, standing_angle, frames_per_phase)
        stand_hold = np.full(frames_per_phase, standing_angle)
        phases.extend([descend, bottom_hold, ascend, stand_hold])

    return np.concatenate(phases)


def _bench_rep_angles(
    n_reps: int,
    frames_per_phase: int = 10,
    lockout_angle: float = 170.0,
    bottom_angle: float = 75.0,
) -> np.ndarray:
    """Bench press elbow-angle time-series."""
    phases: list[np.ndarray] = []
    phases.append(np.full(frames_per_phase, lockout_angle))

    for _ in range(n_reps):
        descend = np.linspace(lockout_angle, bottom_angle, frames_per_phase)
        bottom_hold = np.full(frames_per_phase, bottom_angle)
        ascend = np.linspace(bottom_angle, lockout_angle, frames_per_phase)
        stand_hold = np.full(frames_per_phase, lockout_angle)
        phases.extend([descend, bottom_hold, ascend, stand_hold])

    return np.concatenate(phases)


def _deadlift_rep_angles(
    n_reps: int,
    frames_per_phase: int = 10,
    standing_angle: float = 170.0,
    bottom_angle: float = 55.0,
) -> np.ndarray:
    """Deadlift (conventional) hip-angle time-series."""
    return _squat_rep_angles(
        n_reps,
        frames_per_phase=frames_per_phase,
        standing_angle=standing_angle,
        bottom_angle=bottom_angle,
    )


# ---------------------------------------------------------------------------
# 1. State cycle — squat (STANDING→DESCENDING→BOTTOM→ASCENDING→STANDING)
# ---------------------------------------------------------------------------


class TestSquatStateCycle:
    def test_single_rep_detected(self):
        angles = _squat_rep_angles(n_reps=1)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 1

    def test_rep_index_zero_based(self):
        angles = _squat_rep_angles(n_reps=1)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps[0].rep_index == 0

    def test_min_angle_captured(self):
        bottom_angle = 75.0
        angles = _squat_rep_angles(n_reps=1, bottom_angle=bottom_angle)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps[0].min_angle <= bottom_angle + 1.0  # within 1°

    def test_start_before_end_frame(self):
        angles = _squat_rep_angles(n_reps=1)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps[0].start_frame < reps[0].end_frame

    def test_multiple_reps_correct_count(self):
        for n in [2, 3, 5]:
            angles = _squat_rep_angles(n_reps=n)
            landmarks = _make_landmarks(len(angles))
            reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
            assert len(reps) == n, f"expected {n} reps, got {len(reps)}"

    def test_rep_indices_sequential(self):
        angles = _squat_rep_angles(n_reps=3)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        for i, rep in enumerate(reps):
            assert rep.rep_index == i


# ---------------------------------------------------------------------------
# 2. State cycle — bench press (elbow angle)
# ---------------------------------------------------------------------------


class TestBenchStateCycle:
    def test_single_rep_detected(self):
        angles = _bench_rep_angles(n_reps=1)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "bench", "standard", FPS)
        assert len(reps) == 1

    def test_multiple_reps(self):
        angles = _bench_rep_angles(n_reps=3)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "bench", "standard", FPS)
        assert len(reps) == 3

    def test_min_angle_below_bottom_threshold(self):
        """Bench bottom threshold is <90°; bottom_angle=75° should pass."""
        angles = _bench_rep_angles(n_reps=1, bottom_angle=75.0)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "bench", "standard", FPS)
        assert len(reps) == 1

    def test_insufficient_depth_not_counted(self):
        """Elbow only goes to 95° — never crosses <90° bench depth threshold."""
        angles = _bench_rep_angles(n_reps=2, bottom_angle=95.0)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "bench", "standard", FPS)
        assert len(reps) == 0


# ---------------------------------------------------------------------------
# 3. State cycle — deadlift
# ---------------------------------------------------------------------------


class TestDeadliftStateCycle:
    def test_conventional_single_rep(self):
        """Conventional deadlift: bottom <70°; use 55°."""
        angles = _deadlift_rep_angles(n_reps=1, bottom_angle=55.0)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "deadlift", "conventional", FPS)
        assert len(reps) == 1

    def test_sumo_single_rep(self):
        angles = _deadlift_rep_angles(n_reps=1, bottom_angle=55.0)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "deadlift", "sumo", FPS)
        assert len(reps) == 1

    def test_rdl_variant_threshold_90(self):
        """RDL bottom threshold is <90°; an angle of 80° should be detected."""
        angles = _squat_rep_angles(n_reps=1, bottom_angle=80.0)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "deadlift", "rdl", FPS)
        assert len(reps) == 1

    def test_conventional_angle_70_to_90_not_counted(self):
        """
        For conventional deadlift the depth threshold is <70°.
        An angle that only reaches 75° (never below 70°) must NOT be counted.
        """
        angles = _squat_rep_angles(n_reps=2, bottom_angle=75.0)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "deadlift", "conventional", FPS)
        assert len(reps) == 0

    def test_rdl_vs_conventional_same_data_different_counts(self):
        """
        An angle reaching only 80° counts as an RDL rep (threshold <90°)
        but NOT as a conventional rep (threshold <70°).
        """
        angles = _squat_rep_angles(n_reps=2, bottom_angle=80.0)
        landmarks = _make_landmarks(len(angles))

        rdl_reps = detect_reps(angles, landmarks, "deadlift", "rdl", FPS)
        conv_reps = detect_reps(angles, landmarks, "deadlift", "conventional", FPS)

        assert len(rdl_reps) == 2
        assert len(conv_reps) == 0


# ---------------------------------------------------------------------------
# 4. Hysteresis ±5° prevents chatter
# ---------------------------------------------------------------------------


class TestHysteresis:
    def _chattering_signal(
        self,
        base: float,
        amplitude: float,
        n_frames: int = 60,
    ) -> np.ndarray:
        """
        A signal that oscillates by ±amplitude around *base*.
        For squat: base ~ threshold boundary → should NOT trigger reps.
        """
        t = np.arange(n_frames)
        return base + amplitude * np.sin(2 * np.pi * t / 10)

    def test_chatter_near_standing_threshold_squat(self):
        """
        Oscillation around 160° (squat standing threshold) must not create reps.
        """
        # Signal hovers between ~155° and ~165° — crosses 160° repeatedly
        angles = self._chattering_signal(base=160.0, amplitude=6.0)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 0

    def test_chatter_near_depth_threshold_squat(self):
        """
        Oscillation near the squat depth threshold while already descending
        must not create false bottom detections if the signal never clears
        the effective threshold (depth - hysteresis = 110° - 5° = 105°).
        Signal hovers around 108° ±4° (range 104°–112°) — mostly above 105°,
        meaning BOTTOM may or may not be entered depending on the peak; the
        key invariant is that this noisy, nearly-at-threshold signal does NOT
        produce a rep (the descent portion dips below 105° only transiently
        and the ascent never reaches standing - hysteresis = 145°).
        We verify by ensuring the signal never reaches the return threshold.
        """
        # Build: stand → descend to just above effective depth zone → hover
        stand = np.full(15, 170.0)
        # Descend to 108° but NOT past 105° (stays in hysteresis band)
        descend = np.linspace(170.0, 108.0, 15)
        # hover near 110° with ±4° noise — may dip to 104° but barely
        hover = 108.0 + 4.0 * np.sin(2 * np.pi * np.arange(20) / 5)
        # Ascend but only to 130° — never reaches standing - hysteresis = 145°
        partial_ascend = np.linspace(108.0, 130.0, 15)
        hold_partial = np.full(15, 130.0)
        angles = np.concatenate([stand, descend, hover, partial_ascend, hold_partial])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        # Signal never returns to standing threshold, so no rep completes
        assert len(reps) == 0

    def test_clear_depth_after_hysteresis_band(self):
        """
        A signal that dips clearly below (90° - 5°) = 85° must be detected
        even after hovering near the threshold.
        """
        stand = np.full(15, 170.0)
        descend = np.linspace(170.0, 80.0, 20)
        ascend = np.linspace(80.0, 170.0, 20)
        stand2 = np.full(15, 170.0)
        angles = np.concatenate([stand, descend, ascend, stand2])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 1


# ---------------------------------------------------------------------------
# 5. Min rep duration 0.5 s filter
# ---------------------------------------------------------------------------


class TestMinRepDuration:
    def test_too_short_rep_not_counted(self):
        """
        A rep that takes only 5 frames at 30 fps = 0.17 s (< 0.5 s) must be
        ignored.
        """
        stand = np.full(5, 170.0)
        # Very fast descent + ascent — 2 frames each
        descend = np.array([170.0, 75.0])
        ascend = np.array([75.0, 170.0])
        angles = np.concatenate([stand, descend, ascend, stand])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 0

    def test_long_enough_rep_counted(self):
        """
        A rep spanning well over 0.5 s must count.
        Use frames_per_phase=10: 4 phases × 10 frames = 40 frames → 1.3 s at
        30 fps. The state-machine window (DESCENDING entry → STANDING re-entry)
        comfortably exceeds the 15-frame (0.5 s) minimum even with the updated
        squat standing threshold of 150°.
        """
        angles = _squat_rep_angles(n_reps=1, frames_per_phase=10)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 1


# ---------------------------------------------------------------------------
# 6. Empty / flat signal returns no reps
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_signal_returns_empty(self):
        reps = detect_reps(np.array([]), [], "squat", "standard", FPS)
        assert reps == []

    def test_flat_standing_signal_no_reps(self):
        angles = np.full(60, 170.0)
        landmarks = _make_landmarks(60)
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps == []

    def test_flat_bottom_signal_no_reps(self):
        """Signal stuck at 70° — never returns to standing."""
        angles = np.full(60, 70.0)
        landmarks = _make_landmarks(60)
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps == []

    def test_single_frame_returns_empty(self):
        angles = np.array([170.0])
        landmarks = _make_landmarks(1)
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps == []


# ---------------------------------------------------------------------------
# 7. Confidence score
# ---------------------------------------------------------------------------


class TestConfidenceScore:
    """Confidence is a 0.0 placeholder — pipeline Step 7 backfills with Tier 5."""

    def test_confidence_is_placeholder_zero(self):
        angles = _squat_rep_angles(n_reps=2)
        landmarks = _make_landmarks(len(angles), visibility=0.8)
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        for rep in reps:
            assert rep.confidence_score == 0.0

    def test_confidence_same_regardless_of_visibility(self):
        """detect_reps no longer computes confidence — all reps get 0.0."""
        angles = _squat_rep_angles(n_reps=1)
        n = len(angles)
        high_vis_landmarks = _make_landmarks(n, visibility=2.0)
        low_vis_landmarks = _make_landmarks(n, visibility=-2.0)

        high_reps = detect_reps(angles, high_vis_landmarks, "squat", "standard", FPS)
        low_reps = detect_reps(angles, low_vis_landmarks, "squat", "standard", FPS)

        assert high_reps[0].confidence_score == 0.0
        assert low_reps[0].confidence_score == 0.0


# ---------------------------------------------------------------------------
# 8. DetectedRep dataclass fields
# ---------------------------------------------------------------------------


class TestDetectedRepFields:
    def test_all_fields_present(self):
        angles = _squat_rep_angles(n_reps=1)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        rep = reps[0]
        assert hasattr(rep, "rep_index")
        assert hasattr(rep, "start_frame")
        assert hasattr(rep, "end_frame")
        assert hasattr(rep, "confidence_score")
        assert hasattr(rep, "min_angle")

    def test_frames_within_bounds(self):
        angles = _squat_rep_angles(n_reps=2)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        n = len(angles)
        for rep in reps:
            assert 0 <= rep.start_frame < n
            assert 0 <= rep.end_frame < n


# ---------------------------------------------------------------------------
# 9. Zero-rep and partial-rep edge cases (B-086)
# ---------------------------------------------------------------------------


class TestZeroRepAndPartialRep:
    """Tests for videos where no rep or only a partial rep occurs."""

    # --- Zero-rep scenarios ---

    def test_zero_rep_constant_standing_angle(self):
        """A flat signal at 170° (never descending) yields zero reps."""
        angles = np.full(90, 170.0)
        landmarks = _make_landmarks(90)
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps == []

    def test_zero_rep_never_reaches_depth(self):
        """
        Descent to 120° — never deep enough to cross the squat depth threshold
        (effective threshold: 110° - 5° = 105°). 120° > 105°, so BOTTOM state
        is never entered.  Result: zero reps counted.
        """
        stand = np.full(15, 170.0)
        # descend but only reach 120°, never crosses <105° effective threshold
        descend = np.linspace(170.0, 120.0, 20)
        ascend = np.linspace(120.0, 170.0, 20)
        stand2 = np.full(15, 170.0)
        angles = np.concatenate([stand, descend, ascend, stand2])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps == []

    def test_zero_rep_signal_aborted_before_depth(self):
        """
        Movement starts (transitions to DESCENDING) but immediately rises
        back to standing before reaching depth. Must count as zero reps.
        """
        stand = np.full(10, 170.0)
        # Drop below standing_thresh - hysteresis = 155°, but only to 130°
        partial_down = np.linspace(170.0, 130.0, 8)
        # Rise back to standing immediately
        back_up = np.linspace(130.0, 175.0, 8)
        hold = np.full(10, 175.0)
        angles = np.concatenate([stand, partial_down, back_up, hold])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        # Never hit depth (130° > 85°), so state aborts back to STANDING
        assert reps == []

    def test_zero_rep_single_frame_at_standing(self):
        """A single-frame signal at standing angle returns zero reps."""
        angles = np.array([170.0])
        landmarks = _make_landmarks(1)
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps == []

    def test_zero_rep_two_frames(self):
        """Two frames — insufficient for any state transitions."""
        angles = np.array([170.0, 165.0])
        landmarks = _make_landmarks(2)
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps == []

    def test_zero_rep_empty_signal(self):
        """Empty numpy array yields empty result (no crash)."""
        reps = detect_reps(np.array([]), [], "squat", "standard", FPS)
        assert reps == []

    def test_zero_rep_all_exercises_no_movement(self):
        """Flat standing-angle signal returns zero reps across all exercises."""
        for exercise, variant, standing in [
            ("squat", "high_bar", 170.0),
            ("bench", "flat", 170.0),
            ("deadlift", "conventional", 170.0),
        ]:
            angles = np.full(60, standing)
            landmarks = _make_landmarks(60)
            reps = detect_reps(angles, landmarks, exercise, variant, FPS)
            assert reps == [], f"{exercise}/{variant} should yield 0 reps"

    # --- Partial-rep scenarios ---

    def test_partial_rep_descent_only_no_return(self):
        """
        Movement descends all the way to bottom depth but the video ends
        before the subject returns to standing. The state machine reaches
        ASCENDING or BOTTOM but never completes the final transition.
        Result: zero completed reps.
        """
        stand = np.full(15, 170.0)
        # Descend well below depth threshold (85°), reaching 70°
        descend = np.linspace(170.0, 70.0, 20)
        # Partial ascent — rises to 100° but video ends before reaching 155°
        partial_up = np.linspace(70.0, 100.0, 10)
        angles = np.concatenate([stand, descend, partial_up])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        # Rep never completes (never returned above standing_thresh - hysteresis)
        assert reps == []

    def test_partial_rep_reaches_bottom_but_signal_ends(self):
        """
        Signal descends through depth and stays at bottom — video ends at
        bottom position. No rep completes.
        """
        stand = np.full(10, 170.0)
        descend = np.linspace(170.0, 70.0, 20)
        hold_bottom = np.full(10, 70.0)
        angles = np.concatenate([stand, descend, hold_bottom])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps == []

    def test_partial_rep_does_not_corrupt_subsequent_full_rep(self):
        """
        A partial attempt (descend + abort, no depth) followed by a complete
        rep must yield exactly 1 completed rep.

        The state machine should reset to STANDING after the abort and count
        the subsequent good rep correctly.
        """
        stand = np.full(10, 170.0)
        # First attempt: goes to 130° (no depth) then rises back above standing
        partial_down = np.linspace(170.0, 130.0, 8)
        abort_up = np.linspace(130.0, 175.0, 8)
        stand2 = np.full(5, 175.0)
        # Second attempt: full rep with good depth
        full_rep = _squat_rep_angles(n_reps=1, frames_per_phase=10, standing_angle=175.0)
        angles = np.concatenate([stand, partial_down, abort_up, stand2, full_rep])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 1

    def test_partial_rep_too_short_duration_not_counted(self):
        """
        A rep that achieves the required depth but spans only 2 frames
        at 30 fps (< 0.5 s minimum) must NOT be counted.
        """
        stand = np.full(5, 170.0)
        # Instant descent and ascent — only 2 frames
        instant = np.array([170.0, 80.0, 170.0])
        stand2 = np.full(5, 170.0)
        angles = np.concatenate([stand, instant, stand2])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert reps == []


# ---------------------------------------------------------------------------
# 10. FR-CVPL-07 / FR-REPM-05 — parallel-depth and partial-lockout detection
#     Validates the threshold fix: squat depth 110°, standing 150°.
# ---------------------------------------------------------------------------


class TestSquatThresholdFix:
    """
    FR-CVPL-07: rep detection via threshold-crossing state machine.
    FR-REPM-05: single-rep videos produce valid output.

    The squat depth threshold was lowered from 90° to 110° (effective bottom
    entry: <105° after hysteresis) so that parallel-depth squats (~90–110°
    hip angle) are no longer silently skipped.  The standing threshold was
    lowered from 160° to 150° (effective lockout: >145°) to tolerate athletes
    who do not fully hyperextend at the top.
    """

    def test_parallel_depth_squat_detected(self):
        """
        Hip angle reaching 95° (parallel depth) must be counted as one rep.
        Old threshold (depth=90°, effective=85°) would miss this.
        New threshold (depth=110°, effective=105°): 95° < 105° → BOTTOM entered.
        """
        stand = np.full(15, 165.0)
        descend = np.linspace(165.0, 95.0, 20)
        bottom_hold = np.full(10, 95.0)
        ascend = np.linspace(95.0, 165.0, 20)
        stand2 = np.full(15, 165.0)
        angles = np.concatenate([stand, descend, bottom_hold, ascend, stand2])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 1, (
            f"Expected 1 rep for parallel-depth squat (95°), got {len(reps)}. "
            "Squat depth threshold must be 110° (effective 105°)."
        )

    def test_six_parallel_depth_reps_all_detected(self):
        """
        Six reps where hip reaches 95° must all be counted — this was the
        original undercounting scenario (6-7 reps → 2 detected).
        """
        angles = _squat_rep_angles(n_reps=6, bottom_angle=95.0, standing_angle=165.0)
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 6, (
            f"Expected 6 reps, got {len(reps)}. "
            "Parallel-depth reps at 95° must not be silently skipped."
        )

    def test_quarter_squat_not_detected(self):
        """
        A quarter-squat where hip only reaches 130° must NOT count.
        130° > 105° (effective threshold), so BOTTOM state is never entered.
        """
        stand = np.full(15, 165.0)
        descend = np.linspace(165.0, 130.0, 20)
        bottom_hold = np.full(10, 130.0)
        ascend = np.linspace(130.0, 165.0, 20)
        stand2 = np.full(15, 165.0)
        angles = np.concatenate([stand, descend, bottom_hold, ascend, stand2])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 0, (
            f"Quarter-squat (130°) must not be counted, got {len(reps)} reps."
        )

    def test_incomplete_lockout_rep_still_counted(self):
        """
        An athlete who only returns to 147° between reps (not full 160°+
        lockout) must still have the rep counted.
        New standing threshold is 150°; effective entry is >145°.
        147° > 145° → STANDING state re-entered → rep committed.
        """
        stand = np.full(15, 160.0)
        descend = np.linspace(160.0, 80.0, 20)
        bottom_hold = np.full(10, 80.0)
        # Only return to 147°, not full 160° lockout
        ascend = np.linspace(80.0, 147.0, 20)
        partial_stand = np.full(15, 147.0)
        angles = np.concatenate([stand, descend, bottom_hold, ascend, partial_stand])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        assert len(reps) == 1, (
            f"Incomplete lockout rep (returns to 147°) must be counted, "
            f"got {len(reps)} reps. Standing threshold must be 150°."
        )

    def test_bench_and_deadlift_thresholds_unchanged(self):
        """
        The threshold change is squat-only. Bench (90°) and deadlift
        conventional (70°) depth thresholds must remain unchanged.
        A bench rep reaching 80° must still be detected (80° < 85° effective).
        A deadlift rep reaching 64° must still be detected (64° < 65° effective).
        """
        bench_angles = _bench_rep_angles(n_reps=1, bottom_angle=80.0)
        bench_landmarks = _make_landmarks(len(bench_angles))
        bench_reps = detect_reps(
            bench_angles, bench_landmarks, "bench", "standard", FPS
        )
        assert len(bench_reps) == 1, "Bench at 80° must still be detected."

        dl_angles = _deadlift_rep_angles(n_reps=1, bottom_angle=64.0)
        dl_landmarks = _make_landmarks(len(dl_angles))
        dl_reps = detect_reps(
            dl_angles, dl_landmarks, "deadlift", "conventional", FPS
        )
        assert len(dl_reps) == 1, "Deadlift conventional at 64° must still be detected."
