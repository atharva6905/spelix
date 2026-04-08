"""002_rls_policies

Enable Row Level Security on all user-owned tables and create
SELECT/INSERT/UPDATE/DELETE policies so users can only access their own rows.

Service role (used by the backend) bypasses RLS automatically — this is
Supabase/Postgres default behaviour and requires no explicit grant.

FR-AUTH-06: Row Level Security enforced at Supabase Postgres layer
NFR-SECU-01: RLS enforced on all user-owned tables

Revision ID: 002_rls_policies
Revises: 901e432196c4
Create Date: 2026-04-08
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_rls_policies"
down_revision: Union[str, Sequence[str], None] = "901e432196c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable RLS and create access policies for all user-owned tables."""

    # ------------------------------------------------------------------
    # analyses
    # Direct ownership: analyses.user_id = auth.uid()
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE analyses ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY analyses_select_own
            ON analyses
            FOR SELECT
            USING (user_id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY analyses_insert_own
            ON analyses
            FOR INSERT
            WITH CHECK (user_id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY analyses_update_own
            ON analyses
            FOR UPDATE
            USING (user_id = auth.uid())
            WITH CHECK (user_id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY analyses_delete_own
            ON analyses
            FOR DELETE
            USING (user_id = auth.uid())
        """
    )

    # ------------------------------------------------------------------
    # user_profiles
    # Direct ownership: user_profiles.user_id = auth.uid()
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY user_profiles_select_own
            ON user_profiles
            FOR SELECT
            USING (user_id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY user_profiles_insert_own
            ON user_profiles
            FOR INSERT
            WITH CHECK (user_id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY user_profiles_update_own
            ON user_profiles
            FOR UPDATE
            USING (user_id = auth.uid())
            WITH CHECK (user_id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY user_profiles_delete_own
            ON user_profiles
            FOR DELETE
            USING (user_id = auth.uid())
        """
    )

    # ------------------------------------------------------------------
    # rep_metrics
    # Indirect ownership via analysis_id FK to analyses
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE rep_metrics ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY rep_metrics_select_own
            ON rep_metrics
            FOR SELECT
            USING (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
        """
    )
    op.execute(
        """
        CREATE POLICY rep_metrics_insert_own
            ON rep_metrics
            FOR INSERT
            WITH CHECK (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
        """
    )
    op.execute(
        """
        CREATE POLICY rep_metrics_update_own
            ON rep_metrics
            FOR UPDATE
            USING (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
            WITH CHECK (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
        """
    )
    op.execute(
        """
        CREATE POLICY rep_metrics_delete_own
            ON rep_metrics
            FOR DELETE
            USING (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
        """
    )

    # ------------------------------------------------------------------
    # coaching_results
    # Indirect ownership via analysis_id FK to analyses
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE coaching_results ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY coaching_results_select_own
            ON coaching_results
            FOR SELECT
            USING (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
        """
    )
    op.execute(
        """
        CREATE POLICY coaching_results_insert_own
            ON coaching_results
            FOR INSERT
            WITH CHECK (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
        """
    )
    op.execute(
        """
        CREATE POLICY coaching_results_update_own
            ON coaching_results
            FOR UPDATE
            USING (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
            WITH CHECK (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
        """
    )
    op.execute(
        """
        CREATE POLICY coaching_results_delete_own
            ON coaching_results
            FOR DELETE
            USING (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
        """
    )


def downgrade() -> None:
    """Drop all RLS policies and disable Row Level Security."""

    # coaching_results
    op.execute("DROP POLICY IF EXISTS coaching_results_delete_own ON coaching_results")
    op.execute("DROP POLICY IF EXISTS coaching_results_update_own ON coaching_results")
    op.execute("DROP POLICY IF EXISTS coaching_results_insert_own ON coaching_results")
    op.execute("DROP POLICY IF EXISTS coaching_results_select_own ON coaching_results")
    op.execute("ALTER TABLE coaching_results DISABLE ROW LEVEL SECURITY")

    # rep_metrics
    op.execute("DROP POLICY IF EXISTS rep_metrics_delete_own ON rep_metrics")
    op.execute("DROP POLICY IF EXISTS rep_metrics_update_own ON rep_metrics")
    op.execute("DROP POLICY IF EXISTS rep_metrics_insert_own ON rep_metrics")
    op.execute("DROP POLICY IF EXISTS rep_metrics_select_own ON rep_metrics")
    op.execute("ALTER TABLE rep_metrics DISABLE ROW LEVEL SECURITY")

    # user_profiles
    op.execute("DROP POLICY IF EXISTS user_profiles_delete_own ON user_profiles")
    op.execute("DROP POLICY IF EXISTS user_profiles_update_own ON user_profiles")
    op.execute("DROP POLICY IF EXISTS user_profiles_insert_own ON user_profiles")
    op.execute("DROP POLICY IF EXISTS user_profiles_select_own ON user_profiles")
    op.execute("ALTER TABLE user_profiles DISABLE ROW LEVEL SECURITY")

    # analyses
    op.execute("DROP POLICY IF EXISTS analyses_delete_own ON analyses")
    op.execute("DROP POLICY IF EXISTS analyses_update_own ON analyses")
    op.execute("DROP POLICY IF EXISTS analyses_insert_own ON analyses")
    op.execute("DROP POLICY IF EXISTS analyses_select_own ON analyses")
    op.execute("ALTER TABLE analyses DISABLE ROW LEVEL SECURITY")
