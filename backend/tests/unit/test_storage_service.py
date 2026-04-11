"""Unit tests for StorageService — signed upload URL + delete.

Covers lines 74-89, 105-111 in storage.py.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.analyses import _make_storage_service
from app.services.storage import StorageService, get_storage_path


class TestMakeStorageServiceFactory:
    """Verify the production _make_storage_service factory wires up a real client.

    Regression test for the dormant Phase 0 bug where the if-branch contained
    only `pass`, returning an empty StorageService(supabase_client=None) in
    production. Every prior test mocked _get_service entirely, so this code
    path was never exercised. Result: POST /analyses raised RuntimeError on
    every production request, surfacing as a misleading CORS error in browsers.
    """

    def test_returns_service_with_client_when_env_vars_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")

        fake_client = MagicMock(name="supabase_client")
        with patch("supabase.create_client", return_value=fake_client) as create:
            svc = _make_storage_service()

        assert isinstance(svc, StorageService)
        # The crucial assertion: the underlying client must NOT be None.
        # If this fails, generate_signed_upload_url will raise RuntimeError
        # in production and break uploads.
        assert svc._client is fake_client
        create.assert_called_once_with(
            "https://example.supabase.co", "service-role-key"
        )

    def test_returns_service_without_client_when_env_vars_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

        svc = _make_storage_service()

        assert isinstance(svc, StorageService)
        assert svc._client is None

    def test_client_creation_failure_falls_back_to_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If supabase.create_client raises (e.g. bad URL), don't crash startup."""
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")

        with patch("supabase.create_client", side_effect=RuntimeError("boom")):
            svc = _make_storage_service()

        assert isinstance(svc, StorageService)
        assert svc._client is None


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
