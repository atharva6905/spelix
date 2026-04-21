"""Integration tests proving the MissingGreenlet fix for POST /analyses/{id}/chat.

Production hit HTTP 500 with sqlalchemy.exc.MissingGreenlet when ChatService
called get_by_id() (no eager loading) and then accessed analysis.coaching_result
inside an async context where lazy-loading cannot issue a new SELECT.

Fix at commit f73b793: switch to get_by_id_with_relations() which selectinloads
coaching_result alongside the Analysis row, so no lazy-load is needed.

Test 1 — PROVES THE FIX:
  Load via get_by_id_with_relations → access coaching_result.structured_output_json
  → must NOT raise MissingGreenlet.

Test 2 — PROVES THE OLD BUG EXISTS:
  Load via get_by_id (no eager load) from a FRESH session that didn't see the
  insert, so the identity map is empty and the ORM has no cached relation.
  Accessing coaching_result must raise MissingGreenlet (lazy-load crash).

No transactional rollback — inserted rows use UUID-prefixed IDs to avoid
collisions across runs.  See test_beta_request_repository.py for the fixture
pattern used throughout this project.
"""

import os
import uuid

import pytest
import pytest_asyncio
import sqlalchemy.exc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.analysis import Analysis
from app.models.coaching_result import CoachingResult
from app.repositories.analysis import AnalysisRepository

# ---------------------------------------------------------------------------
# Fixtures — inline session wiring (no global conftest fixture in this project)
# ---------------------------------------------------------------------------

_DB_URL = os.environ.get("DATABASE_URL", "")

_skip_no_db = pytest.mark.skipif(
    not _DB_URL,
    reason="DATABASE_URL not set — skipping live DB integration tests",
)


def _make_async_url(url: str) -> str:
    """Convert postgresql:// → postgresql+asyncpg:// if needed."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


@pytest_asyncio.fixture
async def db_session():
    """Yield a SQLAlchemy AsyncSession backed by the real Supabase Postgres.

    Uses PgBouncer connect_args (statement_cache_size=0) as required by
    backend/CLAUDE.md gotchas.  Each test commits its own work; no rollback
    is performed — IDs are UUID-prefixed to stay unique across runs.
    """
    engine = create_async_engine(
        _make_async_url(_DB_URL),
        connect_args={"statement_cache_size": 0},
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis() -> Analysis:
    """Create a minimal valid Analysis ORM object with a fresh UUID."""
    return Analysis(
        id=uuid.uuid4(),
        # user_id does not reference auth.users via FK (RLS-only, no DDL FK),
        # so any UUID works in integration tests.
        user_id=uuid.uuid4(),
        status="completed",
        exercise_type="squat",
        exercise_variant="high_bar",
    )


def _make_coaching_result(analysis_id: uuid.UUID) -> CoachingResult:
    """Create a minimal CoachingResult associated with *analysis_id*."""
    return CoachingResult(
        id=uuid.uuid4(),
        analysis_id=analysis_id,
        structured_output_json={"summary": "Test coaching output"},
        stream_complete=True,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_get_by_id_with_relations_loads_coaching_result(
    db_session: AsyncSession,
) -> None:
    """PROVES THE FIX: get_by_id_with_relations() selectinloads coaching_result,
    so accessing analysis.coaching_result.structured_output_json inside an async
    context does NOT raise sqlalchemy.exc.MissingGreenlet.

    This is the exact code path that was broken in production and fixed at f73b793.
    """
    # Arrange — insert Analysis + CoachingResult and commit.
    analysis = _make_analysis()
    coaching = _make_coaching_result(analysis.id)
    db_session.add(analysis)
    db_session.add(coaching)
    await db_session.commit()

    # Act — load via the FIXED method (eager-loads coaching_result).
    repo = AnalysisRepository(db_session)
    loaded = await repo.get_by_id_with_relations(analysis.id)

    # Assert — relationship access must NOT raise MissingGreenlet.
    assert loaded is not None, "Analysis row not found"
    assert loaded.coaching_result is not None, "coaching_result relation not loaded"
    assert loaded.coaching_result.structured_output_json == {
        "summary": "Test coaching output"
    }


@_skip_no_db
@pytest.mark.asyncio
async def test_get_by_id_without_relations_raises_on_lazy_access(
    db_session: AsyncSession,
) -> None:
    """PROVES THE OLD BUG EXISTS: get_by_id() issues a plain SELECT with no
    eager loading.  When the ORM object is loaded into a fresh session that
    has an empty identity map, accessing the `coaching_result` relationship
    will attempt a lazy SELECT — which SQLAlchemy cannot do inside an async
    greenlet, raising MissingGreenlet.

    Two-session trick: we insert in *db_session*, then open a SECOND session
    from the same engine (empty identity map) and call get_by_id() there.
    The Analysis loaded in the second session has `coaching_result` as an
    uninitialised lazy attribute — accessing it crashes as expected.
    """
    # Arrange — insert Analysis + CoachingResult in the fixture session.
    analysis = _make_analysis()
    coaching = _make_coaching_result(analysis.id)
    db_session.add(analysis)
    db_session.add(coaching)
    await db_session.commit()

    analysis_id = analysis.id  # capture before we open the second session

    # Open a fresh engine / session — empty identity map, no cached relations.
    engine2 = create_async_engine(
        _make_async_url(_DB_URL),
        connect_args={"statement_cache_size": 0},
    )
    async_session2 = sessionmaker(engine2, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session2() as session2:
            repo2 = AnalysisRepository(session2)

            # Load via the OLD (unfixed) method — no eager loading.
            loaded = await repo2.get_by_id(analysis_id)
            assert loaded is not None, "Analysis row not found in second session"

            # Attempting to access `coaching_result` must trigger a lazy-load
            # attempt, which SQLAlchemy cannot execute asynchronously → raises
            # MissingGreenlet.
            with pytest.raises(sqlalchemy.exc.MissingGreenlet):
                _ = loaded.coaching_result  # noqa: F841 — access triggers lazy-load
    finally:
        await engine2.dispose()
