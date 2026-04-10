"""Repository for the user_profiles table — SQLAlchemy 2.0 async style."""
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis
from app.models.user_profile import UserProfile


class UserProfileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, profile: UserProfile) -> UserProfile:
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def get_by_user_id(self, user_id: UUID) -> UserProfile | None:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update(self, profile: UserProfile) -> UserProfile:
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def delete(self, id: UUID) -> None:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.id == id)
        )
        profile = result.scalar_one_or_none()
        if profile is not None:
            await self.db.delete(profile)
            await self.db.flush()

    async def delete_by_user_id(self, user_id: UUID) -> None:
        """Delete the user_profile row for *user_id* if it exists."""
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if profile is not None:
            await self.db.delete(profile)
            await self.db.flush()

    async def list_with_analysis_counts(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Return user profiles with their analysis count, paginated."""
        stmt = (
            select(UserProfile, func.count(Analysis.id).label("analysis_count"))
            .outerjoin(Analysis, Analysis.user_id == UserProfile.user_id)
            .group_by(UserProfile.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        return [{"profile": row[0], "analysis_count": row[1]} for row in rows]
