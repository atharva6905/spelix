"""Repository for the user_profiles table — SQLAlchemy 2.0 async style."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def delete(self, id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.id == id)
        )
        profile = result.scalar_one_or_none()
        if profile is not None:
            await self.db.delete(profile)
            await self.db.flush()
