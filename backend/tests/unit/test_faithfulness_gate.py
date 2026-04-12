"""Unit tests for FaithfulnessGateService (P2-015, FR-AICP-08 Stage 3).

All Anthropic API calls are mocked — never call the real API.

TDD: these tests are written before the implementation. Run:
    uv run pytest tests/unit/test_faithfulness_gate.py -x
to confirm all fail before implementing faithfulness_gate.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.coaching import CoachingOutput
from app.schemas.rag import ChunkPayload, RetrievedContext
from app.services.faithfulness_gate import (
    FAITHFULNESS_THRESHOLD,
    FaithfulnessGateService,
    FaithfulnessResult,
    FaithfulnessScore,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

MANDATORY_DISCLAIMER = (
    "This feedback is for educational purposes only and is not a substitute "
    "for in-person coaching or medical advice."
)


def _make_coaching_output() -> CoachingOutput:
    return CoachingOutput(
        summary="Good squat session with minor depth issues.",
        strengths=["Consistent bar path", "Good bracing"],
        issues=[],
        correction_plan=["Focus on depth", "Pause at bottom"],
        disclaimer=MANDATORY_DISCLAIMER,
        raw_prompt_tokens=100,
        raw_completion_tokens=200,
    )


def _make_contexts(n: int = 3) -> list[RetrievedContext]:
    return [
        RetrievedContext(
            chunk=ChunkPayload(
                id=f"chunk_{i}",
                text=f"Research finding {i} about squat biomechanics.",
                paper_id=f"paper_{i}",
                chunk_index=0,
                section="results",
                token_count=50,
                quality_tier="L2_rct",
                title=f"Paper {i}",
                authors=["Author A"],
                year=2024,
                doi=None,
            ),
            score=0.9 - i * 0.1,
            collection="papers_rag",
        )
        for i in range(n)
    ]


def _make_service_with_mock_llm(faithfulness_score: FaithfulnessScore) -> tuple[FaithfulnessGateService, MagicMock]:
    """Return a FaithfulnessGateService wired to a mock instructor client.

    The mock instructor client's chat.completions.create is an AsyncMock
    that resolves to the provided FaithfulnessScore.
    """
    anthropic_client = MagicMock()
    mock_instructor_client = MagicMock()
    mock_instructor_client.chat.completions.create = AsyncMock(return_value=faithfulness_score)

    with patch("instructor.from_anthropic", return_value=mock_instructor_client):
        svc = FaithfulnessGateService(anthropic_client=anthropic_client)

    # Inject mock directly so later evaluate() calls use it
    svc._instructor_client = mock_instructor_client
    return svc, mock_instructor_client


def _make_service_with_error_llm(exc: Exception) -> tuple[FaithfulnessGateService, MagicMock]:
    """Return a FaithfulnessGateService whose LLM call raises exc."""
    anthropic_client = MagicMock()
    mock_instructor_client = MagicMock()
    mock_instructor_client.chat.completions.create = AsyncMock(side_effect=exc)

    with patch("instructor.from_anthropic", return_value=mock_instructor_client):
        svc = FaithfulnessGateService(anthropic_client=anthropic_client)

    svc._instructor_client = mock_instructor_client
    return svc, mock_instructor_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFaithfulnessGateService:
    """Tests for FaithfulnessGateService.evaluate()."""

    @pytest.mark.asyncio
    async def test_score_above_threshold_passes(self) -> None:
        """Score 0.9 >= 0.8 threshold — must pass with no flag."""
        llm_score = FaithfulnessScore(
            score=0.9,
            reasoning="well supported",
            unsupported_claims=[],
        )
        svc, _ = _make_service_with_mock_llm(llm_score)

        result = await svc.evaluate(
            coaching_output=_make_coaching_output(),
            retrieved_contexts=_make_contexts(3),
        )

        assert isinstance(result, FaithfulnessResult)
        assert result.score == pytest.approx(0.9)
        assert result.passed is True
        assert result.flagged_for_review is False

    @pytest.mark.asyncio
    async def test_score_below_threshold_flags(self) -> None:
        """Score 0.6 < 0.8 threshold — must fail and flag for review."""
        llm_score = FaithfulnessScore(
            score=0.6,
            reasoning="partial support",
            unsupported_claims=["some claim"],
        )
        svc, _ = _make_service_with_mock_llm(llm_score)

        result = await svc.evaluate(
            coaching_output=_make_coaching_output(),
            retrieved_contexts=_make_contexts(3),
        )

        assert result.score == pytest.approx(0.6)
        assert result.passed is False
        assert result.flagged_for_review is True

    @pytest.mark.asyncio
    async def test_score_exactly_threshold_passes(self) -> None:
        """Score exactly 0.8 == threshold — must pass (>= not >)."""
        llm_score = FaithfulnessScore(
            score=FAITHFULNESS_THRESHOLD,
            reasoning="exactly at threshold",
            unsupported_claims=[],
        )
        svc, _ = _make_service_with_mock_llm(llm_score)

        result = await svc.evaluate(
            coaching_output=_make_coaching_output(),
            retrieved_contexts=_make_contexts(2),
        )

        assert result.score == pytest.approx(FAITHFULNESS_THRESHOLD)
        assert result.passed is True
        assert result.flagged_for_review is False

    @pytest.mark.asyncio
    async def test_unsupported_claims_captured(self) -> None:
        """Unsupported claims from the LLM response must be preserved."""
        llm_score = FaithfulnessScore(
            score=0.7,
            reasoning="two claims lack direct support",
            unsupported_claims=["claim A", "claim B"],
        )
        svc, _ = _make_service_with_mock_llm(llm_score)

        result = await svc.evaluate(
            coaching_output=_make_coaching_output(),
            retrieved_contexts=_make_contexts(3),
        )

        assert result.unsupported_claims == ["claim A", "claim B"]

    @pytest.mark.asyncio
    async def test_llm_error_returns_safe_default(self) -> None:
        """Any LLM exception must be swallowed — returns score=0 safe default."""
        svc, _ = _make_service_with_error_llm(RuntimeError("API error"))

        result = await svc.evaluate(
            coaching_output=_make_coaching_output(),
            retrieved_contexts=_make_contexts(3),
        )

        assert result.score == pytest.approx(0.0)
        assert result.passed is False
        assert result.flagged_for_review is True
        assert "evaluation_failed" in result.reasoning

    @pytest.mark.asyncio
    async def test_empty_contexts_returns_zero(self) -> None:
        """Empty retrieved_contexts must short-circuit before any LLM call."""
        anthropic_client = MagicMock()
        mock_instructor_client = MagicMock()
        mock_instructor_client.chat.completions.create = AsyncMock()

        with patch("instructor.from_anthropic", return_value=mock_instructor_client):
            svc = FaithfulnessGateService(anthropic_client=anthropic_client)

        svc._instructor_client = mock_instructor_client

        result = await svc.evaluate(
            coaching_output=_make_coaching_output(),
            retrieved_contexts=[],
        )

        assert result.score == pytest.approx(0.0)
        assert result.passed is False
        assert result.flagged_for_review is True
        assert result.reasoning == "no_retrieved_contexts"
        mock_instructor_client.chat.completions.create.assert_not_called()
