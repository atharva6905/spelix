import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, gen_uuid


class CoachingResult(Base):
    __tablename__ = "coaching_results"
    __table_args__ = (
        Index("ix_coaching_results_analysis", "analysis_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    structured_output_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    retrieved_sources_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    agent_trace_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    stream_complete: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    cove_verified: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    analysis: Mapped["Analysis"] = relationship(back_populates="coaching_result")


from app.models.analysis import Analysis  # noqa: E402
