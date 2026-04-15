"""Supabase Storage wrapper bound to the `papers` bucket (ADR-EXPERT-01).

Separate from `StorageService` (videos bucket) so the bucket name and path
convention are encoded once, and so `download_head_bytes` — the magic-byte
check helper — lives alongside the upload-URL issuer.

Requirements: FR-EXPV-02
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class SignedPaperUpload:
    url: str
    expires_at: datetime


class PaperStorageService:
    _TTL_SECONDS = 3600

    def __init__(self, *, client: Any, bucket: str = "papers") -> None:
        self._client = client
        self._bucket = bucket

    async def generate_signed_upload_url(self, storage_path: str) -> SignedPaperUpload:
        bucket = self._client.storage.from_(self._bucket)
        result = await bucket.create_signed_upload_url(storage_path)
        url: str = result.get("signed_url") or result.get("signedUrl") or result["url"]
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._TTL_SECONDS)
        return SignedPaperUpload(url=url, expires_at=expires_at)

    async def download_head_bytes(self, storage_path: str, *, n: int) -> bytes:
        """Download the full object via service-role client and slice the head.

        Supabase's download API has no range-read helper; we fetch the object
        (bounded by the 50 MB bucket cap) and slice. For a magic-byte check
        we only inspect the first 8 bytes.
        """
        bucket = self._client.storage.from_(self._bucket)
        data: bytes = await bucket.download(storage_path)
        return data[:n]

    async def delete_object(self, storage_path: str) -> None:
        bucket = self._client.storage.from_(self._bucket)
        await bucket.remove([storage_path])
