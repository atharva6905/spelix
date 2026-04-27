"""Unit tests for CoachBrainCandidateRepository."""

import os
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.coach_brain_candidate import CoachBrainCandidate as CoachBrainCandidateRow
from app.models.coach_brain_entry import CoachBrainEntry
from app.repositories.coach_brain_candidate import CoachBrainCandidateRepository
from app.schemas.coach_brain_candidate import CoachBrainCandidateCreate


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


@pytest.mark.asyncio
async def test_create_inserts_row(db_session: AsyncSession) -> None:
    repo = CoachBrainCandidateRepository(db_session)
    create = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Drive the knees out as you descend to stay stacked.",
        trigger_tags=["knee_cave"],
        source_analysis_ids=[uuid.uuid4()],
        lifecycle_decision="ADD",
    )
    created = await repo.create(create)
    assert created.id is not None
    assert created.review_status == "pending"
    assert created.lifecycle_decision == "ADD"


@pytest.mark.asyncio
async def test_list_pending_returns_only_pending(db_session: AsyncSession) -> None:
    repo = CoachBrainCandidateRepository(db_session)
    a = await repo.create(
        CoachBrainCandidateCreate(
            exercise="squat",
            entry_type="cue",
            content="cue A",
            source_analysis_ids=[uuid.uuid4()],
            lifecycle_decision="ADD",
        )
    )
    await repo.create(
        CoachBrainCandidateCreate(
            exercise="squat",
            entry_type="cue",
            content="cue B",
            source_analysis_ids=[uuid.uuid4()],
            lifecycle_decision="UPDATE",
            review_status="superseded",
        )
    )
    pending = await repo.list_pending()
    ids = [p.id for p in pending]
    assert a.id in ids
    assert all(p.review_status == "pending" for p in pending)


async def _insert_for_sort(
    repo: CoachBrainCandidateRepository,
    *,
    faithfulness: float | None = None,
    overall: float | None = None,
    review_status: str = "pending",
    content: str = "Tuck elbows at 45 degrees.",
) -> object:
    eval_scores: dict[str, float] = {}
    if faithfulness is not None:
        eval_scores["faithfulness"] = faithfulness
    if overall is not None:
        eval_scores["overall"] = overall
    create = CoachBrainCandidateCreate(
        exercise="bench",
        phase="descent",
        entry_type="cue",
        content=content,
        trigger_tags=[],
        source_analysis_ids=[uuid.uuid4()],
        eval_scores=eval_scores,
        lifecycle_decision="ADD",
        review_status=review_status,
    )
    return await repo.create(create)


@pytest.mark.asyncio
async def test_list_pending_ordered_prefers_overall_then_faithfulness_then_created_at(
    db_session: AsyncSession,
) -> None:
    repo = CoachBrainCandidateRepository(db_session)
    low = await _insert_for_sort(repo, faithfulness=0.5, content="A")
    top = await _insert_for_sort(repo, overall=0.95, faithfulness=0.6, content="B")
    mid = await _insert_for_sort(repo, faithfulness=0.85, content="C")
    _ = await _insert_for_sort(
        repo, faithfulness=0.99, review_status="rejected", content="D"
    )

    # Use a large limit to capture all pending rows; filter to the 3 we inserted
    # so the assertion is robust against pre-existing pending rows in the test DB.
    rows = await repo.list_pending_ordered(limit=1000, offset=0)

    our_ids = {low.id, top.id, mid.id}
    ordered = [r for r in rows if r.id in our_ids]
    assert len(ordered) == 3
    assert ordered[0].id == top.id
    assert ordered[1].id == mid.id
    assert ordered[2].id == low.id
    assert all(r.review_status == "pending" for r in rows)


@pytest.mark.asyncio
async def test_count_pending_excludes_non_pending(db_session: AsyncSession) -> None:
    repo = CoachBrainCandidateRepository(db_session)
    before = await repo.count_pending()
    await _insert_for_sort(repo)
    await _insert_for_sort(repo, review_status="approved")
    await _insert_for_sort(repo, review_status="rejected")
    await _insert_for_sort(repo, review_status="superseded")

    # Only the one pending insert should increment the count.
    assert await repo.count_pending() == before + 1


@pytest.mark.asyncio
async def test_get_by_id_for_update_returns_orm_row(db_session: AsyncSession) -> None:
    repo = CoachBrainCandidateRepository(db_session)
    created = await _insert_for_sort(repo)

    locked = await repo.get_by_id_for_update(created.id)

    assert locked is not None
    assert locked.id == created.id
    assert locked.review_status == "pending"
    locked.review_status = "approved"
    await db_session.flush()
    refetched = await repo.get_by_id(created.id)
    assert refetched is not None
    assert refetched.review_status == "approved"


@pytest.mark.asyncio
async def test_list_pending_with_nearest_confirmation_count_joins_count(
    db_session: AsyncSession,
) -> None:
    """FR-ADMN-12 H-02: repo joins coach_brain_entries.confirmation_count
    for each pending candidate via nearest_entry_id, returning
    (CoachBrainCandidate, int | None) tuples."""
    seed_entry = CoachBrainEntry(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="seed",
        trigger_tags=["knee_cave"],
        confirmation_count=7,
        source_analysis_ids=[],
        status="active",
    )
    db_session.add(seed_entry)
    await db_session.flush()

    update_candidate = CoachBrainCandidateRow(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Drive knees out aggressively.",
        source_analysis_ids=[uuid.uuid4()],
        eval_scores={"overall": 0.9},
        lifecycle_decision="UPDATE",
        nearest_entry_id=seed_entry.id,
        nearest_cosine_sim=Decimal("0.81"),
        review_status="pending",
    )
    add_candidate_no_nearest = CoachBrainCandidateRow(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Brand new cue with no near match.",
        source_analysis_ids=[uuid.uuid4()],
        eval_scores={"overall": 0.88},
        lifecycle_decision="ADD",
        nearest_entry_id=None,
        review_status="pending",
    )
    db_session.add_all([update_candidate, add_candidate_no_nearest])
    await db_session.flush()

    repo = CoachBrainCandidateRepository(db_session)
    our_ids = {update_candidate.id, add_candidate_no_nearest.id}
    all_rows = await repo.list_pending_with_nearest_confirmation_count(limit=1000)
    rows = [r for r in all_rows if r[0].id in our_ids]

    assert len(rows) == 2
    by_id = {row[0].id: row for row in rows}
    update_row = by_id[update_candidate.id]
    add_row = by_id[add_candidate_no_nearest.id]
    assert update_row[1] == 7
    assert add_row[1] is None
