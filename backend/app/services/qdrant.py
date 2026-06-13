"""QdrantClientWrapper — async wrapper around qdrant-client AsyncQdrantClient.

Implements P2-002 (FR-AICP-09, ADR-BRAIN-01, ADR-RAG-03, ADR-P2-001).

Architecture notes:
- Both collections use 1024-dim dense vectors (ADR-RAG-03) and server-side
  BM25 sparse vectors named 'bm25' with IDF modifier (ADR-BRAIN-03).
- coach_brain gets keyword payload indexes on 'exercise' and 'status' so
  filters at query time are fast without a full-scan.
- The factory ``get_qdrant_client`` follows the two-state cache pattern from
  ``api/v1/analyses.py::_make_storage_service`` so the underlying gRPC/HTTP
  connection is reused across requests (ADR-032).
- ``qdrant_client.AsyncQdrantClient`` is imported inside ``get_qdrant_client``
  (not at module top) so that ``patch("qdrant_client.AsyncQdrantClient")``
  intercepts the lookup at call time.  This is the ADR-032 source-patch
  pattern — patching the top-level ``from qdrant_client import AsyncQdrantClient``
  binding would only replace the module attribute, not the already-bound local
  name in this module's namespace.

Usage::

    from app.services.qdrant import get_qdrant_client

    wrapper = await get_qdrant_client()
    if wrapper is not None:
        await wrapper.ensure_collections()
        ok = await wrapper.ping()
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Sequence

from qdrant_client.models import (
    Distance,
    Modifier,
    PayloadSchemaType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Collection names — single source of truth (ADR-BRAIN-01)
# ---------------------------------------------------------------------------

COLLECTION_PAPERS_RAG = "papers_rag"
COLLECTION_COACH_BRAIN = "coach_brain"


def paper_points_filter(paper_id: str) -> Any:
    """Build the Qdrant Filter selecting all papers_rag points for one paper.

    Single source of truth for the 3 call sites that select a paper's points:
    the expert metadata PATCH, the restamp retry task, and the #222 payload
    backfill script — so the ``paper_id`` payload key never drifts between them
    (issue #258, #251 /code-review LOW).
    """
    from qdrant_client import models as qdrant_models

    return qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="paper_id",
                match=qdrant_models.MatchValue(value=str(paper_id)),
            )
        ]
    )

# Vector dimensions — cross-cutting invariant from ADR-RAG-03
_VECTOR_SIZE = 1024

# Sparse vector name used for server-side BM25 (ADR-BRAIN-03)
_SPARSE_VECTOR_NAME = "bm25"

# ---------------------------------------------------------------------------
# Module-level factory cache (ADR-032 two-state pattern)
# ---------------------------------------------------------------------------

_qdrant_client_cache: QdrantClientWrapper | None = None
_qdrant_client_cache_initialized: bool = False


async def get_qdrant_client() -> QdrantClientWrapper | None:
    """Build and cache a ``QdrantClientWrapper`` backed by ``AsyncQdrantClient``.

    Reads ``QDRANT_URL`` and ``QDRANT_API_KEY`` from environment variables.
    Returns ``None`` when ``QDRANT_URL`` is not set (tests, local dev without
    Qdrant Cloud configured) — callers must guard on None.

    The constructed wrapper is cached at module level so repeated calls return
    the same instance without reconnecting.

    ``qdrant_client.AsyncQdrantClient`` is imported inside this function body
    (not at module top) so that tests can patch it via
    ``patch("qdrant_client.AsyncQdrantClient")`` and intercept the constructor
    call at runtime (ADR-032 source-patch pattern).

    Regression coverage: ``tests/unit/test_qdrant_client.py::TestGetQdrantClientFactory``.
    """
    global _qdrant_client_cache, _qdrant_client_cache_initialized

    if _qdrant_client_cache_initialized:
        return _qdrant_client_cache

    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")

    if not qdrant_url:
        logger.warning(
            "get_qdrant_client: QDRANT_URL not set — Qdrant unavailable"
        )
        _qdrant_client_cache = None
        _qdrant_client_cache_initialized = True
        return None

    try:
        # Deferred import so patch("qdrant_client.AsyncQdrantClient") intercepts
        # the constructor call at test time (ADR-032).
        import qdrant_client as _qdrant_client_mod

        inner = _qdrant_client_mod.AsyncQdrantClient(
            url=qdrant_url, api_key=qdrant_api_key
        )
        _qdrant_client_cache = QdrantClientWrapper(inner)
    except Exception as exc:
        logger.warning("get_qdrant_client: failed to construct client: %s", exc)
        _qdrant_client_cache = None

    _qdrant_client_cache_initialized = True
    return _qdrant_client_cache


# ---------------------------------------------------------------------------
# QdrantClientWrapper
# ---------------------------------------------------------------------------


class QdrantClientWrapper:
    """Async wrapper around ``qdrant_client.AsyncQdrantClient``.

    Provides the minimal surface needed by Phase 2:

    - ``ensure_collections()`` — idempotent provisioning of both collections
    - ``ping()`` — health check returning ``bool``
    - ``upsert_points()`` — thin passthrough to ``client.upsert``
    - ``query_points()`` — thin passthrough to ``client.query_points``

    Batch 2/3 will add higher-level retrieval methods directly to this class.

    Parameters
    ----------
    client:
        A live ``AsyncQdrantClient`` instance. Injected rather than constructed
        internally so tests can supply a mock.
    """

    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Provisioning
    # ------------------------------------------------------------------

    async def ensure_collections(self) -> None:
        """Idempotently create both Qdrant collections if they don't exist.

        Safe to call multiple times — a no-op if both collections already
        exist. This is the entrypoint for the one-shot provisioning script
        and the startup path once Phase 2 worker is wired.

        Collections created:
        - ``papers_rag``: 1024-dim cosine + BM25 sparse + keyword indexes on
          ``exercise`` and ``sex_applicability`` (ADR-RAG-03, ADR-BRAIN-03,
          FR-AICP-15 retrieval filter, FR-AICP-12 sex filter — issue #222)
        - ``coach_brain``: same vector config + keyword indexes on
          ``exercise`` and ``status`` (ADR-BRAIN-01, FR-BRAIN-04)
        """
        await self._ensure_collection(
            COLLECTION_PAPERS_RAG,
            payload_index_fields=("exercise", "sex_applicability"),
        )
        await self._ensure_collection(
            COLLECTION_COACH_BRAIN, payload_index_fields=("exercise", "status")
        )

    async def _ensure_collection(
        self, name: str, *, payload_index_fields: tuple[str, ...]
    ) -> None:
        exists = await self._client.collection_exists(collection_name=name)
        if exists:
            logger.info("ensure_collections: %r already exists — ensuring indexes", name)
        else:
            logger.info("ensure_collections: creating collection %r", name)
            await self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=_VECTOR_SIZE,
                    distance=Distance.COSINE,
                    on_disk=False,
                ),
                sparse_vectors_config={
                    _SPARSE_VECTOR_NAME: SparseVectorParams(
                        index=SparseIndexParams(on_disk=False),
                        modifier=Modifier.IDF,
                    )
                },
            )
            logger.info("ensure_collections: created %r", name)

        # Ensure payload indexes exist for the given fields — Qdrant ignores
        # duplicate index creation, so this is safe to run on existing
        # collections. This also recovers from collections created by a
        # previous version of this code that didn't provision the needed
        # indexes (prod papers_rag pre-fix). The call is a no-op on an empty
        # tuple; the iteration in _ensure_payload_indexes handles that.
        await self._ensure_payload_indexes(name, payload_index_fields)

    async def _ensure_payload_indexes(
        self, collection_name: str, fields: tuple[str, ...]
    ) -> None:
        """Add keyword payload indexes for query filters on a collection.

        Idempotent: per-field try/except swallows duplicate-index errors so
        this can safely be re-run against existing collections.
        """
        for field in fields:
            try:
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info(
                    "ensure_collections: created payload index on %r.%s",
                    collection_name,
                    field,
                )
            except Exception as exc:
                # Qdrant returns 4xx when the index already exists. Swallow and
                # continue — the index we need is present, which is the desired
                # end state. This branch is the idempotent-rerun path, not an
                # unexpected failure.
                logger.info(
                    "ensure_collections: index on %r.%s already present or unchanged (%s)",
                    collection_name,
                    field,
                    exc.__class__.__name__,
                )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Call the Qdrant health endpoint.

        Returns ``True`` if the cluster responds, ``False`` on any exception.
        Does NOT raise — callers (especially the keepalive cron) must be able
        to handle ``False`` gracefully.
        """
        try:
            await self._client.info()
            return True
        except Exception as exc:
            logger.debug("ping: Qdrant health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Thin passthroughs (Phase 2 Batch 2/3 will add higher-level methods)
    # ------------------------------------------------------------------

    async def upsert_points(
        self, collection: str, points: Sequence[Any]
    ) -> Any:
        """Thin passthrough to ``AsyncQdrantClient.upsert``.

        Parameters
        ----------
        collection:
            Target collection name (``papers_rag`` or ``coach_brain``).
        points:
            Sequence of ``PointStruct`` instances to upsert.
        """
        return await self._client.upsert(
            collection_name=collection, points=points
        )

    async def set_payload(
        self, collection: str, payload: dict, points_filter: Any
    ) -> None:
        """Overwrite payload keys on all points matching points_filter (no re-embed).

        Thin passthrough to ``AsyncQdrantClient.set_payload``. Used by the
        corpus backfill (issue #222) to stamp ``exercise`` + ``sex_applicability``
        onto existing ``papers_rag`` points without re-running embedding.

        Parameters
        ----------
        collection:
            Target collection name.
        payload:
            Mapping of payload keys → values to set/overwrite on matched points.
        points_filter:
            A Qdrant ``Filter`` selecting which points to update.
        """
        await self._client.set_payload(
            collection_name=collection, payload=payload, points=points_filter,
        )

    async def query_points(
        self, collection: str, query: Any, **kwargs: Any
    ) -> Any:
        """Thin passthrough to ``AsyncQdrantClient.query_points``.

        Parameters
        ----------
        collection:
            Target collection name.
        query:
            Dense query vector (list[float] of length 1024) or a Qdrant
            ``Query`` object for hybrid queries.
        **kwargs:
            Forwarded verbatim to ``AsyncQdrantClient.query_points``.
        """
        return await self._client.query_points(
            collection_name=collection, query=query, **kwargs
        )
