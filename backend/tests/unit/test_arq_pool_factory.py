"""Tests for the ARQ Redis pool factory wired into the analyses router.

Regression coverage for the dormant Phase 0 bug where ``_get_service``
in ``app/api/v1/analyses.py`` constructed ``AnalysisService`` without
passing an ``arq_pool``. Combined with ``AnalysisService.start_analysis``'s
silent ``if self._arq_pool is not None`` skip, this meant every
``POST /api/v1/analyses/{id}/start`` flipped the row to
``quality_gate_pending`` AND silently no-op'd the worker enqueue, so the
worker never ran a single job in production. Discovered via Playwright
MCP E2E after PR #7 — row was finally persisted at ``quality_gate_pending``
but ``updated_at`` never moved past the moment of ``start_analysis``.

These tests verify:

- the cached factory creates an arq pool exactly once per process
  (not once per request — that would burn TCP connections to Redis)
- the cached factory falls back gracefully to ``None`` when REDIS_URL is
  missing or arq.create_pool raises (so dev/CI without Redis don't crash
  on import)
- ``_get_service`` actually passes the cached pool to ``AnalysisService``
  (not just discards it)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMakeArqPoolFactory:
    @pytest.mark.asyncio
    async def test_returns_pool_when_redis_url_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

        from app.api.v1 import analyses as analyses_mod

        # Reset the module-level cache so this test sees a fresh create_pool call.
        analyses_mod._arq_pool_cache = None
        analyses_mod._arq_pool_cache_initialized = False

        fake_pool = MagicMock(name="arq_pool")
        with patch(
            "arq.create_pool", new=AsyncMock(return_value=fake_pool)
        ) as create:
            pool = await analyses_mod._get_arq_pool()

        assert pool is fake_pool
        create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_redis_url_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("REDIS_URL", raising=False)

        from app.api.v1 import analyses as analyses_mod

        analyses_mod._arq_pool_cache = None
        analyses_mod._arq_pool_cache_initialized = False

        pool = await analyses_mod._get_arq_pool()
        assert pool is None

    @pytest.mark.asyncio
    async def test_pool_creation_failure_falls_back_to_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If arq.create_pool raises (e.g. Redis unreachable), don't crash
        the request — return None so AnalysisService.start_analysis still
        runs the DB transition (the worker will just never get the job)."""
        monkeypatch.setenv("REDIS_URL", "redis://broken:6379/0")

        from app.api.v1 import analyses as analyses_mod

        analyses_mod._arq_pool_cache = None
        analyses_mod._arq_pool_cache_initialized = False

        with patch(
            "arq.create_pool",
            new=AsyncMock(side_effect=ConnectionError("redis unreachable")),
        ):
            pool = await analyses_mod._get_arq_pool()

        assert pool is None

    @pytest.mark.asyncio
    async def test_pool_is_cached_across_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The arq pool must be created once per process. Without caching
        we'd open a new Redis connection on every POST /analyses/{id}/start
        which would exhaust the connection pool quickly."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

        from app.api.v1 import analyses as analyses_mod

        analyses_mod._arq_pool_cache = None
        analyses_mod._arq_pool_cache_initialized = False

        fake_pool = MagicMock(name="arq_pool")
        with patch(
            "arq.create_pool", new=AsyncMock(return_value=fake_pool)
        ) as create:
            p1 = await analyses_mod._get_arq_pool()
            p2 = await analyses_mod._get_arq_pool()
            p3 = await analyses_mod._get_arq_pool()

        assert create.await_count == 1
        assert p1 is fake_pool
        assert p2 is fake_pool
        assert p3 is fake_pool


class TestGetServicePassesArqPool:
    """The dependency factory must construct AnalysisService WITH the arq pool.

    Regression for the production bug where _get_service forgot to pass
    arq_pool, causing AnalysisService.start_analysis to silently skip the
    worker enqueue while still flipping the row to quality_gate_pending.
    """

    @pytest.mark.asyncio
    async def test_get_service_passes_arq_pool_to_service(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.api.v1 import analyses as analyses_mod

        # Reset both caches so the factories create fresh values.
        analyses_mod._arq_pool_cache = None
        analyses_mod._arq_pool_cache_initialized = False
        analyses_mod._async_supabase_client_cache = None
        analyses_mod._async_supabase_client_cache_initialized = False

        fake_pool = MagicMock(name="arq_pool")
        fake_db_session = AsyncMock()

        async def fake_make_storage_service():
            from app.services.storage import StorageService

            return StorageService(supabase_client=None)

        monkeypatch.setattr(
            analyses_mod, "_get_arq_pool", AsyncMock(return_value=fake_pool)
        )
        monkeypatch.setattr(
            analyses_mod, "_make_storage_service", fake_make_storage_service
        )

        service = await analyses_mod._get_service(db=fake_db_session)

        # The crucial assertion — the service must be constructed WITH the
        # arq pool, otherwise start_analysis will silently no-op the
        # worker enqueue.
        assert service._arq_pool is fake_pool
