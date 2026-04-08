"""SQLAlchemy model for the analyses table (migration 001)."""
from datetime import datetime
from uuid import UUID

import uuid as _uuid

from sqlalchemy import (
    ARRAY,
    VARCHAR,
    Boolean,
    CheckConstraint,
    Float,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

# Valid status values per SRS Section 5.2a
VALID_STATUSES = (
    "queued",
    "quality_gate_pending",
    "quality_gate_rejected",
    "processing",
    "coaching",
    "completed",
    "failed",
)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'queued',"
            "'quality_gate_pending',"
            "'quality_gate_rejected',"
            "'processing',"
            "'coaching',"
            "'completed',"
            "'failed'"
            ")",
            name="ck_analyses_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=_uuid.uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=False)
    status: Mapped[str] = mapped_column(VARCHAR(30), nullable=False, default="queued")
    exercise_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    exercise_variant: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)

    # Scoring — all NULL in Phase 0; written in Phase 1+
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    form_score_safety: Mapped[float | None] = mapped_column(Float, nullable=True)
    form_score_technique: Mapped[float | None] = mapped_column(Float, nullable=True)
    form_score_path_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    form_score_control: Mapped[float | None] = mapped_column(Float, nullable=True)
    form_score_overall: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Artifact paths (nullable; cleaned up after 7 days)
    video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    annotated_video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    plot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSONB columns
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quality_gate_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Metadata
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    threshold_version: Mapped[str | None] = mapped_column(VARCHAR(50), nullable=True)
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_golden_dataset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
