"""RetrievalService — dense vector retrieval from Qdrant (P2-008).

Requirements: FR-AICP-09

Implements dense (Cohere embed-v4) retrieval only.
BM25 sparse retrieval is P2-009; RRF fusion is P2-010.

Flow:
1. Embed the query text via Cohere embed-v4 with input_type=SEARCH_QUERY.
2. Query the target Qdrant collection using the 1024-dim dense vector.
3. Parse each ScoredPoint payload into ChunkPayload and wrap in RetrievedContext.

Architecture notes:
- Inject CohereEmbedClient and QdrantClientWrapper via constructor — never
  reach for the module-level singletons inside service methods.  This keeps
  the service fully testable without environment variables (ADR-032).
- The collection parameter defaults to "papers_rag" but accepts "coach_brain"
  too — the same service class handles both (ADR-BRAIN-01).
- with_payload=True is always requested so ChunkPayload fields are available
  for reranking and citation rendering downstream.
"""

from __future__ import annotations

import logging

from app.schemas.rag import ChunkPayload, CollectionName, RetrievedContext
from app.services.cohere_client import CohereEmbedClient, EmbedInputType
from app.services.qdrant import QdrantClientWrapper

logger = logging.getLogger(__name__)

# Default collection — see ADR-BRAIN-01 for dual-collection rationale.
_DEFAULT_COLLECTION: CollectionName = "papers_rag"


class RetrievalService:
    """Dense vector retrieval from Qdrant using Cohere embed-v4.

    Parameters
    ----------
    cohere_client:
        Configured CohereEmbedClient instance (embed + rerank capability).
    qdrant_client:
        Configured QdrantClientWrapper pointing at the target Qdrant cluster.
    """

    def __init__(
        self,
        cohere_client: CohereEmbedClient,
        qdrant_client: QdrantClientWrapper,
    ) -> None:
        self._cohere = cohere_client
        self._qdrant = qdrant_client

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
