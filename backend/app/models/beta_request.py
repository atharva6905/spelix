"""BetaRequest model — landing-page email-capture queue (migration 008).

No SRS FR — this is a growth/ops surface. See migration 008 docstring
and landing-page-plan §7.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BetaRequest(Base):
    __tablename__ = "beta_requests"
    __table_args__ = (
        CheckConstraint(
            "source IN ('hero','final_cta','reddit','dm','other')",
            name="ck_beta_requests_source",
        ),
        CheckConstraint(
            "status IN ('pending','approved','rejected')",
            name="ck_beta_requests_status",
        ),
        CheckConstraint(
            "consented_to_beta_terms = TRUE",
            name="ck_beta_requests_consent_required",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    consented_to_beta_terms: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # approved_by is the admin user UUID — intentionally NOT a FK to auth.users
    # (root CLAUDE.md: "No DDL FK to auth.users").
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    invite_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invite_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
