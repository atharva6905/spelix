"""014_rls_chat_expert_reviews

Enable Row Level Security on chat_messages and analysis_expert_reviews.
These tables store user data but were created without RLS in migrations 005/006.

Security audit findings H-01 (chat_messages) and H-02 (analysis_expert_reviews).

chat_messages: owned via analysis_id -> analyses.user_id join.
analysis_expert_reviews: owned via annotator_id = auth.uid().

Revision ID: 1862247fad86
Revises: 013_rename_movement_advice
Create Date: 2026-04-20
"""

from typing import Sequence, Union

from alembic import op


revision: str = "1862247fad86"
down_revision: Union[str, Sequence[str], None] = "013_rename_movement_advice"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # chat_messages — owned via analysis_id -> analyses.user_id
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY chat_messages_select_own
            ON chat_messages
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
        CREATE POLICY chat_messages_insert_own
            ON chat_messages
            FOR INSERT
            WITH CHECK (
                analysis_id IN (
                    SELECT id FROM analyses WHERE user_id = auth.uid()
                )
            )
        """
    )

    # ------------------------------------------------------------------
    # analysis_expert_reviews — owned via annotator_id
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE analysis_expert_reviews ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY expert_reviews_select_own
            ON analysis_expert_reviews
            FOR SELECT
            USING (annotator_id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY expert_reviews_insert_own
            ON analysis_expert_reviews
            FOR INSERT
            WITH CHECK (annotator_id = auth.uid())
        """
    )
    op.execute(
        """
        CREATE POLICY expert_reviews_update_own
            ON analysis_expert_reviews
            FOR UPDATE
            USING (annotator_id = auth.uid())
            WITH CHECK (annotator_id = auth.uid())
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS expert_reviews_update_own ON analysis_expert_reviews"
    )
    op.execute(
        "DROP POLICY IF EXISTS expert_reviews_insert_own ON analysis_expert_reviews"
    )
    op.execute(
        "DROP POLICY IF EXISTS expert_reviews_select_own ON analysis_expert_reviews"
    )
    op.execute(
        "ALTER TABLE analysis_expert_reviews DISABLE ROW LEVEL SECURITY"
    )

    op.execute("DROP POLICY IF EXISTS chat_messages_insert_own ON chat_messages")
    op.execute("DROP POLICY IF EXISTS chat_messages_select_own ON chat_messages")
    op.execute("ALTER TABLE chat_messages DISABLE ROW LEVEL SECURITY")
