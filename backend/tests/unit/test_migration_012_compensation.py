"""D-038: coach_brain_candidates + coach_brain_entries must accept entry_type='compensation'.

FR-ADMN-12: The review-card UI already renders a 'biomechanics reviewer required'
banner forward-compatibly when entry_type == 'compensation'. Migration 012 widens
the DB CHECK constraints on both tables so the distillation pipeline can actually
produce compensation-typed rows.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


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
async def test_candidates_accept_compensation_entry_type(db_session: AsyncSession) -> None:
    # After migration 012 the CHECK constraint permits 'compensation'.
    await db_session.execute(
        text(
            """
            INSERT INTO coach_brain_candidates
            (id, exercise, phase, entry_type, content, trigger_tags,
             source_analysis_ids, eval_scores, lifecycle_decision,
             contradiction_flag, review_status)
            VALUES
            (:id, 'squat', 'descent', 'compensation',
             'knee valgus compensates for weak hip abduction',
             '{}', '{}', '{"faithfulness": 0.9}'::jsonb,
             'ADD', false, 'pending')
            """
        ),
        {"id": uuid.uuid4()},
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_entries_accept_compensation_entry_type(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO coach_brain_entries
            (id, content, exercise, phase, entry_type, status,
             confirmation_count, source_analysis_ids, trigger_tags, metadata)
            VALUES
            (:id, 'quad-dominant ascent compensates for posterior-chain weakness',
             'squat', 'ascent', 'compensation', 'seed',
             0, '{}', '{}', '{}'::jsonb)
            """
        ),
        {"id": uuid.uuid4()},
    )
    await db_session.flush()
