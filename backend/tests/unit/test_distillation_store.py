"""Unit tests for store_entry — DB transaction writes."""

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.distillation.state import make_initial_distillation_state
from app.distillation.store import store_entry
from app.models.coach_brain_candidate import CoachBrainCandidate
from app.models.coach_brain_entry import CoachBrainEntry
from app.schemas.coach_brain_candidate import CoachBrainCandidateCreate
from app.schemas.coaching import CoachingOutput


@pytest_asyncio.fixture
async def db_session():
    raw_url = os.environ["DATABASE_URL"]
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


def _state_with_formatted(rows: list[CoachBrainCandidateCreate]):
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )
    state["formatted"] = rows
    return state


@pytest.mark.asyncio
async def test_store_entry_add_inserts_row(db_session: AsyncSession) -> None:
    row = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Drive knees out.",
        source_analysis_ids=[uuid.uuid4()],
        lifecycle_decision="ADD",
    )
    state = _state_with_formatted([row])
    update = await store_entry(state, db_session=db_session)
    assert len(update["stored_ids"]) == 1
    found = (await db_session.execute(
        select(CoachBrainCandidate).where(CoachBrainCandidate.id == update["stored_ids"][0])
    )).scalar_one()
    assert found.review_status == "pending"


@pytest.mark.asyncio
async def test_store_entry_update_bumps_confirmation_count(db_session: AsyncSession) -> None:
    seed = CoachBrainEntry(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="seed",
        trigger_tags=["knee_cave"],
        confirmation_count=2,
        source_analysis_ids=[],
        status="active",
    )
    db_session.add(seed)
    await db_session.flush()

    source_analysis = uuid.uuid4()
    row = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Drive knees out.",
        source_analysis_ids=[source_analysis],
        lifecycle_decision="UPDATE",
        nearest_entry_id=seed.id,
        nearest_cosine_sim=0.81,
        review_status="superseded",
    )
    state = _state_with_formatted([row])
    await store_entry(state, db_session=db_session)

    await db_session.refresh(seed)
    assert seed.confirmation_count == 3
    assert source_analysis in seed.source_analysis_ids


@pytest.mark.asyncio
async def test_store_entry_empty_formatted_writes_nothing(db_session: AsyncSession) -> None:
    state = _state_with_formatted([])
    update = await store_entry(state, db_session=db_session)
    assert update["stored_ids"] == []


@pytest.mark.asyncio
async def test_store_entry_compensation_sets_requires_technical_review(
    db_session: AsyncSession,
) -> None:
    """FR-ADMN-12: compensation entries must have requires_technical_review=True."""
    row = CoachBrainCandidateCreate(
        exercise="bench",
        phase="bottom",
        entry_type="compensation",
        content="Arching excessively to compensate for lack of thoracic mobility.",
        source_analysis_ids=[uuid.uuid4()],
        lifecycle_decision="ADD",
    )
    state = _state_with_formatted([row])
    update = await store_entry(state, db_session=db_session)
    assert len(update["stored_ids"]) == 1
    found = (
        await db_session.execute(
            select(CoachBrainCandidate).where(
                CoachBrainCandidate.id == update["stored_ids"][0]
            )
        )
    ).scalar_one()
    assert found.requires_technical_review is True


@pytest.mark.asyncio
async def test_store_entry_cue_does_not_require_technical_review(
    db_session: AsyncSession,
) -> None:
    """Non-compensation entries must have requires_technical_review=False."""
    row = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Drive knees out.",
        source_analysis_ids=[uuid.uuid4()],
        lifecycle_decision="ADD",
    )
    state = _state_with_formatted([row])
    update = await store_entry(state, db_session=db_session)
    assert len(update["stored_ids"]) == 1
    found = (
        await db_session.execute(
            select(CoachBrainCandidate).where(
                CoachBrainCandidate.id == update["stored_ids"][0]
            )
        )
    ).scalar_one()
    assert found.requires_technical_review is False


@pytest.mark.asyncio
async def test_store_entry_update_with_contradiction_tombstones_existing(
    db_session: AsyncSession,
) -> None:
    """FR-BRAIN-17: UPDATE-path candidate with contradiction_flag=True must
    tombstone the nearest existing coach_brain_entries row.

    The existing row must transition to status='deprecated' and gain
    extra_metadata.rejected_reason='contradicted_by_<candidate_id>'. This
    matches the FR-BRAIN-16 tombstone pattern in
    app/repositories/coach_brain.py:soft_delete_empty_unconfirmed (status
    CHECK constraint allows seed/active/deprecated only).
    """
    seed = CoachBrainEntry(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="seed",
        trigger_tags=["knee_cave"],
        confirmation_count=2,
        source_analysis_ids=[],
        status="active",
    )
    db_session.add(seed)
    await db_session.flush()

    source_analysis = uuid.uuid4()
    row = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Drive knees out.",
        source_analysis_ids=[source_analysis],
        lifecycle_decision="UPDATE",
        nearest_entry_id=seed.id,
        nearest_cosine_sim=0.81,
        contradiction_flag=True,
        review_status="superseded",
    )
    state = _state_with_formatted([row])
    update = await store_entry(state, db_session=db_session)

    # Candidate row inserted (audit trail)
    assert len(update["stored_ids"]) == 1
    candidate_id = update["stored_ids"][0]

    # Nearest entry tombstoned via the FR-BRAIN-16 pattern
    await db_session.refresh(seed)
    assert seed.status == "deprecated"
    assert seed.extra_metadata.get("rejected_reason") == f"contradicted_by_{candidate_id}"

    # M-01: contradiction_flag must NOT bump confirmation_count
    assert seed.confirmation_count == 2
    # M-01: contradicted entries also do NOT receive new source_analysis_ids
    assert source_analysis not in seed.source_analysis_ids


@pytest.mark.asyncio
async def test_store_entry_update_without_contradiction_does_not_tombstone(
    db_session: AsyncSession,
) -> None:
    """Regression guard: the existing UPDATE-path (contradiction_flag=False)
    must continue to bump confirmation_count and append source_analysis_ids
    without changing status or metadata.
    """
    seed = CoachBrainEntry(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="seed",
        trigger_tags=["knee_cave"],
        confirmation_count=2,
        source_analysis_ids=[],
        status="active",
    )
    db_session.add(seed)
    await db_session.flush()

    source_analysis = uuid.uuid4()
    row = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Drive knees out.",
        source_analysis_ids=[source_analysis],
        lifecycle_decision="UPDATE",
        nearest_entry_id=seed.id,
        nearest_cosine_sim=0.81,
        contradiction_flag=False,
        review_status="superseded",
    )
    state = _state_with_formatted([row])
    await store_entry(state, db_session=db_session)

    await db_session.refresh(seed)
    assert seed.status == "active"
    assert seed.extra_metadata == {} or "rejected_reason" not in seed.extra_metadata
    assert seed.confirmation_count == 3
    assert source_analysis in seed.source_analysis_ids
