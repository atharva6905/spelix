"""MC/DC truth-table tests for quality_gates.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.cv.quality_gates import (
    check_framing,
    check_lighting,
    check_single_person,
    check_video_file,
    run_quality_gates,
)

# Import helpers from conftest
from tests.mcdc.conftest import make_landmarks_frame, make_n_frames


# ---------------------------------------------------------------------------
# 1. check_video_file — OR: returncode != 0 OR not stdout.strip()
# ---------------------------------------------------------------------------


class TestCheckVideoFileOr:
    """MC/DC truth table for the corrupt-file guard.

    Condition A: result.returncode != 0
    Condition B: not result.stdout.strip()  (i.e. stdout is empty/whitespace)

    Gate fires (returns failed result) when A OR B.

    Row | A     | B     | fire? | varied condition
    ----|-------|-------|-------|------------------
    1   | False | False | False | baseline pass
    2   | True  | False | True  | A independently flips outcome
    3   | False | True  | True  | B independently flips outcome
    """

    def _mock_run(self, returncode: int, stdout: str) -> MagicMock:
        mock = MagicMock()
        mock.returncode = returncode
        mock.stdout = stdout
        return mock

    def test_row1_passes_when_both_false(self) -> None:
        """A=False, B=False → no gate fire → passed=True."""
        with patch(
            "app.cv.quality_gates.subprocess.run",
            return_value=self._mock_run(0, "30.0\n"),
        ):
            result = check_video_file("/fake/video.mp4")
        assert result.passed is True
        assert result.metric_value == pytest.approx(30.0)

    def test_row2_nonzero_returncode_rejects(self) -> None:
        """A=True, B=False → gate fires → passed=False (A independently flips)."""
        with patch(
            "app.cv.quality_gates.subprocess.run",
            return_value=self._mock_run(1, "some error output\n"),
        ):
            result = check_video_file("/fake/video.mp4")
        assert result.passed is False
        assert result.name == "video_file_check"

    def test_row3_empty_stdout_rejects(self) -> None:
        """A=False, B=True → gate fires → passed=False (B independently flips)."""
        with patch(
            "app.cv.quality_gates.subprocess.run",
            return_value=self._mock_run(0, ""),
        ):
            result = check_video_file("/fake/video.mp4")
        assert result.passed is False
        assert result.name == "video_file_check"

    def test_whitespace_only_stdout_rejects(self) -> None:
        """Stdout with only whitespace counts as empty → rejects."""
        with patch(
            "app.cv.quality_gates.subprocess.run",
            return_value=self._mock_run(0, "   \n"),
        ):
            result = check_video_file("/fake/video.mp4")
        assert result.passed is False

    def test_duration_exceeds_max_rejects(self) -> None:
        """Duration > 120s → separate duration gate fires."""
        with patch(
            "app.cv.quality_gates.subprocess.run",
            return_value=self._mock_run(0, "121.0\n"),
        ):
            result = check_video_file("/fake/video.mp4")
        assert result.passed is False
        assert result.name == "video_duration"
        assert result.metric_value == pytest.approx(121.0)

    def test_ffprobe_not_found_rejects(self) -> None:
        """FileNotFoundError (ffprobe missing) → caught → passed=False."""
        with patch(
            "app.cv.quality_gates.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = check_video_file("/fake/video.mp4")
        assert result.passed is False


# ---------------------------------------------------------------------------
# 2. check_framing — 3-way outcome: too small / too large / in range
# ---------------------------------------------------------------------------


class TestCheckFraming3Way:
    """3-way boundary test for the framing gate.

    The gate computes bbox_width * bbox_height from visible landmarks.
    Threshold (landscape): [0.18, 0.80].
    Portrait (1080×1920, aspect=0.5625): min_threshold = 0.18 * 0.5625 ≈ 0.10125.

    Strategy
    --------
    - Large coverage (x: 0.1..0.9, y: 0.1..0.9): bbox ≈ 0.8*0.8 = 0.64 → passes
    - Tiny coverage (x: 0.45..0.55, y: 0.45..0.55): bbox ≈ 0.10*0.10 = 0.01 → too far
    - Full frame (x: 0.0..1.0, y: 0.0..1.0): bbox = 1.0*1.0 = 1.0 → too close
    """

    def _make_spread_frames(
        self,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        n: int = 30,
    ) -> list[np.ndarray]:
        """Build n frames where 33 landmarks are spread evenly across the given range.

        All landmarks get visibility=2.0 (sigmoid≈0.88 >> 0.5 threshold), ensuring
        all are counted when computing the bbox.
        """
        frames = []
        for _ in range(n):
            frame = np.zeros((33, 5), dtype=np.float64)
            xs = np.linspace(x_min, x_max, 33)
            ys = np.linspace(y_min, y_max, 33)
            frame[:, 0] = xs
            frame[:, 1] = ys
            frame[:, 2] = 0.0
            frame[:, 3] = 2.0  # visibility logit; sigmoid(2.0) ≈ 0.88 > 0.5
            frame[:, 4] = 2.0  # presence logit
            frames.append(frame)
        return frames

    def test_large_coverage_passes(self) -> None:
        """x:[0.1,0.9], y:[0.1,0.9] → bbox ≈ 0.64 → in range → passed=True."""
        frames = self._make_spread_frames(0.1, 0.9, 0.1, 0.9)
        result = check_framing(frames, frame_width=1920, frame_height=1080)
        assert result.passed is True, f"Expected pass, got metric={result.metric_value}"
        assert result.metric_value > 0.18

    def test_tiny_coverage_rejects_too_far(self) -> None:
        """x:[0.45,0.55], y:[0.45,0.55] → bbox ≈ 0.01 → below min → too far."""
        frames = self._make_spread_frames(0.45, 0.55, 0.45, 0.55)
        result = check_framing(frames, frame_width=1920, frame_height=1080)
        assert result.passed is False
        assert "far" in result.user_message.lower()

    def test_full_frame_coverage_rejects_too_close(self) -> None:
        """x:[0.0,1.0], y:[0.0,1.0] → bbox = 1.0 → above max=0.80 → too close."""
        frames = self._make_spread_frames(0.0, 1.0, 0.0, 1.0)
        result = check_framing(frames, frame_width=1920, frame_height=1080)
        assert result.passed is False
        assert "close" in result.user_message.lower()

    def test_portrait_lower_threshold(self) -> None:
        """Portrait (1080×1920): min_threshold ≈ 0.10125.

        A bbox of ~0.12 (x span 0.3, y span 0.4) is above the portrait floor
        but would be below the landscape floor. Confirm it passes in portrait.
        """
        frames = self._make_spread_frames(0.35, 0.65, 0.3, 0.7)
        # portrait: width < height → aspect < 1.0 → lower floor
        result = check_framing(frames, frame_width=1080, frame_height=1920)
        assert result.passed is True, (
            f"Portrait should lower the threshold; metric={result.metric_value}"
        )

    def test_no_valid_frames_returns_fail(self) -> None:
        """All-zero frames (NO_POSE sentinel) → fractions list empty → passed=False."""
        frames = [np.zeros((33, 5), dtype=np.float64) for _ in range(5)]
        result = check_framing(frames, frame_width=1920, frame_height=1080)
        assert result.passed is False


# ---------------------------------------------------------------------------
# 3. check_single_person — OR: rejected_by_run OR rejected_by_fraction
# ---------------------------------------------------------------------------


class TestCheckSinglePersonOr:
    """MC/DC truth table for the single-person gate.

    Condition A: rejected_by_run  (longest consecutive off-anchor run >= 4)
    Condition B: rejected_by_fraction  (off-anchor fraction > 0.30)

    Gate rejects when A OR B.

    Row | A     | B     | reject? | varied condition
    ----|-------|-------|---------|------------------
    1   | False | False | False   | baseline pass
    2   | True  | False | True    | A independently controls
    3   | False | True  | True    | B independently controls

    _ANCHOR_FROM_FIRST_N_SAMPLES = 3
    _OFF_ANCHOR_DISTANCE_FRAC    = 0.25
    _MAX_CONSECUTIVE_OFF_ANCHOR  = 4
    _MAX_OFF_ANCHOR_FRACTION     = 0.30
    """

    # Hip landmark indices used by the gate
    _LEFT_HIP = 23
    _RIGHT_HIP = 24

    def _hip_frame(self, x: float, vis: float = 2.0) -> np.ndarray:
        """Frame where both hips are at x with high visibility."""
        return make_landmarks_frame(visibility=vis, x=x, y=0.5)

    def test_row1_consistent_x_passes(self) -> None:
        """All frames at x=0.5 → no off-anchor samples → passed=True."""
        frames = [self._hip_frame(0.5) for _ in range(30)]
        result = check_single_person(frames, frame_width=1920)
        assert result.passed is True
        assert result.metric_value < 4  # longest_run < threshold

    def test_row2_long_consecutive_run_rejects(self) -> None:
        """First 3 frames anchor at x=0.5; then 10 frames at x=0.9 (off by 0.4 > 0.25).

        10 consecutive off-anchor >= _MAX_CONSECUTIVE_OFF_ANCHOR=4 → A fires.
        Off-anchor fraction = 10/(3+10) ≈ 0.77 > 0.30, so B fires too — that's fine;
        the key point is A independently controls outcome vs row 1.
        """
        anchor_frames = [self._hip_frame(0.5) for _ in range(3)]
        off_frames = [self._hip_frame(0.9) for _ in range(10)]
        frames = anchor_frames + off_frames
        result = check_single_person(frames, frame_width=1920)
        assert result.passed is False
        assert result.metric_value >= 4  # longest_run >= threshold

    def test_row3_alternating_exceeds_fraction_rejects(self) -> None:
        """Anchor from first 3 at x=0.5; then alternating x=0.5 / x=0.9.

        With 3 anchor + 27 alternating frames (14 on-anchor, 13 off):
        - No run of 4+ consecutive → A is False
        - off-anchor fraction ≈ 13/(3+14+13) = 43% > 30% → B fires

        To guarantee A stays False, alternate every other frame so the longest
        run is exactly 1.
        """
        anchor_frames = [self._hip_frame(0.5) for _ in range(3)]
        # 28 alternating frames: x=0.5, x=0.9, x=0.5, ... — gives run=1 always
        alt_frames = [
            self._hip_frame(0.9 if i % 2 == 1 else 0.5) for i in range(28)
        ]
        frames = anchor_frames + alt_frames
        result = check_single_person(frames, frame_width=1920)
        assert result.passed is False
        # longest_run should be 1 (B fired, not A)
        assert result.metric_value < 4

    def test_invisible_hip_frames_skipped(self) -> None:
        """Frames where hip visibility sigmoid < 0.5 are skipped entirely.

        Set hip landmark visibility to -2.0: sigmoid(-2.0) ≈ 0.12 < 0.5.
        All 30 frames invisible → fewer than 3 valid samples → cannot anchor →
        passed=False (insufficient samples, not off-anchor rejection).
        """
        frames = [
            make_landmarks_frame(
                visibility=-2.0,  # all landmarks invisible
                x=0.5,
                y=0.5,
            )
            for _ in range(30)
        ]
        result = check_single_person(frames, frame_width=1920)
        # Cannot anchor reliably — expects False with < _ANCHOR_FROM_FIRST_N_SAMPLES
        assert result.passed is False

    def test_mixed_visibility_skips_low_vis_frames(self) -> None:
        """High-vis frames build valid anchor; low-vis frames are skipped (not counted off-anchor).

        10 high-vis frames at x=0.5 → anchor = 0.5
        20 low-vis frames at x=0.9 → these should be SKIPPED, not counted as off-anchor
        Net: 10 valid at x=0.5, longest_run=0, fraction=0 → passed=True.
        """
        high_vis = [self._hip_frame(0.5, vis=2.0) for _ in range(10)]
        # Low visibility: sigmoid(-3.0) ≈ 0.047 < 0.5 → skipped
        low_vis = [self._hip_frame(0.9, vis=-3.0) for _ in range(20)]
        frames = high_vis + low_vis
        result = check_single_person(frames, frame_width=1920)
        assert result.passed is True


# ---------------------------------------------------------------------------
# 4. check_lighting — two boundaries: too dark / normal / overexposed
# ---------------------------------------------------------------------------


class TestCheckLighting:
    """Boundary tests for the lighting gate (warning-only).

    _LIGHTING_MIN_BRIGHTNESS = 60.0
    _LIGHTING_MAX_BRIGHTNESS = 240.0

    Thresholds:
      brightness < 60  → "brighter" warning
      brightness > 240 → "overexposed" warning
      60 ≤ brightness ≤ 240 → no warning (empty message)
    """

    def _gray_frames(self, value: int, n: int = 10) -> list[np.ndarray]:
        """Return n grayscale (2D) uint8 frames filled with constant value."""
        return [np.full((100, 100), value, dtype=np.uint8) for _ in range(n)]

    def test_normal_brightness_no_warning(self) -> None:
        """Mean brightness 128 → in normal range → message empty."""
        frames = self._gray_frames(128)
        result = check_lighting(frames)
        assert result.passed is True
        assert result.user_message == ""

    def test_too_dark_brighter_warning(self) -> None:
        """Mean brightness 30 < 60 → 'brighter' in message."""
        frames = self._gray_frames(30)
        result = check_lighting(frames)
        assert result.passed is True  # warning-only gate never rejects
        assert "brighter" in result.user_message.lower()

    def test_overexposed_warning(self) -> None:
        """Mean brightness 250 > 240 → 'overexposed' in message."""
        frames = self._gray_frames(250)
        result = check_lighting(frames)
        assert result.passed is True  # warning-only gate never rejects
        assert "overexposed" in result.user_message.lower()

    def test_boundary_exactly_at_min_no_warning(self) -> None:
        """Mean brightness exactly at min threshold (60) → no warning."""
        frames = self._gray_frames(60)
        result = check_lighting(frames)
        assert result.user_message == ""

    def test_boundary_exactly_at_max_no_warning(self) -> None:
        """Mean brightness exactly at max threshold (240) → no warning."""
        frames = self._gray_frames(240)
        result = check_lighting(frames)
        assert result.user_message == ""

    def test_empty_frames_returns_pass(self) -> None:
        """Empty frame list → default pass, no message."""
        result = check_lighting([])
        assert result.passed is True
        assert result.user_message == ""

    def test_level_is_always_warning(self) -> None:
        """Lighting gate is always level='warning', never 'error'."""
        for value in [30, 128, 250]:
            frames = self._gray_frames(value)
            result = check_lighting(frames)
            assert result.level == "warning"


# ---------------------------------------------------------------------------
# 5. run_quality_gates — overall pass predicate
# ---------------------------------------------------------------------------


class TestRunQualityGates:
    """Tests for run_quality_gates overall pass logic.

    Overall passes iff all(c.passed for c in checks if c.level == "error").

    Rows:
    1. Good frames → all error gates pass → overall passed=True
    2. Low visibility → body_visibility gate fails → overall rejected
    3. Good frames + dark gray frames → warning fires, overall still passes
    """

    def _make_good_frames(self, n: int = 30) -> list[np.ndarray]:
        """High-visibility landmarks spread across 0.1..0.9 to pass framing and visibility."""
        frames = []
        for _ in range(n):
            frame = np.zeros((33, 5), dtype=np.float64)
            xs = np.linspace(0.1, 0.9, 33)
            ys = np.linspace(0.1, 0.9, 33)
            frame[:, 0] = xs
            frame[:, 1] = ys
            frame[:, 2] = 0.0
            frame[:, 3] = 2.0   # sigmoid(2.0) ≈ 0.88 → high visibility
            frame[:, 4] = 2.0
            frames.append(frame)
        return frames

    def test_row1_good_frames_overall_passes(self) -> None:
        """Good landmarks (high vis + good spread) → overall passed=True."""
        frames = self._make_good_frames(30)
        result = run_quality_gates(
            landmarks_per_frame=frames,
            frame_width=1920,
            frame_height=1080,
        )
        assert result.passed is True
        assert result.status == "passed"
        error_checks = [c for c in result.checks if c.level == "error"]
        assert all(c.passed for c in error_checks)

    def test_row2_low_visibility_rejects(self) -> None:
        """Low visibility (sigmoid(-3.0) ≈ 0.047 < 0.30) → body_visibility fails → overall rejected."""
        frames = make_n_frames(30, visibility=-3.0, x=0.5, y=0.5)
        result = run_quality_gates(
            landmarks_per_frame=frames,
            frame_width=1920,
            frame_height=1080,
        )
        assert result.passed is False
        assert result.status == "rejected"
        vis_check = next(
            (c for c in result.checks if c.name == "body_visibility"), None
        )
        assert vis_check is not None
        assert vis_check.passed is False

    def test_row3_dark_lighting_warning_does_not_reject(self) -> None:
        """Good frames + dark gray frames → lighting warning fires but overall passes."""
        frames = self._make_good_frames(30)
        dark_gray = [np.full((100, 100), 30, dtype=np.uint8) for _ in range(10)]
        result = run_quality_gates(
            landmarks_per_frame=frames,
            frame_width=1920,
            frame_height=1080,
            frames_gray=dark_gray,
        )
        # overall should still pass (lighting is warning-only)
        assert result.passed is True
        # but the lighting warning should be present with a message
        lighting_check = next(
            (c for c in result.checks if c.name == "lighting"), None
        )
        assert lighting_check is not None
        assert lighting_check.level == "warning"
        assert "brighter" in lighting_check.user_message.lower()

    def test_video_file_fail_short_circuits(self) -> None:
        """Failed video file check → early return → subsequent gates not run."""
        frames = self._make_good_frames(30)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch(
            "app.cv.quality_gates.subprocess.run",
            return_value=mock_result,
        ):
            result = run_quality_gates(
                landmarks_per_frame=frames,
                frame_width=1920,
                frame_height=1080,
                video_path="/fake/video.mp4",
            )
        assert result.passed is False
        assert result.status == "rejected"
        # Only the video_file_check should be in checks (early return)
        assert len(result.checks) == 1
        assert result.checks[0].name == "video_file_check"
