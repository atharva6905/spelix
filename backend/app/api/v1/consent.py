"""FastAPI router for consent endpoints (P2-029).

Routes:
    POST /api/v1/consent/          — grant consent (inserts new row, granted=True)
    GET  /api/v1/consent/          — list all consent records for current user
    POST /api/v1/consent/withdraw  — withdraw consent (inserts new row, granted=False)

Append-only: withdrawals insert NEW rows — existing rows are never updated.

Requirements: FR-BRAIN-11, NFR-PRIV-01
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db import get_db
from app.models.consent_record import ConsentRecord
from app.repositories.consent import ConsentRepository
from app.schemas.consent import ConsentCreate, ConsentResponse, ConsentWithdraw

router = APIRouter(tags=["consent"])


def _get_repo(db: AsyncSession = Depends(get_db)) -> ConsentRepository:
    return ConsentRepository(db)


@router.post("/", response_model=ConsentResponse, status_code=201)
async def grant_consent(
    body: ConsentCreate,
    user: CurrentUser = Depends(get_current_user),
    repo: ConsentRepository = Depends(_get_repo),
) -> ConsentResponse:
    """Grant consent — inserts a new row with granted=True."""
    now = datetime.now(timezone.utc)
    record = ConsentRecord(
        user_id=user["id"],
        consent_type=body.consent_type,
        granted=body.granted,
        granted_at=now if body.granted else None,
        withdrawn_at=None,
        consent_version=body.consent_version,
        ip_address_hash=body.ip_address_hash,
    )
    saved = await repo.create(record)
    return ConsentResponse.model_validate(saved)


@router.get("/", response_model=list[ConsentResponse])
async def list_consents(
    user: CurrentUser = Depends(get_current_user),
    repo: ConsentRepository = Depends(_get_repo),
) -> list[ConsentResponse]:
    """Return all consent records for the authenticated user, newest first."""
    records = await repo.get_by_user(user["id"])
    return [ConsentResponse.model_validate(r) for r in records]


@router.post("/withdraw", response_model=ConsentResponse)
async def withdraw_consent(
    body: ConsentWithdraw,
    user: CurrentUser = Depends(get_current_user),
    repo: ConsentRepository = Depends(_get_repo),
) -> ConsentResponse:
    """Withdraw consent — inserts a NEW row with granted=False, withdrawn_at=now().

    Append-only: the original grant row is preserved for audit purposes.
    """
    now = datetime.now(timezone.utc)
    record = ConsentRecord(
        user_id=user["id"],
        consent_type=body.consent_type,
        granted=False,
        granted_at=None,
        withdrawn_at=now,
        consent_version="1.0",
        ip_address_hash=None,
    )
    saved = await repo.create(record)
    return ConsentResponse.model_validate(saved)
