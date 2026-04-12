"""RetrievalService — dense + hybrid retrieval from Qdrant (P2-008, P2-010).

Requirements: FR-AICP-09

Dense retrieval (P2-008):
  Embed the query via Cohere embed-v4 (input_type=SEARCH_QUERY) and issue a
  cosine-similarity query against the Qdrant collection.

Hybrid retrieval (P2-010):
  1. Run dense_search and sparse_search concurrently via asyncio.gather.
  2. Fuse results with Reciprocal Rank Fusion (rrf_fuse, pure function).
  3. Rerank the fused set with Cohere Rerank 4.0 — scores replace RRF scores.
  Return reranked list[RetrievedContext].

Architecture notes:
- Inject CohereEmbedClient, QdrantClientWrapper, and SparseRetrievalService
  via constructor — never reach for module-level singletons inside service
  methods. This keeps the service fully testable without environment variables
  (ADR-032).
- sparse_service is Optional for backwards compat — callers that only need
  dense retrieval (e.g. coach_brain cold-start) need not supply it.
- The collection parameter defaults to "papers_rag" but accepts "coach_brain"
  too — the same service class handles both (ADR-BRAIN-01).
- with_payload=True is always requested so ChunkPayload fields are available
  for reranking and citation rendering downstream.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.schemas.rag import ChunkPayload, CollectionName, RetrievedContext
from app.services.cohere_client import CohereEmbedClient, EmbedInputType
from app.services.qdrant import QdrantClientWrapper

if TYPE_CHECKING:
    from app.services.sparse_retrieval import SparseRetrievalService

logger = logging.getLogger(__name__)

# Default collection — see ADR-BRAIN-01 for dual-collection rationale.
_DEFAULT_COLLECTION: CollectionName = "papers_rag"


# ---------------------------------------------------------------------------
# Pure helper — independently testable, no async, no side effects
# ---------------------------------------------------------------------------


def rrf_fuse(
    dense_results: list[RetrievedContext],
    sparse_results: list[RetrievedContext],
    k: int = 60,
) -> list[RetrievedContext]:
    """Reciprocal Rank Fusion of two ranked result lists.

    Merges dense and sparse retrieval results using the standard RRF formula:

        score(d) = sum over each ranked list L: 1 / (k + rank_L(d))

    where rank_L(d) is the 1-based rank of document d in list L, or absent
    if d does not appear in L.  Documents appearing in both lists accumulate
    contributions from both, so cross-method agreement lifts their rank.

    Deduplication is by ``chunk.id`` (SHA-256 hex digest set at ingest time).
    When the same chunk appears in both lists, it contributes one entry to the
    output with the summed RRF score.

    Parameters
    ----------
    dense_results:
        Ranked list from dense (Cohere embed-v4) retrieval, highest score
        first.  Index 0 = rank 1.
    sparse_results:
        Ranked list from BM25 sparse retrieval, highest score first.
    k:
        RRF smoothing constant.  60 is the standard value from the original
        Cormack et al. 2009 paper and is the default throughout Phase 2.

    Returns
    -------
    list[RetrievedContext]
        Deduplicated list sorted by fused RRF score descending.  The
        ``score`` field on each item is the RRF score (not cosine similarity
        or BM25 score).  The ``collection`` field is preserved from whichever
        list contained the item (dense takes priority on conflict).
    """
    # Map chunk_id → (RetrievedContext, accumulated_rrf_score)
    scores: dict[str, float] = {}
    contexts: dict[str, RetrievedContext] = {}

    for rank_zero, ctx in enumerate(dense_results):
        chunk_id = ctx.chunk.id
        contribution = 1.0 / (k + rank_zero + 1)  # rank is 1-based
        scores[chunk_id] = scores.get(chunk_id, 0.0) + contribution
        if chunk_id not in contexts:
            contexts[chunk_id] = ctx

    for rank_zero, ctx in enumerate(sparse_results):
        chunk_id = ctx.chunk.id
        contribution = 1.0 / (k + rank_zero + 1)
        scores[chunk_id] = scores.get(chunk_id, 0.0) + contribution
        if chunk_id not in contexts:
            contexts[chunk_id] = ctx

    # Build output list with fused scores, sort descending
    fused: list[RetrievedContext] = []
    for chunk_id, rrf_score in scores.items():
        original = contexts[chunk_id]
        # Replace score with the RRF fusion score via model_copy
        fused.append(original.model_copy(update={"score": rrf_score}))

    fused.sort(key=lambda ctx: ctx.score, reverse=True)
    return fused


# ---------------------------------------------------------------------------
# RetrievalService
# ---------------------------------------------------------------------------


class RetrievalService:
    """Dense and hybrid vector retrieval from Qdrant using Cohere embed-v4.

    Parameters
    ----------
    cohere_client:
        Configured CohereEmbedClient instance (embed + rerank capability).
    qdrant_client:
        Configured QdrantClientWrapper pointing at the target Qdrant cluster.
    sparse_service:
        Optional SparseRetrievalService for BM25 hybrid retrieval (P2-009).
        When None, hybrid_search falls back to dense-only + reranking.
    """

    def __init__(
        self,
        cohere_client: CohereEmbedClient,
        qdrant_client: QdrantClientWrapper,
        sparse_service: SparseRetrievalService | None = None,
    ) -> None:
        self._cohere = cohere_client
        self._qdrant = qdrant_client
        self._sparse = sparse_service

    async def dense_search(
        self,
        query: str,
        collection: CollectionName = _DEFAULT_COLLECTION,
        top_k: int = 10,
    ) -> list[RetrievedContext]:
        """Embed ``query`` with Cohere and retrieve top-K dense matches from Qdrant.

        Parameters
        ----------
        query:
            The natural-language query string from the coaching context.
        collection:
            Qdrant collection to search.  Must be "papers_rag" or "coach_brain".
            Defaults to "papers_rag".
        top_k:
            Maximum number of results to return.  Forwarded to Qdrant as ``limit``.

        Returns
        -------
        list[RetrievedContext]
            Ordered list of retrieved chunks, highest cosine similarity first.
            Empty list when Qdrant returns no points.
        """
        # Step 1: embed query — input_type MUST be SEARCH_QUERY, not SEARCH_DOCUMENT.
        # Using the wrong input_type is a silent retrieval-quality bug (no error raised).
        vectors = await self._cohere.embed_batch(
            [query],
            input_type=EmbedInputType.SEARCH_QUERY,
        )
        query_vector: list[float] = vectors[0]

        logger.debug(
            "dense_search: embedded query (%d dims) for collection=%r top_k=%d",
            len(query_vector),
            collection,
            top_k,
        )

        # Step 2: query Qdrant dense index.
        result = await self._qdrant.query_points(
            collection,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        # Step 3: parse ScoredPoints into RetrievedContext.
        contexts: list[RetrievedContext] = []
        for point in result.points:
            payload = point.payload or {}
            chunk = ChunkPayload(
                id=payload.get("id", ""),
                text=payload.get("text", ""),
                paper_id=payload.get("paper_id", ""),
                chunk_index=int(payload.get("chunk_index", 0)),
                section=payload.get("section"),
                token_count=int(payload.get("token_count", 0)),
                quality_tier=payload.get("quality_tier", "L3_observational"),
                title=payload.get("title", ""),
                authors=payload.get("authors", []),
                year=payload.get("year"),
                doi=payload.get("doi"),
            )
            contexts.append(
                RetrievedContext(
                    chunk=chunk,
                    score=float(point.score),
                    collection=collection,
                )
            )

        logger.debug(
            "dense_search: returned %d results from %r",
            len(contexts),
            collection,
        )
        return contexts

    async def hybrid_search(
        self,
        query: str,
        collection: CollectionName = _DEFAULT_COLLECTION,
        top_k: int = 10,
        rrf_k: int = 60,
        rerank_top_n: int | None = None,
    ) -> list[RetrievedContext]:
        """Run dense + sparse retrieval, fuse via RRF, rerank with Cohere Rerank 4.0.

        Flow
        ----
        1. Run ``dense_search`` and ``sparse_search`` concurrently via
           ``asyncio.gather``.  If ``sparse_service`` is None, only dense
           results are used.
        2. Fuse results with ``rrf_fuse`` (Reciprocal Rank Fusion, k=rrf_k).
        3. Pass fused chunk texts to ``cohere_client.rerank`` with
           ``top_n = rerank_top_n or top_k``.
        4. Return reranked ``list[RetrievedContext]`` with Cohere relevance
           scores replacing the RRF scores.

        Parameters
        ----------
        query:
            Natural-language query string.
        collection:
            Qdrant collection to search.  Forwarded to both dense and sparse.
        top_k:
            Number of results to return after reranking.
        rrf_k:
            RRF smoothing constant (default 60 — Cormack et al. 2009).
        rerank_top_n:
            Explicit top-N for Cohere Rerank.  Defaults to ``top_k`` when
            None.

        Returns
        -------
        list[RetrievedContext]
            Reranked contexts ordered by Cohere relevance score descending.
            Scores are Cohere relevance scores, not RRF scores.
        """
        effective_top_n = rerank_top_n if rerank_top_n is not None else top_k

        # Step 1: run dense + sparse concurrently (sparse is no-op if missing)
        if self._sparse is not None:
            dense_results, sparse_results = await asyncio.gather(
                self.dense_search(query, collection=collection, top_k=top_k),
                self._sparse.sparse_search(query, collection=collection, top_k=top_k),
            )
        else:
            logger.debug(
                "hybrid_search: no sparse_service configured — using dense-only fallback"
            )
            dense_results = await self.dense_search(query, collection=collection, top_k=top_k)
            sparse_results = []

        logger.debug(
            "hybrid_search: dense=%d sparse=%d candidates for collection=%r",
            len(dense_results),
            len(sparse_results),
            collection,
        )

        # Step 2: fuse via RRF
        fused = rrf_fuse(dense_results, sparse_results, k=rrf_k)

        if not fused:
            logger.debug("hybrid_search: fused result is empty — returning []")
            return []

        # Step 3: rerank the fused set with Cohere Rerank 4.0
        texts = [ctx.chunk.text for ctx in fused]
        rerank_pairs = await self._cohere.rerank(
            query,
            texts,
            top_n=effective_top_n,
        )

        # Step 4: build output list using reranker ordering and scores
        reranked: list[RetrievedContext] = []
        for original_idx, relevance_score in rerank_pairs:
            if original_idx >= len(fused):
                logger.warning(
                    "hybrid_search: reranker returned index %d but fused list has %d items — skipping",
                    original_idx,
                    len(fused),
                )
                continue
            ctx = fused[original_idx]
            reranked.append(ctx.model_copy(update={"score": relevance_score}))

        logger.debug(
            "hybrid_search: returning %d reranked results from %r",
            len(reranked),
            collection,
        )
        return reranked
