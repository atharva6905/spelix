"""SQLAlchemy model for the analysis_expert_reviews table.

Maps to migration 005. Stores expert reviewer annotations on analyses.
FR-EXPV-04: structured annotation per flagged analysis.
FR-EXPV-07: is_golden_label for golden dataset workflow.

NOT the same as expert_annotations (chunk-level RAG provenance from migration 004).
See ADR-040 for naming rationale.
"""

import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, gen_uuid


class AnalysisExpertReview(TimestampMixin, Base):
    __tablename__ = "analysis_expert_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    # No DDL FK to auth.users — enforced via RLS only (Spelix rule)
    annotator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    issues_identified: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    coaching_quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1), nullable=True)
    injury_advice_accurate: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    engagement_advice_accurate: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    suggested_corrections: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cited_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default="[]")
    is_golden_label: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
