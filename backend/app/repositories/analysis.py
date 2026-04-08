"""Repository for the analyses table — SQLAlchemy 2.0 async style."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analysis import Analysis


class AnalysisRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, analysis: Analysis) -> Analysis:
        self.db.add(analysis)
        await self.db.flush()
        await self.db.refresh(analysis)
        return analysis

    async def get_by_id(self, id: UUID) -> Analysis | None:
        result = await self.db.execute(
            select(Analysis).where(Analysis.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(
        self, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[Analysis]:
        result = await self.db.execute(
            select(Analysis)
            .where(Analysis.user_id == user_id)
            .order_by(Analysis.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_status(self, id: UUID, status: str) -> Analysis:
        """Update status with row-level lock to prevent concurrent transitions."""
        result = await self.db.execute(
            select(Analysis)
            .where(Analysis.id == id)
            .with_for_update()
        )
        analysis = result.scalar_one()
        analysis.status = status
        await self.db.flush()
        await self.db.refresh(analysis)
        return analysis

    async def update(self, analysis: Analysis) -> Analysis:
        await self.db.flush()
        await self.db.refresh(analysis)
        return analysis

    async def get_by_id_with_relations(self, id: UUID) -> Analysis | None:
        """Fetch an analysis with rep_metrics and coaching_result eagerly loaded."""
        result = await self.db.execute(
            select(Analysis)
            .where(Analysis.id == id)
            .options(
                selectinload(Analysis.rep_metrics),
                selectinload(Analysis.coaching_result),
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, id: UUID) -> None:
        result = await self.db.execute(
            select(Analysis).where(Analysis.id == id)
        )
        analysis = result.scalar_one_or_none()
        if analysis is not None:
            await self.db.delete(analysis)
            await self.db.flush()
