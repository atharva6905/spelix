"""Unit tests for lifecycle_decision — embed + Qdrant cosine routing."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.distillation.lifecycle import lifecycle_decision
from app.distillation.state import CandidateInsight, make_initial_distillation_state
from app.schemas.coaching import CoachingOutput


def _state_with_candidates(candidates: list[CandidateInsight]):
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )
    state["candidates"] = candidates
    state["validation_decision"] = "pass"
    return state


def _stub_candidate():
    return CandidateInsight(
        content="Drive knees out as you descend.",
        exercise="squat",
        phase="descent",
        entry_type="cue",
        trigger_tags=["knee_cave"],
    )


def _mock_brain_embedding(vector):
    svc = MagicMock()
    svc.build_contextual_text = MagicMock(return_value="stub contextual text")
    return svc


def _mock_cohere(vector):
    c = MagicMock()
    c.embed_batch = AsyncMock(return_value=[vector])
    return c


def _mock_qdrant(nearest_id, score):
    q = MagicMock()
    if nearest_id is None:
        q.search = AsyncMock(return_value=[])
    else:
        hit = MagicMock()
        hit.id = str(nearest_id)
        hit.score = score
        q.search = AsyncMock(return_value=[hit])
    return q


@pytest.mark.asyncio
async def test_lifecycle_noop_when_cosine_above_092() -> None:
    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(nearest, 0.95),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert len(update["decisions"]) == 1
    assert update["decisions"][0].decision == "NOOP"
    assert update["decisions"][0].nearest_entry_id == nearest


@pytest.mark.asyncio
async def test_lifecycle_update_when_cosine_in_075_092() -> None:
    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(nearest, 0.81),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert update["decisions"][0].decision == "UPDATE"


@pytest.mark.asyncio
async def test_lifecycle_add_when_cosine_below_075() -> None:
    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(nearest, 0.6),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert update["decisions"][0].decision == "ADD"


@pytest.mark.asyncio
async def test_lifecycle_add_when_empty_qdrant() -> None:
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(None, 0.0),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert update["decisions"][0].decision == "ADD"
    assert update["decisions"][0].nearest_entry_id is None


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
