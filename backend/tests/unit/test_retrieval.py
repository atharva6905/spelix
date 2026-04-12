"""Tests for RetrievalService — dense vector retrieval from Qdrant (P2-008).
Also covers hybrid_search + rrf_fuse (P2-010, FR-AICP-09).
Also covers exercise_filter parameter (P2-011, FR-AICP-12).

Requirements: FR-AICP-09, FR-AICP-12

TDD protocol: tests written before implementation.
All Cohere and Qdrant calls are mocked (ADR-032).
Never call the real Cohere or Qdrant APIs in these tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — shared mock factories
# ---------------------------------------------------------------------------


def _make_cohere_client(
    vectors: list[list[float]] | None = None,
    rerank_results: list[tuple[int, float]] | None = None,
) -> MagicMock:
    """Return a mock CohereEmbedClient whose embed_batch returns ``vectors``."""
    if vectors is None:
        vectors = [[0.1] * 1024]

    client = MagicMock()
    client.embed_batch = AsyncMock(return_value=vectors)
    # Default rerank: returns identity mapping with descending dummy scores
    if rerank_results is None:
        rerank_results = [(0, 0.9)]
    client.rerank = AsyncMock(return_value=rerank_results)
    return client


def _make_chunk_payload(
    chunk_id: str = "a" * 64,
    text: str = "Squat depth improves with hip mobility.",
    paper_id: str = "paper-001",
    quality_tier: str = "L1_systematic_review",
    year: int | None = 2022,
) -> dict:
    return {
        "id": chunk_id,
        "text": text,
        "paper_id": paper_id,
        "chunk_index": 0,
        "section": "results",
        "token_count": 12,
        "quality_tier": quality_tier,
        "title": "Squat Mechanics Review",
        "authors": ["Smith J", "Jones K"],
        "year": year,
        "doi": "10.1234/example",
    }


def _make_qdrant_scored_point(
    *,
    score: float = 0.85,
    payload: dict | None = None,
) -> MagicMock:
    """Return a mock ScoredPoint as returned by AsyncQdrantClient.query_points."""
    if payload is None:
        payload = _make_chunk_payload()

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


def _make_retrieved_context(
    chunk_id: str = "a" * 64,
    text: str = "Squat depth improves with hip mobility.",
    paper_id: str = "paper-001",
    score: float = 0.85,
    collection: str = "papers_rag",
    quality_tier: str = "L1_systematic_review",
    year: int | None = 2022,
):
    """Build a real RetrievedContext for use in rrf_fuse tests."""
    from app.schemas.rag import ChunkPayload, RetrievedContext

    chunk = ChunkPayload(
        id=chunk_id,
        text=text,
        paper_id=paper_id,
        chunk_index=0,
        section="results",
        token_count=12,
        quality_tier=quality_tier,  # type: ignore[arg-type]
        title="Test Paper",
        authors=["Author A"],
        year=year,
        doi=None,
    )
    return RetrievedContext(chunk=chunk, score=score, collection=collection)  # type: ignore[arg-type]


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


# ===========================================================================
# P2-010 tests — rrf_fuse pure function (FR-AICP-09)
# ===========================================================================

# ---------------------------------------------------------------------------
# Test 9 — rrf_fuse: overlapping lists produce merged scores, dedup by chunk.id
# ---------------------------------------------------------------------------


def test_rrf_fuse_overlap_merges_scores_and_deduplicates() -> None:
    """Items appearing in both lists must appear once with summed RRF contributions.

    RRF formula: score = sum(1 / (k + rank)) across all lists the item appears in.
    Ranks are 1-based within each list.
    """
    from app.services.retrieval import rrf_fuse

    shared_id = "shared" + "x" * 58  # 64 chars total
    unique_dense_id = "dense" + "y" * 59
    unique_sparse_id = "sparse" + "z" * 58

    # Dense list: shared chunk at rank 1, unique chunk at rank 2
    dense = [
        _make_retrieved_context(chunk_id=shared_id, score=0.9),
        _make_retrieved_context(chunk_id=unique_dense_id, score=0.7, paper_id="paper-002"),
    ]
    # Sparse list: unique chunk at rank 1, shared chunk at rank 2
    sparse = [
        _make_retrieved_context(chunk_id=unique_sparse_id, score=0.8, paper_id="paper-003"),
        _make_retrieved_context(chunk_id=shared_id, score=0.5),
    ]

    fused = rrf_fuse(dense, sparse, k=60)

    # Each chunk_id must appear exactly once
    ids = [ctx.chunk.id for ctx in fused]
    assert len(ids) == len(set(ids)), f"Duplicate chunk ids in fused output: {ids}"

    # All three distinct chunks must be present
    assert shared_id in ids
    assert unique_dense_id in ids
    assert unique_sparse_id in ids

    # The shared chunk must have a higher RRF score than either unique chunk
    shared_score = next(ctx.score for ctx in fused if ctx.chunk.id == shared_id)
    dense_only_score = next(ctx.score for ctx in fused if ctx.chunk.id == unique_dense_id)
    sparse_only_score = next(ctx.score for ctx in fused if ctx.chunk.id == unique_sparse_id)

    assert shared_score > dense_only_score, (
        "Shared chunk (rank 1 dense + rank 2 sparse) must outscore dense-only chunk."
    )
    assert shared_score > sparse_only_score, (
        "Shared chunk (rank 1 dense + rank 2 sparse) must outscore sparse-only chunk."
    )


# ---------------------------------------------------------------------------
# Test 10 — rrf_fuse: disjoint lists — all items present in output
# ---------------------------------------------------------------------------


def test_rrf_fuse_disjoint_lists_all_items_present() -> None:
    """When dense and sparse results share no chunks, all items must appear in output."""
    from app.services.retrieval import rrf_fuse

    dense = [
        _make_retrieved_context(chunk_id="d1" + "x" * 62, paper_id="p1"),
        _make_retrieved_context(chunk_id="d2" + "x" * 62, paper_id="p2"),
    ]
    sparse = [
        _make_retrieved_context(chunk_id="s1" + "y" * 62, paper_id="p3"),
        _make_retrieved_context(chunk_id="s2" + "y" * 62, paper_id="p4"),
    ]

    fused = rrf_fuse(dense, sparse, k=60)

    assert len(fused) == 4, f"Expected 4 items (all disjoint), got {len(fused)}"
    ids = {ctx.chunk.id for ctx in fused}
    assert "d1" + "x" * 62 in ids
    assert "d2" + "x" * 62 in ids
    assert "s1" + "y" * 62 in ids
    assert "s2" + "y" * 62 in ids


# ---------------------------------------------------------------------------
# Test 11 — rrf_fuse: ordering — items in both lists rank higher than single-list
# ---------------------------------------------------------------------------


def test_rrf_fuse_items_in_both_lists_rank_higher() -> None:
    """A chunk appearing in both dense and sparse must outscore any single-list chunk.

    This validates the core RRF property: cross-method agreement lifts rank.
    The worst possible shared position (last in both) must still beat any
    single-list item at the same rank via double contribution.
    """
    from app.services.retrieval import rrf_fuse

    k = 60
    shared_id = "shared" + "a" * 58

    # 5-item lists; shared chunk appears last in both (rank 5)
    dense = [
        _make_retrieved_context(chunk_id=f"d{i}" + "x" * 62, paper_id=f"p{i}") for i in range(4)
    ] + [_make_retrieved_context(chunk_id=shared_id)]

    sparse = [
        _make_retrieved_context(chunk_id=f"s{i}" + "y" * 62, paper_id=f"q{i}") for i in range(4)
    ] + [_make_retrieved_context(chunk_id=shared_id)]

    fused = rrf_fuse(dense, sparse, k=k)

    shared_score = next(ctx.score for ctx in fused if ctx.chunk.id == shared_id)
    # Any single-list item's maximum RRF contribution is 1/(k+1) (rank 1)
    max_single_rrf = 1 / (k + 1)
    # Shared at rank 5 in both: 1/(k+5) + 1/(k+5) = 2/(k+5)
    shared_expected = 2 / (k + 5)

    assert shared_score == pytest.approx(shared_expected, rel=1e-6)
    assert shared_score > max_single_rrf, (
        f"Shared chunk score {shared_score:.6f} must exceed max single-list "
        f"contribution {max_single_rrf:.6f} (rank-1 in one list)."
    )


# ---------------------------------------------------------------------------
# Test 12 — rrf_fuse: output is sorted descending by score
# ---------------------------------------------------------------------------


def test_rrf_fuse_output_is_sorted_descending() -> None:
    """rrf_fuse output must be sorted by score descending (highest first)."""
    from app.services.retrieval import rrf_fuse

    dense = [
        _make_retrieved_context(chunk_id=f"d{i}" + "x" * 62, paper_id=f"p{i}") for i in range(5)
    ]
    sparse = [
        _make_retrieved_context(chunk_id=f"s{i}" + "y" * 62, paper_id=f"q{i}") for i in range(5)
    ]

    fused = rrf_fuse(dense, sparse, k=60)

    scores = [ctx.score for ctx in fused]
    assert scores == sorted(scores, reverse=True), (
        "rrf_fuse output must be sorted by score descending."
    )


# ---------------------------------------------------------------------------
# Test 13 — rrf_fuse: empty lists
# ---------------------------------------------------------------------------


def test_rrf_fuse_both_empty_returns_empty() -> None:
    """rrf_fuse of two empty lists must return an empty list."""
    from app.services.retrieval import rrf_fuse

    assert rrf_fuse([], [], k=60) == []


def test_rrf_fuse_one_empty_returns_other() -> None:
    """rrf_fuse with one empty list must return the non-empty list items."""
    from app.services.retrieval import rrf_fuse

    dense = [_make_retrieved_context(chunk_id="d1" + "x" * 62, paper_id="p1")]
    fused = rrf_fuse(dense, [], k=60)
    assert len(fused) == 1
    assert fused[0].chunk.id == "d1" + "x" * 62


# ===========================================================================
# P2-010 tests — hybrid_search integration (FR-AICP-09)
# ===========================================================================

# ---------------------------------------------------------------------------
# Test 14 — hybrid_search calls dense and sparse concurrently
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_search_calls_dense_and_sparse_concurrently() -> None:
    """hybrid_search must call both dense_search and sparse_search.

    We verify both methods are called (concurrency is an implementation detail
    tested implicitly via asyncio.gather — we assert both are invoked).
    """
    from app.services.retrieval import RetrievalService
    from app.services.sparse_retrieval import SparseRetrievalService

    cohere_client = _make_cohere_client(
        vectors=[[0.1] * 1024],
        rerank_results=[(0, 0.95)],
    )
    qdrant_client = _make_qdrant_client()

    sparse_service = MagicMock(spec=SparseRetrievalService)
    sparse_service.sparse_search = AsyncMock(
        return_value=[_make_retrieved_context(chunk_id="s1" + "y" * 62, paper_id="p2")]
    )

    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        sparse_service=sparse_service,
    )

    with patch.object(service, "dense_search", wraps=service.dense_search) as mock_dense:
        await service.hybrid_search("squat depth knee angle", collection="papers_rag", top_k=5)
        mock_dense.assert_called_once()

    sparse_service.sparse_search.assert_called_once()


# ---------------------------------------------------------------------------
# Test 15 — hybrid_search calls rerank with fused texts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_search_calls_rerank_with_fused_texts() -> None:
    """hybrid_search must pass fused chunk texts to cohere_client.rerank."""
    from app.services.retrieval import RetrievalService
    from app.services.sparse_retrieval import SparseRetrievalService

    dense_chunk_id = "dense" + "x" * 59
    sparse_chunk_id = "sparse" + "y" * 58

    dense_result = [
        _make_retrieved_context(
            chunk_id=dense_chunk_id, text="Dense result text", paper_id="p1"
        )
    ]
    sparse_result = [
        _make_retrieved_context(
            chunk_id=sparse_chunk_id, text="Sparse result text", paper_id="p2"
        )
    ]

    cohere_client = _make_cohere_client(
        vectors=[[0.1] * 1024],
        rerank_results=[(0, 0.9), (1, 0.7)],
    )
    qdrant_client = _make_qdrant_client()

    sparse_service = MagicMock(spec=SparseRetrievalService)
    sparse_service.sparse_search = AsyncMock(return_value=sparse_result)

    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        sparse_service=sparse_service,
    )

    with patch.object(service, "dense_search", AsyncMock(return_value=dense_result)):
        await service.hybrid_search("squat depth", collection="papers_rag", top_k=5)

    cohere_client.rerank.assert_called_once()
    call_args = cohere_client.rerank.call_args
    query_arg = call_args.args[0] if call_args.args else call_args.kwargs.get("query")
    documents_arg = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("documents")
    assert query_arg == "squat depth"
    assert "Dense result text" in documents_arg
    assert "Sparse result text" in documents_arg


# ---------------------------------------------------------------------------
# Test 16 — hybrid_search returns reranked results with reranker scores
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_search_returns_reranked_results_with_reranker_scores() -> None:
    """hybrid_search must return results ordered by Cohere reranker relevance scores."""
    from app.services.retrieval import RetrievalService
    from app.services.sparse_retrieval import SparseRetrievalService

    chunk_a_id = "aaa" + "x" * 61
    chunk_b_id = "bbb" + "y" * 61

    dense_result = [
        _make_retrieved_context(chunk_id=chunk_a_id, text="Text A", paper_id="p1", score=0.9),
        _make_retrieved_context(chunk_id=chunk_b_id, text="Text B", paper_id="p2", score=0.5),
    ]

    # Reranker flips order: B scores higher than A
    cohere_client = _make_cohere_client(
        vectors=[[0.1] * 1024],
        rerank_results=[(1, 0.95), (0, 0.30)],  # index 1 = chunk_b, index 0 = chunk_a
    )
    qdrant_client = _make_qdrant_client()

    sparse_service = MagicMock(spec=SparseRetrievalService)
    sparse_service.sparse_search = AsyncMock(return_value=[])

    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        sparse_service=sparse_service,
    )

    with patch.object(service, "dense_search", AsyncMock(return_value=dense_result)):
        results = await service.hybrid_search("test query", collection="papers_rag", top_k=2)

    assert len(results) == 2
    # First result must have chunk_b (reranker put it first)
    assert results[0].chunk.id == chunk_b_id, (
        f"Expected reranker-promoted chunk_b first, got {results[0].chunk.id!r}"
    )
    assert results[0].score == pytest.approx(0.95)
    assert results[1].chunk.id == chunk_a_id
    assert results[1].score == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# Test 17 — hybrid_search without sparse_service falls back to dense-only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_search_without_sparse_service_falls_back_to_dense_only() -> None:
    """When sparse_service is None, hybrid_search must still complete using dense results."""
    from app.services.retrieval import RetrievalService

    chunk_id = "denseonly" + "x" * 55

    dense_result = [
        _make_retrieved_context(chunk_id=chunk_id, text="Dense only text", paper_id="p1")
    ]

    cohere_client = _make_cohere_client(
        vectors=[[0.1] * 1024],
        rerank_results=[(0, 0.88)],
    )
    qdrant_client = _make_qdrant_client()

    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        sparse_service=None,
    )

    with patch.object(service, "dense_search", AsyncMock(return_value=dense_result)):
        results = await service.hybrid_search("fallback query", collection="papers_rag", top_k=5)

    assert len(results) == 1
    assert results[0].chunk.id == chunk_id
    assert results[0].score == pytest.approx(0.88)


# ---------------------------------------------------------------------------
# Test 18 — hybrid_search rerank_top_n defaults to top_k
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_search_rerank_top_n_defaults_to_top_k() -> None:
    """When rerank_top_n is not specified, top_n passed to rerank must equal top_k."""
    from app.services.retrieval import RetrievalService
    from app.services.sparse_retrieval import SparseRetrievalService

    cohere_client = _make_cohere_client(
        vectors=[[0.1] * 1024],
        rerank_results=[(0, 0.9)],
    )
    qdrant_client = _make_qdrant_client()

    sparse_service = MagicMock(spec=SparseRetrievalService)
    sparse_service.sparse_search = AsyncMock(return_value=[])

    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        sparse_service=sparse_service,
    )

    dense_result = [_make_retrieved_context(chunk_id="c1" + "x" * 62, paper_id="p1")]

    with patch.object(service, "dense_search", AsyncMock(return_value=dense_result)):
        await service.hybrid_search("some query", collection="papers_rag", top_k=7)

    call_args = cohere_client.rerank.call_args
    top_n_arg = call_args.kwargs.get("top_n")
    assert top_n_arg == 7, (
        f"Expected top_n=7 (matching top_k), got {top_n_arg!r}"
    )


# ===========================================================================
# P2-011 tests — exercise_filter (FR-AICP-12)
# ===========================================================================

# ---------------------------------------------------------------------------
# Test 19 — dense_search with exercise_filter passes query_filter to query_points
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_exercise_filter_passes_filter_to_query_points() -> None:
    """When exercise_filter is provided, query_points must receive a query_filter.

    The filter must restrict results to points where payload.exercise == the
    supplied value (FR-AICP-12).
    """
    from qdrant_client import models as qdrant_models

    from app.services.retrieval import RetrievalService

    cohere_client = _make_cohere_client()
    qdrant_client = _make_qdrant_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)
    await service.dense_search(
        "squat depth cue",
        collection="coach_brain",
        top_k=5,
        exercise_filter="squat",
    )

    qdrant_client.query_points.assert_called_once()
    call_kwargs = qdrant_client.query_points.call_args.kwargs

    query_filter = call_kwargs.get("query_filter")
    assert query_filter is not None, (
        "query_filter must be passed to query_points when exercise_filter is set."
    )
    assert isinstance(query_filter, qdrant_models.Filter), (
        f"query_filter must be a qdrant_client.models.Filter, got {type(query_filter)}"
    )
    # Inspect the must conditions
    must_conditions = query_filter.must
    assert must_conditions and len(must_conditions) == 1, (
        "Filter must contain exactly one must condition."
    )
    condition = must_conditions[0]
    assert isinstance(condition, qdrant_models.FieldCondition), (
        f"Condition must be FieldCondition, got {type(condition)}"
    )
    assert condition.key == "exercise", (
        f"FieldCondition key must be 'exercise', got {condition.key!r}"
    )
    assert isinstance(condition.match, qdrant_models.MatchValue), (
        f"Condition match must be MatchValue, got {type(condition.match)}"
    )
    assert condition.match.value == "squat", (
        f"MatchValue must be 'squat', got {condition.match.value!r}"
    )


# ---------------------------------------------------------------------------
# Test 20 — dense_search without exercise_filter passes no query_filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_no_exercise_filter_omits_query_filter() -> None:
    """When exercise_filter is None (default), query_filter must NOT be passed to query_points."""
    from app.services.retrieval import RetrievalService

    cohere_client = _make_cohere_client()
    qdrant_client = _make_qdrant_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)
    await service.dense_search("squat depth cue", collection="coach_brain", top_k=5)

    call_kwargs = qdrant_client.query_points.call_args.kwargs
    assert "query_filter" not in call_kwargs, (
        "query_filter must not be passed to query_points when exercise_filter is None."
    )


# ---------------------------------------------------------------------------
# Test 21 — hybrid_search with exercise_filter forwards to both dense and sparse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_search_exercise_filter_forwarded_to_dense_and_sparse() -> None:
    """When exercise_filter is set, hybrid_search must pass it to both dense_search
    and sparse_search so both legs of retrieval are filtered consistently (FR-AICP-12).
    """
    from app.services.retrieval import RetrievalService
    from app.services.sparse_retrieval import SparseRetrievalService

    cohere_client = _make_cohere_client(
        vectors=[[0.1] * 1024],
        rerank_results=[(0, 0.9)],
    )
    qdrant_client = _make_qdrant_client()

    sparse_service = MagicMock(spec=SparseRetrievalService)
    sparse_service.sparse_search = AsyncMock(return_value=[])

    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        sparse_service=sparse_service,
    )

    dense_result = [_make_retrieved_context(chunk_id="c1" + "x" * 62, paper_id="p1")]

    mock_dense = AsyncMock(return_value=dense_result)
    with patch.object(service, "dense_search", mock_dense):
        await service.hybrid_search(
            "bench press cue",
            collection="coach_brain",
            top_k=5,
            exercise_filter="bench",
        )

    # dense_search must have been called with exercise_filter="bench"
    dense_call_kwargs = mock_dense.call_args.kwargs
    assert dense_call_kwargs.get("exercise_filter") == "bench", (
        f"dense_search must receive exercise_filter='bench', got {dense_call_kwargs.get('exercise_filter')!r}"
    )

    # sparse_search must have been called with exercise_filter="bench"
    sparse_call_kwargs = sparse_service.sparse_search.call_args.kwargs
    assert sparse_call_kwargs.get("exercise_filter") == "bench", (
        f"sparse_search must receive exercise_filter='bench', got {sparse_call_kwargs.get('exercise_filter')!r}"
    )


# ---------------------------------------------------------------------------
# Test 22 — hybrid_search without exercise_filter passes None to both legs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_search_no_exercise_filter_passes_none_to_legs() -> None:
    """When exercise_filter is not specified, both legs must receive exercise_filter=None."""
    from app.services.retrieval import RetrievalService
    from app.services.sparse_retrieval import SparseRetrievalService

    cohere_client = _make_cohere_client(
        vectors=[[0.1] * 1024],
        rerank_results=[(0, 0.9)],
    )
    qdrant_client = _make_qdrant_client()

    sparse_service = MagicMock(spec=SparseRetrievalService)
    sparse_service.sparse_search = AsyncMock(return_value=[])

    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        sparse_service=sparse_service,
    )

    dense_result = [_make_retrieved_context(chunk_id="c1" + "x" * 62, paper_id="p1")]

    mock_dense = AsyncMock(return_value=dense_result)
    with patch.object(service, "dense_search", mock_dense):
        await service.hybrid_search(
            "deadlift lockout",
            collection="coach_brain",
            top_k=5,
        )

    dense_call_kwargs = mock_dense.call_args.kwargs
    assert dense_call_kwargs.get("exercise_filter") is None

    sparse_call_kwargs = sparse_service.sparse_search.call_args.kwargs
    assert sparse_call_kwargs.get("exercise_filter") is None


# ---------------------------------------------------------------------------
# P2-020 — Rerank timeout handling (FR-AICP-09)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_search_returns_fused_on_rerank_timeout() -> None:
    """When Cohere rerank exceeds _RERANK_TIMEOUT_S, return RRF-fused results.

    P2-020: 3-second timeout on rerank, graceful fallback to RRF scores.
    """
    import asyncio

    from app.services.retrieval import RetrievalService

    # Two fused results with known RRF scores
    ctx_a = _make_retrieved_context(chunk_id="a" * 64, score=0.80, text="Alpha paper.")
    ctx_b = _make_retrieved_context(chunk_id="b" * 64, score=0.60, text="Beta paper.")

    cohere_client = _make_cohere_client()
    cohere_client.rerank = AsyncMock(side_effect=asyncio.TimeoutError)

    qdrant_client = _make_qdrant_client()
    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
    )

    # Patch dense_search to return our known results; fuse will pass them through
    with patch.object(service, "dense_search", AsyncMock(return_value=[ctx_a, ctx_b])):
        results = await service.hybrid_search("squat depth", top_k=5)

    # Should get results back (from RRF fuse) even though rerank timed out
    assert len(results) >= 1
    # Scores should be RRF scores (not reranker scores)
    for r in results:
        assert r.score > 0


@pytest.mark.asyncio
async def test_hybrid_search_rerank_timeout_respects_top_n() -> None:
    """On rerank timeout, return at most effective_top_n results from fused list."""
    import asyncio

    from app.services.retrieval import RetrievalService

    contexts = [
        _make_retrieved_context(chunk_id=f"{chr(97 + i)}" * 64, score=0.9 - i * 0.1)
        for i in range(5)
    ]

    cohere_client = _make_cohere_client()
    cohere_client.rerank = AsyncMock(side_effect=asyncio.TimeoutError)

    qdrant_client = _make_qdrant_client()
    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
    )

    with patch.object(service, "dense_search", AsyncMock(return_value=contexts)):
        results = await service.hybrid_search("squat depth", top_k=10, rerank_top_n=3)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_hybrid_search_normal_path_unaffected_by_timeout_wrapper() -> None:
    """The asyncio.wait_for wrapper must not alter the normal rerank path."""
    from app.services.retrieval import RetrievalService

    ctx = _make_retrieved_context(chunk_id="a" * 64, score=0.80)

    cohere_client = _make_cohere_client(rerank_results=[(0, 0.95)])
    qdrant_client = _make_qdrant_client()
    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
    )

    with patch.object(service, "dense_search", AsyncMock(return_value=[ctx])):
        results = await service.hybrid_search("squat depth", top_k=5)

    assert len(results) == 1
    # Score should be the reranker score, not the RRF score
    assert results[0].score == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# Test — additional_filters forwarded to Qdrant alongside exercise_filter
# (P2-026 prerequisite: status="active" filter on coach_brain queries)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_search_additional_filters_forwarded_to_qdrant() -> None:
    """When additional_filters is provided alongside exercise_filter, all
    conditions must be merged into a single Filter(must=[...])."""
    from qdrant_client import models as qdrant_models

    from app.services.retrieval import RetrievalService

    cohere_client = _make_cohere_client()
    qdrant_client = _make_qdrant_client()

    service = RetrievalService(cohere_client=cohere_client, qdrant_client=qdrant_client)

    status_filter = qdrant_models.FieldCondition(
        key="status",
        match=qdrant_models.MatchValue(value="active"),
    )

    await service.dense_search(
        "squat depth cue",
        collection="coach_brain",
        exercise_filter="squat",
        additional_filters=[status_filter],
    )

    qdrant_client.query_points.assert_called_once()
    call_kwargs = qdrant_client.query_points.call_args.kwargs

    query_filter = call_kwargs.get("query_filter")
    assert query_filter is not None, "query_filter must be passed when filters are set"
    assert isinstance(query_filter, qdrant_models.Filter)

    must_conditions = query_filter.must
    assert must_conditions is not None and len(must_conditions) == 2, (
        f"Filter must contain 2 must conditions (exercise + status), got {len(must_conditions or [])}"
    )

    keys = {c.key for c in must_conditions}
    assert keys == {"exercise", "status"}, f"Expected exercise + status filters, got {keys}"


# ---------------------------------------------------------------------------
# Test — hybrid_search with rerank=False returns RRF-fused results directly
# (P2-026 prerequisite: orchestrator calls hybrid_search(rerank=False)
#  and does its own cross-collection rerank)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_search_skip_rerank_returns_rrf_fused_results() -> None:
    """When rerank=False, hybrid_search must return RRF-fused results without
    calling cohere_client.rerank."""
    from app.services.retrieval import RetrievalService

    ctx_dense = _make_retrieved_context(chunk_id="d" * 64, score=0.90)
    ctx_sparse = _make_retrieved_context(chunk_id="s" * 64, score=0.70, text="BM25 result")

    cohere_client = _make_cohere_client()
    qdrant_client = _make_qdrant_client()
    sparse_svc = MagicMock()
    sparse_svc.sparse_search = AsyncMock(return_value=[ctx_sparse])

    service = RetrievalService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        sparse_service=sparse_svc,
    )

    with patch.object(service, "dense_search", AsyncMock(return_value=[ctx_dense])):
        results = await service.hybrid_search("squat depth", top_k=5, rerank=False)

    # Should have results from RRF fusion
    assert len(results) >= 1
    # Cohere rerank must NOT have been called
    cohere_client.rerank.assert_not_called()
