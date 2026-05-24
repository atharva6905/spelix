import uuid
from typing import Any, Optional

from sqlalchemy import Float, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, gen_uuid


class RepMetric(Base):
    __tablename__ = "rep_metrics"
    __table_args__ = (
        Index("ix_rep_metrics_analysis", "analysis_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    rep_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    end_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # R5 (L2-CV-DEPTHFRAME-R5): fraction of this rep's frames R2 had to
    # reconstruct over dropout (mean of compute_invalid_frame_mask over the
    # rep window). NULL = pre-R5 analysis or empty rep window; 0.0 = nothing
    # reconstructed (clean rep, or bench which is not R2-gated). Surfaced in
    # the expert portal as the "why" behind a None metric.
    interpolation_fraction: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metrics_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    analysis: Mapped["Analysis"] = relationship(back_populates="rep_metrics")


from app.models.analysis import Analysis  # noqa: E402
