"""CohereEmbedClient — Cohere embed-v4.0 + rerank-v4.0-pro wrapper (P2-003).

Requirements: FR-AICP-09, ADR-RAG-01, ADR-RAG-03

SDK: cohere 6.1.0 — AsyncClientV2 is async-native; no asyncio.to_thread needed.

Verified SDK shape (cohere 6.1.0):
  - cohere.AsyncClientV2 is available at package root.
  - embed() is an async method on AsyncClientV2.
  - Response: EmbedByTypeResponse — float vectors at response.embeddings.float_
  - rerank() is an async method on AsyncClientV2.
  - Response: V2RerankResponse — results are list[V2RerankResponseResultsItem]
    with .index (int) and .relevance_score (float).

Critical constraints (load-bearing — do not deviate):
  - Model for embedding: "embed-v4.0"
  - Model for reranking: "rerank-v4.0-pro"  (ADR-RAG-01)
  - output_dimension=1024 MUST be passed on every embed call (ADR-RAG-03)
    Omitting it defaults to 1536 and causes Qdrant dimension mismatch on upsert.
  - Batch limit: 96 texts per embed API call
  - input_type="search_document" when indexing, "search_query" at query time
"""

from __future__ import annotations

import logging
import os
from enum import StrEnum

import cohere

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — pinned per ADRs, never magic strings at call sites
# ---------------------------------------------------------------------------

_EMBED_MODEL = "embed-v4.0"
_RERANK_MODEL = "rerank-v4.0-pro"
_OUTPUT_DIMENSION = 1024
_EMBED_BATCH_SIZE = 96

# ---------------------------------------------------------------------------
# Input type enum
# ---------------------------------------------------------------------------


class EmbedInputType(StrEnum):
    SEARCH_DOCUMENT = "search_document"
    SEARCH_QUERY = "search_query"


# ---------------------------------------------------------------------------
# Client wrapper
# ---------------------------------------------------------------------------


class CohereEmbedClient:
    """Async wrapper around cohere.AsyncClientV2 for embed + rerank operations.

    Use get_cohere_client() to obtain the module-level cached singleton.
    Construct directly (CohereEmbedClient(api_key=...)) in tests via
    __new__ + monkey-patch of _client attribute.
    """

    def __init__(self, api_key: str) -> None:
        self._client = cohere.AsyncClientV2(api_key=api_key)

    async def embed_batch(
        self,
        texts: list[str],
        *,
        input_type: EmbedInputType,
    ) -> list[list[float]]:
        """Embed a batch of texts into 1024-dim float vectors.

        Chunks the input internally into sub-batches of at most 96 texts
        and issues one API call per chunk (Cohere batch limit). Results are
        concatenated in input order before returning.

        Always passes output_dimension=1024 per ADR-RAG-03. Omitting this
        would default to 1536 dims and cause Qdrant dimension mismatch on
        every upsert. This is the single most dangerous footgun in Phase 2.

        Parameters
        ----------
        texts:
            The strings to embed. May be any length; chunking is handled
            internally.
        input_type:
            EmbedInputType.SEARCH_DOCUMENT when indexing corpus chunks.
            EmbedInputType.SEARCH_QUERY at query time.

        Returns
        -------
        list[list[float]]
            One 1024-dimensional float vector per input text, in input order.

        Raises
        ------
        Exception
            Any Cohere API error propagates to the caller. The caller is
            responsible for retry / fallback decisions.
        """
        all_embeddings: list[list[float]] = []

        for chunk_start in range(0, len(texts), _EMBED_BATCH_SIZE):
            chunk = texts[chunk_start : chunk_start + _EMBED_BATCH_SIZE]

            response = await self._client.embed(
                model=_EMBED_MODEL,
                texts=chunk,
                input_type=input_type.value,
                output_dimension=_OUTPUT_DIMENSION,
                embedding_types=["float"],
            )

            float_vecs = response.embeddings.float_
            if float_vecs is None:
                raise ValueError(
                    "Cohere embed response returned None for float embeddings. "
                    "Ensure embedding_types=['float'] is passed and the model "
                    "supports Matryoshka truncation at output_dimension=1024."
                )

            all_embeddings.extend(float_vecs)

        return all_embeddings

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int | None = None,
    ) -> list[tuple[int, float]]:
        """Rerank documents with rerank-v4.0-pro (ADR-RAG-01).

        Used by the hybrid retrieval layer as a cross-collection score
        normaliser — merges results from papers_rag and coach_brain into
        a single ranked list with comparable, content-aware scores.

        Parameters
        ----------
        query:
            The search query string.
        documents:
            The candidate document strings to rerank.
        top_n:
            If provided, only the top N results are returned by the API.
            If None, the API returns all results.

        Returns
        -------
        list[tuple[int, float]]
            List of (original_index_into_documents, relevance_score) sorted
            by relevance_score descending. Index refers to position in the
            input ``documents`` list.

        Raises
        ------
        Exception
            Any Cohere API error propagates to the caller.
        """
        kwargs: dict = dict(
            model=_RERANK_MODEL,
            query=query,
            documents=documents,
        )
        if top_n is not None:
            kwargs["top_n"] = top_n

        response = await self._client.rerank(**kwargs)

        results = sorted(
            response.results,
            key=lambda r: r.relevance_score,
            reverse=True,
        )
        return [(r.index, r.relevance_score) for r in results]


# ---------------------------------------------------------------------------
# Module-level cached factory (ADR-032 pattern)
# ---------------------------------------------------------------------------

_cohere_client_cache: CohereEmbedClient | None = None


def get_cohere_client() -> CohereEmbedClient:
    """Return the module-level cached CohereEmbedClient singleton.

    Reads COHERE_API_KEY from the environment. Raises RuntimeError if the
    key is absent — the caller should ensure the env var is set before the
    service starts.

    Cache is module-level (per process). Tests that need a clean factory
    must reset ``app.services.cohere_client._cohere_client_cache = None``
    before calling this function.

    ADR-032: tests must patch ``cohere.AsyncClientV2`` at its source module
    (not at the consumer) to exercise the real factory path.
    """
    global _cohere_client_cache

    if _cohere_client_cache is not None:
        return _cohere_client_cache

    api_key = os.environ.get("COHERE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "COHERE_API_KEY environment variable is not set. "
            "Phase 2 RAG features require a valid Cohere API key."
        )

    _cohere_client_cache = CohereEmbedClient(api_key=api_key)
    return _cohere_client_cache
