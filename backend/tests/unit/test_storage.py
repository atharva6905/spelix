"""Unit tests for StorageService.create_signed_read_url.

TDD gate:
- create_signed_read_url returns the signedURL value from the Supabase response
- create_signed_read_url raises RuntimeError when no client is configured
- create_signed_read_url handles alternate key name 'signedUrl' (camelCase)

Requirements: FR-RESL-02, FR-RESL-05, FR-XPRT-02
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.storage import StorageService


class TestCreateSignedReadUrl:
    """Tests for StorageService.create_signed_read_url."""

    @pytest.mark.asyncio
    async def test_returns_signed_url_from_supabase_response(self):
        """create_signed_read_url returns the URL from the Supabase signedURL key."""
        signed_url = "https://xyz.supabase.co/storage/v1/object/sign/videos/path/file.mp4?token=abc"

        mock_bucket = AsyncMock()
        mock_bucket.create_signed_url.return_value = {"signedURL": signed_url}

        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket

        mock_client = MagicMock()
        mock_client.storage = mock_storage

        service = StorageService(supabase_client=mock_client)
        result = await service.create_signed_read_url(
            "artifacts/some-id/annotated.mp4", expires_in=3600
        )

        assert result == signed_url
        mock_storage.from_.assert_called_once_with("videos")
        mock_bucket.create_signed_url.assert_called_once_with(
            "artifacts/some-id/annotated.mp4", 3600
        )

    @pytest.mark.asyncio
    async def test_handles_camel_case_signed_url_key(self):
        """create_signed_read_url also accepts 'signedUrl' (camelCase) from Supabase."""
        signed_url = "https://xyz.supabase.co/storage/v1/object/sign/videos/path/file.mp4?token=def"

        mock_bucket = AsyncMock()
        mock_bucket.create_signed_url.return_value = {"signedUrl": signed_url}

        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket

        mock_client = MagicMock()
        mock_client.storage = mock_storage

        service = StorageService(supabase_client=mock_client)
        result = await service.create_signed_read_url(
            "artifacts/some-id/plot.png", expires_in=3600
        )

        assert result == signed_url

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_no_client(self):
        """create_signed_read_url raises RuntimeError if no Supabase client is set."""
        service = StorageService(supabase_client=None)

        with pytest.raises(RuntimeError, match="StorageService has no Supabase client"):
            await service.create_signed_read_url("artifacts/some-id/report.pdf")

    @pytest.mark.asyncio
    async def test_default_expires_in_is_3600(self):
        """create_signed_read_url defaults to 3600 seconds TTL when not specified."""
        signed_url = "https://xyz.supabase.co/storage/v1/object/sign/videos/path/file.mp4?token=ghi"

        mock_bucket = AsyncMock()
        mock_bucket.create_signed_url.return_value = {"signedURL": signed_url}

        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket

        mock_client = MagicMock()
        mock_client.storage = mock_storage

        service = StorageService(supabase_client=mock_client)
        await service.create_signed_read_url("artifacts/some-id/annotated.mp4")

        mock_bucket.create_signed_url.assert_called_once_with(
            "artifacts/some-id/annotated.mp4", 3600
        )

    @pytest.mark.asyncio
    async def test_returns_raw_path_on_signing_error(self):
        """create_signed_read_url returns the raw path if Supabase raises an exception."""
        mock_bucket = AsyncMock()
        mock_bucket.create_signed_url.side_effect = Exception("network error")

        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket

        mock_client = MagicMock()
        mock_client.storage = mock_storage

        service = StorageService(supabase_client=mock_client)
        path = "artifacts/some-id/annotated.mp4"
        result = await service.create_signed_read_url(path)

        # Graceful degradation — raw path returned, no exception raised
        assert result == path
