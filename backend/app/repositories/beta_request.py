"""Repository for beta_requests — landing-page email-capture queue."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_request import BetaRequest


class BetaRequestRepository:
    """DB access for the beta_requests table."""

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

    async def list_all(
        self,
        *,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BetaRequest]:
        from sqlalchemy import select

        stmt = select(BetaRequest)
        if status_filter is not None:
            stmt = stmt.where(BetaRequest.status == status_filter)
        stmt = stmt.order_by(BetaRequest.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, request_id: uuid.UUID) -> BetaRequest | None:
        from sqlalchemy import select

        result = await self.db.execute(
            select(BetaRequest).where(BetaRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def approve(
        self, request_id: uuid.UUID, approved_by: uuid.UUID
    ) -> BetaRequest | None:
        from datetime import datetime, timezone

        from sqlalchemy import select

        result = await self.db.execute(
            select(BetaRequest).where(BetaRequest.id == request_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = "approved"
        row.approved_by = approved_by
        row.approved_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def reject(self, request_id: uuid.UUID) -> BetaRequest | None:
        from sqlalchemy import select

        result = await self.db.execute(
            select(BetaRequest).where(BetaRequest.id == request_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = "rejected"
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get_stats(self) -> dict[str, int]:
        from sqlalchemy import func, select

        result = await self.db.execute(
            select(BetaRequest.status, func.count().label("cnt")).group_by(
                BetaRequest.status
            )
        )
        counts: dict[str, int] = {"pending": 0, "approved": 0, "rejected": 0}
        for status, cnt in result.all():
            if status in counts:
                counts[status] = cnt
        counts["total"] = sum(counts.values())
        return counts
