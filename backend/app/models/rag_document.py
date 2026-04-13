"""SQLAlchemy model for the rag_documents table.

Maps to migration 004 (base) + 005 (promoted metadata columns).
FR-RAGK-05: document metadata as real columns for queryability.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, gen_uuid


class RagDocument(TimestampMixin, Base):
    __tablename__ = "rag_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    exercise_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    # Migration 005 — promoted from JSONB metadata for queryability (FR-RAGK-05)
    authors: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    year: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    study_design: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    population: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    measurement_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_tier: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3), nullable=True)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
