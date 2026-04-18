"""Unit tests for BrainCoveService.verify_claim (single-claim CoVe)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.distillation.cove_brain import BrainCoveService
from app.distillation.state import BrainCoveResult
from app.schemas.rag import Chunk, RetrievedContext


def _stub_context(text: str) -> RetrievedContext:
    chunk = Chunk(
        id="c1",
        document_id="d1",
        text=text,
        title="Schoenfeld 2010",
        year=2010,
        collection="papers_rag",
    )
    return RetrievedContext(chunk=chunk, score=0.9, collection="papers_rag")


class _StubQuestionOutput(MagicMock):
    pass


class _StubAnswerOutput(MagicMock):
    pass


@pytest.mark.asyncio
async def test_verify_claim_supported_returns_verified_true() -> None:
    from app.distillation.cove_brain import _VerificationQuestion, _VerificationAnswerOut

    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        side_effect=[
            _VerificationQuestion(question="Does knee-out cueing reduce valgus collapse?"),
            _VerificationAnswerOut(answer="Yes", reasoning="Schoenfeld 2010 reports reduced valgus."),
        ]
    )
    svc = BrainCoveService(anthropic_client=anthropic_client, instructor_client=instructor_client)
    result = await svc.verify_claim(
        claim="Drive knees out as you descend.",
        contexts=[_stub_context("Knee-out cueing reduced valgus collapse in trained lifters.")],
    )
    assert result.verified is True
    assert "Schoenfeld" in result.explanation


@pytest.mark.asyncio
async def test_verify_claim_unsupported_returns_verified_false() -> None:
    from app.distillation.cove_brain import _VerificationQuestion, _VerificationAnswerOut

    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        side_effect=[
            _VerificationQuestion(question="Does breath holding improve bench press 1RM?"),
            _VerificationAnswerOut(answer="No", reasoning="No evidence in provided sources."),
        ]
    )
    svc = BrainCoveService(anthropic_client=anthropic_client, instructor_client=instructor_client)
    result = await svc.verify_claim(
        claim="Holding breath increases bench press 1RM by 20%.",
        contexts=[_stub_context("Unrelated discussion of hip hinge mechanics.")],
    )
    assert result.verified is False


@pytest.mark.asyncio
async def test_verify_claim_empty_contexts_skips_llm() -> None:
    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock()
    svc = BrainCoveService(anthropic_client=anthropic_client, instructor_client=instructor_client)
    result = await svc.verify_claim(claim="any claim", contexts=[])
    assert result.verified is False
    assert result.explanation == "no_papers_evidence"
    instructor_client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_verify_claim_llm_error_returns_safe_default() -> None:
    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    svc = BrainCoveService(anthropic_client=anthropic_client, instructor_client=instructor_client)
    result = await svc.verify_claim(
        claim="any claim",
        contexts=[_stub_context("something")],
    )
    assert result.verified is False
    # H-2: explanation must NOT embed the raw exception message (could leak
    # URLs with API keys). Only type name + "evaluation_failed:" prefix.
    assert result.explanation == "evaluation_failed: RuntimeError"
    assert "boom" not in result.explanation
    assert result.trace == [{"claim": "any claim", "error_type": "RuntimeError"}]


# ---- cove_verify node tests ----


@pytest.mark.asyncio
async def test_cove_verify_skips_noop_candidates() -> None:
    from unittest.mock import AsyncMock, MagicMock
    import uuid as _uuid

    from app.distillation.cove_node import cove_verify
    from app.distillation.state import (
        CandidateInsight,
        LifecycleDecision,
        make_initial_distillation_state,
    )
    from app.schemas.coaching import CoachingOutput

    co = CoachingOutput(
        summary="s",
        strengths=["Consistent tempo"],
        issues=[],
        correction_plan=["Maintain neutral spine throughout the lift."],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="High",
        dimension_addressed="Movement Quality",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )
    state = make_initial_distillation_state(
        analysis_id=_uuid.uuid4(),
        exercise_type="squat",
        coaching_output=co,
        retrieved_papers_contexts=[_stub_context("evidence text")],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )
    state["candidates"] = [
        CandidateInsight(
            content="C1", exercise="squat", phase="descent", entry_type="cue"
        ),
        CandidateInsight(
            content="C2", exercise="squat", phase="descent", entry_type="cue"
        ),
    ]
    state["decisions"] = [
        LifecycleDecision(decision="ADD", nearest_entry_id=None, cosine_sim=0.1),
        LifecycleDecision(decision="NOOP", nearest_entry_id=_uuid.uuid4(), cosine_sim=0.95),
    ]
    svc = MagicMock()
    svc.verify_claim = AsyncMock(
        return_value=BrainCoveResult(verified=True, explanation="ok", trace=[])
    )
    update = await cove_verify(state, cove_service=svc)
    assert len(update["cove_results"]) == 2
    assert update["cove_results"][1].explanation == "noop_skip"
    assert svc.verify_claim.await_count == 1


@pytest.mark.asyncio
async def test_verify_claim_uses_adequate_max_tokens() -> None:
    """M-05: question max_tokens ≥ 512, answer max_tokens ≥ 2048.

    Instructor retries on schema-validation failures. If max_tokens truncates
    Haiku 4.5's reasoning mid-JSON, the Pydantic model fails, instructor
    retries, and after three attempts BrainCoveResult carries
    explanation='evaluation_failed: ValidationError'. Session 42 showed this
    on 11/11 candidates. 2048 tokens on the answer call leaves comfortable
    headroom for reasoning strings with source citations.
    """
    from app.distillation.cove_brain import _VerificationQuestion, _VerificationAnswerOut

    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        side_effect=[
            _VerificationQuestion(question="Q?"),
            _VerificationAnswerOut(answer="Yes", reasoning="r"),
        ]
    )
    svc = BrainCoveService(
        anthropic_client=anthropic_client, instructor_client=instructor_client
    )
    await svc.verify_claim(
        claim="any claim",
        contexts=[_stub_context("evidence text")],
    )

    calls = instructor_client.chat.completions.create.await_args_list
    assert len(calls) == 2, "expected one question call + one answer call"

    # Question-generation call: response_model=_VerificationQuestion, max_tokens >= 512
    question_kwargs = calls[0].kwargs
    assert question_kwargs["response_model"] is _VerificationQuestion
    assert question_kwargs["max_tokens"] >= 512, (
        f"question max_tokens {question_kwargs['max_tokens']} < 512 "
        "— instructor retries on truncation (M-05)."
    )

    # Answer call: response_model=_VerificationAnswerOut, max_tokens >= 2048
    answer_kwargs = calls[1].kwargs
    assert answer_kwargs["response_model"] is _VerificationAnswerOut
    assert answer_kwargs["max_tokens"] >= 2048, (
        f"answer max_tokens {answer_kwargs['max_tokens']} < 2048 "
        "— session-42 observed all 11 candidates blew instructor retries "
        "when max_tokens=512 (M-05)."
    )
