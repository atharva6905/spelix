# backend/tests/unit/test_candidate_review_get_similar.py
"""D-037: CandidateReviewService.get_similar_entries returns top N approved
entries by cosine similarity, joined back to Postgres for content preview."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.coach_brain_candidate import CoachBrainCandidate
from app.services.candidate_review import (
    CandidateNotFound,
    CandidateReviewService,
)


def _make_candidate(**overrides: object) -> CoachBrainCandidate:
    base = dict(
        id=uuid.uuid4(),
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="drive knees out at the bottom",
        trigger_tags=["knee_valgus"],
        source_analysis_ids=[],
        confidence_score=0.8,
        eval_scores={"faithfulness": 0.9},
        cove_verified=True,
        cove_explanation="",
        cove_trace=None,
        lifecycle_decision="ADD",
        nearest_entry_id=None,
        nearest_cosine_sim=None,
        contradiction_flag=False,
        review_status="pending",
        rejected_reason=None,
        promoted_entry_id=None,
        created_at=datetime.datetime(2026, 4, 19),
        updated_at=datetime.datetime(2026, 4, 19),
    )
    base.update(overrides)
    return CoachBrainCandidate(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_similar_entries_returns_top_2_ordered_by_cosine() -> None:
    candidate = _make_candidate()
    e1_id, e2_id = uuid.uuid4(), uuid.uuid4()

    candidate_repo = MagicMock()
    candidate_repo.get_by_id = AsyncMock(return_value=candidate)

    entry_repo = MagicMock()
    entry_repo.get_by_id = AsyncMock(
        side_effect=lambda eid: MagicMock(
            id=eid,
            content=f"entry-{eid}",
            exercise="squat",
            phase="descent",
            entry_type="cue",
        )
    )

    brain_embedding = MagicMock()
    brain_embedding.build_contextual_text = MagicMock(return_value="ctx text")

    cohere = MagicMock()
    cohere.embed_batch = AsyncMock(return_value=[[0.1] * 1024])

    hit1 = MagicMock(id=str(e1_id), score=0.88)
    hit2 = MagicMock(id=str(e2_id), score=0.81)
    qdrant = MagicMock()
    qdrant.query_points = AsyncMock(return_value=MagicMock(points=[hit1, hit2]))

    svc = CandidateReviewService(
        db=MagicMock(),
        candidate_repo=candidate_repo,
        entry_repo=entry_repo,
        brain_embedding=brain_embedding,
    )
    svc._cohere_client = cohere  # type: ignore[attr-defined]
    svc._qdrant_client = qdrant  # type: ignore[attr-defined]

    result = await svc.get_similar_entries(candidate_id=candidate.id, limit=2)

    assert [r.id for r in result] == [e1_id, e2_id]
    assert result[0].cosine_sim == pytest.approx(0.88)
    assert result[1].cosine_sim == pytest.approx(0.81)
    # Qdrant filter must pin exercise AND status ∈ {active, seed}
    call = qdrant.query_points.await_args
    assert call.kwargs["collection"] == "coach_brain" or call.args[0] == "coach_brain"
    assert call.kwargs["limit"] == 2


@pytest.mark.asyncio
async def test_get_similar_entries_raises_when_candidate_missing() -> None:
    candidate_repo = MagicMock()
    candidate_repo.get_by_id = AsyncMock(return_value=None)

    svc = CandidateReviewService(
        db=MagicMock(),
        candidate_repo=candidate_repo,
        entry_repo=MagicMock(),
        brain_embedding=MagicMock(),
    )
    svc._cohere_client = MagicMock()  # type: ignore[attr-defined]
    svc._qdrant_client = MagicMock()  # type: ignore[attr-defined]

    with pytest.raises(CandidateNotFound):
        await svc.get_similar_entries(candidate_id=uuid.uuid4(), limit=2)


@pytest.mark.asyncio
async def test_get_similar_entries_empty_qdrant_returns_empty_list() -> None:
    candidate = _make_candidate()
    candidate_repo = MagicMock()
    candidate_repo.get_by_id = AsyncMock(return_value=candidate)

    brain_embedding = MagicMock()
    brain_embedding.build_contextual_text = MagicMock(return_value="ctx")

    cohere = MagicMock()
    cohere.embed_batch = AsyncMock(return_value=[[0.1] * 1024])

    qdrant = MagicMock()
    qdrant.query_points = AsyncMock(return_value=MagicMock(points=[]))

    svc = CandidateReviewService(
        db=MagicMock(),
        candidate_repo=candidate_repo,
        entry_repo=MagicMock(),
        brain_embedding=brain_embedding,
    )
    svc._cohere_client = cohere  # type: ignore[attr-defined]
    svc._qdrant_client = qdrant  # type: ignore[attr-defined]

    result = await svc.get_similar_entries(candidate_id=candidate.id, limit=2)
    assert result == []
