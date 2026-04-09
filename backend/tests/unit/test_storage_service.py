"""Unit tests for StorageService — signed upload URL + delete.

Covers lines 74-89, 105-111 in storage.py.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.storage import StorageService, get_storage_path


class TestStorageService:
    @pytest.mark.asyncio
    async def test_generate_signed_upload_url_returns_url_and_expiry(self) -> None:
        mock_client = MagicMock()
        mock_bucket = AsyncMock()
        mock_bucket.create_signed_upload_url = AsyncMock(
            return_value={"signed_url": "https://storage.example.com/upload?token=abc"}
        )
        mock_client.storage.from_ = MagicMock(return_value=mock_bucket)

        svc = StorageService(supabase_client=mock_client, bucket="test-bucket")
        analysis_id = uuid.uuid4()
        result = await svc.generate_signed_upload_url(analysis_id, "squat.mp4")

        assert result["url"] == "https://storage.example.com/upload?token=abc"
        assert result["expires_at"] is not None
        mock_bucket.create_signed_upload_url.assert_called_once_with(
            f"videos/{analysis_id}/squat.mp4"
        )

    @pytest.mark.asyncio
    async def test_generate_signed_upload_url_signedUrl_key(self) -> None:
        """Handles Supabase SDK response with signedUrl key."""
        mock_client = MagicMock()
        mock_bucket = AsyncMock()
        mock_bucket.create_signed_upload_url = AsyncMock(
            return_value={"signedUrl": "https://example.com/signed"}
        )
        mock_client.storage.from_ = MagicMock(return_value=mock_bucket)

        svc = StorageService(supabase_client=mock_client)
        result = await svc.generate_signed_upload_url(uuid.uuid4(), "test.mp4")
        assert result["url"] == "https://example.com/signed"

    @pytest.mark.asyncio
    async def test_generate_signed_upload_url_raises_without_client(self) -> None:
        svc = StorageService(supabase_client=None)
        with pytest.raises(RuntimeError, match="no Supabase client"):
            await svc.generate_signed_upload_url(uuid.uuid4(), "test.mp4")

    @pytest.mark.asyncio
    async def test_delete_file_calls_storage_remove(self) -> None:
        mock_client = MagicMock()
        mock_bucket = AsyncMock()
        mock_bucket.remove = AsyncMock()
        mock_client.storage.from_ = MagicMock(return_value=mock_bucket)

        svc = StorageService(supabase_client=mock_client, bucket="videos")
        await svc.delete_file("videos/abc/squat.mp4")

        mock_bucket.remove.assert_called_once_with(["videos/abc/squat.mp4"])

    @pytest.mark.asyncio
    async def test_delete_file_raises_without_client(self) -> None:
        svc = StorageService(supabase_client=None)
        with pytest.raises(RuntimeError, match="no Supabase client"):
            await svc.delete_file("videos/abc/squat.mp4")


class TestGetStoragePath:
    def test_returns_canonical_path(self) -> None:
        aid = uuid.uuid4()
        assert get_storage_path(aid, "test.mp4") == f"videos/{aid}/test.mp4"
