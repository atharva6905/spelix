"""Integration tests for RLS policies.

Tests are split into two categories:

1. Static tests (no DB required) — verify the migration file structure:
   SQL statements cover all required tables, correct predicates, proper
   enable/disable, and full CRUD (SELECT/INSERT/UPDATE/DELETE) coverage.

2. Live DB tests (@pytest.mark.integration) — verify actual policy enforcement
   against a real Postgres instance with Supabase auth functions. These are
   skipped when DATABASE_URL is not set.

FR-AUTH-06: Row Level Security enforced at Supabase Postgres layer
NFR-SECU-01: RLS enforced on all user-owned tables
NFR-SECU-06: Storage access policies (covered separately; this file
             covers database-layer RLS)
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
import types
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "002_rls_policies.py"
)

TABLES = ["analyses", "user_profiles", "rep_metrics", "coaching_results"]
OPERATIONS = ["SELECT", "INSERT", "UPDATE", "DELETE"]


def _load_migration() -> types.ModuleType:
    """Load the migration file as a module without executing it."""
    spec = importlib.util.spec_from_file_location("migration_002", MIGRATION_PATH)
    assert spec is not None, f"Cannot load migration from {MIGRATION_PATH}"
    mod = importlib.util.module_from_spec(spec)
    # Inject alembic stubs so the module-level imports resolve
    alembic_stub = types.ModuleType("alembic")
    op_stub = MagicMock()
    alembic_stub.op = op_stub  # type: ignore[attr-defined]
    sys.modules.setdefault("alembic", alembic_stub)
    sys.modules.setdefault("alembic.op", op_stub)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def _collect_sql(migration_fn: Any) -> list[str]:
    """Call upgrade() or downgrade() with a mocked op and collect SQL strings."""
    executed: list[str] = []

    mock_op = MagicMock()
    mock_op.execute.side_effect = lambda sql: executed.append(str(sql))

    with patch.dict(sys.modules, {"alembic": MagicMock(op=mock_op)}):
        # Patch op inside the migration module namespace
        mod = _load_migration()
        mod.op = mock_op  # type: ignore[attr-defined]
        migration_fn(mod)

    return executed


def _upgrade_sql() -> list[str]:
    def _run(mod: types.ModuleType) -> None:
        mod.upgrade()

    return _collect_sql(_run)


def _downgrade_sql() -> list[str]:
    def _run(mod: types.ModuleType) -> None:
        mod.downgrade()

    return _collect_sql(_run)


def _combined_upgrade_sql() -> str:
    """Return all upgrade SQL joined for easy regex search."""
    return "\n".join(_upgrade_sql()).upper()


def _combined_downgrade_sql() -> str:
    return "\n".join(_downgrade_sql()).upper()


# ---------------------------------------------------------------------------
# Static structure tests (no DB required)
# ---------------------------------------------------------------------------


class TestMigrationFileExists:
    def test_migration_file_present(self) -> None:
        assert MIGRATION_PATH.exists(), (
            f"Migration 002 not found at {MIGRATION_PATH}"
        )

    def test_migration_is_valid_python(self) -> None:
        source = MIGRATION_PATH.read_text()
        compile(source, str(MIGRATION_PATH), "exec")  # raises SyntaxError if invalid

    def test_migration_has_upgrade_and_downgrade(self) -> None:
        mod = _load_migration()
        assert callable(getattr(mod, "upgrade", None)), "upgrade() missing"
        assert callable(getattr(mod, "downgrade", None)), "downgrade() missing"

    def test_down_revision_is_001(self) -> None:
        mod = _load_migration()
        assert mod.down_revision == "901e432196c4", (
            f"down_revision must be '901e432196c4', got {mod.down_revision!r}"
        )


class TestRLSEnabledOnAllTables:
    """ENABLE ROW LEVEL SECURITY must appear for every table in upgrade."""

    @pytest.mark.parametrize("table", TABLES)
    def test_rls_enabled(self, table: str) -> None:
        sql = _combined_upgrade_sql()
        assert "ENABLE ROW LEVEL SECURITY" in sql, "ENABLE ROW LEVEL SECURITY not found"
        assert table.upper() in sql, f"Table '{table}' not referenced in upgrade SQL"
        # Check explicit enable for this table
        pattern = rf"ALTER TABLE\s+{table.upper()}\s+ENABLE ROW LEVEL SECURITY"
        assert re.search(pattern, sql), (
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY not found in upgrade"
        )

    @pytest.mark.parametrize("table", TABLES)
    def test_rls_disabled_on_downgrade(self, table: str) -> None:
        sql = _combined_downgrade_sql()
        pattern = rf"ALTER TABLE\s+{table.upper()}\s+DISABLE ROW LEVEL SECURITY"
        assert re.search(pattern, sql), (
            f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY not found in downgrade"
        )


class TestPolicyCoverage:
    """Each table must have SELECT, INSERT, UPDATE, DELETE policies."""

    @pytest.mark.parametrize("table", TABLES)
    @pytest.mark.parametrize("op", OPERATIONS)
    def test_policy_exists_for_operation(self, table: str, op: str) -> None:
        sql = _combined_upgrade_sql()
        # Policy creation must reference both the table and the operation
        # e.g. CREATE POLICY ... ON analyses ... FOR SELECT
        pattern = rf"CREATE POLICY[^;]+ON\s+{table.upper()}[^;]+FOR\s+{op}"
        assert re.search(pattern, sql, re.DOTALL), (
            f"No {op} policy found for table '{table}' in upgrade SQL"
        )


class TestPredicateCorrectness:
    """Verify that policy USING predicates contain the correct auth.uid() expressions."""

    def test_analyses_predicate_uses_user_id_eq_auth_uid(self) -> None:
        sql = _combined_upgrade_sql()
        # Must reference user_id = auth.uid() for analyses
        assert "USER_ID = AUTH.UID()" in sql or "USER_ID=AUTH.UID()" in sql, (
            "analyses policy must use 'user_id = auth.uid()'"
        )

    def test_user_profiles_predicate_uses_user_id_eq_auth_uid(self) -> None:
        sql = _combined_upgrade_sql()
        assert "USER_ID = AUTH.UID()" in sql or "USER_ID=AUTH.UID()" in sql, (
            "user_profiles policy must use 'user_id = auth.uid()'"
        )

    def test_rep_metrics_predicate_uses_subquery_into_analyses(self) -> None:
        sql = _combined_upgrade_sql()
        # Must join back to analyses via subquery
        assert "REP_METRICS" in sql
        assert "ANALYSIS_ID IN" in sql or "ANALYSIS_ID =ANY" in sql, (
            "rep_metrics policy must filter via analysis_id subquery"
        )
        assert "SELECT ID FROM ANALYSES" in sql or "SELECT ANALYSES.ID FROM ANALYSES" in sql, (
            "rep_metrics policy subquery must reference analyses table"
        )

    def test_coaching_results_predicate_uses_subquery_into_analyses(self) -> None:
        sql = _combined_upgrade_sql()
        assert "COACHING_RESULTS" in sql
        # coaching_results also goes via analysis_id → analyses
        assert "SELECT ID FROM ANALYSES" in sql or "SELECT ANALYSES.ID FROM ANALYSES" in sql, (
            "coaching_results policy subquery must reference analyses table"
        )


class TestDowngradeDropsPolicies:
    """Downgrade must DROP all policies before disabling RLS."""

    @pytest.mark.parametrize("table", TABLES)
    def test_drop_policy_on_downgrade(self, table: str) -> None:
        sql = _combined_downgrade_sql()
        assert "DROP POLICY" in sql, "DROP POLICY not found in downgrade"
        assert table.upper() in sql, f"Table '{table}' not referenced in downgrade SQL"


# ---------------------------------------------------------------------------
# Live DB tests — need a real Postgres instance with Supabase-style auth setup
# ---------------------------------------------------------------------------
# These tests require:
#   - DATABASE_URL pointing to a Postgres DB (not PgBouncer — needs DDL support)
#   - The schema from migration 001 already applied
#   - The Supabase auth schema present (auth.uid() function available)
# Mark: @pytest.mark.integration — skipped by default; run with
#   pytest -m integration tests/integration/test_rls_policies.py

try:
    import asyncpg  # noqa: F401

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

LIVE_DB_URL = os.environ.get("TEST_DATABASE_URL", "")
_skip_live = pytest.mark.skipif(
    not LIVE_DB_URL or not HAS_ASYNCPG,
    reason="TEST_DATABASE_URL not set or asyncpg not installed — skipping live DB tests",
)


@pytest.mark.integration
class TestRLSEnforcementLiveDB:
    """
    Live DB integration tests that verify actual Postgres RLS policy enforcement.

    These require:
    - TEST_DATABASE_URL env var pointing to a Postgres instance
    - migration 001 already applied (tables exist)
    - migration 002 applied (RLS enabled)
    - A mock for auth.uid() via SET LOCAL request.jwt.claims

    Supabase exposes auth.uid() as a PG function that reads the JWT claim from
    the current_setting('request.jwt.claims', true). We simulate this in tests
    by setting the local config variable.
    """

    @_skip_live
    @pytest.mark.asyncio
    async def test_rls_enabled_flag_in_pg_catalog(self) -> None:
        """Verify pg_class.relrowsecurity = true for all tables after migration 002."""
        import asyncpg

        conn = await asyncpg.connect(LIVE_DB_URL)
        try:
            rows = await conn.fetch(
                """
                SELECT relname, relrowsecurity
                FROM pg_class
                WHERE relname = ANY($1) AND relkind = 'r'
                """,
                TABLES,
            )
            enabled = {r["relname"]: r["relrowsecurity"] for r in rows}
            for table in TABLES:
                assert enabled.get(table) is True, (
                    f"RLS not enabled on '{table}' (got {enabled.get(table)})"
                )
        finally:
            await conn.close()

    @_skip_live
    @pytest.mark.asyncio
    async def test_user_cannot_read_other_users_analysis(self) -> None:
        """
        Insert an analysis row as user A (via service role), then attempt to
        read it as user B — should return empty result set.
        """
        import asyncpg
        import json

        user_a_id = str(uuid.uuid4())
        user_b_id = str(uuid.uuid4())
        analysis_id = str(uuid.uuid4())

        conn = await asyncpg.connect(LIVE_DB_URL)
        try:
            # Insert row as service role (bypasses RLS)
            await conn.execute(
                """
                INSERT INTO analyses
                    (id, user_id, status, exercise_type, exercise_variant,
                     retry_count, flagged_for_review, is_golden_dataset)
                VALUES ($1, $2, 'queued', 'squat', 'high_bar', 0, false, false)
                """,
                uuid.UUID(analysis_id),
                uuid.UUID(user_a_id),
            )

            # Set local role to authenticated + impersonate user B
            await conn.execute("SET LOCAL ROLE authenticated")
            claims = json.dumps({"sub": user_b_id})
            await conn.execute(
                "SELECT set_config('request.jwt.claims', $1, true)", claims
            )

            rows = await conn.fetch(
                "SELECT id FROM analyses WHERE id = $1", uuid.UUID(analysis_id)
            )
            assert len(rows) == 0, (
                f"User B should not see user A's analysis; got {len(rows)} rows"
            )
        finally:
            # Cleanup — must reset role first
            await conn.execute("RESET ROLE")
            await conn.execute(
                "DELETE FROM analyses WHERE id = $1", uuid.UUID(analysis_id)
            )
            await conn.close()

    @_skip_live
    @pytest.mark.asyncio
    async def test_user_can_read_own_analysis(self) -> None:
        """User A can read their own analysis after RLS is enforced."""
        import asyncpg
        import json

        user_a_id = str(uuid.uuid4())
        analysis_id = str(uuid.uuid4())

        conn = await asyncpg.connect(LIVE_DB_URL)
        try:
            await conn.execute(
                """
                INSERT INTO analyses
                    (id, user_id, status, exercise_type, exercise_variant,
                     retry_count, flagged_for_review, is_golden_dataset)
                VALUES ($1, $2, 'queued', 'squat', 'high_bar', 0, false, false)
                """,
                uuid.UUID(analysis_id),
                uuid.UUID(user_a_id),
            )

            await conn.execute("SET LOCAL ROLE authenticated")
            claims = json.dumps({"sub": user_a_id})
            await conn.execute(
                "SELECT set_config('request.jwt.claims', $1, true)", claims
            )

            rows = await conn.fetch(
                "SELECT id FROM analyses WHERE id = $1", uuid.UUID(analysis_id)
            )
            assert len(rows) == 1, (
                f"User A should see their own analysis; got {len(rows)} rows"
            )
        finally:
            await conn.execute("RESET ROLE")
            await conn.execute(
                "DELETE FROM analyses WHERE id = $1", uuid.UUID(analysis_id)
            )
            await conn.close()

    @_skip_live
    @pytest.mark.asyncio
    async def test_service_role_bypasses_rls(self) -> None:
        """Service role (used by backend) must see all rows regardless of RLS."""
        import asyncpg

        user_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        analysis_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

        conn = await asyncpg.connect(LIVE_DB_URL)
        try:
            for uid, aid in zip(user_ids, analysis_ids):
                await conn.execute(
                    """
                    INSERT INTO analyses
                        (id, user_id, status, exercise_type, exercise_variant,
                         retry_count, flagged_for_review, is_golden_dataset)
                    VALUES ($1, $2, 'queued', 'deadlift', 'conventional', 0, false, false)
                    """,
                    uuid.UUID(aid),
                    uuid.UUID(uid),
                )

            # Service role bypasses RLS by default in Supabase Postgres
            rows = await conn.fetch(
                "SELECT id FROM analyses WHERE id = ANY($1)",
                [uuid.UUID(aid) for aid in analysis_ids],
            )
            assert len(rows) == 2, (
                f"Service role should see all rows; got {len(rows)}"
            )
        finally:
            for aid in analysis_ids:
                await conn.execute(
                    "DELETE FROM analyses WHERE id = $1", uuid.UUID(aid)
                )
            await conn.close()

    @_skip_live
    @pytest.mark.asyncio
    async def test_rep_metrics_isolated_by_owner(self) -> None:
        """User B cannot read rep_metrics rows belonging to user A's analysis."""
        import asyncpg
        import json

        user_a_id = str(uuid.uuid4())
        user_b_id = str(uuid.uuid4())
        analysis_id = str(uuid.uuid4())
        metric_id = str(uuid.uuid4())

        conn = await asyncpg.connect(LIVE_DB_URL)
        try:
            await conn.execute(
                """
                INSERT INTO analyses
                    (id, user_id, status, exercise_type, exercise_variant,
                     retry_count, flagged_for_review, is_golden_dataset)
                VALUES ($1, $2, 'queued', 'squat', 'high_bar', 0, false, false)
                """,
                uuid.UUID(analysis_id),
                uuid.UUID(user_a_id),
            )
            await conn.execute(
                """
                INSERT INTO rep_metrics
                    (id, analysis_id, rep_index, start_frame, end_frame)
                VALUES ($1, $2, 1, 0, 100)
                """,
                uuid.UUID(metric_id),
                uuid.UUID(analysis_id),
            )

            await conn.execute("SET LOCAL ROLE authenticated")
            claims = json.dumps({"sub": user_b_id})
            await conn.execute(
                "SELECT set_config('request.jwt.claims', $1, true)", claims
            )

            rows = await conn.fetch(
                "SELECT id FROM rep_metrics WHERE id = $1", uuid.UUID(metric_id)
            )
            assert len(rows) == 0, (
                f"User B should not see user A's rep_metrics; got {len(rows)} rows"
            )
        finally:
            await conn.execute("RESET ROLE")
            await conn.execute(
                "DELETE FROM rep_metrics WHERE id = $1", uuid.UUID(metric_id)
            )
            await conn.execute(
                "DELETE FROM analyses WHERE id = $1", uuid.UUID(analysis_id)
            )
            await conn.close()

    @_skip_live
    @pytest.mark.asyncio
    async def test_coaching_results_isolated_by_owner(self) -> None:
        """User B cannot read coaching_results belonging to user A's analysis."""
        import asyncpg
        import json

        user_a_id = str(uuid.uuid4())
        user_b_id = str(uuid.uuid4())
        analysis_id = str(uuid.uuid4())
        coaching_id = str(uuid.uuid4())

        conn = await asyncpg.connect(LIVE_DB_URL)
        try:
            await conn.execute(
                """
                INSERT INTO analyses
                    (id, user_id, status, exercise_type, exercise_variant,
                     retry_count, flagged_for_review, is_golden_dataset)
                VALUES ($1, $2, 'queued', 'bench', 'flat', 0, false, false)
                """,
                uuid.UUID(analysis_id),
                uuid.UUID(user_a_id),
            )
            await conn.execute(
                """
                INSERT INTO coaching_results
                    (id, analysis_id)
                VALUES ($1, $2)
                """,
                uuid.UUID(coaching_id),
                uuid.UUID(analysis_id),
            )

            await conn.execute("SET LOCAL ROLE authenticated")
            claims = json.dumps({"sub": user_b_id})
            await conn.execute(
                "SELECT set_config('request.jwt.claims', $1, true)", claims
            )

            rows = await conn.fetch(
                "SELECT id FROM coaching_results WHERE id = $1",
                uuid.UUID(coaching_id),
            )
            assert len(rows) == 0, (
                f"User B should not see user A's coaching_results; got {len(rows)} rows"
            )
        finally:
            await conn.execute("RESET ROLE")
            await conn.execute(
                "DELETE FROM coaching_results WHERE id = $1", uuid.UUID(coaching_id)
            )
            await conn.execute(
                "DELETE FROM analyses WHERE id = $1", uuid.UUID(analysis_id)
            )
            await conn.close()
