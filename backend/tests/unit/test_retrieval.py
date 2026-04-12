"""Tests for RetrievalService — dense vector retrieval from Qdrant (P2-008).

Requirements: FR-AICP-09

TDD protocol: tests written before implementation.
All Cohere and Qdrant calls are mocked (ADR-032).
Never call the real Cohere or Qdrant APIs in these tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers — shared mock factories
# ---------------------------------------------------------------------------


def _make_cohere_client(vectors: list[list[float]] | None = None) -> MagicMock:
    """Return a mock CohereEmbedClient whose embed_batch returns ``vectors``."""
    if vectors is None:
        vectors = [[0.1] * 1024]

    client = MagicMock()
    client.embed_batch = AsyncMock(return_value=vectors)
    return client


def _make_qdrant_scored_point(
    *,
    score: float = 0.85,
    payload: dict | None = None,
) -> MagicMock:
    """Return a mock ScoredPoint as returned by AsyncQdrantClient.query_points."""
    if payload is None:
        payload = {
            "id": "a" * 64,
            "text": "Squat depth improves with hip mobility.",
            "paper_id": "paper-001",
            "chunk_index": 0,
            "section": "results",
            "token_count": 12,
            "quality_tier": "L1_systematic_review",
            "title": "Squat Mechanics Review",
            "authors": ["Smith J", "Jones K"],
            "year": 2022,
            "doi": "10.1234/example",
        }

    point = MagicMock()
    point.score = score
    point.payload = payload
    return point


def _make_qdrant_result(points: list[MagicMock]) -> MagicMock:
    """Wrap a list of ScoredPoints in the QueryResponse envelope."""
    result = MagicMock()
    result.points = points
    return result


def _make_qdrant_client(result: MagicMock | None = None) -> MagicMock:
    """Return a mock QdrantClientWrapper whose query_points returns ``result``."""
    if result is None:
        result = _make_qdrant_result([_make_qdrant_scored_point()])

    client = MagicMock()
    client.query_points = AsyncMock(return_value=result)
    return client


# ---------------------------------------------------------------------------
# Test 1 — query is embedded with input_type=SEARCH_QUERY, not SEARCH_DOCUMENT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_uses_search_query_input_type() -> None:
    """embed_batch must be called with EmbedInputType.SEARCH_QUERY at retrieval time.

    Using SEARCH_DOCUMENT at query time is an asymmetric embedding error that
    silently degrades retrieval quality — the guard lives here because the call
    site is easy to get wrong.
    """
    from app.services.cohere_client import EmbedInputType
    from app.services.retrieval import RetrievalService

    cohere_client = _make_cohere_client()
    qdrant_client = _make_qdrant_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)
    await service.dense_search("how does squat depth affect knee angle?")

    cohere_client.embed_batch.assert_called_once()
    call_kwargs = cohere_client.embed_batch.call_args
    # embed_batch signature: embed_batch(texts, *, input_type)
    # The input_type kwarg must be SEARCH_QUERY.
    actual_input_type = call_kwargs.kwargs.get("input_type") or call_kwargs.args[1]
    assert actual_input_type == EmbedInputType.SEARCH_QUERY, (
        f"input_type was {actual_input_type!r}, expected EmbedInputType.SEARCH_QUERY. "
        "Using SEARCH_DOCUMENT at query time silently degrades retrieval quality."
    )


# ---------------------------------------------------------------------------
# Test 2 — Qdrant query_points is called with the correct collection and vector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_calls_qdrant_with_embedded_vector() -> None:
    """query_points must receive the exact vector returned by embed_batch."""
    from app.services.retrieval import RetrievalService

    expected_vector = [0.42] * 1024
    cohere_client = _make_cohere_client(vectors=[expected_vector])
    qdrant_client = _make_qdrant_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)
    await service.dense_search("bench press elbow angle", collection="papers_rag", top_k=5)

    qdrant_client.query_points.assert_called_once()
    call_args = qdrant_client.query_points.call_args

    # First positional arg is collection name.
    assert call_args.args[0] == "papers_rag" or call_args.kwargs.get("collection") == "papers_rag"

    # query kwarg (or second positional) must be the embedded vector.
    actual_query = call_args.kwargs.get("query") or call_args.args[1]
    assert actual_query == expected_vector, (
        "query_points must receive the vector returned by embed_batch."
    )


# ---------------------------------------------------------------------------
# Test 3 — top_k parameter is forwarded to Qdrant as limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_forwards_top_k_as_limit() -> None:
    """top_k must be forwarded to query_points as the ``limit`` kwarg."""
    from app.services.retrieval import RetrievalService

    cohere_client = _make_cohere_client()
    qdrant_client = _make_qdrant_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)
    await service.dense_search("deadlift hip angle", top_k=7)

    call_kwargs = qdrant_client.query_points.call_args.kwargs
    assert call_kwargs.get("limit") == 7, (
        f"limit was {call_kwargs.get('limit')!r}, expected 7. "
        "top_k must be forwarded to Qdrant as the limit parameter."
    )


# ---------------------------------------------------------------------------
# Test 4 — results are correctly parsed into list[RetrievedContext]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_parses_results_into_retrieved_context() -> None:
    """Each Qdrant ScoredPoint must map to one RetrievedContext with a ChunkPayload."""
    from app.schemas.rag import RetrievedContext
    from app.services.retrieval import RetrievalService

    payload = {
        "id": "b" * 64,
        "text": "Hip mobility limits squat depth.",
        "paper_id": "paper-042",
        "chunk_index": 3,
        "section": "discussion",
        "token_count": 8,
        "quality_tier": "L2_rct",
        "title": "Hip Mobility Study",
        "authors": ["Doe A"],
        "year": 2021,
        "doi": None,
    }
    point = _make_qdrant_scored_point(score=0.77, payload=payload)
    qdrant_client = _make_qdrant_client(_make_qdrant_result([point]))
    cohere_client = _make_cohere_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)
    results = await service.dense_search("hip mobility squat")

    assert len(results) == 1
    ctx = results[0]
    assert isinstance(ctx, RetrievedContext)
    assert ctx.score == pytest.approx(0.77)
    assert ctx.collection == "papers_rag"
    assert ctx.chunk.paper_id == "paper-042"
    assert ctx.chunk.title == "Hip Mobility Study"
    assert ctx.chunk.quality_tier == "L2_rct"
    assert ctx.chunk.year == 2021
    assert ctx.chunk.doi is None


# ---------------------------------------------------------------------------
# Test 5 — empty Qdrant result returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_empty_results_returns_empty_list() -> None:
    """When Qdrant returns zero points, dense_search must return []."""
    from app.services.retrieval import RetrievalService

    qdrant_client = _make_qdrant_client(_make_qdrant_result([]))
    cohere_client = _make_cohere_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)
    results = await service.dense_search("nonexistent topic")

    assert results == [], f"Expected [], got {results}"


# ---------------------------------------------------------------------------
# Test 6 — collection parameter is forwarded (coach_brain support)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_forwards_collection_param() -> None:
    """The collection parameter must be forwarded verbatim to query_points.

    Ensures coach_brain can be queried with the same service, not just papers_rag.
    """
    from app.services.retrieval import RetrievalService

    cohere_client = _make_cohere_client()
    qdrant_client = _make_qdrant_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)
    await service.dense_search("bench lockout cues", collection="coach_brain")

    call_args = qdrant_client.query_points.call_args
    actual_collection = call_args.args[0] if call_args.args else call_args.kwargs.get("collection")
    assert actual_collection == "coach_brain", (
        f"collection forwarded as {actual_collection!r}, expected 'coach_brain'."
    )


# ---------------------------------------------------------------------------
# Test 7 — collection name in RetrievedContext matches what was queried
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_sets_collection_on_retrieved_context() -> None:
    """The collection field on each RetrievedContext must match the queried collection."""
    from app.services.retrieval import RetrievalService

    cohere_client = _make_cohere_client()
    qdrant_client = _make_qdrant_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)
    results = await service.dense_search("squat cues", collection="coach_brain")

    assert len(results) == 1
    assert results[0].collection == "coach_brain"


# ---------------------------------------------------------------------------
# Test 8 — with_payload=True is requested from Qdrant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_requests_payload_from_qdrant() -> None:
    """query_points must request payloads (with_payload=True) so ChunkPayload can be built."""
    from app.services.retrieval import RetrievalService

    cohere_client = _make_cohere_client()
    qdrant_client = _make_qdrant_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)
    await service.dense_search("squat technique")

    call_kwargs = qdrant_client.query_points.call_args.kwargs
    assert call_kwargs.get("with_payload") is True, (
        f"with_payload was {call_kwargs.get('with_payload')!r}, expected True. "
        "Without payload, ChunkPayload cannot be populated."
    )
