"""004_phase2_rag_coach_brain

Phase 2 schema additions for RAG retrieval and Coach Brain.

SRS requirements:
- FR-AICP-11  — rag_documents + expert_annotations (citation provenance)
- FR-BRAIN-01 — coach_brain_entries (exercise/phase/entry_type/trigger_tags/
                confirmation_count/status)
- FR-BRAIN-11 — consent_records + RLS policy user_own_data
- FR-BRAIN-16 — source_analysis_ids UUID[] on coach_brain_entries
- NFR-PRIV-01 — no DDL FK from consent_records.user_id to auth.users; RLS only

ADRs implemented: ADR-BRAIN-01, ADR-BRAIN-05, ADR-BRAIN-06 (reserved, no column
yet), ADR-BRAIN-07 (no distillation_* columns), ADR-P2-001 (Postgres half only).

Revision ID: 004_phase2_rag_coach_brain
Revises: 003_add_detection_result
Create Date: 2026-04-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "004_phase2_rag_coach_brain"
down_revision: Union[str, Sequence[str], None] = "003_add_detection_result"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # rag_documents — FR-AICP-11 (citation provenance mirror in Postgres)
    # ------------------------------------------------------------------
    op.create_table(
        "rag_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "document_type",
            sa.String(30),
            nullable=False,
            comment="research_paper | textbook | clinical_guideline | expert_annotation | other",
        ),
        sa.Column("exercise_tags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "document_type IN ('research_paper','textbook','clinical_guideline','expert_annotation','other')",
            name="ck_rag_documents_document_type",
        ),
    )

    # ------------------------------------------------------------------
    # expert_annotations — FR-AICP-11 (chunk-level provenance + Qdrant mirror)
    # ------------------------------------------------------------------
    op.create_table(
        "expert_annotations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column(
            "embedding_model",
            sa.String(30),
            nullable=False,
            comment="cohere-embed-v4 | text-embedding-3-large | other",
        ),
        sa.Column("qdrant_point_id", UUID(as_uuid=True), nullable=True),
        sa.Column("citation_metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], ["rag_documents.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "embedding_model IN ('cohere-embed-v4','text-embedding-3-large','other')",
            name="ck_expert_annotations_embedding_model",
        ),
    )
    op.create_index(
        "ix_expert_annotations_document_id",
        "expert_annotations",
        ["document_id"],
    )

    # ------------------------------------------------------------------
    # coach_brain_entries — FR-BRAIN-01 + FR-BRAIN-16
    # Note: source_analysis_ids UUID[] is the withdrawal cascade target (FR-BRAIN-16).
    # No distillation_* columns — Phase 3 only (ADR-BRAIN-07).
    # No episodic_memory column — Phase 4 only (ADR-BRAIN-06).
    # ------------------------------------------------------------------
    op.create_table(
        "coach_brain_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "exercise",
            sa.String(30),
            nullable=False,
            comment="squat | bench | deadlift",
        ),
        sa.Column(
            "phase",
            sa.String(30),
            nullable=False,
            comment="setup | descent | bottom | ascent | lockout | general",
        ),
        sa.Column(
            "entry_type",
            sa.String(30),
            nullable=False,
            comment="cue | correction | principle | drill",
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("trigger_tags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("confirmation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="seed",
            comment="seed | active | deprecated",
        ),
        # FR-BRAIN-16: cascade withdrawal target — stays empty until Phase 3 distillation
        sa.Column(
            "source_analysis_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
            comment="FR-BRAIN-16: analysis UUIDs that contributed this entry (withdrawal cascade target)",
        ),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "exercise IN ('squat','bench','deadlift')",
            name="ck_coach_brain_entries_exercise",
        ),
        sa.CheckConstraint(
            "phase IN ('setup','descent','bottom','ascent','lockout','general')",
            name="ck_coach_brain_entries_phase",
        ),
        sa.CheckConstraint(
            "entry_type IN ('cue','correction','principle','drill')",
            name="ck_coach_brain_entries_entry_type",
        ),
        sa.CheckConstraint(
            "status IN ('seed','active','deprecated')",
            name="ck_coach_brain_entries_status",
        ),
    )
    op.create_index(
        "ix_coach_brain_entries_exercise_phase_status",
        "coach_brain_entries",
        ["exercise", "phase", "status"],
    )
    op.create_index(
        "ix_coach_brain_entries_trigger_tags",
        "coach_brain_entries",
        ["trigger_tags"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_coach_brain_entries_source_analysis_ids",
        "coach_brain_entries",
        ["source_analysis_ids"],
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------
    # consent_records — FR-BRAIN-11, NFR-PRIV-01, ADR-BRAIN-05
    # IMPORTANT: No DDL FK to auth.users — enforced by RLS only (NFR-PRIV-01 / ADR-003)
    # ------------------------------------------------------------------
    op.create_table(
        "consent_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        # user_id is intentionally NOT a FK to auth.users (NFR-PRIV-01 / ADR-003)
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "consent_type",
            sa.String(30),
            nullable=False,
            comment="coach_brain_contribution | health_data_processing | analytics",
        ),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address_hash", sa.Text(), nullable=True),
        sa.Column("consent_version", sa.String(20), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "consent_type IN ('coach_brain_contribution','health_data_processing','analytics')",
            name="ck_consent_records_consent_type",
        ),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])

    # RLS on consent_records — FR-BRAIN-11, NFR-PRIV-01
    op.execute("ALTER TABLE consent_records ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY user_own_data
            ON consent_records
            FOR ALL
            USING (user_id = auth.uid())
            WITH CHECK (user_id = auth.uid())
        """
    )

    # ------------------------------------------------------------------
    # analyses — add Phase 2 JSONB columns (nullable; existing rows unaffected)
    # retrieval_context: chunks + scores used during coaching generation
    # eval_scores: per-analysis RAGAS / HHEM scores
    # ------------------------------------------------------------------
    op.add_column("analyses", sa.Column("retrieval_context", JSONB, nullable=True))
    op.add_column("analyses", sa.Column("eval_scores", JSONB, nullable=True))


def downgrade() -> None:
    # analyses — drop Phase 2 columns
    op.drop_column("analyses", "eval_scores")
    op.drop_column("analyses", "retrieval_context")

    # consent_records
    op.execute("DROP POLICY IF EXISTS user_own_data ON consent_records")
    op.execute("ALTER TABLE consent_records DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_consent_records_user_id", table_name="consent_records")
    op.drop_table("consent_records")

    # coach_brain_entries
    op.drop_index("ix_coach_brain_entries_source_analysis_ids", table_name="coach_brain_entries")
    op.drop_index("ix_coach_brain_entries_trigger_tags", table_name="coach_brain_entries")
    op.drop_index("ix_coach_brain_entries_exercise_phase_status", table_name="coach_brain_entries")
    op.drop_table("coach_brain_entries")

    # expert_annotations
    op.drop_index("ix_expert_annotations_document_id", table_name="expert_annotations")
    op.drop_table("expert_annotations")

    # rag_documents
    op.drop_table("rag_documents")
