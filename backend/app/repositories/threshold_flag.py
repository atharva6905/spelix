"""Repository for the threshold_flags table (FR-EXPV-08).

All DB access for Expert Reviewer threshold proposals passes through this
class. The API layer uses create + list_by_reviewer; admin triage uses
list_all + update_status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.threshold_flag import ThresholdFlag


class ThresholdFlagRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, flag: ThresholdFlag) -> ThresholdFlag:
        self._db.add(flag)
        await self._db.flush()
        await self._db.refresh(flag)
        return flag

    async def get_by_id(self, flag_id: UUID) -> ThresholdFlag | None:
        result = await self._db.execute(
            select(ThresholdFlag).where(ThresholdFlag.id == flag_id)
        )
        return result.scalar_one_or_none()

    async def list_by_reviewer(
        self, reviewer_id: UUID, *, limit: int, offset: int
    ) -> list[ThresholdFlag]:
        stmt = (
            select(ThresholdFlag)
            .where(ThresholdFlag.reviewer_id == reviewer_id)
            .order_by(ThresholdFlag.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_all(
        self, *, status: str | None, limit: int, offset: int
    ) -> list[ThresholdFlag]:
        stmt = select(ThresholdFlag)
        if status is not None:
            stmt = stmt.where(ThresholdFlag.status == status)
        stmt = (
            stmt.order_by(ThresholdFlag.created_at.desc()).limit(limit).offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        flag_id: UUID,
        *,
        status: str,
        resolution_note: str | None,
        resolved_by: UUID,
    ) -> ThresholdFlag | None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(ThresholdFlag)
            .where(ThresholdFlag.id == flag_id)
            .values(
                status=status,
                resolution_note=resolution_note,
                resolved_by=resolved_by,
                resolved_at=now,
                updated_at=now,
            )
            .returning(ThresholdFlag)
        )
        result = await self._db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            await self._db.flush()
        return row
