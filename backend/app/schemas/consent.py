"""Pydantic v2 schemas for the consent resource (P2-029).

Requirements: FR-BRAIN-11, NFR-PRIV-01
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

ConsentType = Literal[
    "health_data_processing",
    "coach_brain_contribution",
    "analytics",
]


class ConsentCreate(BaseModel):
    """Request body for POST /api/v1/consent."""

    consent_type: ConsentType
    granted: bool = True
    consent_version: str
    ip_address_hash: Optional[str] = None


class ConsentWithdraw(BaseModel):
    """Request body for POST /api/v1/consent/withdraw."""

    consent_type: ConsentType


class ConsentResponse(BaseModel):
    """Response schema for a single consent record."""

    id: UUID
    consent_type: str
    granted: bool
    granted_at: Optional[datetime]
    withdrawn_at: Optional[datetime]
    consent_version: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConsentStatus(BaseModel):
    """Summary of latest consent state per type."""

    consent_type: str
    granted: bool
    last_updated: datetime
