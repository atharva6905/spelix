"""IngestionService — document ingestion pipeline for Phase 2 RAG.

Requirements: FR-AICP-09 (hybrid RAG pipeline), FR-RAGK-01 (corpus ingestion).
ADR reference: ADR-RAG-02.

Pipeline stages:
    text input → chunk → embed (Cohere embed-v4.0) → upsert (Qdrant papers_rag)

Design decisions:
- Idempotent: point IDs are deterministic SHA-256(paper_id:chunk_index) → UUID.
  Re-ingesting the same document overwrites existing Qdrant points safely.
- Status guard: only documents with review_status="reviewed_approved" are ever
  indexed. An assertion + ValueError at upsert entry is the hard gate — pending
  or rejected documents must never reach Qdrant (FR-RAGK-01 hard requirement).
- Token counting: whitespace-split approximation (len(text.split())) — not
  tiktoken. Fast, zero extra deps, accurate enough for 500-token budget chunks.
- Docling PDF parsing: NOT in this file (P2-005). This service accepts raw text.
- Batch embedding: delegated to CohereEmbedClient.embed_batch() which handles
  the 96-text-per-call Cohere limit internally.
- Section-awareness: when sections dict is provided, each section is chunked
  independently and carries its section label in ChunkPayload.section.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field

from app.config_constants import LLM_MAX_TOKENS_INGESTION as _DEFAULT_MAX_TOKENS
from app.schemas.rag import ChunkPayload, QualityTier
from app.services.cohere_client import CohereEmbedClient, EmbedInputType
from app.services.qdrant import QdrantClientWrapper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_OVERLAP_TOKENS = 50
_PAPERS_RAG_COLLECTION = "papers_rag"

# Valid review statuses — only reviewed_approved may be indexed.
_APPROVED_STATUS = "reviewed_approved"

# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------


@dataclass
class DocumentMetadata:
    """Caller-supplied metadata for a document being ingested.

    Attributes
    ----------
    title:
        Full paper or document title.
    authors:
        Ordered list of author name strings.
    year:
        Publication year, or None if unknown.
    doi:
        DOI string without the ``https://doi.org/`` prefix, or None.
    quality_tier:
        Evidence quality tier — must be one of the QualityTier literals
        (L1_systematic_review, L2_rct, L3_observational, L4_guideline).
    review_status:
        Document curation status. Only "reviewed_approved" documents
        may pass through to Qdrant. This is a hard gate (FR-RAGK-01).
    """

    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    quality_tier: QualityTier
    review_status: str


@dataclass
class IngestionResult:
    """Result returned after a successful document ingest.

    Attributes
    ----------
    paper_id:
        The paper_id passed to ingest_document().
    chunk_count:
        Number of chunks produced and upserted to Qdrant.
    point_ids:
        Deterministic UUID strings for every Qdrant point upserted.
        Useful for callers that want to verify idempotency.
    """

    paper_id: str
    chunk_count: int
    point_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure helper functions (importable for unit tests)
# ---------------------------------------------------------------------------


def _make_point_id(paper_id: str, chunk_index: int) -> str:
    """Derive a deterministic UUID from paper_id and chunk_index.

    Uses the first 32 hex characters of SHA-256(paper_id:chunk_index) to
    construct a UUID v4-shaped string.  Identical inputs always produce the
    same UUID, making re-ingest idempotent (same point ID → Qdrant overwrites
    the existing point rather than creating a duplicate).

    Parameters
    ----------
    paper_id:
        Stable document identifier.
    chunk_index:
        Zero-based chunk index within the document.

    Returns
    -------
    str
        A UUID-formatted string (e.g. "550e8400-e29b-41d4-a716-446655440000").
    """
    raw = hashlib.sha256(f"{paper_id}:{chunk_index}".encode()).hexdigest()
    return str(uuid.UUID(raw[:32]))


def _chunk_text(
    text: str,
    *,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    overlap_tokens: int = _DEFAULT_OVERLAP_TOKENS,
) -> list[str]:
    """Split text into overlapping token-budget chunks.

    Token counting uses whitespace splitting (len(text.split())) — a fast,
    dependency-free approximation accurate to ±5% for English scientific prose.

    Parameters
    ----------
    text:
        The full text to chunk.
    max_tokens:
        Maximum tokens per chunk (default 500).
    overlap_tokens:
        Number of tokens repeated at the start of the next chunk from the end
        of the current chunk (default 50).

    Returns
    -------
    list[str]
        Ordered list of chunk strings. Empty or whitespace-only input returns
        an empty list.
    """
    text = text.strip()
    if not text:
        return []

    tokens = text.split()
    total = len(tokens)

    if total <= max_tokens:
        return [text]

    chunks: list[str] = []
    start = 0
    step = max_tokens - overlap_tokens

    while start < total:
        end = min(start + max_tokens, total)
        chunks.append(" ".join(tokens[start:end]))
        if end == total:
            break
        start += step

    return chunks


def _section_chunks(
    full_text: str,
    sections: dict[str, str] | None,
    *,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    overlap_tokens: int = _DEFAULT_OVERLAP_TOKENS,
) -> list[tuple[str | None, str]]:
    """Produce (section_name, chunk_text) pairs, section-aware.

    When ``sections`` is provided and non-empty, each section is chunked
    independently with its section label preserved.  This keeps section
    boundaries intact — a chunk will never span two sections.

    When ``sections`` is None or empty, ``full_text`` is chunked with
    section_name set to None.

    Parameters
    ----------
    full_text:
        Full document text, used as fallback when no sections provided.
    sections:
        Optional mapping of section_name → section_text.
    max_tokens:
        Maximum tokens per chunk.
    overlap_tokens:
        Overlap tokens between adjacent chunks within the same section.

    Returns
    -------
    list[tuple[str | None, str]]
        Ordered list of (section_name, chunk_text) pairs.
    """
    if sections:
        result: list[tuple[str | None, str]] = []
        for section_name, section_text in sections.items():
            for chunk in _chunk_text(section_text, max_tokens=max_tokens, overlap_tokens=overlap_tokens):
                result.append((section_name, chunk))
        return result

    # No sections: chunk full text with section=None
    return [(None, chunk) for chunk in _chunk_text(full_text, max_tokens=max_tokens, overlap_tokens=overlap_tokens)]


# ---------------------------------------------------------------------------
# IngestionService
# ---------------------------------------------------------------------------


class IngestionService:
    """Orchestrates the document ingestion pipeline for ``papers_rag``.

    Accepts raw text + metadata, produces and upserts Qdrant points backed by
    Cohere embed-v4.0 dense vectors.

    Parameters
    ----------
    cohere_client:
        A ``CohereEmbedClient`` instance for embedding.
    qdrant_client:
        A ``QdrantClientWrapper`` instance for Qdrant upserts.
    """

    def __init__(
        self,
        cohere_client: CohereEmbedClient,
        qdrant_client: QdrantClientWrapper,
    ) -> None:
        self._cohere = cohere_client
        self._qdrant = qdrant_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest_document(
        self,
        paper_id: str,
        text: str,
        metadata: DocumentMetadata,
        sections: dict[str, str] | None = None,
    ) -> IngestionResult:
        """Parse, chunk, embed, and upsert a single document.

        Parameters
        ----------
        paper_id:
            Stable identifier for this document (typically the rag_documents.id
            UUID as a string).
        text:
            Full document text.  Used directly when ``sections`` is None.
        metadata:
            Bibliographic and quality metadata.
        sections:
            Optional pre-split sections (section_name → text).  When provided,
            each section is chunked independently with section label preserved.

        Returns
        -------
        IngestionResult
            chunk_count and deterministic point_ids for all upserted points.

        Raises
        ------
        ValueError
            If ``metadata.review_status`` is not "reviewed_approved".
            This is a hard gate — no Cohere or Qdrant calls are made.
        """
        # Hard gate: only reviewed_approved documents enter Qdrant.
        # Raises ValueError (not AssertionError) so the guard cannot be silenced
        # by running Python with -O (optimise flag disables assert statements).
        if metadata.review_status != _APPROVED_STATUS:
            raise ValueError(
                f"Document {paper_id!r} has review_status={metadata.review_status!r}. "
                "Only documents with review_status='reviewed_approved' may be indexed."
            )

        logger.info(
            "ingestion: starting ingest paper_id=%r title=%r",
            paper_id,
            metadata.title,
        )

        # 1. Chunk (section-aware)
        section_text_pairs = _section_chunks(text, sections)
        if not section_text_pairs:
            logger.warning("ingestion: no chunks produced for paper_id=%r — skipping upsert", paper_id)
            return IngestionResult(paper_id=paper_id, chunk_count=0, point_ids=[])

        # 2. Build ChunkPayload objects (carries all metadata per chunk)
        payloads = self._build_payloads(paper_id, section_text_pairs, metadata)

        # 3. Embed all chunk texts via Cohere (batched internally by CohereEmbedClient)
        chunk_texts = [p.text for p in payloads]
        vectors = await self._cohere.embed_batch(
            chunk_texts,
            input_type=EmbedInputType.SEARCH_DOCUMENT,
        )

        if len(vectors) != len(payloads):
            raise RuntimeError(
                f"Cohere returned {len(vectors)} vectors for {len(payloads)} chunks. "
                "Lengths must match."
            )

        # 4. Build Qdrant PointStructs and upsert
        points = self._build_points(payloads, vectors)
        await self._qdrant.upsert_points(collection=_PAPERS_RAG_COLLECTION, points=points)

        point_ids = [p.id for p in payloads]
        logger.info(
            "ingestion: upserted %d chunks for paper_id=%r",
            len(payloads),
            paper_id,
        )

        return IngestionResult(
            paper_id=paper_id,
            chunk_count=len(payloads),
            point_ids=point_ids,
        )

    # ------------------------------------------------------------------
    # Internal helpers (prefixed with _ but accessible for unit tests)
    # ------------------------------------------------------------------

    def _build_payloads(
        self,
        paper_id: str,
        section_text_pairs: list[tuple[str | None, str]],
        metadata: DocumentMetadata,
    ) -> list[ChunkPayload]:
        """Construct ChunkPayload objects for each (section, chunk_text) pair.

        Parameters
        ----------
        paper_id:
            Stable document identifier.
        section_text_pairs:
            Ordered list of (section_name_or_None, chunk_text) tuples.
        metadata:
            Bibliographic metadata applied to all chunks.

        Returns
        -------
        list[ChunkPayload]
            One ChunkPayload per chunk, with deterministic ``id`` values.
        """
        payloads: list[ChunkPayload] = []
        for chunk_index, (section, chunk_text) in enumerate(section_text_pairs):
            point_id = _make_point_id(paper_id, chunk_index)
            token_count = len(chunk_text.split())
            payloads.append(
                ChunkPayload(
                    id=point_id,
                    text=chunk_text,
                    paper_id=paper_id,
                    chunk_index=chunk_index,
                    section=section,
                    token_count=token_count,
                    quality_tier=metadata.quality_tier,
                    title=metadata.title,
                    authors=metadata.authors,
                    year=metadata.year,
                    doi=metadata.doi,
                )
            )
        return payloads

    def _build_points(
        self,
        payloads: list[ChunkPayload],
        vectors: list[list[float]],
    ) -> list[_PointStruct]:
        """Combine ChunkPayload metadata and dense vectors into Qdrant PointStructs.

        Deferred import of ``qdrant_client.models.PointStruct`` keeps the module
        importable in test environments that stub out the qdrant_client package.

        Parameters
        ----------
        payloads:
            ChunkPayload objects (one per chunk).
        vectors:
            1024-dim float vectors in the same order as payloads.

        Returns
        -------
        list[PointStruct]
            Ready for ``QdrantClientWrapper.upsert_points``.
        """
        from qdrant_client.models import PointStruct  # deferred — ADR-032 pattern

        points: list[_PointStruct] = []
        for payload, vector in zip(payloads, vectors):
            points.append(
                PointStruct(
                    id=payload.id,
                    vector=vector,
                    payload=payload.model_dump(),
                )
            )
        return points


# Type alias for annotation only — avoids importing at module level.
_PointStruct = object
