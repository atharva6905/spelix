"""FastAPI router for the landing-page beta-request email capture.

Routes:
    POST /api/v1/beta/requests  — anonymous; 5/hour per IP.

Provenance: landing-page-plan §7. No SRS FR — growth/ops surface.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.rate_limit import limiter
from app.repositories.beta_request import BetaRequestRepository
from app.schemas.beta_request import BetaRequestCreate, BetaRequestResponse
from app.services.beta_request import (
    BetaRequestConflictError,
    BetaRequestService,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["beta"])


class BetaRequestCountResponse(BaseModel):
    count: int


def _get_service(db: AsyncSession = Depends(get_db)) -> BetaRequestService:
    return BetaRequestService(repo=BetaRequestRepository(db))


@router.get(
    "/count",
    response_model=BetaRequestCountResponse,
    summary="Get total beta waitlist count (public)",
)
async def get_beta_count(
    db: AsyncSession = Depends(get_db),
) -> BetaRequestCountResponse:
    repo = BetaRequestRepository(db)
    count = await repo.count_all()
    return BetaRequestCountResponse(count=count)


@router.post(
    "/requests",
    status_code=status.HTTP_201_CREATED,
    response_model=BetaRequestResponse,
    summary="Submit a private-beta access request (anonymous)",
)
@limiter.limit("5/hour")
async def submit_beta_request(
    request: Request,
    response: Response,
    body: BetaRequestCreate,
    service: BetaRequestService = Depends(_get_service),
) -> BetaRequestResponse:
    try:
        row = await service.submit(body)
    except BetaRequestConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "beta_request_duplicate",
                    "message": (
                        "This email is already in our private-beta queue. "
                        "You'll receive an invite link soon."
                    ),
                }
            },
        )
    logger.info(
        "beta_request.submitted",
        extra={"source": body.source, "email_domain": body.email.split("@")[-1]},
    )
    return BetaRequestResponse.model_validate(row)
