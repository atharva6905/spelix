"""Pydantic schemas for the beta-request endpoint (landing email capture)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

BetaRequestSource = Literal["hero", "final_cta", "reddit", "dm", "other"]


class BetaRequestCreate(BaseModel):
    """Request body for POST /api/v1/beta/requests."""

    email: EmailStr
    source: BetaRequestSource
    consented_to_beta_terms: bool = Field(
        ..., description="Must be True — enforced by DB CHECK constraint too."
    )

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        return v.strip().lower()

    @field_validator("consented_to_beta_terms")
    @classmethod
    def _consent_must_be_true(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("consented_to_beta_terms must be True")
        return v


class BetaRequestResponse(BaseModel):
    """Response body for POST /api/v1/beta/requests (201).

    Email is intentionally omitted — echoing PII back to an anonymous caller
    creates observability/logging PII surface (Sentry/Loki breadcrumbs index
    response bodies). The client already has the email from form state.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    created_at: datetime
