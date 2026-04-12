"""DualCollectionOrchestrator — concurrent papers_rag + coach_brain retrieval.

Requirements: FR-BRAIN-04, FR-BRAIN-05, FR-AICP-09

Orchestrates the dual-collection RAG pipeline:
1. Query both papers_rag and coach_brain concurrently via asyncio.gather
   (each call uses hybrid_search with rerank=False to get RRF-fused results).
2. Merge both result lists, deduplicate by chunk.id.
3. Single Cohere Rerank 4.0 call on the merged set (ADR-RAG-01).
4. Classify retrieval_source based on top coach_brain score (FR-BRAIN-05).
5. Return RetrievalResult with primary/supplementary split.

Architecture notes:
- Sits above RetrievalService — pure orchestration, no Qdrant/Cohere calls
  of its own except the single cross-collection rerank.
- Per-collection reranking is skipped (rerank=False) to avoid triple rerank cost.
- Coach brain queries always filter by status="active" (FR-BRAIN-04).
- Empty coach_brain → top score 0.0 → papers_only_fallback (P2-027 cold-start).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.schemas.rag import RetrievalResult, RetrievedContext

if TYPE_CHECKING:
    from app.services.cohere_client import CohereEmbedClient
    from app.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)

# FR-BRAIN-05 thresholds — named constants, never inline magic numbers.
_COACH_BRAIN_PRIMARY_THRESHOLD: float = 0.82
_HYBRID_FLOOR_THRESHOLD: float = 0.65

# P2-020: rerank timeout before falling back to RRF-fused results
_RERANK_TIMEOUT_S: float = 3.0


class DualCollectionOrchestrator:
    """Concurrent dual-collection retrieval with threshold-based routing.

    Parameters
    ----------
    retrieval_service:
        Configured RetrievalService instance (handles per-collection
        dense + sparse + RRF fusion).
    cohere_client:
        CohereEmbedClient for the cross-collection Rerank 4.0 call.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        cohere_client: CohereEmbedClient,
    ) -> None:
        self._retrieval = retrieval_service
        self._cohere = cohere_client

    async def retrieve(
        self,
        query: str,
        exercise_type: str,
        top_k: int = 10,
        rerank_top_n: int = 5,
    ) -> RetrievalResult:
        """Query both collections concurrently, rerank merged results, route.

        Parameters
        ----------
        query:
            Natural-language retrieval query from the coaching context.
        exercise_type:
            Exercise type filter applied to both collections (FR-AICP-12).
        top_k:
            Per-collection result limit before merging.
        rerank_top_n:
            Final result count after cross-collection reranking.

        Returns
        -------
        RetrievalResult
            Contains primary contexts, supplementary contexts, and the
            retrieval_source classification.
        """
        # Step 1: build coach_brain status filter (FR-BRAIN-04).
        # Deferred import follows ADR-032 source-patch pattern.
        from qdrant_client import models as qdrant_models

        status_filter = qdrant_models.FieldCondition(
            key="status",
            match=qdrant_models.MatchValue(value="active"),
        )

        # Step 2: concurrent collection queries (FR-AICP-09).
        # rerank=False — we do ONE cross-collection rerank below (ADR-RAG-01).
        papers_results, brain_results = await asyncio.gather(
            self._retrieval.hybrid_search(
                query,
                collection="papers_rag",
                top_k=top_k,
                exercise_filter=exercise_type,
                rerank=False,
            ),
            self._retrieval.hybrid_search(
                query,
                collection="coach_brain",
                top_k=top_k,
                exercise_filter=exercise_type,
                additional_filters=[status_filter],
                rerank=False,
            ),
        )

        logger.debug(
            "dual_collection: papers=%d brain=%d for exercise=%r",
            len(papers_results),
            len(brain_results),
            exercise_type,
        )

        # Step 3: merge + deduplicate by chunk.id.
        seen: set[str] = set()
        merged: list[RetrievedContext] = []
        for ctx in papers_results + brain_results:
            if ctx.chunk.id not in seen:
                seen.add(ctx.chunk.id)
                merged.append(ctx)

        if not merged:
            logger.debug("dual_collection: no results from either collection")
            return RetrievalResult(
                primary=[],
                supplementary=[],
                retrieval_source="papers_only_fallback",
            )

        # Step 4: single cross-collection Cohere Rerank 4.0 (ADR-RAG-01).
        texts = [ctx.chunk.text for ctx in merged]
        reranked: list[RetrievedContext] | None = None

        try:
            rerank_pairs = await asyncio.wait_for(
                self._cohere.rerank(
                    query,
                    texts,
                    top_n=min(rerank_top_n, len(merged)),
                ),
                timeout=_RERANK_TIMEOUT_S,
            )
            reranked = []
            for original_idx, relevance_score in rerank_pairs:
                if original_idx < len(merged):
                    ctx = merged[original_idx]
                    reranked.append(ctx.model_copy(update={"score": relevance_score}))
        except asyncio.TimeoutError:
            logger.warning(
                "dual_collection: Cohere rerank timed out after %.1fs "
                "— using RRF-fused results directly. "
                "TODO(P2-034): log this event to Langfuse.",
                _RERANK_TIMEOUT_S,
            )

        # On timeout, use merged RRF results (no coach_brain scores available
        # from reranker, so route to papers_only_fallback).
        if reranked is None:
            return RetrievalResult(
                primary=[ctx for ctx in merged if ctx.collection == "papers_rag"][:rerank_top_n],
                supplementary=[ctx for ctx in merged if ctx.collection == "coach_brain"],
                retrieval_source="papers_only_fallback",
            )

        # Step 5: classify retrieval_source (FR-BRAIN-05).
        top_brain_score = max(
            (ctx.score for ctx in reranked if ctx.collection == "coach_brain"),
            default=0.0,
        )

        logger.debug(
            "dual_collection: top_brain_score=%.3f threshold_primary=%.2f threshold_hybrid=%.2f",
            top_brain_score,
            _COACH_BRAIN_PRIMARY_THRESHOLD,
            _HYBRID_FLOOR_THRESHOLD,
        )

        if top_brain_score >= _COACH_BRAIN_PRIMARY_THRESHOLD:
            # Coach Brain is primary source, papers are supplementary
            primary = [ctx for ctx in reranked if ctx.collection == "coach_brain"]
            supplementary = [ctx for ctx in reranked if ctx.collection == "papers_rag"]
            retrieval_source = "coach_brain_primary"
        elif top_brain_score >= _HYBRID_FLOOR_THRESHOLD:
            # Both contribute to primary (interleaved, rerank-ordered)
            primary = reranked
            supplementary = []
            retrieval_source = "hybrid_brain_supplementary"
        else:
            # Papers only — coach brain results are supplementary
            primary = [ctx for ctx in reranked if ctx.collection == "papers_rag"]
            supplementary = [ctx for ctx in reranked if ctx.collection == "coach_brain"]
            retrieval_source = "papers_only_fallback"

        logger.info(
            "dual_collection: retrieval_source=%r primary=%d supplementary=%d",
            retrieval_source,
            len(primary),
            len(supplementary),
        )

        return RetrievalResult(
            primary=primary,
            supplementary=supplementary,
            retrieval_source=retrieval_source,  # type: ignore[arg-type]
        )
