"""Admin service — business logic for admin-only operations.

Requirements: FR-ADMN-01 through FR-ADMN-05
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.models.analysis import Analysis
from app.repositories.analysis import AnalysisRepository
from app.repositories.user_profile import UserProfileRepository

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        user_profile_repo: UserProfileRepository,
        redis: Any | None = None,
    ) -> None:
        self._analysis_repo = analysis_repo
        self._profile_repo = user_profile_repo
        self._redis = redis

    async def list_users(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        return await self._profile_repo.list_with_analysis_counts(
            limit=limit, offset=offset
        )

    async def delete_user_data(self, user_id: UUID) -> None:
        await self._analysis_repo.delete_by_user(user_id)
        await self._profile_repo.delete_by_user_id(user_id)

    async def list_all_analyses(
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: str | None = None,
    ) -> list[Analysis]:
        return await self._analysis_repo.list_all(
            limit=limit, offset=offset, status_filter=status_filter
        )

    async def get_health(self) -> dict[str, Any]:
        # DB connectivity
        db_ok = await self._analysis_repo.ping()

        # Redis metrics
        queue_depth = 0
        worker_heartbeat = False
        if self._redis is not None:
            try:
                # streaq stores the task queue as a Redis Stream at `streaq:{queue_name}:queues:`,
                # not a list — so we query via XLEN, not LLEN.
                queue_depth = await self._redis.xlen("streaq:spelix:queues:")
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
        return await self._analysis_repo.get_below_confidence(threshold=threshold)

    async def list_flagged_analyses(
        self, limit: int = 50, offset: int = 0
    ) -> list[Analysis]:
        """List analyses flagged for expert review (FR-ADMN-07)."""
        return await self._analysis_repo.list_flagged(limit=limit, offset=offset)

    async def get_expert_queue_stats(self) -> dict[str, Any]:
        """Aggregate stats for the admin expert queue view (FR-ADMN-07)."""
        total_flagged = await self._analysis_repo.count_flagged()
        total_annotated = await self._analysis_repo.count_annotated()
        golden_dataset_count = await self._analysis_repo.count_golden()
        return {
            "total_flagged": total_flagged,
            "total_annotated": total_annotated,
            "golden_dataset_count": golden_dataset_count,
        }
