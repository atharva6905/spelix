"""Unit tests for the extract_insights distillation node."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.distillation.extract import ExtractedInsights, extract_insights
from app.distillation.state import CandidateInsight, make_initial_distillation_state
from app.schemas.coaching import CoachingOutput, Issue


@pytest.mark.asyncio
async def test_extract_insights_returns_candidates_from_llm() -> None:
    state = _state_with_coaching_output(
        CoachingOutput(
            summary="Good depth, slight knee cave on rep 2.",
            strengths=["Consistent tempo"],
            issues=[
                Issue(rep_number=2, joint="knee", description="knees cave inward at bottom",
                      severity="Medium"),
            ],
            correction_plan=["Drive knees out as you descend."],
            recommended_cues=["Spread the floor"],
            citations=[],
            safety_warnings=[],
            confidence_level="High",
            dimension_addressed="Movement Quality",
            disclaimer=_disclaimer(),
            raw_prompt_tokens=0,
            raw_completion_tokens=0,
        )
    )
    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        return_value=ExtractedInsights(
            candidates=[
                CandidateInsight(
                    content="Drive knees out as you descend.",
                    exercise="squat",
                    phase="descent",
                    entry_type="cue",
                    trigger_tags=["knee_cave"],
                    confidence_score=0.9,
                ),
            ]
        )
    )
    update = await extract_insights(
        state,
        anthropic_client=anthropic_client,
        instructor_client=instructor_client,
    )
    assert len(update["candidates"]) == 1
    assert update["candidates"][0].content.startswith("Drive knees")


@pytest.mark.asyncio
async def test_extract_insights_empty_output_returns_empty() -> None:
    state = _state_with_coaching_output(_empty_coaching_output())
    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        return_value=ExtractedInsights(candidates=[]),
    )
    update = await extract_insights(
        state,
        anthropic_client=anthropic_client,
        instructor_client=instructor_client,
    )
    assert update["candidates"] == []


@pytest.mark.asyncio
async def test_extract_insights_llm_error_returns_empty_safely() -> None:
    state = _state_with_coaching_output(_empty_coaching_output())
    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError("boom"),
    )
    update = await extract_insights(
        state,
        anthropic_client=anthropic_client,
        instructor_client=instructor_client,
    )
    assert update["candidates"] == []


def _state_with_coaching_output(co):
    return make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=co,
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )


def _empty_coaching_output():
    return CoachingOutput(
        summary="No significant issues observed.",
        strengths=["Consistent bar path"],
        issues=[],
        correction_plan=["Maintain current form."],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="Low",
        dimension_addressed="Movement Quality",
        disclaimer=_disclaimer(),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )


def _disclaimer():
    return (
        "This feedback is for educational purposes only and is not a "
        "substitute for in-person coaching or medical advice."
    )
