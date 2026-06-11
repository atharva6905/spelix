"""Tests for QdrantClientWrapper and get_qdrant_client factory.

TDD gate for P2-002 (FR-AICP-09, ADR-BRAIN-01, ADR-RAG-03, ADR-P2-001).

Covers:
- ADR-032: real factory exercised with qdrant_client.AsyncQdrantClient patched
  at its source, not at the consumer
- ensure_collections() idempotency: creates on first call, no-ops on second
- ping() returns True on success, False on exception
- upsert_points() and query_points() are thin async passthroughs
- Factory caches the instance (second call returns same object)
- Factory falls back gracefully when QDRANT_URL is missing
- Nightly cron ping_qdrant_health: calls client.ping(), logs on failure but
  never raises
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_factory() -> None:
    """Reset the module-level factory cache so each test starts clean."""
    from app.services import qdrant as qdrant_mod

    qdrant_mod._qdrant_client_cache = None
    qdrant_mod._qdrant_client_cache_initialized = False


# ---------------------------------------------------------------------------
# Factory tests (ADR-032 pattern: patch at source, not consumer)
# ---------------------------------------------------------------------------


class TestGetQdrantClientFactory:
    """Factory must wire URL + API key through correctly and cache."""

    @pytest.mark.asyncio
    async def test_factory_passes_url_and_api_key_to_async_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ADR-032 regression: exercise the REAL factory with AsyncQdrantClient
        patched at its source (qdrant_client.AsyncQdrantClient)."""
        monkeypatch.setenv("QDRANT_URL", "https://test.qdrant.example.com:6333")
        monkeypatch.setenv("QDRANT_API_KEY", "test-api-key-secret")
        _reset_factory()

        fake_inner = MagicMock(name="AsyncQdrantClient_instance")

        with patch(
            "qdrant_client.AsyncQdrantClient", return_value=fake_inner
        ) as mock_cls:
            from app.services.qdrant import get_qdrant_client

            wrapper = await get_qdrant_client()

        mock_cls.assert_called_once_with(
            url="https://test.qdrant.example.com:6333",
            api_key="test-api-key-secret",
        )
        assert wrapper._client is fake_inner

    @pytest.mark.asyncio
    async def test_factory_returns_cached_instance_on_repeat_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Factory must create exactly one instance per process (ADR-032 pattern)."""
        monkeypatch.setenv("QDRANT_URL", "https://test.qdrant.example.com:6333")
        monkeypatch.setenv("QDRANT_API_KEY", "test-key")
        _reset_factory()

        fake_inner = MagicMock(name="AsyncQdrantClient_instance")

        with patch(
            "qdrant_client.AsyncQdrantClient", return_value=fake_inner
        ) as mock_cls:
            from app.services.qdrant import get_qdrant_client

            w1 = await get_qdrant_client()
            w2 = await get_qdrant_client()
            w3 = await get_qdrant_client()

        assert mock_cls.call_count == 1
        assert w1 is w2 is w3

    @pytest.mark.asyncio
    async def test_factory_returns_none_when_qdrant_url_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing QDRANT_URL → factory returns None, does not crash."""
        monkeypatch.delenv("QDRANT_URL", raising=False)
        monkeypatch.delenv("QDRANT_API_KEY", raising=False)
        _reset_factory()

        from app.services.qdrant import get_qdrant_client

        result = await get_qdrant_client()
        assert result is None

    @pytest.mark.asyncio
    async def test_factory_returns_none_on_client_construction_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If AsyncQdrantClient raises (e.g. bad URL), factory returns None."""
        monkeypatch.setenv("QDRANT_URL", "https://broken.example.com")
        monkeypatch.setenv("QDRANT_API_KEY", "key")
        _reset_factory()

        with patch(
            "qdrant_client.AsyncQdrantClient",
            side_effect=ValueError("bad url"),
        ):
            from app.services.qdrant import get_qdrant_client

            result = await get_qdrant_client()

        assert result is None


# ---------------------------------------------------------------------------
# ensure_collections() idempotency
# ---------------------------------------------------------------------------


class TestEnsureCollections:
    """ensure_collections() must be idempotent: create on empty, no-op on exist."""

    def _make_wrapper(self) -> object:
        """Return a QdrantClientWrapper with a fully mocked inner client."""
        from app.services.qdrant import QdrantClientWrapper

        mock_inner = AsyncMock()
        wrapper = QdrantClientWrapper.__new__(QdrantClientWrapper)
        wrapper._client = mock_inner
        return wrapper

    @pytest.mark.asyncio
    async def test_creates_both_collections_when_neither_exists(self) -> None:
        wrapper = self._make_wrapper()
        # Neither collection exists yet
        wrapper._client.collection_exists = AsyncMock(return_value=False)
        wrapper._client.create_collection = AsyncMock(return_value=True)
        wrapper._client.create_payload_index = AsyncMock()

        await wrapper.ensure_collections()

        # Both collections should be created
        assert wrapper._client.create_collection.call_count == 2
        calls = {
            c.kwargs["collection_name"]
            for c in wrapper._client.create_collection.call_args_list
        }
        assert calls == {"papers_rag", "coach_brain"}

    @pytest.mark.asyncio
    async def test_no_op_when_both_collections_already_exist(self) -> None:
        wrapper = self._make_wrapper()
        wrapper._client.collection_exists = AsyncMock(return_value=True)
        wrapper._client.create_collection = AsyncMock()
        wrapper._client.create_payload_index = AsyncMock()

        await wrapper.ensure_collections()

        wrapper._client.create_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_only_missing_collection(self) -> None:
        """If papers_rag exists but coach_brain does not, only coach_brain is created."""
        wrapper = self._make_wrapper()

        async def _exists(collection_name: str) -> bool:
            return collection_name == "papers_rag"

        wrapper._client.collection_exists = _exists  # type: ignore[assignment]
        wrapper._client.create_collection = AsyncMock(return_value=True)
        wrapper._client.create_payload_index = AsyncMock()

        await wrapper.ensure_collections()

        assert wrapper._client.create_collection.call_count == 1
        assert (
            wrapper._client.create_collection.call_args.kwargs["collection_name"]
            == "coach_brain"
        )

    @pytest.mark.asyncio
    async def test_coach_brain_gets_payload_indexes(self) -> None:
        """coach_brain must have keyword indexes on 'exercise' and 'status'."""
        wrapper = self._make_wrapper()
        wrapper._client.collection_exists = AsyncMock(return_value=False)
        wrapper._client.create_collection = AsyncMock(return_value=True)
        wrapper._client.create_payload_index = AsyncMock()

        await wrapper.ensure_collections()

        indexed_fields = {
            c.kwargs.get("field_name") or c.args[1]
            for c in wrapper._client.create_payload_index.call_args_list
        }
        assert "exercise" in indexed_fields
        assert "status" in indexed_fields

    @pytest.mark.asyncio
    async def test_vector_size_is_1024(self) -> None:
        """Both collections must be created with 1024-dim vectors (ADR-RAG-03)."""
        from qdrant_client.models import VectorParams

        wrapper = self._make_wrapper()
        wrapper._client.collection_exists = AsyncMock(return_value=False)
        wrapper._client.create_collection = AsyncMock(return_value=True)
        wrapper._client.create_payload_index = AsyncMock()

        await wrapper.ensure_collections()

        for call in wrapper._client.create_collection.call_args_list:
            vectors_config = call.kwargs.get("vectors_config")
            assert isinstance(vectors_config, VectorParams), (
                f"Expected VectorParams, got {type(vectors_config)}"
            )
            assert vectors_config.size == 1024, (
                f"Expected size=1024, got {vectors_config.size}"
            )

    @pytest.mark.asyncio
    async def test_sparse_vector_named_bm25_with_idf_modifier(self) -> None:
        """Both collections must have a sparse vector named 'bm25' with IDF modifier
        (ADR-BRAIN-03: server-side BM25 via Qdrant sparse vectors)."""
        from qdrant_client.models import Modifier, SparseVectorParams

        wrapper = self._make_wrapper()
        wrapper._client.collection_exists = AsyncMock(return_value=False)
        wrapper._client.create_collection = AsyncMock(return_value=True)
        wrapper._client.create_payload_index = AsyncMock()

        await wrapper.ensure_collections()

        for call in wrapper._client.create_collection.call_args_list:
            sparse_config = call.kwargs.get("sparse_vectors_config")
            assert sparse_config is not None, "sparse_vectors_config must be set"
            assert "bm25" in sparse_config, "Sparse vector must be named 'bm25'"
            bm25_params = sparse_config["bm25"]
            assert isinstance(bm25_params, SparseVectorParams)
            assert bm25_params.modifier == Modifier.IDF

    @pytest.mark.asyncio
    async def test_ensure_collections_creates_exercise_index_on_papers_rag(
        self,
    ) -> None:
        """B1 regression: papers_rag must get a keyword payload index on `exercise`
        so that retrieve_papers's exercise_filter does not raise 400 under Qdrant
        strict mode (FR-AICP-15 / ADR-BRAIN-03).
        """
        from qdrant_client.http.models import PayloadSchemaType

        from app.services.qdrant import COLLECTION_PAPERS_RAG

        wrapper = self._make_wrapper()
        wrapper._client.collection_exists = AsyncMock(return_value=False)
        wrapper._client.create_collection = AsyncMock(return_value=True)
        wrapper._client.create_payload_index = AsyncMock()

        await wrapper.ensure_collections()

        # Assert create_payload_index was called for papers_rag.exercise
        index_calls = [
            c
            for c in wrapper._client.create_payload_index.await_args_list
            if c.kwargs.get("collection_name") == COLLECTION_PAPERS_RAG
            and c.kwargs.get("field_name") == "exercise"
            and c.kwargs.get("field_schema") == PayloadSchemaType.KEYWORD
        ]
        assert len(index_calls) == 1, (
            f"expected exactly one create_payload_index call for "
            f"papers_rag.exercise, got {wrapper._client.create_payload_index.await_args_list}"
        )

    @pytest.mark.asyncio
    async def test_ensure_collections_creates_sex_applicability_index_on_papers_rag(
        self,
    ) -> None:
        """Issue #222 (FR-AICP-12): papers_rag must get a keyword payload index on
        `sex_applicability` so retrieval-side sex filtering (issue #225) does not
        raise under Qdrant strict mode."""
        from qdrant_client.http.models import PayloadSchemaType

        from app.services.qdrant import COLLECTION_PAPERS_RAG

        wrapper = self._make_wrapper()
        wrapper._client.collection_exists = AsyncMock(return_value=False)
        wrapper._client.create_collection = AsyncMock(return_value=True)
        wrapper._client.create_payload_index = AsyncMock()

        await wrapper.ensure_collections()

        index_calls = [
            c
            for c in wrapper._client.create_payload_index.await_args_list
            if c.kwargs.get("collection_name") == COLLECTION_PAPERS_RAG
            and c.kwargs.get("field_name") == "sex_applicability"
            and c.kwargs.get("field_schema") == PayloadSchemaType.KEYWORD
        ]
        assert len(index_calls) == 1, (
            f"expected exactly one create_payload_index call for "
            f"papers_rag.sex_applicability, got "
            f"{wrapper._client.create_payload_index.await_args_list}"
        )


# ---------------------------------------------------------------------------
# ping()
# ---------------------------------------------------------------------------


class TestPing:
    def _make_wrapper(self) -> object:
        from app.services.qdrant import QdrantClientWrapper

        mock_inner = AsyncMock()
        wrapper = QdrantClientWrapper.__new__(QdrantClientWrapper)
        wrapper._client = mock_inner
        return wrapper

    @pytest.mark.asyncio
    async def test_ping_returns_true_on_success(self) -> None:
        wrapper = self._make_wrapper()
        wrapper._client.info = AsyncMock(return_value=MagicMock(title="qdrant"))

        result = await wrapper.ping()

        assert result is True

    @pytest.mark.asyncio
    async def test_ping_returns_false_on_exception(self) -> None:
        wrapper = self._make_wrapper()
        wrapper._client.info = AsyncMock(side_effect=ConnectionError("unreachable"))

        result = await wrapper.ping()

        assert result is False


# ---------------------------------------------------------------------------
# upsert_points() and query_points() — thin passthroughs
# ---------------------------------------------------------------------------


class TestPassthroughMethods:
    def _make_wrapper(self) -> object:
        from app.services.qdrant import QdrantClientWrapper

        mock_inner = AsyncMock()
        wrapper = QdrantClientWrapper.__new__(QdrantClientWrapper)
        wrapper._client = mock_inner
        return wrapper

    @pytest.mark.asyncio
    async def test_upsert_points_delegates_to_inner_client(self) -> None:
        wrapper = self._make_wrapper()
        fake_result = MagicMock(name="update_result")
        wrapper._client.upsert = AsyncMock(return_value=fake_result)

        fake_points = [MagicMock()]
        result = await wrapper.upsert_points("papers_rag", fake_points)

        wrapper._client.upsert.assert_awaited_once_with(
            collection_name="papers_rag", points=fake_points
        )
        assert result is fake_result

    @pytest.mark.asyncio
    async def test_query_points_delegates_to_inner_client(self) -> None:
        wrapper = self._make_wrapper()
        fake_result = MagicMock(name="query_result")
        wrapper._client.query_points = AsyncMock(return_value=fake_result)

        result = await wrapper.query_points(
            "coach_brain", query=[0.1] * 1024, limit=5
        )

        wrapper._client.query_points.assert_awaited_once_with(
            collection_name="coach_brain", query=[0.1] * 1024, limit=5
        )
        assert result is fake_result

    @pytest.mark.asyncio
    async def test_set_payload_delegates_to_inner_client(self) -> None:
        """Issue #222 (FR-RAGK-02 ext.): set_payload forwards
        (collection, payload, points_filter) to the inner client's set_payload,
        used by the corpus backfill to overwrite keys without re-embedding."""
        wrapper = self._make_wrapper()
        wrapper._client.set_payload = AsyncMock(return_value=None)

        fake_filter = MagicMock(name="points_filter")
        payload = {"exercise": ["squat"], "sex_applicability": "both"}

        await wrapper.set_payload("papers_rag", payload, fake_filter)

        wrapper._client.set_payload.assert_awaited_once_with(
            collection_name="papers_rag", payload=payload, points=fake_filter
        )


# ---------------------------------------------------------------------------
# Nightly cron: ping_qdrant_health
# ---------------------------------------------------------------------------


class TestPingQdrantHealthCron:
    @pytest.mark.asyncio
    async def test_cron_calls_ping_on_success(self) -> None:
        """Cron must import the factory and call client.ping()."""
        from app.workers.keepalive import ping_qdrant_health

        fake_wrapper = AsyncMock()
        fake_wrapper.ping = AsyncMock(return_value=True)

        with patch(
            "app.workers.keepalive.get_qdrant_client",
            new=AsyncMock(return_value=fake_wrapper),
        ):
            await ping_qdrant_health(ctx={})

        fake_wrapper.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cron_logs_warning_on_ping_failure_does_not_raise(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When ping() returns False, cron logs a warning but never raises."""
        from app.workers.keepalive import ping_qdrant_health

        fake_wrapper = AsyncMock()
        fake_wrapper.ping = AsyncMock(return_value=False)

        with patch(
            "app.workers.keepalive.get_qdrant_client",
            new=AsyncMock(return_value=fake_wrapper),
        ):
            with caplog.at_level(logging.WARNING, logger="app.workers.keepalive"):
                await ping_qdrant_health(ctx={})  # must not raise

        assert any("qdrant" in r.message.lower() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_cron_handles_none_client_gracefully(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If factory returns None (missing env vars), cron logs warning, no raise."""
        from app.workers.keepalive import ping_qdrant_health

        with patch(
            "app.workers.keepalive.get_qdrant_client",
            new=AsyncMock(return_value=None),
        ):
            with caplog.at_level(logging.WARNING, logger="app.workers.keepalive"):
                await ping_qdrant_health(ctx={})  # must not raise

    @pytest.mark.asyncio
    async def test_cron_does_not_raise_when_ping_raises_exception(self) -> None:
        """If ping() raises unexpectedly, cron must catch and log — never propagate."""
        from app.workers.keepalive import ping_qdrant_health

        fake_wrapper = AsyncMock()
        fake_wrapper.ping = AsyncMock(side_effect=RuntimeError("network blip"))

        with patch(
            "app.workers.keepalive.get_qdrant_client",
            new=AsyncMock(return_value=fake_wrapper),
        ):
            await ping_qdrant_health(ctx={})  # must not raise
