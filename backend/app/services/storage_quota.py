from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SPELIX_STORAGE_QUOTA_BYTES = 1_073_741_824  # 1 GB Supabase free tier


@dataclass(frozen=True)
class QuotaStatus:
    status: str  # "ok" | "warning" | "full"
    used_bytes: int
    quota_bytes: int
    message: str | None = None


class StorageQuotaService:
    def __init__(self, quota_bytes: int = SPELIX_STORAGE_QUOTA_BYTES):
        self._quota = quota_bytes

    async def check(self, db: AsyncSession | None = None) -> QuotaStatus:
        try:
            used = await self._get_used_bytes(db)
        except Exception:
            logger.warning("storage quota check failed — fail-open")
            return QuotaStatus(status="ok", used_bytes=0, quota_bytes=self._quota)

        ratio = used / self._quota if self._quota > 0 else 0.0

        if ratio >= 1.0:
            return QuotaStatus(
                status="full",
                used_bytes=used,
                quota_bytes=self._quota,
                message="Storage full — contact admin.",
            )
        if ratio >= 0.95:
            return QuotaStatus(
                status="warning",
                used_bytes=used,
                quota_bytes=self._quota,
                message=f"Storage at {ratio:.0%} capacity.",
            )
        return QuotaStatus(status="ok", used_bytes=used, quota_bytes=self._quota)

    async def _get_used_bytes(self, db: AsyncSession | None = None) -> int:
        if db is None:
            return 0
        row = await db.execute(
            text(
                "SELECT COALESCE(SUM((metadata->>'size')::bigint), 0) "
                "FROM storage.objects WHERE bucket_id = 'videos'"
            )
        )
        return row.scalar_one()
