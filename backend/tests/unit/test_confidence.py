"""
Unit tests for app.cv.confidence (FR-RESL-08, FR-SCOR-10, FR-CVPL-24).

All tests use synthetic numpy arrays — no real video, no DB, no IO.
Landmark arrays: shape (33, 5) per frame — [x, y, z, visibility, presence].

Phase 0 compute_rep_confidence tests removed: function superseded by
compute_confidence_result (FR-CVPL-24, ADR-015).  Removal enforced by
TestComputeRepConfidenceIsRemoved guard below.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.cv.confidence import (
    compute_session_confidence,
    confidence_guidance,
    confidence_label,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_frame(visibility_by_index: dict[int, float], default_vis: float = 0.9) -> np.ndarray:
    """
    Create a (33, 5) landmark array.

    Parameters
    ----------
    visibility_by_index:
        Mapping from landmark index to raw visibility value (may be logit).
    default_vis:
        Visibility used for all landmarks not in visibility_by_index.
    """
    frame = np.zeros((33, 5), dtype=np.float64)
    for i in range(33):
        frame[i, 3] = visibility_by_index.get(i, default_vis)
    return frame


# ---------------------------------------------------------------------------
# Tests: compute_session_confidence
# ---------------------------------------------------------------------------


class TestComputeSessionConfidence:
    def test_mean_of_rep_confidences(self):
        """Session confidence is the simple mean of per-rep scores."""
        rep_scores = [0.8, 0.6, 0.7]
        result = compute_session_confidence(rep_scores)
        assert abs(result - (0.8 + 0.6 + 0.7) / 3) < 1e-9

    def test_single_rep(self):
        """Single-rep session confidence equals that rep's confidence."""
        result = compute_session_confidence([0.75])
        assert abs(result - 0.75) < 1e-9

    def test_all_ones(self):
        result = compute_session_confidence([1.0, 1.0, 1.0])
        assert abs(result - 1.0) < 1e-9

    def test_all_zeros(self):
        result = compute_session_confidence([0.0, 0.0])
        assert abs(result - 0.0) < 1e-9

    def test_result_in_unit_interval(self):
        """Output must be in [0, 1] for valid inputs."""
        result = compute_session_confidence([0.5, 0.9, 0.3])
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Tests: confidence_label
# ---------------------------------------------------------------------------


class TestConfidenceLabel:
    @pytest.mark.parametrize(
        "score, expected_label",
        [
            (1.00, "High"),
            (0.80, "High"),        # boundary: exactly 0.80 → High
            (0.79, "Moderate"),    # boundary: 0.79 → Moderate
            (0.65, "Moderate"),    # boundary: 0.65 → Moderate
            (0.64, "Low"),         # boundary: 0.64 → Low
            (0.50, "Low"),         # boundary: 0.50 → Low
            (0.49, "Very Low"),    # boundary: 0.49 → Very Low
            (0.00, "Very Low"),
            (0.73, "Moderate"),
            (0.55, "Low"),
            (0.82, "High"),
        ],
    )
    def test_label_boundaries(self, score: float, expected_label: str):
        assert confidence_label(score) == expected_label

    def test_returns_string(self):
        assert isinstance(confidence_label(0.7), str)


# ---------------------------------------------------------------------------
# Tests: confidence_guidance
# ---------------------------------------------------------------------------


class TestConfidenceGuidance:
    def test_high_guidance(self):
        result = confidence_guidance("High")
        assert result == (
            "Landmark visibility is strong — high confidence in analysis accuracy."
        )

    def test_moderate_guidance(self):
        result = confidence_guidance("Moderate")
        assert result == (
            "Moderate landmark visibility — results are generally reliable but may have minor inaccuracies."
        )

    def test_low_guidance(self):
        result = confidence_guidance("Low")
        assert result == (
            "Low landmark visibility — results should be interpreted with caution. "
            "Consider re-recording with better lighting or camera angle."
        )

    def test_very_low_guidance(self):
        result = confidence_guidance("Very Low")
        assert result == (
            "Very low landmark visibility — analysis accuracy is significantly reduced. "
            "We strongly recommend re-recording."
        )

    def test_all_labels_return_non_empty_string(self):
        for label in ["High", "Moderate", "Low", "Very Low"]:
            result = confidence_guidance(label)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_unknown_label_raises(self):
        """Unknown label should raise ValueError."""
        with pytest.raises((ValueError, KeyError)):
            confidence_guidance("Unknown")


# ---------------------------------------------------------------------------
# Tests: round-trip label + guidance
# ---------------------------------------------------------------------------


class TestRoundTrip:
    @pytest.mark.parametrize(
        "score, expected_label",
        [
            (0.90, "High"),
            (0.72, "Moderate"),
            (0.55, "Low"),
            (0.30, "Very Low"),
        ],
    )
    def test_label_then_guidance_matches(self, score: float, expected_label: str):
        """confidence_label → confidence_guidance pipeline produces non-empty strings."""
        label = confidence_label(score)
        assert label == expected_label
        guidance = confidence_guidance(label)
        assert len(guidance) > 0


# ---------------------------------------------------------------------------
# Guard: compute_rep_confidence must NOT exist (FR-CVPL-24 / ADR-015)
# ---------------------------------------------------------------------------


class TestComputeRepConfidenceIsRemoved:
    """Deletion guard for the Phase 0 compute_rep_confidence dead code.

    FR-CVPL-24 (Tier 5 per-rep 10th-percentile confidence) supersedes the
    Phase 0 mean-visibility approach implemented in compute_rep_confidence.
    ADR-015 documents the switch.  Leaving the old function in the module
    creates a risk that a future contributor imports it thinking it is current,
    silently reverting per-rep confidence to Phase 0 semantics.

    This test will FAIL as long as compute_rep_confidence exists in the module,
    enforcing the "one canonical confidence pipeline" invariant.
    """

    def test_compute_rep_confidence_is_removed(self) -> None:
        """compute_rep_confidence must not be importable from app.cv.confidence.

        Governing requirements: FR-CVPL-20..24 (Tier 1–5 composite pipeline),
        ADR-015 (switch from Phase 0 mean-visibility to Phase 1 10th-percentile).
        """
        import app.cv.confidence as _confidence_module

        assert not hasattr(_confidence_module, "compute_rep_confidence"), (
            "compute_rep_confidence is Phase 0 dead code superseded by "
            "compute_confidence_result (FR-CVPL-24, ADR-015). "
            "Delete the function from app/cv/confidence.py."
        )
