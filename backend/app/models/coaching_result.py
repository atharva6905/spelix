"""SQLAlchemy model for the coaching_results table (migration 001)."""
from datetime import datetime
from uuid import UUID

import uuid as _uuid

from sqlalchemy import Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class CoachingResult(Base):
    __tablename__ = "coaching_results"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=_uuid.uuid4,
    )
    analysis_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    # Full coaching response as JSONB (per FR-COACH and CLAUDE.md)
    structured_output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Phase 2+: citations
    retrieved_sources_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Phase 3+: LangGraph agent trace
    agent_trace_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    stream_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # True if CoVe converged; false pre-Phase-2 or if max_iterations reached
    cove_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
