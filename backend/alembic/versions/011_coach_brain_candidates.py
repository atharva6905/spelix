"""011_coach_brain_candidates

Add coach_brain_candidates table for the async distillation pipeline.

SRS requirements:
- FR-BRAIN-06  — distillation pipeline emits candidate entries; this table is
                 where they land (DistillationOutput.status stored/rejected/
                 needs_review/error)
- FR-BRAIN-14  — cove_verified, cove_explanation, cove_trace columns so CoVe
                 results are persisted for the expert review queue
- FR-BRAIN-17  — lifecycle_decision + nearest_entry_id + nearest_cosine_sim +
                 contradiction_flag capture ADD/UPDATE/NOOP routing
- FR-BRAIN-18  — source_analysis_ids UUID[] + GIN index (confirmation-count
                 bumping on UPDATE path; FR-BRAIN-16 cascade target)
- FR-BRAIN-16  — source_analysis_ids GIN index is the cascade target when a
                 user withdraws consent
- FR-ADMN-12 / FR-BRAIN-07  — review_status column drives Batch 3 expert
                 review queue (Batch 2 writes rows only)

ADRs: ADR-BRAIN-07 (distillation as standalone StateGraph),
      ADR-DISTILL-01 (new table, not a status extension of coach_brain_entries)

Revision ID: 011_coach_brain_candidates
Revises: 010_add_timing_json
Create Date: 2026-04-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "011_coach_brain_candidates"
down_revision: Union[str, Sequence[str], None] = "010_add_timing_json"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # coach_brain_candidates — FR-BRAIN-06/14/17/18, FR-ADMN-12
    # Admin-only table; users must never see raw candidate rows.
    # Expert review in Batch 3 promotes rows to coach_brain_entries.
    # ------------------------------------------------------------------
    op.create_table(
        "coach_brain_candidates",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("exercise", sa.String(30), nullable=False),
        sa.Column("phase", sa.String(30), nullable=True),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "trigger_tags",
            ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        # length-1 array on INSERT; grows on UPDATE-path confirmation bumps
        sa.Column("source_analysis_ids", ARRAY(UUID(as_uuid=True)), nullable=False),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=True),
        # copy of analysis.eval_scores at distillation time
        sa.Column("eval_scores", JSONB, nullable=False, server_default="{}"),
        # null until cove_verify node runs (FR-BRAIN-14)
        sa.Column("cove_verified", sa.Boolean(), nullable=True),
        sa.Column("cove_explanation", sa.Text(), nullable=True),
        sa.Column("cove_trace", JSONB, nullable=True),
        # ADD / UPDATE / NOOP routing (FR-BRAIN-17)
        sa.Column("lifecycle_decision", sa.String(10), nullable=False),
        # cosine-nearest existing entry for UPDATE / NOOP audit (FR-BRAIN-17)
        sa.Column("nearest_entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("nearest_cosine_sim", sa.Numeric(5, 4), nullable=True),
        # contradiction detection — expert confirms deprecation in Batch 3
        sa.Column(
            "contradiction_flag",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # expert review queue driver (FR-ADMN-12, FR-BRAIN-07)
        sa.Column(
            "review_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        # set by Batch 3 approve action
        sa.Column("promoted_entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # CHECK constraints
        sa.CheckConstraint(
            "exercise IN ('squat','bench','deadlift')",
            name="ck_coach_brain_candidates_exercise",
        ),
        sa.CheckConstraint(
            "phase IS NULL OR phase IN ('setup','descent','bottom','ascent','lockout','general')",
            name="ck_coach_brain_candidates_phase",
        ),
        sa.CheckConstraint(
            "entry_type IN ('cue','correction','principle','drill')",
            name="ck_coach_brain_candidates_entry_type",
        ),
        sa.CheckConstraint(
            "lifecycle_decision IN ('ADD','UPDATE','NOOP')",
            name="ck_coach_brain_candidates_lifecycle",
        ),
        sa.CheckConstraint(
            "review_status IN ('pending','approved','rejected','superseded')",
            name="ck_coach_brain_candidates_review_status",
        ),
    )

    # Composite index for review queue pagination (review_status + newest-first)
    op.create_index(
        "ix_cbc_review_status_created",
        "coach_brain_candidates",
        ["review_status", sa.text("created_at DESC")],
        postgresql_using="btree",
    )

    # GIN index on source_analysis_ids array — FR-BRAIN-16 consent cascade target,
    # FR-BRAIN-18 confirmation-count UPDATE path
    op.create_index(
        "ix_cbc_source_analysis_ids",
        "coach_brain_candidates",
        ["source_analysis_ids"],
        postgresql_using="gin",
    )

    # Partial index on nearest_entry_id — only rows with a cosine neighbour
    op.create_index(
        "ix_cbc_nearest_entry_id",
        "coach_brain_candidates",
        ["nearest_entry_id"],
        postgresql_using="btree",
        postgresql_where=sa.text("nearest_entry_id IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # RLS: admin-only (deny by default, service_role bypasses RLS)
    # Users must NEVER see raw candidate rows — RLS enforces this at the
    # Postgres layer without requiring application-level guards.
    # No DDL FK to auth.users — Supabase Auth manages that table.
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE coach_brain_candidates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE coach_brain_candidates FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY coach_brain_candidates_admin_all
        ON coach_brain_candidates
        FOR ALL
        TO service_role
        USING (true)
        WITH CHECK (true)
        """
    )


def downgrade() -> None:
    # Drop policy first, then indexes, then table
    op.execute(
        "DROP POLICY IF EXISTS coach_brain_candidates_admin_all ON coach_brain_candidates"
    )
    op.drop_index("ix_cbc_nearest_entry_id", table_name="coach_brain_candidates")
    op.drop_index("ix_cbc_source_analysis_ids", table_name="coach_brain_candidates")
    op.drop_index("ix_cbc_review_status_created", table_name="coach_brain_candidates")
    op.drop_table("coach_brain_candidates")
