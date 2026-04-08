"""Repository for the coaching_results table — SQLAlchemy 2.0 async style."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coaching_result import CoachingResult


class CoachingResultRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, result: CoachingResult) -> CoachingResult:
        self.db.add(result)
        await self.db.flush()
        await self.db.refresh(result)
        return result

    async def get_by_analysis(self, analysis_id: UUID) -> CoachingResult | None:
        result = await self.db.execute(
            select(CoachingResult).where(CoachingResult.analysis_id == analysis_id)
        )
        return result.scalar_one_or_none()
