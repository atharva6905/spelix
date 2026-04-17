"""Unit tests for CoachBrainCandidateRepository."""

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
