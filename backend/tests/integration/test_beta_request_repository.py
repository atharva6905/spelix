"""Integration tests for BetaRequestRepository — hits real Postgres.

Uses DATABASE_URL env var (Supabase PgBouncer at port 6543).
Tests are skipped automatically when DATABASE_URL is not set, so
the CI unit-test job stays green without a live DB.

No shared db_session fixture exists in this project — session is
created inline per test, following the pattern used in test_rls_policies.py.
Emails are UUID-prefixed to prevent collisions on repeated test runs
(no transactional rollback — rows are committed and must be unique).
"""

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.repositories.beta_request import BetaRequestRepository

# ---------------------------------------------------------------------------
# Fixtures — inline session wiring (no global conftest fixture in this project)
# ---------------------------------------------------------------------------

_DB_URL = os.environ.get("DATABASE_URL", "")

_skip_no_db = pytest.mark.skipif(
    not _DB_URL,
    reason="DATABASE_URL not set — skipping live DB integration tests",
)


def _make_async_url(url: str) -> str:
    """Convert postgresql:// -> postgresql+asyncpg:// if needed."""
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
    is performed — emails are UUID-prefixed to stay unique across runs.
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
# Tests
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_create_inserts_row(db_session: AsyncSession) -> None:
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"integration-test-1-{unique_suffix}@example.com"

    repo = BetaRequestRepository(db_session)
    row = await repo.create(
        email=email,
        source="hero",
        consented=True,
    )
    await db_session.commit()

    assert row.id is not None
    assert row.email == email
    assert row.source == "hero"
    assert row.status == "pending"
    assert row.consented_to_beta_terms is True


@_skip_no_db
@pytest.mark.asyncio
async def test_create_duplicate_email_raises_integrity_error(
    db_session: AsyncSession,
) -> None:
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"integration-test-2-{unique_suffix}@example.com"

    repo = BetaRequestRepository(db_session)
    await repo.create(
        email=email,
        source="hero",
        consented=True,
    )
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await repo.create(
            email=email,
            source="final_cta",
            consented=True,
        )
