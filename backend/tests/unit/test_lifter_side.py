"""Unit tests for lifter-side detection (Session 2, L2-LIFTER-SIDE-01).

All tests use synthetic (n_frames, 33, 5) landmark arrays.
"""
from __future__ import annotations

import logging

import numpy as np
import pytest

from app.cv.lifter_side import (
    SideIndices,
    detect_lifter_side,
    landmark_indices_for_side,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LEFT_INDICES = (11, 13, 15, 23, 25, 27, 29, 31)
RIGHT_INDICES = (12, 14, 16, 24, 26, 28, 30, 32)


def _make_session(
    n_frames: int = 30,
    right_visibility: float = 0.9,
    left_visibility: float = 0.3,
    centroid_x: float = 0.5,
) -> np.ndarray:
    """Build a (n_frames, 33, 5) synthetic landmark session.

    Every landmark gets a sensible position so anchor centroid is computable.
    Visibility (col 3) and presence (col 4) are set per side.
    """
    session = np.zeros((n_frames, 33, 5), dtype=float)
    for f in range(n_frames):
        for idx in range(33):
            session[f, idx, 0] = centroid_x  # x
            session[f, idx, 1] = 0.4 + (idx % 10) * 0.05  # y spread
            session[f, idx, 4] = 1.0  # presence
        for idx in RIGHT_INDICES:
            session[f, idx, 3] = right_visibility
        for idx in LEFT_INDICES:
            session[f, idx, 3] = left_visibility
    return session


# ---------------------------------------------------------------------------
# detect_lifter_side
# ---------------------------------------------------------------------------


class TestDetectLifterSide:
    def test_right_dominant_visibility_returns_right(self) -> None:
        session = _make_session(right_visibility=0.95, left_visibility=0.20)
        assert detect_lifter_side(session) == "right"

    def test_left_dominant_visibility_returns_left(self) -> None:
        session = _make_session(right_visibility=0.20, left_visibility=0.95)
        assert detect_lifter_side(session) == "left"

    def test_tie_defaults_to_right(self) -> None:
        session = _make_session(right_visibility=0.7, left_visibility=0.7)
        assert detect_lifter_side(session) == "right"

    def test_near_tie_within_5pct_defaults_to_right(self) -> None:
        # 0.70 vs 0.72 → relative diff 0.0278 < 0.05 → ambiguous → "right".
        session = _make_session(right_visibility=0.70, left_visibility=0.72)
        assert detect_lifter_side(session) == "right"

    def test_clear_left_dominance_above_5pct_returns_left(self) -> None:
        # 0.70 vs 0.80 → relative diff 0.125 > 0.05 → unambiguous → "left".
        session = _make_session(right_visibility=0.70, left_visibility=0.80)
        assert detect_lifter_side(session) == "left"

    def test_only_uses_first_three_seconds_when_fps_provided(self) -> None:
        left = _make_session(n_frames=90, right_visibility=0.10, left_visibility=0.95)
        right = _make_session(n_frames=210, right_visibility=0.95, left_visibility=0.10)
        session = np.concatenate([left, right], axis=0)
        assert detect_lifter_side(session, fps=30.0) == "left"

    def test_handles_empty_session_returns_right(self) -> None:
        empty = np.zeros((0, 33, 5), dtype=float)
        assert detect_lifter_side(empty) == "right"

    def test_returns_literal_left_or_right_only(self) -> None:
        session = _make_session()
        result = detect_lifter_side(session)
        assert result in ("left", "right")

    def test_handles_wrong_shape_returns_right(self) -> None:
        # 2-D array slips through — treat as no-detection, default right.
        bad = np.zeros((10, 33), dtype=float)
        assert detect_lifter_side(bad) == "right"


# ---------------------------------------------------------------------------
# Ambiguous detection logs WARNING
# ---------------------------------------------------------------------------


class TestDetectLifterSideLogging:
    def test_ambiguous_detection_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        session = _make_session(right_visibility=0.70, left_visibility=0.72)
        with caplog.at_level(logging.WARNING, logger="app.cv.lifter_side"):
            detect_lifter_side(session)
        assert any(
            "ambiguous lifter-side detection" in rec.message.lower()
            for rec in caplog.records
        ), f"Expected WARNING for ambiguous case; got: {[r.message for r in caplog.records]}"

    def test_clear_dominance_does_not_log_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        session = _make_session(right_visibility=0.95, left_visibility=0.20)
        with caplog.at_level(logging.WARNING, logger="app.cv.lifter_side"):
            detect_lifter_side(session)
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warnings == [], (
            f"Did not expect WARNING for clear-dominance case; got: "
            f"{[r.message for r in warnings]}"
        )


# ---------------------------------------------------------------------------
# landmark_indices_for_side
# ---------------------------------------------------------------------------


class TestLandmarkIndicesForSide:
    def test_right_side_returns_even_indices(self) -> None:
        idx = landmark_indices_for_side("right")
        assert isinstance(idx, SideIndices)
        assert idx.shoulder == 12
        assert idx.elbow == 14
        assert idx.wrist == 16
        assert idx.hip == 24
        assert idx.knee == 26
        assert idx.ankle == 28
        assert idx.heel == 30
        assert idx.foot_index == 32

    def test_left_side_returns_odd_indices(self) -> None:
        idx = landmark_indices_for_side("left")
        assert idx.shoulder == 11
        assert idx.elbow == 13
        assert idx.wrist == 15
        assert idx.hip == 23
        assert idx.knee == 25
        assert idx.ankle == 27
        assert idx.heel == 29
        assert idx.foot_index == 31

    def test_rejects_unknown_side(self) -> None:
        with pytest.raises(ValueError, match="side must be"):
            landmark_indices_for_side("unknown")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Anchor-based robustness (R1 mitigation)
# ---------------------------------------------------------------------------


class TestAnchorRobustness:
    def test_bystander_on_opposite_side_does_not_flip_detection(self) -> None:
        """A bystander whose visible body-side is OPPOSITE the lifter must
        not flip detection. With the anchor restriction the lifter's side
        still wins even when bystander landmarks at the same indices are
        far from the lifter centroid.
        """
        # Lifter occupies x ~ 0.5 with right-side dominance.
        session = _make_session(
            n_frames=30,
            right_visibility=0.90,
            left_visibility=0.30,
            centroid_x=0.5,
        )
        # Simulate a bystander: move LEFT-side landmarks (EXCEPT the hip,
        # which defines the anchor) far from the lifter centroid (to x=0.9)
        # and crank their visibility, mimicking MediaPipe briefly locking
        # onto a second person for the shoulder/elbow/etc. The lifter's
        # hips remain at x=0.5 so the anchor centroid is unchanged.
        bystander_indices = tuple(i for i in LEFT_INDICES if i != 23)
        for f in range(30):
            for idx in bystander_indices:
                session[f, idx, 0] = 0.9  # far from centroid 0.5
                session[f, idx, 3] = 0.99
        # Without anchor: bystander left landmarks at vis=0.99 dominate over
        # lifter right at vis=0.90 → left would win.
        # With anchor (centroid ~0.5, threshold 0.25 → window [0.25, 0.75]):
        # bystander left landmarks at x=0.9 are excluded → lifter's right wins.
        assert detect_lifter_side(session) == "right"

    def test_no_anchor_available_falls_back_to_naive_mean(self) -> None:
        """If no hip samples meet the visibility floor, anchor is None and
        the function still returns a valid side without raising.
        """
        session = _make_session(right_visibility=0.95, left_visibility=0.20)
        session[:, 23, 3] = 0.0
        session[:, 24, 3] = 0.0
        result = detect_lifter_side(session)
        assert result in ("left", "right")


# ---------------------------------------------------------------------------
# Stability (no randomness)
# ---------------------------------------------------------------------------


class TestStability:
    def test_repeated_invocations_return_same_side(self) -> None:
        session = _make_session()
        sides = {detect_lifter_side(session) for _ in range(5)}
        assert len(sides) == 1
