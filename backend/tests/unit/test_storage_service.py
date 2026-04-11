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
    """Verify the production _make_storage_service factory wires up a real
    *async* Supabase client.

    Regression test for the **two-layer** dormant Phase 0 bug:

    * Layer 1 (PR #3): the if-branch contained only ``pass``, so the factory
      returned ``StorageService(supabase_client=None)`` even when env vars
      were set, raising RuntimeError on every production POST /analyses.
    * Layer 2 (this PR): PR #3 fixed Layer 1 by calling
      ``supabase.create_client``, but that returns a *sync* ``Client``.
      ``StorageService.generate_signed_upload_url`` does
      ``await self._client.storage.from_(...).create_signed_upload_url(...)``
      — on a sync client that method returns a ``dict``, and ``await dict``
      raises ``TypeError: object dict can't be used in 'await' expression``.

    The fix: use ``supabase.acreate_client`` (async). These tests assert the
    async client is wired up, so neither layer can return.
    """

    @pytest.mark.asyncio
    async def test_returns_service_with_async_client_when_env_vars_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
        # Reset module-level cache so this test sees a fresh acreate_client call.
        from app.api.v1 import analyses as analyses_mod

        analyses_mod._async_supabase_client_cache = None
        analyses_mod._async_supabase_client_cache_initialized = False

        fake_client = MagicMock(name="async_supabase_client")
        with patch(
            "supabase.acreate_client", new=AsyncMock(return_value=fake_client)
        ) as create:
            svc = await _make_storage_service()

        assert isinstance(svc, StorageService)
        # Crucial: the underlying client must NOT be None and must be the
        # async client (not the sync one).
        assert svc._client is fake_client
        create.assert_called_once_with(
            "https://example.supabase.co", "service-role-key"
        )

    @pytest.mark.asyncio
    async def test_returns_service_without_client_when_env_vars_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
        from app.api.v1 import analyses as analyses_mod

        analyses_mod._async_supabase_client_cache = None
        analyses_mod._async_supabase_client_cache_initialized = False

        svc = await _make_storage_service()

        assert isinstance(svc, StorageService)
        assert svc._client is None

    @pytest.mark.asyncio
    async def test_client_creation_failure_falls_back_to_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If acreate_client raises (e.g. bad URL), don't crash the request."""
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
        from app.api.v1 import analyses as analyses_mod

        analyses_mod._async_supabase_client_cache = None
        analyses_mod._async_supabase_client_cache_initialized = False

        with patch(
            "supabase.acreate_client",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            svc = await _make_storage_service()

        assert isinstance(svc, StorageService)
        assert svc._client is None

    @pytest.mark.asyncio
    async def test_client_is_cached_across_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The async client is created once and reused across requests.

        Without caching we'd open a new HTTPS connection on every request,
        which would noticeably slow down POST /analyses and waste resources.
        """
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
        from app.api.v1 import analyses as analyses_mod

        analyses_mod._async_supabase_client_cache = None
        analyses_mod._async_supabase_client_cache_initialized = False

        fake_client = MagicMock(name="async_supabase_client")
        with patch(
            "supabase.acreate_client", new=AsyncMock(return_value=fake_client)
        ) as create:
            svc1 = await _make_storage_service()
            svc2 = await _make_storage_service()
            svc3 = await _make_storage_service()

        # acreate_client must only have been called once even across 3 requests.
        assert create.call_count == 1
        assert svc1._client is fake_client
        assert svc2._client is fake_client
        assert svc3._client is fake_client


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
