"""Repository for the rep_metrics table — SQLAlchemy 2.0 async style."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rep_metric import RepMetric


class RepMetricRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_batch(self, metrics: list[RepMetric]) -> list[RepMetric]:
        for metric in metrics:
            self.db.add(metric)
        await self.db.flush()
        for metric in metrics:
            await self.db.refresh(metric)
        return metrics

    async def get_by_analysis(self, analysis_id: UUID) -> list[RepMetric]:
        result = await self.db.execute(
            select(RepMetric)
            .where(RepMetric.analysis_id == analysis_id)
            .order_by(RepMetric.rep_index)
        )
        return list(result.scalars().all())
