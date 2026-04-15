from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.paper_storage import PaperStorageService, SignedPaperUpload


@pytest.fixture()
def mock_supabase():
    client = MagicMock()
    storage = MagicMock()
    bucket = MagicMock()
    client.storage = storage
    storage.from_ = MagicMock(return_value=bucket)
    return client, bucket


class TestGenerateSignedUploadUrl:
    @pytest.mark.asyncio
    async def test_builds_correct_path_and_returns_url(self, mock_supabase):
        client, bucket = mock_supabase
        bucket.create_signed_upload_url = AsyncMock(
            return_value={"signed_url": "https://x.supabase.co/upload/tok", "token": "tok"}
        )

        svc = PaperStorageService(client=client, bucket="papers")
        result = await svc.generate_signed_upload_url("papers/abc/paper.pdf")

        assert isinstance(result, SignedPaperUpload)
        assert result.url == "https://x.supabase.co/upload/tok"
        assert result.expires_at > datetime.now(timezone.utc)
        bucket.create_signed_upload_url.assert_awaited_once_with("papers/abc/paper.pdf")

    @pytest.mark.asyncio
    async def test_handles_camelcase_response_key(self, mock_supabase):
        """Supabase client may return either 'signed_url' or 'signedUrl' depending on version."""
        client, bucket = mock_supabase
        bucket.create_signed_upload_url = AsyncMock(
            return_value={"signedUrl": "https://x.supabase.co/upload/tok2"}
        )

        svc = PaperStorageService(client=client, bucket="papers")
        result = await svc.generate_signed_upload_url("papers/abc/paper.pdf")

        assert result.url == "https://x.supabase.co/upload/tok2"


class TestDownloadHeadBytes:
    @pytest.mark.asyncio
    async def test_returns_first_n_bytes(self, mock_supabase):
        client, bucket = mock_supabase
        bucket.download = AsyncMock(return_value=b"%PDF-1.4\nrest of file...")

        svc = PaperStorageService(client=client, bucket="papers")
        head = await svc.download_head_bytes("papers/abc/paper.pdf", n=8)

        assert head == b"%PDF-1.4"
        bucket.download.assert_awaited_once_with("papers/abc/paper.pdf")

    @pytest.mark.asyncio
    async def test_shorter_file_returns_what_exists(self, mock_supabase):
        client, bucket = mock_supabase
        bucket.download = AsyncMock(return_value=b"%PDF")

        svc = PaperStorageService(client=client, bucket="papers")
        head = await svc.download_head_bytes("papers/abc/paper.pdf", n=8)

        assert head == b"%PDF"


class TestDeleteObject:
    @pytest.mark.asyncio
    async def test_calls_remove(self, mock_supabase):
        client, bucket = mock_supabase
        bucket.remove = AsyncMock(return_value=[{"name": "papers/abc/paper.pdf"}])

        svc = PaperStorageService(client=client, bucket="papers")
        await svc.delete_object("papers/abc/paper.pdf")

        bucket.remove.assert_awaited_once_with(["papers/abc/paper.pdf"])
