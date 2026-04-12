"""SQLAlchemy model for the consent_records table.

Maps to migration 004's consent_records table.
Append-only: withdrawals insert new rows with granted=False — never update.

Requirements: FR-BRAIN-11, NFR-PRIV-01
ADR: ADR-BRAIN-05 (no DDL FK to auth.users — RLS only)
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, CheckConstraint, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, gen_uuid

VALID_CONSENT_TYPES = (
    "health_data_processing",
    "coach_brain_contribution",
    "analytics",
)


class ConsentRecord(TimestampMixin, Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        CheckConstraint(
            "consent_type IN ('health_data_processing','coach_brain_contribution','analytics')",
            name="ck_consent_records_consent_type",
        ),
        Index("ix_consent_records_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    # user_id intentionally NOT a FK to auth.users — enforced by RLS only (NFR-PRIV-01 / ADR-003)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    consent_type: Mapped[str] = mapped_column(String(30), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    ip_address_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consent_version: Mapped[str] = mapped_column(String(20), nullable=False)
    # "metadata" is reserved by SQLAlchemy's DeclarativeBase — use extra_metadata
    # as the Python attribute; the DB column name stays "metadata".
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
