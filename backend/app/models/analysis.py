import uuid
from typing import Any, Optional

from sqlalchemy import Boolean, CheckConstraint, Float, Index, Integer, String, Text, desc
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, gen_uuid

VALID_STATUSES = (
    "queued",
    "quality_gate_pending",
    "quality_gate_rejected",
    "processing",
    "coaching",
    "completed",
    "failed",
)


class Analysis(TimestampMixin, Base):
    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','quality_gate_pending','quality_gate_rejected',"
            "'processing','coaching','completed','failed')",
            name="ck_analyses_status",
        ),
        Index("ix_analyses_user_created", "user_id", desc("created_at")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    exercise_type: Mapped[str] = mapped_column(String(20), nullable=False)
    exercise_variant: Mapped[str] = mapped_column(String(30), nullable=False)

    # Scores — nullable in Phase 0, written in Phase 1
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    form_score_safety: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    form_score_technique: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    form_score_path_balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    form_score_control: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    form_score_overall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Paths
    video_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    annotated_video_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plot_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # JSONB columns
    summary_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    quality_gate_result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Metadata
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    threshold_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_golden_dataset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    rep_metrics: Mapped[list["RepMetric"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    coaching_result: Mapped[Optional["CoachingResult"]] = relationship(back_populates="analysis", cascade="all, delete-orphan", uselist=False)


# Avoid circular import — these are string refs resolved by SQLAlchemy
from app.models.rep_metric import RepMetric  # noqa: E402
from app.models.coaching_result import CoachingResult  # noqa: E402
