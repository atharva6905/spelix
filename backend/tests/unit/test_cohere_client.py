"""Tests for CohereEmbedClient wrapper (P2-003).

Requirements: FR-AICP-09, ADR-RAG-01, ADR-RAG-03

TDD protocol: these tests are written BEFORE the implementation. They must
fail until the implementation is complete.

NEVER call the real Cohere API in these tests. All tests mock cohere.AsyncClientV2
at its source module (cohere.AsyncClientV2), per the ADR-032 real-factory pattern.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Test 1 — ADR-032: real factory exercises AsyncClientV2 with correct API key
# ---------------------------------------------------------------------------


def test_get_cohere_client_factory_passes_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory must call cohere.AsyncClientV2 with the key from COHERE_API_KEY env var.

    This is the ADR-032 real-factory test — it patches at the source module, not
    at the consumer, so a broken factory path (wrong constructor call, missing
    get_secret_value(), etc.) is caught immediately rather than silently passing
    behind a MagicMock.
    """
    monkeypatch.setenv("COHERE_API_KEY", "test-cohere-key-xyz")

    # Reset the module-level cache so we exercise the full construction path.
    import app.services.cohere_client as cc_module

    cc_module._cohere_client_cache = None

    fake_async_client = MagicMock()

    with patch("cohere.AsyncClientV2", return_value=fake_async_client) as mock_constructor:
        from app.services.cohere_client import get_cohere_client

        client = get_cohere_client()

    # The factory must have passed the raw string key to the constructor.
    mock_constructor.assert_called_once_with(api_key="test-cohere-key-xyz")
    assert client._client is fake_async_client


# ---------------------------------------------------------------------------
# Test 2 — output_dimension=1024 MUST appear on every embed call (ADR-RAG-03)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_batch_always_passes_output_dimension_1024() -> None:
    """output_dimension=1024 must be passed explicitly on every embed call.

    This is the load-bearing regression test for the entire Phase 2 ingestion
    pipeline. Omitting output_dimension defaults to 1536, which causes a Qdrant
    dimension mismatch on every upsert and breaks the collection at init time.
    """
    from app.services.cohere_client import CohereEmbedClient, EmbedInputType

    # Build a mock embed response with 2 float vectors of length 1024.
    fake_embed_response = MagicMock()
    fake_embed_response.embeddings.float_ = [[0.1] * 1024, [0.2] * 1024]

    mock_async_client = AsyncMock()
    mock_async_client.embed = AsyncMock(return_value=fake_embed_response)

    client = CohereEmbedClient.__new__(CohereEmbedClient)
    client._client = mock_async_client

    result = await client.embed_batch(
        ["foo", "bar"],
        input_type=EmbedInputType.SEARCH_DOCUMENT,
    )

    # Verify output_dimension=1024 was in the call kwargs — this is the guard.
    mock_async_client.embed.assert_called_once()
    call_kwargs = mock_async_client.embed.call_args.kwargs
    assert call_kwargs["output_dimension"] == 1024, (
        f"output_dimension was {call_kwargs.get('output_dimension')!r}, expected 1024. "
        "This breaks Qdrant upsert — see ADR-RAG-03."
    )
    assert call_kwargs["model"] == "embed-v4.0"
    assert call_kwargs["embedding_types"] == ["float"]

    # Result must contain 2 vectors of 1024 dims.
    assert len(result) == 2
    assert len(result[0]) == 1024


