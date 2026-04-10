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
        Oscillation around 90° (squat depth threshold) while already descending
        must not create multiple false bottom detections.
        """
        # Build: stand → descend to exactly at-threshold zone
        stand = np.full(15, 170.0)
        descend = np.linspace(170.0, 92.0, 15)
        # hover near 90° with ±4° noise (within hysteresis band)
        hover = 92.0 + 4.0 * np.sin(2 * np.pi * np.arange(20) / 5)
        ascend = np.linspace(92.0, 170.0, 15)
        stand2 = np.full(15, 170.0)
        angles = np.concatenate([stand, descend, hover, ascend, stand2])
        landmarks = _make_landmarks(len(angles))
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        # Should be 0 reps — never truly reached depth (<90°)
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
        A rep spanning 24 frames at 30 fps = 0.8 s (> 0.5 s) must count.
        """
        angles = _squat_rep_angles(n_reps=1, frames_per_phase=6)
        # Total per rep ≈ 4 phases × 6 frames = 24 frames → 0.8 s at 30 fps
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
    def test_confidence_in_unit_interval(self):
        angles = _squat_rep_angles(n_reps=2)
        landmarks = _make_landmarks(len(angles), visibility=0.8)
        reps = detect_reps(angles, landmarks, "squat", "standard", FPS)
        for rep in reps:
            assert 0.0 <= rep.confidence_score <= 1.0

    def test_higher_visibility_gives_higher_confidence(self):
        angles = _squat_rep_angles(n_reps=1)
        n = len(angles)
        high_vis_landmarks = _make_landmarks(n, visibility=2.0)  # high logit
        low_vis_landmarks = _make_landmarks(n, visibility=-2.0)  # low logit

        high_reps = detect_reps(angles, high_vis_landmarks, "squat", "standard", FPS)
        low_reps = detect_reps(angles, low_vis_landmarks, "squat", "standard", FPS)

        assert len(high_reps) == 1
        assert len(low_reps) == 1
        assert high_reps[0].confidence_score > low_reps[0].confidence_score

    def test_bench_uses_upper_body_landmarks(self):
        """
        Bench should use landmarks {11,12,13,14,15,16}.
        We set those to high visibility and hip/lower landmarks to low.
        """
        angles = _bench_rep_angles(n_reps=1)
        n = len(angles)
        landmarks = _make_landmarks(n, visibility=-3.0)  # all low
        # Set upper-body bench landmarks to high
        for lm in landmarks:
            for idx in (11, 12, 13, 14, 15, 16):
                lm[idx, 3] = 3.0  # high logit → sigmoid ~0.95

        reps = detect_reps(angles, landmarks, "bench", "standard", FPS)
        assert len(reps) == 1
        assert reps[0].confidence_score > 0.7


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
        Descent to 100° — within standing hysteresis band but never deep
        enough to cross the squat depth threshold (<90° - 5° = 85°).
        Result: zero reps counted.
        """
        stand = np.full(15, 170.0)
        # descend but only reach 100°, never crosses <85°
        descend = np.linspace(170.0, 100.0, 20)
        ascend = np.linspace(100.0, 170.0, 20)
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
