"""FastAPI router for consent endpoints (P2-029, P2-030).

Routes:
    POST /api/v1/consent          — grant consent (inserts new row, granted=True)
    GET  /api/v1/consent          — list all consent records for current user
    POST /api/v1/consent/withdraw — withdraw consent (inserts new row, granted=False)

Append-only: withdrawals insert NEW rows — existing rows are never updated.
FR-BRAIN-16: withdrawing coach_brain_contribution enqueues an ARQ cascade job.

Requirements: FR-BRAIN-11, FR-BRAIN-16, NFR-PRIV-01
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db import get_db
from app.models.consent_record import ConsentRecord
from app.repositories.consent import ConsentRepository
from app.schemas.consent import ConsentCreate, ConsentResponse, ConsentWithdraw

logger = logging.getLogger(__name__)

router = APIRouter(tags=["consent"])

# Module-level ARQ pool cache (same pattern as analyses.py)
_arq_pool_cache: Any | None = None
_arq_pool_cache_initialized: bool = False


async def _get_arq_pool() -> Any | None:
    """Build and cache the ARQ Redis pool for enqueueing cascade jobs."""
    global _arq_pool_cache, _arq_pool_cache_initialized

    if _arq_pool_cache_initialized:
        return _arq_pool_cache

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        _arq_pool_cache = None
        _arq_pool_cache_initialized = True
        return None

    try:
        import arq
        from arq.connections import RedisSettings

        _arq_pool_cache = await arq.create_pool(RedisSettings.from_dsn(redis_url))
    except Exception:
        logger.warning("Failed to create ARQ pool for consent cascade", exc_info=True)
        _arq_pool_cache = None

    _arq_pool_cache_initialized = True
    return _arq_pool_cache


def _get_repo(db: AsyncSession = Depends(get_db)) -> ConsentRepository:
    return ConsentRepository(db)


@router.post("", response_model=ConsentResponse, status_code=201)
async def grant_consent(
    body: ConsentCreate,
    user: CurrentUser = Depends(get_current_user),
    repo: ConsentRepository = Depends(_get_repo),
) -> ConsentResponse:
    """Grant consent — inserts a new row with granted=True."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
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


@router.get("", response_model=list[ConsentResponse])
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
    FR-BRAIN-16: if consent_type is coach_brain_contribution, enqueues
    an ARQ cascade job to remove the user's analysis contributions.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
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

    # FR-BRAIN-16: enqueue cascade job for coach_brain_contribution withdrawal
    if body.consent_type == "coach_brain_contribution":
        pool = await _get_arq_pool()
        if pool is not None:
            try:
                await pool.enqueue_job(
                    "cascade_consent_withdrawal",
                    user_id=str(user["id"]),
                )
                logger.info("Enqueued consent withdrawal cascade for user %s", user["id"])
            except Exception:
                logger.warning("Failed to enqueue consent cascade", exc_info=True)

    return ConsentResponse.model_validate(saved)
