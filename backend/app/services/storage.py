"""Supabase Storage service — signed upload URL generation.

Generates TUS signed upload URLs via the Supabase Storage API.
Video path convention: videos/{analysis_id}/{filename}

Mock-friendly: StorageService takes a supabase client at construction time;
tests pass a mock. In production, the client is created from env vars.

Requirements: FR-UPLD-07 (TUS signed URL, 1h TTL)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict
from uuid import UUID


class SignedUploadResult(TypedDict):
    url: str
    expires_at: datetime


class StorageService:
    """Wraps Supabase Storage signed upload URL creation.

    Parameters
    ----------
    supabase_client:
        An initialised ``supabase.AsyncClient`` (or compatible mock).
        If ``None``, the service is constructed but ``generate_signed_upload_url``
        will raise ``RuntimeError`` unless a mock is injected (test mode).
    bucket:
        Storage bucket name.  Defaults to ``SUPABASE_STORAGE_BUCKET`` env var,
        falling back to ``"videos"``.
    """

    _TTL_SECONDS = 3600  # 1 hour

    def __init__(
        self,
        supabase_client: Any | None = None,
        bucket: str | None = None,
    ) -> None:
        self._client = supabase_client
        self._bucket = bucket or os.environ.get("SUPABASE_STORAGE_BUCKET", "videos")

    async def generate_signed_upload_url(
        self,
        analysis_id: UUID,
        filename: str,
    ) -> SignedUploadResult:
        """Create a Supabase Storage signed TUS upload URL.

        Parameters
        ----------
        analysis_id:
            UUID of the analysis row — used to build the storage path.
        filename:
            Original filename supplied by the client (e.g. ``squat.mp4``).

        Returns
        -------
        SignedUploadResult
            ``url`` — the signed upload URL to hand back to the browser.
            ``expires_at`` — UTC datetime when the URL expires (now + 1h).

        Raises
        ------
        RuntimeError
            If no Supabase client has been configured.
        """
        if self._client is None:
            raise RuntimeError(
                "StorageService has no Supabase client. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables."
            )

        path = f"videos/{analysis_id}/{filename}"

        result = await self._client.storage.from_(self._bucket).create_signed_upload_url(path)

        # result is a dict: {"signed_url": str, "signedUrl": str, "token": str, "path": str}
        signed_url: str = result.get("signed_url") or result.get("signedUrl") or result["url"]

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._TTL_SECONDS)

        return SignedUploadResult(url=signed_url, expires_at=expires_at)


    async def delete_file(self, path: str) -> None:
        """Delete a file from Supabase Storage.

        Parameters
        ----------
        path:
            Storage path to delete (e.g. ``videos/{analysis_id}/{filename}``).

        Raises
        ------
        RuntimeError
            If no Supabase client has been configured.
        """
        if self._client is None:
            raise RuntimeError(
                "StorageService has no Supabase client. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables."
            )

        await self._client.storage.from_(self._bucket).remove([path])


def get_storage_path(analysis_id: UUID, filename: str) -> str:
    """Return the canonical Storage path for an analysis video.

    ``videos/{analysis_id}/{filename}``
    """
    return f"videos/{analysis_id}/{filename}"
