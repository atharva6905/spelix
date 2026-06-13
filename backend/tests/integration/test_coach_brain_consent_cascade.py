"""Integration test for Coach Brain consent-cascade tombstone predicate.

FR-BRAIN-16: soft_delete_empty_unconfirmed() must tombstone ONLY the
active+empty+unconfirmed rows and leave every other category untouched.

Origin: PR #213 /code-review MEDIUM — the existing unit test
(test_coach_brain_repository.py::test_soft_delete_empty_unconfirmed_predicate_uses_cardinality)
only string-asserts the rendered SQL, which is brittle against dialect version bumps and
does NOT prove row selection. This test proves row selection against real Postgres.

ADR-BRAIN-12: seed entries ship source_analysis_ids=[] and must never be tombstoned.
ADR-BRAIN-08: cascade is scoped to status='active' only.

No rollback fixture exists in this project — rows are committed and cleaned up via
DELETE in finally: (same pattern as test_beta_request_repository.py).
Unique content strings (UUID-prefixed) prevent collision on repeated runs.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.coach_brain_entry import CoachBrainEntry
from app.repositories.coach_brain import CoachBrainRepository

# ---------------------------------------------------------------------------
# Skip gate — auto-skip when DATABASE_URL is not set
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
    """Yield an AsyncSession backed by real Supabase Postgres.

    Uses PgBouncer connect_args (statement_cache_size=0) as required by
    backend/CLAUDE.md gotchas. Each test commits its own work; cleanup is
    done via explicit DELETE in finally: blocks — no rollback isolation
    (same pattern as test_beta_request_repository.py).
    """
    if not _DB_URL:
        pytest.skip("DATABASE_URL not set — skipping live DB integration tests")

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

_FAKE_AID = uuid.uuid4()  # stable fake analysis UUID for non-empty arrays


def _make_entry(
    *,
    tag: str,
    status: str,
    source_analysis_ids: list[uuid.UUID],
    confirmation_count: int,
) -> CoachBrainEntry:
    """Build a CoachBrainEntry with a unique content string for identification."""
    return CoachBrainEntry(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content=f"integration-test-brain16-{tag}",
        trigger_tags=[],
        status=status,
        source_analysis_ids=source_analysis_ids,
        confirmation_count=confirmation_count,
        extra_metadata={},
    )


# ---------------------------------------------------------------------------
# Test: soft_delete_empty_unconfirmed — row selection matrix
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_soft_delete_empty_unconfirmed_row_selection(
    db_session: AsyncSession,
) -> None:
    """Verify soft_delete_empty_unconfirmed() tombstones the CORRECT rows.

    Matrix inserted:
    - seed:                status='seed',       ids=[],        count=1   → UNTOUCHED (ADR-BRAIN-12)
    - active_empty_low:    status='active',     ids=[],        count=0   → TOMBSTONED  ← the bug target
    - active_empty_conf:   status='active',     ids=[],        count=3   → UNTOUCHED (confirmed)
    - active_nonempty:     status='active',     ids=[fake],    count=0   → UNTOUCHED (non-empty)
    - deprecated_empty:    status='deprecated', ids=[],        count=0   → UNTOUCHED (already deprecated)

    Assertions:
    - active_empty_low:  status='deprecated', extra_metadata['rejected_reason']='source_consent_withdrawn'
    - all others:        status unchanged, extra_metadata unchanged
    """
    # unique run tag to allow repeated test runs without collision
    run_id = uuid.uuid4().hex[:8]

    # Build the five rows
    seed = _make_entry(
        tag=f"seed-{run_id}",
        status="seed",
        source_analysis_ids=[],
        confirmation_count=1,
    )
    active_empty_low = _make_entry(
        tag=f"active-empty-low-{run_id}",
        status="active",
        source_analysis_ids=[],
        confirmation_count=0,
    )
    active_empty_conf = _make_entry(
        tag=f"active-empty-conf-{run_id}",
        status="active",
        source_analysis_ids=[],
        confirmation_count=3,
    )
    active_nonempty = _make_entry(
        tag=f"active-nonempty-{run_id}",
        status="active",
        source_analysis_ids=[_FAKE_AID],
        confirmation_count=0,
    )
    deprecated_empty = _make_entry(
        tag=f"deprecated-empty-{run_id}",
        status="deprecated",
        source_analysis_ids=[],
        confirmation_count=0,
    )

    all_entries = [seed, active_empty_low, active_empty_conf, active_nonempty, deprecated_empty]
    # collect IDs for cleanup (populated after flush)
    inserted_ids: list[uuid.UUID] = []

    try:
        # Insert all rows
        for entry in all_entries:
            db_session.add(entry)
        await db_session.flush()
        inserted_ids = [e.id for e in all_entries]
        await db_session.commit()

        # Run the cascade predicate under test
        repo = CoachBrainRepository(db_session)
        tombstoned_count = await repo.soft_delete_empty_unconfirmed()
        await db_session.commit()

        # Reload all rows so we see the post-update state.
        # expire_all() is required: soft_delete_empty_unconfirmed() uses an ORM-level
        # bulk UPDATE which may not expire all in-memory objects when the WHERE clause
        # uses Postgres-specific functions (func.cardinality) that SQLAlchemy's
        # evaluate strategy cannot evaluate in Python. Without expiry the identity map
        # may return stale status/'deprecated' for entries that were NOT tombstoned.
        db_session.expire_all()

        from sqlalchemy import select

        result = await db_session.execute(
            select(CoachBrainEntry).where(CoachBrainEntry.id.in_(inserted_ids))
        )
        rows_by_id = {r.id: r for r in result.scalars().all()}

        # --- Primary assertion: exactly 1 row tombstoned ---
        assert tombstoned_count == 1, (
            f"Expected exactly 1 tombstone, got {tombstoned_count}"
        )

        # --- active_empty_low: MUST be tombstoned ---
        tombstoned = rows_by_id[active_empty_low.id]
        assert tombstoned.status == "deprecated", (
            f"active_empty_low: expected status='deprecated', got {tombstoned.status!r}"
        )
        assert tombstoned.extra_metadata.get("rejected_reason") == "source_consent_withdrawn", (
            f"active_empty_low: missing rejected_reason in extra_metadata, got {tombstoned.extra_metadata!r}"
        )

        # --- seed: MUST be untouched (ADR-BRAIN-12) ---
        seed_row = rows_by_id[seed.id]
        assert seed_row.status == "seed", (
            f"seed: expected status='seed', got {seed_row.status!r} — ADR-BRAIN-12 violated"
        )
        assert "rejected_reason" not in seed_row.extra_metadata, (
            "seed: rejected_reason must not appear in extra_metadata"
        )

        # --- active_empty_conf: MUST be untouched (confirmation_count >= 3) ---
        conf_row = rows_by_id[active_empty_conf.id]
        assert conf_row.status == "active", (
            f"active_empty_conf: expected status='active', got {conf_row.status!r}"
        )

        # --- active_nonempty: MUST be untouched (non-empty array) ---
        nonempty_row = rows_by_id[active_nonempty.id]
        assert nonempty_row.status == "active", (
            f"active_nonempty: expected status='active', got {nonempty_row.status!r}"
        )

        # --- deprecated_empty: MUST be untouched (already deprecated) ---
        deprecated_row = rows_by_id[deprecated_empty.id]
        assert deprecated_row.status == "deprecated", (
            f"deprecated_empty: expected status='deprecated' unchanged, got {deprecated_row.status!r}"
        )
        assert "rejected_reason" not in deprecated_row.extra_metadata, (
            "deprecated_empty: rejected_reason must not appear for pre-existing deprecated row"
        )

    finally:
        # Clean up test rows — always runs regardless of assertion outcome
        if inserted_ids:
            from sqlalchemy import delete

            await db_session.execute(
                delete(CoachBrainEntry).where(CoachBrainEntry.id.in_(inserted_ids))
            )
            await db_session.commit()


# ---------------------------------------------------------------------------
# Test: cascade_consent_withdrawal — end-to-end array_remove → tombstone
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_cascade_array_remove_then_tombstone(
    db_session: AsyncSession,
) -> None:
    """Verify the full cascade flow: array_remove shrinks source_analysis_ids,
    leaving the entry empty, which soft_delete_empty_unconfirmed then tombstones.

    This exercises the path that produced the original #203 bug:
    - Entry starts with one analysis ID in source_analysis_ids
    - remove_analysis_ids_for_user strips it (leaving [])
    - soft_delete_empty_unconfirmed tombstones the now-empty entry
    """
    run_id = uuid.uuid4().hex[:8]
    target_analysis_id = uuid.uuid4()  # the ID we will "remove"

    # One active entry seeded with a single source analysis ID
    entry = _make_entry(
        tag=f"cascade-e2e-{run_id}",
        status="active",
        source_analysis_ids=[target_analysis_id],
        confirmation_count=1,
    )

    inserted_ids: list[uuid.UUID] = []
    entry_id: uuid.UUID  # captured before expire_all() to avoid greenlet error

    try:
        db_session.add(entry)
        await db_session.flush()
        # Capture the PK into a plain Python variable NOW — before any expire_all()
        # call. After expire_all(), accessing entry.id triggers a synchronous lazy
        # load that raises MissingGreenlet in SQLAlchemy 2.0 async sessions.
        entry_id = entry.id
        inserted_ids = [entry_id]
        await db_session.commit()

        repo = CoachBrainRepository(db_session)

        # Step 1: strip the analysis ID from the entry
        modified = await repo.remove_analysis_ids_for_user([target_analysis_id])
        await db_session.commit()
        assert modified == 1, f"Expected 1 modified entry, got {modified}"

        # Step 2: tombstone the now-empty entry
        deleted = await repo.soft_delete_empty_unconfirmed()
        await db_session.commit()
        assert deleted == 1, f"Expected 1 tombstoned entry, got {deleted}"

        # Reload and verify final state.
        # expire_all() is required: both remove_analysis_ids_for_user() and
        # soft_delete_empty_unconfirmed() use raw text() / ORM-bulk UPDATEs that
        # bypass the identity map, leaving stale source_analysis_ids and status
        # values in the in-memory object. Without expiry the SELECT below returns
        # the cached object, not the actual DB state.
        # Use entry_id (plain UUID) rather than entry.id after expire_all() to
        # avoid triggering a synchronous lazy load (MissingGreenlet error).
        db_session.expire_all()

        from sqlalchemy import select

        result = await db_session.execute(
            select(CoachBrainEntry).where(CoachBrainEntry.id == entry_id)
        )
        row = result.scalar_one()

        assert row.status == "deprecated", (
            f"Expected status='deprecated' after cascade, got {row.status!r}"
        )
        assert row.extra_metadata.get("rejected_reason") == "source_consent_withdrawn", (
            f"Expected rejected_reason in extra_metadata, got {row.extra_metadata!r}"
        )
        assert row.source_analysis_ids == [], (
            f"Expected empty source_analysis_ids after array_remove, got {row.source_analysis_ids!r}"
        )

    finally:
        if inserted_ids:
            from sqlalchemy import delete

            await db_session.execute(
                delete(CoachBrainEntry).where(CoachBrainEntry.id.in_(inserted_ids))
            )
            await db_session.commit()
