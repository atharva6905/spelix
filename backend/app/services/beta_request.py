"""BetaRequestService — thin wrapper translating IntegrityError to HTTP 409."""

from sqlalchemy.exc import IntegrityError

from app.repositories.beta_request import BetaRequestRepository
from app.schemas.beta_request import BetaRequestCreate


class BetaRequestConflictError(Exception):
    """Raised when an email is already in the beta_requests queue."""


class BetaRequestService:
    def __init__(self, *, repo: BetaRequestRepository) -> None:
        self._repo = repo

    async def submit(self, payload: BetaRequestCreate):
        try:
            return await self._repo.create(
                email=payload.email,
                source=payload.source,
                consented=payload.consented_to_beta_terms,
            )
        except IntegrityError as e:
            raise BetaRequestConflictError(
                "email already in beta_requests queue"
            ) from e
