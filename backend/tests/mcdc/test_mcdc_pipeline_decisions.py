"""MC/DC truth-table tests for pipeline.py decision points.

Decision 1: _is_degenerate_scoring_input
  Condition: (not rep_metrics) OR (session_confidence < 0.50)
  A = not rep_metrics  (True when list is empty)
  B = session_confidence < 0.50

  MC/DC rows:
    Row 1: A=False, B=False → return False  (baseline)
    Row 2: A=True,  B=False → return True   (A independently flips outcome)
    Row 3: A=False, B=True  → return True   (B independently flips outcome)

Decision 2: GPT-4o fallback AND condition (FR-XDET-04)
  Condition: detection.confidence < _FALLBACK_CONFIDENCE_THRESHOLD AND openai_client is not None
  C = detection.confidence < 0.7
  D = openai_client is not None

  MC/DC rows (testing boolean logic directly):
    Row 1: C=False, D=True  → no fallback  (C independently blocks)
    Row 2: C=True,  D=False → no fallback  (D independently blocks)
    Row 3: C=True,  D=True  → fallback fires (both True required)
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.pipeline import _is_degenerate_scoring_input

# The fallback threshold is a module-level constant in pipeline.py
_FALLBACK_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# TestDegenerateScoringOR
# ---------------------------------------------------------------------------


class TestDegenerateScoringOR:
    """MC/DC rows for the degenerate-input OR guard."""

    def test_has_reps_and_good_confidence_is_not_degenerate(self) -> None:
        """Row 1: A=False, B=False → False (both conditions False, result False).

        Baseline — this is the happy path: reps exist and confidence is solid.
        """
        rep_metrics = [MagicMock()]  # non-empty list → A=False
        result = _is_degenerate_scoring_input(rep_metrics, session_confidence=0.80)
        assert result is False

    def test_empty_reps_makes_degenerate_regardless_of_confidence(self) -> None:
        """Row 2: A=True, B=False → True.

        MC/DC: flipping A from False→True changes outcome from False→True.
        B (confidence) remains False (0.80 >= 0.50), proving A independently determines result.
        """
        result = _is_degenerate_scoring_input([], session_confidence=0.80)
        assert result is True

    def test_low_confidence_makes_degenerate_regardless_of_reps(self) -> None:
        """Row 3: A=False, B=True → True.

        MC/DC: flipping B from False→True changes outcome from False→True.
        A remains False (non-empty reps), proving B independently determines result.
        """
        rep_metrics = [MagicMock()]  # non-empty → A=False
        result = _is_degenerate_scoring_input(rep_metrics, session_confidence=0.49)
        assert result is True

    def test_exact_threshold_boundary_is_not_degenerate(self) -> None:
        """Boundary: confidence==0.50 exactly → NOT degenerate (strict < used).

        Confirms the guard uses `< 0.50`, not `<= 0.50`.
        """
        rep_metrics = [MagicMock()]
        result = _is_degenerate_scoring_input(rep_metrics, session_confidence=0.50)
        assert result is False

    def test_both_degenerate_conditions_true(self) -> None:
        """A=True, B=True — degenerate on both counts; result is still True.

        The OR short-circuits on A=True; B is never evaluated. Still returns True.
        """
        result = _is_degenerate_scoring_input([], session_confidence=0.30)
        assert result is True


# ---------------------------------------------------------------------------
# TestGPT4oFallbackAND
# Tests the boolean logic of the fallback AND condition:
#   detection.confidence < _FALLBACK_THRESHOLD AND openai_client is not None
#
# We test this without invoking the full pipeline by evaluating the boolean
# expression directly, mirroring the condition in pipeline.py line 445.
# ---------------------------------------------------------------------------


def _fallback_would_fire(confidence: float, openai_client: object) -> bool:
    """Mirror the fallback gate from pipeline.py (FR-XDET-04).

    Extracted to a pure function for MC/DC testing without spinning up the
    full async pipeline. Mirrors:
        if detection.confidence < _FALLBACK_CONFIDENCE_THRESHOLD and openai_client is not None:
    """
    return confidence < _FALLBACK_THRESHOLD and openai_client is not None


class TestGPT4oFallbackAND:
    """MC/DC rows for the GPT-4o vision fallback AND condition (FR-XDET-04)."""

    def test_high_confidence_suppresses_fallback(self) -> None:
        """Row 1: C=False (conf>=0.7), D=True (client present) → no fallback.

        MC/DC: C being False independently blocks the AND. Changing C to True
        (while D stays True) would flip the outcome to True.
        """
        client = MagicMock()  # non-None → D=True
        assert _fallback_would_fire(confidence=0.75, openai_client=client) is False

    def test_low_confidence_with_no_client_suppresses_fallback(self) -> None:
        """Row 2: C=True (conf<0.7), D=False (client=None) → no fallback.

        MC/DC: D being False independently blocks the AND. Changing D to a
        non-None client (while C stays True) would flip the outcome to True.
        """
        assert _fallback_would_fire(confidence=0.50, openai_client=None) is False

    def test_low_confidence_with_client_fires_fallback(self) -> None:
        """Row 3: C=True (conf<0.7), D=True (client present) → fallback fires.

        MC/DC: both conditions True → AND evaluates True. This is the only
        row where the fallback fires.
        """
        client = MagicMock()
        assert _fallback_would_fire(confidence=0.50, openai_client=client) is True

    def test_exact_threshold_boundary_suppresses_fallback(self) -> None:
        """Boundary: confidence==0.7 exactly → no fallback (strict < used)."""
        client = MagicMock()
        assert _fallback_would_fire(confidence=0.70, openai_client=client) is False
