"""Admin service — business logic for admin-only operations.

Requirements: FR-ADMN-01 through FR-ADMN-05
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis
from app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(
        self,
        db: AsyncSession,
        redis: Any | None = None,
    ) -> None:
        self._db = db
        self._redis = redis

    async def list_users(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        stmt = (
            select(UserProfile, func.count(Analysis.id).label("analysis_count"))
            .outerjoin(Analysis, Analysis.user_id == UserProfile.user_id)
            .group_by(UserProfile.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        rows = result.all()
        return [{"profile": row[0], "analysis_count": row[1]} for row in rows]

    async def delete_user_data(self, user_id: UUID) -> None:
        # Delete analyses (cascades to rep_metrics + coaching_results)
        analyses_result = await self._db.execute(
            select(Analysis).where(Analysis.user_id == user_id)
        )
        for analysis in analyses_result.scalars().all():
            await self._db.delete(analysis)

        # Delete user profile
        profile_result = await self._db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile is not None:
            await self._db.delete(profile)

        await self._db.flush()

    async def list_all_analyses(
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: str | None = None,
    ) -> list[Analysis]:
        stmt = select(Analysis).order_by(Analysis.created_at.desc())
        if status_filter is not None:
            stmt = stmt.where(Analysis.status == status_filter)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_health(self) -> dict[str, Any]:
        # DB connectivity
        db_ok = True
        try:
            await self._db.execute(text("SELECT 1"))
        except Exception:
            db_ok = False

        # Redis metrics
        queue_depth = 0
        worker_heartbeat = False
        if self._redis is not None:
            try:
                queue_depth = await self._redis.llen("arq:queue")
            except Exception:
                pass
            try:
                hb = await self._redis.get("spelix:worker:heartbeat")
                worker_heartbeat = hb is not None
            except Exception:
                pass

        return {
            "queue_depth": queue_depth,
            "worker_heartbeat": worker_heartbeat,
            "db_ok": db_ok,
        }

    async def confidence_audit(
        self, threshold: float = 0.50
    ) -> list[Analysis]:
        stmt = (
            select(Analysis)
            .where(Analysis.confidence_score < threshold)
            .where(Analysis.confidence_score.isnot(None))
            .order_by(Analysis.confidence_score.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
