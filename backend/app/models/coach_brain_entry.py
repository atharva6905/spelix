"""SQLAlchemy model for the coach_brain_entries table.

Maps to migration 004's coach_brain_entries table.
FR-BRAIN-16: source_analysis_ids is the cascade withdrawal target.
"""

import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import CheckConstraint, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, gen_uuid


class CoachBrainEntry(TimestampMixin, Base):
    __tablename__ = "coach_brain_entries"
    __table_args__ = (
        CheckConstraint(
            "exercise IN ('squat','bench','deadlift')",
            name="ck_coach_brain_entries_exercise",
        ),
        CheckConstraint(
            "phase IN ('setup','descent','bottom','ascent','lockout','general')",
            name="ck_coach_brain_entries_phase",
        ),
        CheckConstraint(
            "entry_type IN ('cue','correction','principle','drill')",
            name="ck_coach_brain_entries_entry_type",
        ),
        CheckConstraint(
            "status IN ('seed','active','deprecated')",
            name="ck_coach_brain_entries_status",
        ),
        Index("ix_coach_brain_entries_exercise_phase_status", "exercise", "phase", "status"),
        Index(
            "ix_coach_brain_entries_source_analysis_ids",
            "source_analysis_ids",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    exercise: Mapped[str] = mapped_column(String(30), nullable=False)
    phase: Mapped[str] = mapped_column(String(30), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    confirmation_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="seed")
    source_analysis_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"
    )
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3), nullable=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
