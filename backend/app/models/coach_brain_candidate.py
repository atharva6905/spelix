"""SQLAlchemy model for the coach_brain_candidates table.

Maps to migration 011. Distillation pipeline INSERTs rows here; expert
review promotes them to coach_brain_entries (Batch 3). FR-BRAIN-16
cascade target via source_analysis_ids GIN index.
"""

import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, CheckConstraint, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, gen_uuid


class CoachBrainCandidate(TimestampMixin, Base):
    __tablename__ = "coach_brain_candidates"
    __table_args__ = (
        CheckConstraint(
            "exercise IN ('squat','bench','deadlift')",
            name="ck_coach_brain_candidates_exercise",
        ),
        CheckConstraint(
            "phase IS NULL OR phase IN ('setup','descent','bottom','ascent','lockout','general')",
            name="ck_coach_brain_candidates_phase",
        ),
        CheckConstraint(
            "entry_type IN ('cue','correction','principle','drill')",
            name="ck_coach_brain_candidates_entry_type",
        ),
        CheckConstraint(
            "lifecycle_decision IN ('ADD','UPDATE','NOOP')",
            name="ck_coach_brain_candidates_lifecycle",
        ),
        CheckConstraint(
            "review_status IN ('pending','approved','rejected','superseded')",
            name="ck_coach_brain_candidates_review_status",
        ),
        Index(
            "ix_cbc_review_status_created",
            "review_status",
            "created_at",
        ),
        Index(
            "ix_cbc_source_analysis_ids",
            "source_analysis_ids",
            postgresql_using="gin",
        ),
        Index(
            "ix_cbc_nearest_entry_id",
            "nearest_entry_id",
            postgresql_where="nearest_entry_id IS NOT NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    exercise: Mapped[str] = mapped_column(String(30), nullable=False)
    phase: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    source_analysis_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3), nullable=True)
    eval_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    cove_verified: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    cove_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cove_trace: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    lifecycle_decision: Mapped[str] = mapped_column(String(10), nullable=False)
    nearest_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    nearest_cosine_sim: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    contradiction_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    rejected_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    promoted_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
