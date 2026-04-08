"""SQLAlchemy model for the rep_metrics table (migration 001)."""
from uuid import UUID

import uuid as _uuid

from sqlalchemy import Float, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RepMetric(Base):
    __tablename__ = "rep_metrics"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=_uuid.uuid4,
    )
    analysis_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    rep_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    end_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    # Phase 0: mean landmark visibility (FR-CVPL-16)
    # Phase 1+: Tier 5 10th-percentile (FR-CVPL-24)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
