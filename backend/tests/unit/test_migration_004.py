"""TDD gate for migration 004 — Phase 2 RAG + Coach Brain schema.

SRS requirements covered:
- FR-AICP-11 — rag_documents + expert_annotations (citation provenance)
- FR-BRAIN-01 — coach_brain_entries (exercise/phase/entry_type/trigger_tags/
                confirmation_count/status)
- FR-BRAIN-11 — consent_records + RLS policy user_own_data
- FR-BRAIN-16 — source_analysis_ids UUID[] on coach_brain_entries
- NFR-PRIV-01 — no DDL FK from consent_records.user_id to auth.users

Tests run against a real Postgres session (DATABASE_URL env var required).
They are structurally identical to test_models.py patterns — async session
fixture with rollback, raw SQL introspection via information_schema.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session():
    """Fresh async session against the project DB, rolls back after each test."""
    raw_url = os.environ["DATABASE_URL"]
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(
        raw_url,
        connect_args={"statement_cache_size": 0},
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()

    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _table_exists(session: AsyncSession, table_name: str) -> bool:
    result = await session.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :t"
        ),
        {"t": table_name},
    )
    return result.scalar() is not None


async def _column_exists(session: AsyncSession, table_name: str, column_name: str) -> bool:
    result = await session.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = :t AND column_name = :c"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.scalar() is not None


async def _column_data_type(session: AsyncSession, table_name: str, column_name: str) -> str:
    result = await session.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = :t AND column_name = :c"
        ),
        {"t": table_name, "c": column_name},
    )
    row = result.scalar()
    return row or ""


async def _check_constraints_for_table(session: AsyncSession, table_name: str) -> list[str]:
    """Return list of check constraint definitions for a table."""
    result = await session.execute(
        text(
            "SELECT pg_get_constraintdef(c.oid) "
            "FROM pg_constraint c "
            "JOIN pg_class r ON r.oid = c.conrelid "
            "JOIN pg_namespace n ON n.oid = r.relnamespace "
            "WHERE c.contype = 'c' "
            "AND n.nspname = 'public' "
            "AND r.relname = :t"
        ),
        {"t": table_name},
    )
    return [row[0] for row in result.fetchall()]


async def _fk_targets_for_column(
    session: AsyncSession, table_name: str, column_name: str
) -> list[str]:
    """Return FK target table names for a given column."""
    result = await session.execute(
        text(
            """
            SELECT ccu.table_name AS foreign_table
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
            AND tc.table_name = :t
            AND kcu.column_name = :c
            """
        ),
        {"t": table_name, "c": column_name},
    )
    return [row[0] for row in result.fetchall()]


async def _rls_enabled(session: AsyncSession, table_name: str) -> bool:
    result = await session.execute(
        text(
            "SELECT rowsecurity FROM pg_class "
            "JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace "
            "WHERE pg_class.relname = :t AND pg_namespace.nspname = 'public'"
        ),
        {"t": table_name},
    )
    row = result.scalar()
    return bool(row)


async def _rls_policy_exists(session: AsyncSession, table_name: str, policy_name: str) -> bool:
    result = await session.execute(
        text(
            "SELECT 1 FROM pg_policies "
            "WHERE schemaname = 'public' "
            "AND tablename = :t AND policyname = :p"
        ),
        {"t": table_name, "p": policy_name},
    )
    return result.scalar() is not None


# ---------------------------------------------------------------------------
# Table existence
# ---------------------------------------------------------------------------


class TestTablesExist:
    @pytest.mark.asyncio
    async def test_rag_documents_table_exists(self, db_session: AsyncSession) -> None:
        assert await _table_exists(db_session, "rag_documents"), (
            "Table rag_documents not found — migration 004 not applied"
        )

    @pytest.mark.asyncio
    async def test_expert_annotations_table_exists(self, db_session: AsyncSession) -> None:
        assert await _table_exists(db_session, "expert_annotations"), (
            "Table expert_annotations not found — migration 004 not applied"
        )

    @pytest.mark.asyncio
    async def test_coach_brain_entries_table_exists(self, db_session: AsyncSession) -> None:
        assert await _table_exists(db_session, "coach_brain_entries"), (
            "Table coach_brain_entries not found — migration 004 not applied"
        )

    @pytest.mark.asyncio
    async def test_consent_records_table_exists(self, db_session: AsyncSession) -> None:
        assert await _table_exists(db_session, "consent_records"), (
            "Table consent_records not found — migration 004 not applied"
        )


# ---------------------------------------------------------------------------
# analyses table — new Phase 2 JSONB columns
# ---------------------------------------------------------------------------


class TestAnalysesPhase2Columns:
    @pytest.mark.asyncio
    async def test_analyses_has_retrieval_context_column(
        self, db_session: AsyncSession
    ) -> None:
        assert await _column_exists(db_session, "analyses", "retrieval_context"), (
            "Column analyses.retrieval_context not found — migration 004 not applied"
        )
        dtype = await _column_data_type(db_session, "analyses", "retrieval_context")
        assert dtype == "jsonb", f"Expected jsonb, got {dtype!r}"

    @pytest.mark.asyncio
    async def test_analyses_has_eval_scores_column(self, db_session: AsyncSession) -> None:
        assert await _column_exists(db_session, "analyses", "eval_scores"), (
            "Column analyses.eval_scores not found — migration 004 not applied"
        )
        dtype = await _column_data_type(db_session, "analyses", "eval_scores")
        assert dtype == "jsonb", f"Expected jsonb, got {dtype!r}"


# ---------------------------------------------------------------------------
# coach_brain_entries — source_analysis_ids is an array (FR-BRAIN-16)
# ---------------------------------------------------------------------------


class TestCoachBrainEntriesSourceAnalysisIds:
    @pytest.mark.asyncio
    async def test_coach_brain_entries_source_analysis_ids_is_array(
        self, db_session: AsyncSession
    ) -> None:
        assert await _column_exists(db_session, "coach_brain_entries", "source_analysis_ids"), (
            "Column coach_brain_entries.source_analysis_ids not found"
        )
        # information_schema reports ARRAY columns as "ARRAY"
        dtype = await _column_data_type(
            db_session, "coach_brain_entries", "source_analysis_ids"
        )
        assert dtype == "ARRAY", f"Expected ARRAY, got {dtype!r}"

    @pytest.mark.asyncio
    async def test_coach_brain_entries_trigger_tags_is_array(
        self, db_session: AsyncSession
    ) -> None:
        assert await _column_exists(db_session, "coach_brain_entries", "trigger_tags"), (
            "Column coach_brain_entries.trigger_tags not found"
        )
        dtype = await _column_data_type(db_session, "coach_brain_entries", "trigger_tags")
        assert dtype == "ARRAY", f"Expected ARRAY, got {dtype!r}"


# ---------------------------------------------------------------------------
# consent_records — no FK to auth.users (NFR-PRIV-01)
# ---------------------------------------------------------------------------


class TestConsentRecordsPrivacy:
    @pytest.mark.asyncio
    async def test_consent_records_no_fk_to_auth_users(
        self, db_session: AsyncSession
    ) -> None:
        """NFR-PRIV-01: user_id must NOT have a DDL FK to auth.users."""
        targets = await _fk_targets_for_column(db_session, "consent_records", "user_id")
        assert "users" not in targets, (
            f"consent_records.user_id has a FK to: {targets!r} — violates NFR-PRIV-01"
        )

    @pytest.mark.asyncio
    async def test_consent_records_rls_enabled(self, db_session: AsyncSession) -> None:
        """FR-BRAIN-11: RLS must be enabled on consent_records."""
        assert await _rls_enabled(db_session, "consent_records"), (
            "RLS not enabled on consent_records"
        )

    @pytest.mark.asyncio
    async def test_consent_records_rls_policy_exists(self, db_session: AsyncSession) -> None:
        """FR-BRAIN-11: policy user_own_data must exist on consent_records."""
        assert await _rls_policy_exists(db_session, "consent_records", "user_own_data"), (
            "RLS policy user_own_data not found on consent_records"
        )


# ---------------------------------------------------------------------------
# CHECK constraints spot-check (VARCHAR(30) + explicit CHECK on enum columns)
# ---------------------------------------------------------------------------


class TestCheckConstraints:
    @pytest.mark.asyncio
    async def test_rag_documents_document_type_check_exists(
        self, db_session: AsyncSession
    ) -> None:
        constraints = await _check_constraints_for_table(db_session, "rag_documents")
        assert any("research_paper" in c for c in constraints), (
            f"Expected document_type CHECK constraint on rag_documents; got: {constraints}"
        )

    @pytest.mark.asyncio
    async def test_coach_brain_entries_exercise_check_exists(
        self, db_session: AsyncSession
    ) -> None:
        constraints = await _check_constraints_for_table(db_session, "coach_brain_entries")
        assert any("squat" in c for c in constraints), (
            f"Expected exercise CHECK constraint on coach_brain_entries; got: {constraints}"
        )

    @pytest.mark.asyncio
    async def test_coach_brain_entries_status_check_exists(
        self, db_session: AsyncSession
    ) -> None:
        constraints = await _check_constraints_for_table(db_session, "coach_brain_entries")
        assert any("deprecated" in c for c in constraints), (
            f"Expected status CHECK constraint on coach_brain_entries; got: {constraints}"
        )

    @pytest.mark.asyncio
    async def test_consent_records_consent_type_check_exists(
        self, db_session: AsyncSession
    ) -> None:
        constraints = await _check_constraints_for_table(db_session, "consent_records")
        assert any("coach_brain_contribution" in c for c in constraints), (
            f"Expected consent_type CHECK constraint on consent_records; got: {constraints}"
        )

    @pytest.mark.asyncio
    async def test_expert_annotations_embedding_model_check_exists(
        self, db_session: AsyncSession
    ) -> None:
        constraints = await _check_constraints_for_table(db_session, "expert_annotations")
        assert any("cohere-embed-v4" in c for c in constraints), (
            f"Expected embedding_model CHECK on expert_annotations; got: {constraints}"
        )


# ---------------------------------------------------------------------------
# Indexes spot-check
# ---------------------------------------------------------------------------


class TestIndexes:
    @pytest.mark.asyncio
    async def test_expected_indexes_exist(self, db_session: AsyncSession) -> None:
        result = await db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = 'public' "
                "AND tablename IN ("
                "  'expert_annotations', 'coach_brain_entries', 'consent_records'"
                ") "
                "ORDER BY indexname"
            )
        )
        index_names = {row[0] for row in result.fetchall()}
        assert "ix_expert_annotations_document_id" in index_names, (
            f"Missing ix_expert_annotations_document_id; found: {index_names}"
        )
        assert "ix_coach_brain_entries_exercise_phase_status" in index_names, (
            f"Missing ix_coach_brain_entries_exercise_phase_status; found: {index_names}"
        )
        assert "ix_consent_records_user_id" in index_names, (
            f"Missing ix_consent_records_user_id; found: {index_names}"
        )
