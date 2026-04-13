"""Repository for analysis_expert_reviews table operations.

FR-EXPV-04: create annotations.
FR-ADMN-07: list annotations for admin queue.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_expert_review import AnalysisExpertReview


class AnalysisExpertReviewRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, review: AnalysisExpertReview) -> AnalysisExpertReview:
        self._db.add(review)
        await self._db.flush()
        await self._db.refresh(review)
        return review

    async def list_by_analysis(self, analysis_id: uuid.UUID) -> list[AnalysisExpertReview]:
        result = await self._db.execute(
            select(AnalysisExpertReview)
            .where(AnalysisExpertReview.analysis_id == analysis_id)
            .order_by(AnalysisExpertReview.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_annotator(
        self,
        annotator_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AnalysisExpertReview]:
        result = await self._db.execute(
            select(AnalysisExpertReview)
            .where(AnalysisExpertReview.annotator_id == annotator_id)
            .order_by(AnalysisExpertReview.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_analysis(self, analysis_id: uuid.UUID) -> int:
        result = await self._db.execute(
            select(func.count(AnalysisExpertReview.id))
            .where(AnalysisExpertReview.analysis_id == analysis_id)
        )
        return result.scalar_one()

    async def latest_annotation_at(self, analysis_id: uuid.UUID):
        result = await self._db.execute(
            select(func.max(AnalysisExpertReview.created_at))
            .where(AnalysisExpertReview.analysis_id == analysis_id)
        )
        return result.scalar_one_or_none()
