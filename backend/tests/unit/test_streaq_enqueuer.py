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
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        fake_worker = MagicMock(name="streaq_worker")
        # Use a sys.modules shim with a call counter so we can prove the
        # lazy import executes exactly once across N calls.
        import sys

        class _ProbeModule:
            access_count = 0

            def __getattr__(self, name: str) -> object:
                type(self).access_count += 1
                if name == "worker":
                    return fake_worker
                raise AttributeError(name)

        probe = _ProbeModule()
        monkeypatch.setitem(sys.modules, "app.workers.streaq_worker", probe)

        w1 = await analyses_mod._get_streaq_worker()
        # Capture import-machinery access count after first call (includes
        # __spec__ and __path__ probes from Python's import system in addition
        # to "worker" itself — typically 3 total, but may vary).
        count_after_first = type(probe).access_count
        assert count_after_first >= 1, "expected at least one attribute access on first call"

        w2 = await analyses_mod._get_streaq_worker()
        w3 = await analyses_mod._get_streaq_worker()

        assert w1 is w2 is w3 is fake_worker
        assert type(probe).access_count == count_after_first, (
            "cache should not trigger additional attribute accesses after first call; "
            f"got {type(probe).access_count - count_after_first} extra access(es)"
        )

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

    @pytest.mark.asyncio
    async def test_returns_none_when_worker_import_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: if the lazy `from app.workers.streaq_worker import worker`
        inside `_get_streaq_worker` raises, the factory must swallow it and
        return None (matching the old ARQ pool's silent-fail contract). The
        API request path then treats None as 'enqueue disabled' instead of
        crashing the request.
        """
        from app.api.v1 import analyses as analyses_mod

        analyses_mod._streaq_worker_cache = None
        analyses_mod._streaq_worker_cache_initialized = False

        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        # Force the lazy import statement itself to raise by shadowing the
        # streaq_worker module with something that explodes on attribute access.
        import sys

        class _BrokenModule:
            def __getattr__(self, name: str) -> object:
                raise ImportError(f"simulated failure on {name}")

        monkeypatch.setitem(sys.modules, "app.workers.streaq_worker", _BrokenModule())

        w = await analyses_mod._get_streaq_worker()
        assert w is None
        # Cache should still be flagged initialized so subsequent calls don't retry.
        assert analyses_mod._streaq_worker_cache_initialized is True


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
