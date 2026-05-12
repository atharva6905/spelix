"""Repository for beta_requests — landing-page email-capture queue."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_request import BetaRequest


class BetaRequestRepository:
    """DB access for the beta_requests table.

    Scope: INSERT only for the public endpoint. Admin approval endpoints
    (separate PR) will add UPDATE queries for approvals and invites.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, *, email: str, source: str, consented: bool
    ) -> BetaRequest:
        row = BetaRequest(
            email=email,
            source=source,
            consented_to_beta_terms=consented,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def count_all(self) -> int:
        from sqlalchemy import func, select

        result = await self.db.execute(select(func.count(BetaRequest.id)))
        return result.scalar_one()
