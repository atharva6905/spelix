"""End-to-end integration test for the distillation graph."""

import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.distillation.graph import run_distillation_graph
from app.distillation.state import CandidateInsight
from app.models.coach_brain_candidate import CoachBrainCandidate as CoachBrainCandidateRow
from app.schemas.coaching import CoachingOutput, Issue


# ---------------------------------------------------------------------------
# Fixtures — inline session (same pattern as test_distillation_store.py)
# ---------------------------------------------------------------------------

_DB_URL = os.environ.get("DATABASE_URL", "")

_skip_no_db = pytest.mark.skipif(
    not _DB_URL,
    reason="DATABASE_URL not set — skipping live DB integration tests",
)


@pytest_asyncio.fixture
async def db_session():
    raw_url = _DB_URL
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(raw_url, connect_args={"statement_cache_size": 0})
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_coaching_output():
    return CoachingOutput(
        summary="Good depth, slight knee cave on rep 2.",
        strengths=["Consistent tempo"],
        issues=[Issue(rep_number=2, joint="knee", description="knees cave", severity="Medium")],
        correction_plan=["Drive knees out as you descend."],
        recommended_cues=["Spread the floor"],
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


def _stub_cove_service(instructor_client, anthropic_client):
    from app.distillation.cove_brain import BrainCoveService

    return BrainCoveService(
        anthropic_client=anthropic_client, instructor_client=instructor_client
    )


def _stub_context(text: str):
    from app.schemas.rag import Chunk, RetrievedContext

    chunk = Chunk(
        id="c1",
        document_id="d1",
        text=text,
        title="Stub 2024",
        year=2024,
        collection="papers_rag",
    )
    return RetrievedContext(chunk=chunk, score=0.9, collection="papers_rag")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_full_graph_end_to_end_add_path(db_session: AsyncSession) -> None:
    from app.distillation.extract import ExtractedInsights

    # Mock: extraction yields one candidate
    instructor_client = MagicMock()
    from app.distillation.cove_brain import _VerificationAnswerOut, _VerificationQuestion

    instructor_client.chat.completions.create = AsyncMock(
        side_effect=[
            ExtractedInsights(
                candidates=[
                    CandidateInsight(
                        content="Drive knees out as you descend.",
                        exercise="squat",
                        phase="descent",
                        entry_type="cue",
                        trigger_tags=["knee_cave"],
                        confidence_score=0.9,
                    )
                ]
            ),
            _VerificationQuestion(question="Does knee-out cueing reduce valgus?"),
            _VerificationAnswerOut(answer="Yes", reasoning="Schoenfeld 2010 supports."),
        ]
    )
    anthropic_client = MagicMock()

    cohere = MagicMock()
    cohere.embed_batch = AsyncMock(return_value=[[0.0] * 1024])

    qdrant = MagicMock()
    qdrant.search = AsyncMock(return_value=[])  # empty coach_brain → ADD

    brain_embedding = MagicMock()
    brain_embedding.build_contextual_text = MagicMock(return_value="ctx")

    analysis_id = uuid.uuid4()
    final_state, trace_payload = await run_distillation_graph(
        analysis_id=analysis_id,
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[_stub_context("Knee-out cueing reduced valgus")],
        eval_scores={"overall": 0.9, "correctness": 0.85},
        anthropic_client=anthropic_client,
        instructor_client=instructor_client,
        cohere_client=cohere,
        qdrant_client=qdrant,
        brain_embedding_svc=brain_embedding,
        cove_service_factory=lambda: _stub_cove_service(instructor_client, anthropic_client),
        db_session=db_session,
    )

    assert final_state["validation_decision"] == "pass"
    assert len(final_state["stored_ids"]) == 1
    assert trace_payload["nodes_executed"][0]["node"] == "extract_insights"

    # Verify candidate row landed in Postgres
    found = (
        await db_session.execute(
            select(CoachBrainCandidateRow).where(
                CoachBrainCandidateRow.id == final_state["stored_ids"][0]
            )
        )
    ).scalar_one()
    assert found.lifecycle_decision == "ADD"
    assert found.review_status == "pending"
    assert found.cove_verified is True


@_skip_no_db
@pytest.mark.asyncio
async def test_graph_rejects_low_eval_scores(db_session: AsyncSession) -> None:
    from app.distillation.extract import ExtractedInsights

    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        return_value=ExtractedInsights(candidates=[])
    )

    final_state, _ = await run_distillation_graph(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.4, "correctness": 0.3},  # below 0.6 floor
        anthropic_client=MagicMock(),
        instructor_client=instructor_client,
        cohere_client=MagicMock(),
        qdrant_client=MagicMock(),
        brain_embedding_svc=MagicMock(),
        cove_service_factory=lambda: MagicMock(),
        db_session=db_session,
    )
    assert final_state["validation_decision"] == "reject"
    assert final_state["stored_ids"] == []
