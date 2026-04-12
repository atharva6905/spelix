"""Repository for the consent_records table.

Append-only pattern: grants insert rows with granted=True.
Withdrawals insert NEW rows with granted=False, withdrawn_at=now().
NEVER update existing rows.

Requirements: FR-BRAIN-11, NFR-PRIV-01
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent_record import ConsentRecord


class ConsentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_user(self, user_id: uuid.UUID) -> list[ConsentRecord]:
        """Return all consent records for a user, ordered newest first."""
        result = await self.db.execute(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)
            .order_by(ConsentRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_latest_by_type(
        self, user_id: uuid.UUID, consent_type: str
    ) -> ConsentRecord | None:
        """Return the most recent consent record for a user+type combination."""
        result = await self.db.execute(
            select(ConsentRecord)
            .where(
                ConsentRecord.user_id == user_id,
                ConsentRecord.consent_type == consent_type,
            )
            .order_by(ConsentRecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self, record: ConsentRecord) -> ConsentRecord:
        """Insert a new consent record. Append-only — never call update."""
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record
