"""006_admin_expert_reviews

Admin UI + Expert Reviewer Portal schema additions.

SRS requirements:
- FR-RAGK-05 — document metadata columns on rag_documents (promoted from JSONB)
- FR-RAGK-08 — admin corpus view needs queryable columns (authors, year, doi, etc.)
- FR-RAGK-09 — admin delete + re-embed needs storage_path
- FR-EXPV-04 — expert annotation submission -> analysis_expert_reviews table
- FR-EXPV-07 — golden dataset labeling -> is_golden_label column
- FR-ADMN-07 — admin expert reviewer queue (review_status index + reviewer_id)

Changes:
1. Add promoted metadata columns to rag_documents (FR-RAGK-05/08/09):
   authors, year, doi, study_design, population, measurement_method,
   quality_tier, quality_score, review_status (with CHECK), reviewer_id,
   reviewed_at, storage_path.
   Index: ix_rag_documents_review_status on review_status.

2. Create analysis_expert_reviews table (FR-EXPV-04/07, FR-ADMN-07).
   Indexes: ix_analysis_expert_reviews_analysis_id,
            ix_analysis_expert_reviews_annotator_id.

IMPORTANT: reviewer_id and annotator_id are UUID columns with NO DDL FK to
auth.users — Supabase Auth manages that table in a separate schema. Ownership
is enforced at query time via RLS policies only (Spelix schema rule).

Revision ID: 006_admin_expert_reviews
Revises: 005_add_chat_messages
Create Date: 2026-04-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "006_admin_expert_reviews"
down_revision: Union[str, Sequence[str], None] = "005_add_chat_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # rag_documents — promoted metadata columns (FR-RAGK-05/08/09)
    # All new columns are nullable or have a server_default so that
    # existing rows (already ingested documents) are unaffected.
    # ------------------------------------------------------------------

    # authors: ARRAY(Text) NOT NULL with empty-array default
    op.add_column(
        "rag_documents",
        sa.Column(
            "authors",
            ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )

    # year: SmallInteger, nullable — publication year
    op.add_column(
        "rag_documents",
        sa.Column("year", sa.SmallInteger(), nullable=True),
    )

    # doi: Text, nullable — Digital Object Identifier
    op.add_column(
        "rag_documents",
        sa.Column("doi", sa.Text(), nullable=True),
    )

    # study_design: String(50), nullable
    # Valid values: rct, observational, systematic_review, narrative_review,
    #               guideline, other
    op.add_column(
        "rag_documents",
        sa.Column("study_design", sa.String(50), nullable=True),
    )
    op.create_check_constraint(
        "ck_rag_documents_study_design",
        "rag_documents",
        "study_design IS NULL OR study_design IN ("
        "'rct','observational','systematic_review',"
        "'narrative_review','guideline','other')",
    )

    # population: Text, nullable — study population description
    op.add_column(
        "rag_documents",
        sa.Column("population", sa.Text(), nullable=True),
    )

    # measurement_method: Text, nullable — how metrics were measured
    op.add_column(
        "rag_documents",
        sa.Column("measurement_method", sa.Text(), nullable=True),
    )

    # quality_tier: String(30), nullable
    # Valid values: L1_systematic_review, L2_rct, L3_observational, L4_guideline
    op.add_column(
        "rag_documents",
        sa.Column("quality_tier", sa.String(30), nullable=True),
    )
    op.create_check_constraint(
        "ck_rag_documents_quality_tier",
        "rag_documents",
        "quality_tier IS NULL OR quality_tier IN ("
        "'L1_systematic_review','L2_rct','L3_observational','L4_guideline')",
    )

    # quality_score: Numeric(4,3), nullable — 0.000 to 1.000
    op.add_column(
        "rag_documents",
        sa.Column("quality_score", sa.Numeric(4, 3), nullable=True),
    )

    # review_status: String(30) NOT NULL, server_default='pending'
    # Valid values: pending, needs_revision, reviewed_approved, reviewed_rejected
    op.add_column(
        "rag_documents",
        sa.Column(
            "review_status",
            sa.String(30),
            nullable=False,
            server_default="pending",
        ),
    )
    op.create_check_constraint(
        "ck_rag_documents_review_status",
        "rag_documents",
        "review_status IN ("
        "'pending','needs_revision','reviewed_approved','reviewed_rejected')",
    )

    # reviewer_id: UUID, nullable
    # NO DDL FK to auth.users — Supabase Auth manages that table.
    # Ownership enforced via RLS only.
    op.add_column(
        "rag_documents",
        sa.Column("reviewer_id", UUID(as_uuid=True), nullable=True),
    )

    # reviewed_at: DateTime(timezone=True), nullable
    op.add_column(
        "rag_documents",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # storage_path: Text, nullable — Supabase Storage path for re-embed (FR-RAGK-09)
    op.add_column(
        "rag_documents",
        sa.Column("storage_path", sa.Text(), nullable=True),
    )

    # Index for admin reviewer queue queries (FR-ADMN-07)
    op.create_index(
        "ix_rag_documents_review_status",
        "rag_documents",
        ["review_status"],
        postgresql_using="btree",
    )

    # ------------------------------------------------------------------
    # analysis_expert_reviews — expert annotation per analysis (FR-EXPV-04/07)
    # NOT the same as expert_annotations (chunk-level RAG provenance, migration 004).
    #
    # annotator_id is intentionally NOT a DDL FK to auth.users — Spelix schema
    # rule: Supabase Auth table lives in the auth schema; enforce via RLS only.
    # analysis_id FK to analyses.id is fine (both in public schema).
    # ------------------------------------------------------------------
    op.create_table(
        "analysis_expert_reviews",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # annotator_id: NO DDL FK to auth.users (Spelix rule: RLS only)
        sa.Column("annotator_id", UUID(as_uuid=True), nullable=False),
        sa.Column("issues_identified", JSONB, nullable=False, server_default="{}"),
        sa.Column("coaching_quality_score", sa.Numeric(3, 1), nullable=True),
        sa.Column("injury_advice_accurate", sa.Boolean(), nullable=True),
        sa.Column("engagement_advice_accurate", sa.Boolean(), nullable=True),
        sa.Column("suggested_corrections", sa.Text(), nullable=True),
        sa.Column("cited_sources", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "is_golden_label",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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
    )

    # Child-of-analyses index (schema rule: any child table gets (analysis_id))
    op.create_index(
        "ix_analysis_expert_reviews_analysis_id",
        "analysis_expert_reviews",
        ["analysis_id"],
        postgresql_using="btree",
    )

    # Annotator lookup index (FR-ADMN-07: reviewer queue per user)
    op.create_index(
        "ix_analysis_expert_reviews_annotator_id",
        "analysis_expert_reviews",
        ["annotator_id"],
        postgresql_using="btree",
    )


def downgrade() -> None:
    # analysis_expert_reviews
    op.drop_index(
        "ix_analysis_expert_reviews_annotator_id",
        table_name="analysis_expert_reviews",
    )
    op.drop_index(
        "ix_analysis_expert_reviews_analysis_id",
        table_name="analysis_expert_reviews",
    )
    op.drop_table("analysis_expert_reviews")

    # rag_documents — drop in reverse order of addition
    op.drop_index("ix_rag_documents_review_status", table_name="rag_documents")
    op.drop_column("rag_documents", "storage_path")
    op.drop_column("rag_documents", "reviewed_at")
    op.drop_column("rag_documents", "reviewer_id")
    op.drop_constraint("ck_rag_documents_review_status", "rag_documents", type_="check")
    op.drop_column("rag_documents", "review_status")
    op.drop_column("rag_documents", "quality_score")
    op.drop_constraint("ck_rag_documents_quality_tier", "rag_documents", type_="check")
    op.drop_column("rag_documents", "quality_tier")
    op.drop_column("rag_documents", "measurement_method")
    op.drop_column("rag_documents", "population")
    op.drop_constraint("ck_rag_documents_study_design", "rag_documents", type_="check")
    op.drop_column("rag_documents", "study_design")
    op.drop_column("rag_documents", "doi")
    op.drop_column("rag_documents", "year")
    op.drop_column("rag_documents", "authors")
