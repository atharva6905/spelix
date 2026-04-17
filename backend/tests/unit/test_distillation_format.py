"""Unit tests for format_entry — pure zip-and-pack function."""

import uuid

import pytest

from app.distillation.format import format_entry
from app.distillation.state import (
    BrainCoveResult,
    CandidateInsight,
    LifecycleDecision,
    make_initial_distillation_state,
)
from app.schemas.coaching import CoachingOutput


def _state_with(candidates, decisions, cove_results, analysis_id=None, eval_scores=None):
    state = make_initial_distillation_state(
        analysis_id=analysis_id or uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores=eval_scores or {"overall": 0.9, "correctness": 0.85},
    )
    state["candidates"] = candidates
    state["decisions"] = decisions
    state["cove_results"] = cove_results
    state["validation_decision"] = "pass"
    return state


def _candidate(content="C1"):
    return CandidateInsight(
        content=content,
        exercise="squat",
        phase="descent",
        entry_type="cue",
        trigger_tags=["knee_cave"],
        confidence_score=0.9,
    )


@pytest.mark.asyncio
async def test_format_entry_add_produces_pending_row() -> None:
    state = _state_with(
        [_candidate()],
        [LifecycleDecision(decision="ADD", nearest_entry_id=None, cosine_sim=0.4)],
        [BrainCoveResult(verified=True, explanation="supported", trace=[{"q": "?"}])],
    )
    update = await format_entry(state)
    formatted = update["formatted"]
    assert len(formatted) == 1
    row = formatted[0]
    assert row.lifecycle_decision == "ADD"
    assert row.review_status == "pending"
    assert row.cove_verified is True
    assert row.contradiction_flag is False
    assert row.source_analysis_ids == [state["analysis_id"]]
    assert row.eval_scores == {"overall": 0.9, "correctness": 0.85}


@pytest.mark.asyncio
async def test_format_entry_update_produces_superseded_row() -> None:
    nearest = uuid.uuid4()
    state = _state_with(
        [_candidate()],
        [LifecycleDecision(decision="UPDATE", nearest_entry_id=nearest, cosine_sim=0.81)],
        [BrainCoveResult(verified=True, explanation="ok", trace=[])],
    )
    update = await format_entry(state)
    row = update["formatted"][0]
    assert row.lifecycle_decision == "UPDATE"
    assert row.review_status == "superseded"
    assert row.nearest_entry_id == nearest


@pytest.mark.asyncio
async def test_format_entry_noop_produces_no_row() -> None:
    state = _state_with(
        [_candidate()],
        [LifecycleDecision(decision="NOOP", nearest_entry_id=uuid.uuid4(), cosine_sim=0.95)],
        [BrainCoveResult(verified=True, explanation="noop_skip", trace=[])],
    )
    update = await format_entry(state)
    assert update["formatted"] == []


@pytest.mark.asyncio
async def test_format_entry_contradiction_flag_set() -> None:
    nearest = uuid.uuid4()
    state = _state_with(
        [_candidate()],
        [LifecycleDecision(decision="UPDATE", nearest_entry_id=nearest, cosine_sim=0.80)],
        [BrainCoveResult(verified=False, explanation="contradicts", trace=[])],
    )
    update = await format_entry(state)
    row = update["formatted"][0]
    assert row.contradiction_flag is True
    assert row.cove_verified is False


def _stub_coaching_output():
    return CoachingOutput(
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
