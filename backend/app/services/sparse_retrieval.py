"""SparseRetrievalService — BM25 sparse vector search via Qdrant server-side index.

Requirements: FR-AICP-09 (hybrid RAG pipeline — sparse leg of dense+BM25 hybrid).

Architecture notes:
- Qdrant collections are configured with a sparse vector named "bm25" using
  SparseVectorParams(modifier=Modifier.IDF). The IDF weighting is applied
  server-side; the client supplies term indices and raw TF weights.
- Query-time tokenization: whitespace split + lowercasing + mmh3 hashing.
  Term hashes map query tokens to integer indices in the same vocabulary
  space as the indexed sparse vectors (which use the same hashing scheme
  at ingest time). Stopwords are not filtered — the IDF modifier down-weights
  common terms automatically.
- No Cohere dependency. BM25 is purely Qdrant server-side (ADR-BRAIN-03).
- The `using="bm25"` parameter tells Qdrant to route the query through the
  named sparse index rather than the default dense vector index.

Tokenization vocabulary contract:
  index = abs(mmh3.hash(token.lower())) % _VOCAB_SIZE

  _VOCAB_SIZE = 2**17 (131072) — large enough to avoid catastrophic collisions
  for a 300–600 paper corpus while keeping the sparse vector dimension bounded.

Query vector construction:
  For each unique token in the query, compute TF (raw count / total_tokens).
  Pass indices=[...] and values=[...] as models.SparseVector to query_points.
  The server's IDF modifier multiplies each value by IDF(token) at query time.
"""

from __future__ import annotations

import logging
from collections import Counter

import mmh3

from app.schemas.rag import ChunkPayload, CollectionName, RetrievedContext
from app.services.qdrant import QdrantClientWrapper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Vocabulary size for mmh3 token-to-index mapping.
# Must match the value used at index/ingest time.
_VOCAB_SIZE = 2**17  # 131072

# Default collection for RAG paper retrieval
_DEFAULT_COLLECTION: CollectionName = "papers_rag"

# Sparse vector name — matches _SPARSE_VECTOR_NAME in qdrant.py (ADR-BRAIN-03)
_SPARSE_VECTOR_NAME = "bm25"


# ---------------------------------------------------------------------------
# SparseRetrievalService
# ---------------------------------------------------------------------------


class SparseRetrievalService:
    """BM25 sparse vector search against a Qdrant collection.

    Uses Qdrant's server-side BM25 index (sparse vector named "bm25" with
    Modifier.IDF). The client tokenizes the query text and sends a TF-weighted
    SparseVector; the server applies IDF weighting and returns ranked results.

    Parameters
    ----------
    qdrant_client:
        A live ``QdrantClientWrapper`` instance.
    """

    def __init__(self, qdrant_client: QdrantClientWrapper) -> None:
        self._qdrant = qdrant_client

    async def sparse_search(
        self,
        query: str,
        collection: CollectionName = _DEFAULT_COLLECTION,
        top_k: int = 10,
    ) -> list[RetrievedContext]:
        """BM25 sparse vector search using Qdrant's server-side sparse index.

        Tokenizes the query text, constructs a ``SparseVector`` of TF-weighted
        term indices, and submits it to Qdrant with ``using="bm25"`` so that
        the server applies IDF weighting via the configured ``Modifier.IDF``.

        Parameters
        ----------
        query:
            Raw query text (e.g. "squat knee valgus depth").
        collection:
            Target collection name ("papers_rag" or "coach_brain").
        top_k:
            Maximum number of results to return.

        Returns
        -------
        list[RetrievedContext]
            Retrieved chunks ordered by BM25 relevance score (highest first).
            Empty list if the query is blank or produces no results.
        """
        sparse_vector = _build_sparse_vector(query)
        if sparse_vector is None:
            logger.debug("sparse_search: empty query — returning no results")
            return []

        # Deferred import follows ADR-032 source-patch pattern so tests can
        # patch qdrant_client.models.SparseVector at call time.
        from qdrant_client import models as qdrant_models

        response = await self._qdrant.query_points(
            collection=collection,
            query=qdrant_models.SparseVector(
                indices=sparse_vector["indices"],
                values=sparse_vector["values"],
            ),
            using=_SPARSE_VECTOR_NAME,
            limit=top_k,
            with_payload=True,
        )

        return _parse_response(response, collection)


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions, importable for unit tests)
# ---------------------------------------------------------------------------


def _build_sparse_vector(
    text: str,
) -> dict[str, list[int] | list[float]] | None:
    """Tokenize ``text`` and produce TF-weighted sparse vector indices/values.

    Tokenization: whitespace split, lowercase. mmh3 hashing maps each unique
    token to a non-negative integer index in [0, _VOCAB_SIZE).

    TF weight = raw_count / total_tokens — so a 4-word query where "squat"
    appears twice gives squat a TF of 0.5. The server multiplies each value
    by IDF(token) via Modifier.IDF.

    Parameters
    ----------
    text:
        Raw query or document text.

    Returns
    -------
    dict with "indices" and "values" keys, or None if the text is blank.
    """
    tokens = text.lower().split()
    if not tokens:
        return None

    total = len(tokens)
    counts = Counter(tokens)

    indices: list[int] = []
    values: list[float] = []

    for token, count in counts.items():
        # abs() prevents negative hash values; % _VOCAB_SIZE bounds the index
        idx = abs(mmh3.hash(token)) % _VOCAB_SIZE
        tf = count / total
        indices.append(idx)
        values.append(tf)

    return {"indices": indices, "values": values}


def _parse_response(
    response: object,
    collection: CollectionName,
) -> list[RetrievedContext]:
    """Convert a Qdrant ``QueryResponse`` into ``list[RetrievedContext]``.

    Qdrant returns a ``QueryResponse`` object whose ``.points`` attribute is
    a ``list[ScoredPoint]``. Each ``ScoredPoint`` carries:
    - ``.score`` — BM25 relevance score (post IDF weighting)
    - ``.payload`` — dict matching ``ChunkPayload`` fields

    Points whose payload cannot be validated as ``ChunkPayload`` are skipped
    with a warning rather than crashing the retrieval path.

    Parameters
    ----------
    response:
        The raw return value of ``QdrantClientWrapper.query_points``.
    collection:
        The collection name to stamp on each ``RetrievedContext``.

    Returns
    -------
    list[RetrievedContext]
        Parsed contexts in the order returned by Qdrant (highest score first).
    """
    results: list[RetrievedContext] = []

    points = getattr(response, "points", [])
    for point in points:
        payload = getattr(point, "payload", None)
        score = getattr(point, "score", 0.0)

        if not payload:
            logger.warning(
                "sparse_search: point %s has no payload — skipping",
                getattr(point, "id", "?"),
            )
            continue

        try:
            chunk = ChunkPayload.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "sparse_search: failed to parse payload for point %s: %s — skipping",
                getattr(point, "id", "?"),
                exc,
            )
            continue

        results.append(
            RetrievedContext(
                chunk=chunk,
                score=float(score),
                collection=collection,
            )
        )

    return results
