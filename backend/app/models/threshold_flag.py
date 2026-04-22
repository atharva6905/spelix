"""SQLAlchemy model for the threshold_flags table (FR-EXPV-08).

Expert Reviewers use this table to propose changes to angle thresholds in
config/thresholds_v1.json. Values in that JSON file remain the source of
truth (FR-SCOR-11 — changes ship via PR review); this table records
proposals for admin triage only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ThresholdFlag(Base):
    __tablename__ = "threshold_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # No DDL FK to auth.users — enforced via RLS (root CLAUDE.md rule).
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    section: Mapped[str] = mapped_column(String(30), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    current_citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_value: Mapped[float] = mapped_column(Float, nullable=False)
    proposed_citation: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="open"
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'resolved', 'rejected')",
            name="ck_threshold_flags_status",
        ),
        CheckConstraint(
            "char_length(rationale) >= 20",
            name="ck_threshold_flags_rationale_min_len",
        ),
        CheckConstraint(
            "char_length(proposed_citation) >= 5",
            name="ck_threshold_flags_citation_min_len",
        ),
        Index(
            "ix_threshold_flags_reviewer_created",
            "reviewer_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_threshold_flags_status_created",
            "status",
            text("created_at DESC"),
        ),
        Index("ix_threshold_flags_section_key", "section", "key"),
    )