# ---------------------------------------------------------------------------
# Test 3 — chunking: 200 texts → 3 sub-batches of [96, 96, 8]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_batch_chunks_at_96() -> None:
    """200 texts must be split into 3 sub-batches: [96, 96, 8].

    Each sub-batch is a separate API call. All embeddings are concatenated
    in order and returned as a flat list.
    """
    from app.services.cohere_client import CohereEmbedClient, EmbedInputType

    def make_fake_response(n: int) -> MagicMock:
        resp = MagicMock()
        resp.embeddings.float_ = [[float(i)] * 1024 for i in range(n)]
        return resp

    call_count = 0
    batch_sizes_seen: list[int] = []

    async def fake_embed(**kwargs: object) -> MagicMock:
        nonlocal call_count
        texts = kwargs["texts"]
        batch_sizes_seen.append(len(texts))
        call_count += 1
        return make_fake_response(len(texts))

    mock_async_client = AsyncMock()
    mock_async_client.embed = fake_embed

    client = CohereEmbedClient.__new__(CohereEmbedClient)
    client._client = mock_async_client

    result = await client.embed_batch(
        ["x"] * 200,
        input_type=EmbedInputType.SEARCH_DOCUMENT,
    )

    assert call_count == 3, f"Expected 3 API calls, got {call_count}"
    assert batch_sizes_seen == [96, 96, 8], (
        f"Expected batch sizes [96, 96, 8], got {batch_sizes_seen}"
    )
    assert len(result) == 200, f"Expected 200 concatenated embeddings, got {len(result)}"


# ---------------------------------------------------------------------------
# Test 4 — input_type=search_query is forwarded correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_batch_passes_search_query_input_type() -> None:
    """input_type=SEARCH_QUERY must be forwarded as 'search_query' string."""
    from app.services.cohere_client import CohereEmbedClient, EmbedInputType

    fake_embed_response = MagicMock()
    fake_embed_response.embeddings.float_ = [[0.5] * 1024]

    mock_async_client = AsyncMock()
    mock_async_client.embed = AsyncMock(return_value=fake_embed_response)

    client = CohereEmbedClient.__new__(CohereEmbedClient)
    client._client = mock_async_client

    await client.embed_batch(["my query"], input_type=EmbedInputType.SEARCH_QUERY)

    call_kwargs = mock_async_client.embed.call_args.kwargs
    assert call_kwargs["input_type"] == "search_query"


# ---------------------------------------------------------------------------
# Test 5 — rerank uses exact model string "rerank-v4.0-pro" (ADR-RAG-01)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rerank_uses_v4_pro_model() -> None:
    """Rerank must use exactly 'rerank-v4.0-pro' — never 3.5 or non-pro variants.

    Regression guard against accidental downgrade. ADR-RAG-01 explicitly
    supersedes any prior reference to rerank-3.5 or rerank-english-v3.0.
    """
    from app.services.cohere_client import CohereEmbedClient

    fake_result = MagicMock()
    fake_result.results = [
        MagicMock(index=0, relevance_score=0.9),
        MagicMock(index=1, relevance_score=0.7),
        MagicMock(index=2, relevance_score=0.3),
    ]

    mock_async_client = AsyncMock()
    mock_async_client.rerank = AsyncMock(return_value=fake_result)

    client = CohereEmbedClient.__new__(CohereEmbedClient)
    client._client = mock_async_client

    await client.rerank("q", ["a", "b", "c"])

    call_kwargs = mock_async_client.rerank.call_args.kwargs
    assert call_kwargs["model"] == "rerank-v4.0-pro", (
        f"model was {call_kwargs.get('model')!r}, expected 'rerank-v4.0-pro'. "
        "ADR-RAG-01 mandates rerank-v4.0-pro — do not use 3.5 or non-pro variants."
    )


# ---------------------------------------------------------------------------
# Test 6 — rerank returns (index, score) sorted by score descending
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rerank_returns_sorted_indices() -> None:
    """rerank() must return list[tuple[int, float]] sorted by score descending."""
    from app.services.cohere_client import CohereEmbedClient

    # API returns in its own order; we assert wrapper sorts them.
    api_results = [
        MagicMock(index=2, relevance_score=0.4),
        MagicMock(index=0, relevance_score=0.95),
        MagicMock(index=1, relevance_score=0.7),
    ]
    fake_result = MagicMock()
    fake_result.results = api_results

    mock_async_client = AsyncMock()
    mock_async_client.rerank = AsyncMock(return_value=fake_result)

    client = CohereEmbedClient.__new__(CohereEmbedClient)
    client._client = mock_async_client

    ranked = await client.rerank("query text", ["doc a", "doc b", "doc c"])

    # Must be tuples of (original_index, score) sorted descending by score.
    assert ranked == [(0, 0.95), (1, 0.7), (2, 0.4)], (
        f"Expected [(0, 0.95), (1, 0.7), (2, 0.4)], got {ranked}"
    )
