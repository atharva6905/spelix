"""Repository for the analyses table — SQLAlchemy 2.0 async style."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select, text
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

    # ------------------------------------------------------------------
    # Insights queries
    # ------------------------------------------------------------------

    async def get_recent_for_exercise(
        self,
        user_id: UUID,
        exercise_type: str,
        exercise_variant: str,
        limit: int = 7,
    ) -> list[Analysis]:
        """Return up to *limit* most-recent completed analyses for a user+exercise."""
        result = await self.db.execute(
            select(Analysis)
            .where(
                and_(
                    Analysis.user_id == user_id,
                    Analysis.exercise_type == exercise_type,
                    Analysis.exercise_variant == exercise_variant,
                    Analysis.status == "completed",
                )
            )
            .order_by(Analysis.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_personal_best_confidence(
        self,
        user_id: UUID,
        exercise_type: str,
        exercise_variant: str,
    ) -> float:
        """Return the maximum confidence_score for a user+exercise combination."""
        result = await self.db.execute(
            select(func.max(Analysis.confidence_score))
            .where(
                and_(
                    Analysis.user_id == user_id,
                    Analysis.exercise_type == exercise_type,
                    Analysis.exercise_variant == exercise_variant,
                    Analysis.status == "completed",
                    Analysis.confidence_score.isnot(None),
                )
            )
        )
        return float(result.scalar() or 0.0)

    async def get_completed_since(
        self,
        user_id: UUID,
        since: datetime,
    ) -> list[Analysis]:
        """Return all completed analyses for a user created on or after *since*."""
        result = await self.db.execute(
            select(Analysis)
            .where(
                and_(
                    Analysis.user_id == user_id,
                    Analysis.status == "completed",
                    Analysis.created_at >= since,
                )
            )
            .order_by(Analysis.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Admin queries
    # ------------------------------------------------------------------

    async def list_all(
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: str | None = None,
    ) -> list[Analysis]:
        """Return all analyses ordered by created_at desc, with optional status filter."""
        stmt = select(Analysis).order_by(Analysis.created_at.desc())
        if status_filter is not None:
            stmt = stmt.where(Analysis.status == status_filter)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_below_confidence(self, threshold: float) -> list[Analysis]:
        """Return analyses whose confidence_score is below *threshold*, ordered asc."""
        result = await self.db.execute(
            select(Analysis)
            .where(Analysis.confidence_score < threshold)
            .where(Analysis.confidence_score.isnot(None))
            .order_by(Analysis.confidence_score.asc())
        )
        return list(result.scalars().all())

    async def delete_by_user(self, user_id: UUID) -> None:
        """Delete all analyses belonging to *user_id* (cascades to related rows)."""
        result = await self.db.execute(
            select(Analysis).where(Analysis.user_id == user_id)
        )
        for analysis in result.scalars().all():
            await self.db.delete(analysis)
        await self.db.flush()

    async def ping(self) -> bool:
        """Return True if the DB connection is healthy."""
        try:
            await self.db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def list_flagged(
        self, limit: int = 50, offset: int = 0
    ) -> list[Analysis]:
        """List analyses flagged for expert review (FR-ADMN-07)."""
        result = await self.db.execute(
            select(Analysis)
            .where(Analysis.flagged_for_review == True)  # noqa: E712
            .order_by(Analysis.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_flagged(self) -> int:
        result = await self.db.execute(
            select(func.count(Analysis.id)).where(Analysis.flagged_for_review == True)  # noqa: E712
        )
        return result.scalar_one()

    async def count_annotated(self) -> int:
        """Count analyses that have at least one expert annotation."""
        from app.models.analysis_expert_review import AnalysisExpertReview

        subq = select(AnalysisExpertReview.analysis_id).distinct().subquery()
        result = await self.db.execute(
            select(func.count()).select_from(subq)
        )
        return result.scalar_one()

    async def count_golden(self) -> int:
        result = await self.db.execute(
            select(func.count(Analysis.id)).where(Analysis.is_golden_dataset == True)  # noqa: E712
        )
        return result.scalar_one()
