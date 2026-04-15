"""Unit tests for the FastAPI web-process streaq Worker cache.

Parallels the old test_arq_pool_factory.py — same caching contract, new type.
The key regression to guard against: AnalysisService used to silently skip
enqueue when arq_pool=None. The same skip path exists for streaq_worker=None
and must stay testable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGetStreaqWorker:
    @pytest.mark.asyncio
    async def test_returns_worker_on_first_call_and_caches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.api.v1 import analyses as analyses_mod

        analyses_mod._streaq_worker_cache = None
        analyses_mod._streaq_worker_cache_initialized = False

        # Ensure REDIS_URL is set so the factory attempts to load the worker.
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        fake_worker = MagicMock(name="streaq_worker")
        # Patch the module-level `worker` symbol in streaq_worker so that
        # analyses._get_streaq_worker's `from app.workers.streaq_worker import worker`
        # returns our fake.
        with patch("app.workers.streaq_worker.worker", new=fake_worker):
            w1 = await analyses_mod._get_streaq_worker()
            w2 = await analyses_mod._get_streaq_worker()

        assert w1 is fake_worker
        assert w2 is fake_worker  # cached

    @pytest.mark.asyncio
    async def test_returns_none_when_redis_url_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.api.v1 import analyses as analyses_mod

        analyses_mod._streaq_worker_cache = None
        analyses_mod._streaq_worker_cache_initialized = False

        monkeypatch.delenv("REDIS_URL", raising=False)
        w = await analyses_mod._get_streaq_worker()
        assert w is None


class TestGetServicePassesStreaqWorker:
    """Regression: FastAPI DI must actually pass the worker to
    AnalysisService, otherwise start_analysis silently skips enqueue.
    """

    @pytest.mark.asyncio
    async def test_get_service_passes_streaq_worker_to_service(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.api.v1 import analyses as analyses_mod

        analyses_mod._streaq_worker_cache = None
        analyses_mod._streaq_worker_cache_initialized = False

        fake_worker = MagicMock(name="streaq_worker")
        fake_db = MagicMock(name="db_session")
        fake_storage = MagicMock(name="storage_service")

        with patch.object(
            analyses_mod,
            "_get_streaq_worker",
            AsyncMock(return_value=fake_worker),
        ), patch.object(
            analyses_mod,
            "_make_storage_service",
            AsyncMock(return_value=fake_storage),
        ):
            service = await analyses_mod._get_service(db=fake_db)

        assert service._streaq_worker is fake_worker
