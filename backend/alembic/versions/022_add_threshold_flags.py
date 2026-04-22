"""add threshold_flags table for FR-EXPV-08

Revision ID: 022_threshold_flags
Revises: 021_coach_brain_status_idx
Create Date: 2026-04-21

Adds a lightweight audit table capturing Expert Reviewer flags against
angle thresholds in config/thresholds_v1.json. Values in the config file
remain the source of truth (FR-SCOR-11 — changes ship via PR review);
this table only records *proposals* for admin triage.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "022_threshold_flags"
down_revision: Union[str, Sequence[str], None] = "021_coach_brain_status_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "threshold_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        # No DDL FK to auth.users — enforced via RLS (root CLAUDE.md rule).
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", sa.String(length=30), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("current_citation", sa.Text(), nullable=True),
        sa.Column("proposed_value", sa.Float(), nullable=False),
        sa.Column("proposed_citation", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False,
                  server_default="open"),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'rejected')",
            name="ck_threshold_flags_status",
        ),
        sa.CheckConstraint(
            "char_length(rationale) >= 20",
            name="ck_threshold_flags_rationale_min_len",
        ),
        sa.CheckConstraint(
            "char_length(proposed_citation) >= 5",
            name="ck_threshold_flags_citation_min_len",
        ),
    )
    op.create_index(
        "ix_threshold_flags_reviewer_created",
        "threshold_flags",
        ["reviewer_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_threshold_flags_status_created",
        "threshold_flags",
        ["status", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_threshold_flags_section_key",
        "threshold_flags", ["section", "key"],
    )

    # Row-Level Security (Spelix rule: no DDL FK to auth.users — enforce via RLS).
    # Access model:
    #   SELECT — reviewer sees own flags; admin sees all.
    #   INSERT — expert_reviewer or admin; reviewer_id must equal auth.uid().
    #   UPDATE — admin only (service layer enforces reviewer_id/section/key
    #            immutability; DB-level WITH CHECK only constrains the role).
    op.execute("ALTER TABLE threshold_flags ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY threshold_flags_select_own_or_admin ON threshold_flags
        FOR SELECT
        USING (
            reviewer_id = auth.uid()
            OR (auth.jwt() ->> 'role')::text = 'admin'
        );
    """)
    op.execute("""
        CREATE POLICY threshold_flags_insert_expert_or_admin ON threshold_flags
        FOR INSERT
        WITH CHECK (
            (auth.jwt() ->> 'role')::text IN ('admin', 'expert_reviewer')
            AND reviewer_id = auth.uid()
        );
    """)
    op.execute("""
        CREATE POLICY threshold_flags_update_admin_only ON threshold_flags
        FOR UPDATE
        USING ((auth.jwt() ->> 'role')::text = 'admin')
        WITH CHECK ((auth.jwt() ->> 'role')::text = 'admin');
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS threshold_flags_update_admin_only ON threshold_flags;")
    op.execute("DROP POLICY IF EXISTS threshold_flags_insert_expert_or_admin ON threshold_flags;")
    op.execute("DROP POLICY IF EXISTS threshold_flags_select_own_or_admin ON threshold_flags;")
    op.execute("ALTER TABLE threshold_flags DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_threshold_flags_section_key", table_name="threshold_flags")
    op.drop_index("ix_threshold_flags_status_created", table_name="threshold_flags")
    op.drop_index("ix_threshold_flags_reviewer_created", table_name="threshold_flags")
    op.drop_table("threshold_flags")
