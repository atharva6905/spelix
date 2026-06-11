"""Shared Phase 2 RAG Pydantic schemas.

These types are shared across the entire Phase 2 RAG pipeline:
ingest → embed → retrieve → rerank → coach → cite.

Requirements: FR-AICP-09 (hybrid RAG pipeline), FR-BRAIN-13 (retrieval
metrics logged per query — retrieval_source on RetrievalResult carries
the source tag).

Types defined here (P2-002 scope):
- ChunkPayload    — metadata for a single text chunk stored in Qdrant
- RetrievedContext — a retrieved chunk with its similarity score
- RetrievalResult  — the full retrieval response (primary + supplementary)
- CitationBlock    — a numbered citation reference for coaching output

NOT defined here (different task IDs):
- CoachBrainEntry — P2-023
- RagDocument     — lives in SQLAlchemy models (P2-001)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Quality tier literals (evidence hierarchy for research papers)
# ---------------------------------------------------------------------------

QualityTier = Literal[
    "L1_systematic_review",
    "L2_rct",
    "L3_observational",
    "L4_guideline",
]

# ---------------------------------------------------------------------------
# Collection name literals (ADR-BRAIN-01 — two separate collections)
# ---------------------------------------------------------------------------

CollectionName = Literal["papers_rag", "coach_brain"]

# ---------------------------------------------------------------------------
# Retrieval source literals (FR-BRAIN-13 — logged per query)
# ---------------------------------------------------------------------------

RetrievalSource = Literal[
    "coach_brain_primary",
    "hybrid_brain_supplementary",
    "papers_only_fallback",
]


# ---------------------------------------------------------------------------
# ChunkPayload
# ---------------------------------------------------------------------------


class ChunkPayload(BaseModel):
    """Metadata stored alongside each vector in Qdrant.

    This mirrors the payload stored at upsert time and returned from
    ``query_points``.  The ``id`` is a SHA-256 hex digest of the chunk text
    so deduplication on re-ingest is O(1).

    Attributes
    ----------
    id:
        SHA-256 hex digest of the chunk text (64 hex chars).
    text:
        The raw chunk text, used for reranking and citation excerpts.
    paper_id:
        Stable identifier for the source document (set at ingest time).
    chunk_index:
        Zero-based index of this chunk within its document.
    section:
        Document section label (e.g. "methods", "results") — None if unknown.
    token_count:
        Approximate token count for context budget accounting.
    quality_tier:
        Evidence quality level (L1 = highest, L4 = lowest).
    title:
        Paper or document title for citation display.
    authors:
        Author list.  Must be a list[str], never a bare string.
    year:
        Publication year, or None if unknown.
    doi:
        DOI string (without ``https://doi.org/`` prefix), or None.
    exercise:
        Exercise tags from ``rag_documents.exercise_tags`` — multi-value;
        a Qdrant ``MatchValue`` matches if any element equals the query value.
    sex_applicability:
        Which lifter sex the source's findings apply to (FR-RAGK-05 ext.):
        ``'male'`` | ``'female'`` | ``'both'``. Defaults to ``'both'``.
    """

    id: str
    text: str
    paper_id: str
    chunk_index: int
    section: str | None
    token_count: int
    quality_tier: QualityTier
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    exercise: list[str] = []          # from rag_documents.exercise_tags — multi-value, MatchValue matches any element
    sex_applicability: str = "both"   # 'male' | 'female' | 'both' (FR-RAGK-05 ext.)


# ---------------------------------------------------------------------------
# Chunk — lightweight chunk model for distillation / test stubs
# ---------------------------------------------------------------------------


class Chunk(BaseModel):
    """Lightweight chunk model used by the distillation pipeline.

    Unlike ``ChunkPayload`` (which mirrors the full Qdrant payload), ``Chunk``
    carries only the fields needed for single-claim CoVe verification:
    human-readable title, publication year, and the raw text content.

    Attributes
    ----------
    id:
        Chunk identifier (opaque string).
    document_id:
        Source document identifier.
    text:
        The raw chunk text.
    title:
        Paper or document title for citation display.
    year:
        Publication year, or None if unknown.
    collection:
        Which Qdrant collection this chunk came from.
    """

    id: str
    document_id: str
    text: str
    title: str
    year: int | None = None
    collection: CollectionName


# ---------------------------------------------------------------------------
# RetrievedContext
# ---------------------------------------------------------------------------


class RetrievedContext(BaseModel):
    """A single retrieved chunk with its similarity score.

    Wraps ``ChunkPayload`` or ``Chunk`` with the score returned by the Qdrant
    query so downstream reranking and citation code can order results.

    Attributes
    ----------
    chunk:
        The chunk metadata and text.
    score:
        Cosine similarity (or RRF fusion score) from Qdrant.
    collection:
        Which Qdrant collection this result came from (ADR-BRAIN-01).
    """

    chunk: ChunkPayload | Chunk
    score: float
    collection: CollectionName


# ---------------------------------------------------------------------------
# RetrievalResult
# ---------------------------------------------------------------------------


class RetrievalResult(BaseModel):
    """Full retrieval response for a single query.

    Carries FR-BRAIN-13 ``retrieval_source`` tag so the logging layer
    (P2-032) can record where results came from without inspecting the
    collection field on each individual chunk.

    Attributes
    ----------
    primary:
        Top-ranked contexts used directly in the coaching prompt.
    supplementary:
        Lower-ranked or secondary contexts (e.g. from the other collection).
    retrieval_source:
        Categorical tag describing the retrieval path taken (FR-BRAIN-13).
    """

    primary: list[RetrievedContext]
    supplementary: list[RetrievedContext]
    retrieval_source: RetrievalSource


# ---------------------------------------------------------------------------
# CitationBlock
# ---------------------------------------------------------------------------


class CitationBlock(BaseModel):
    """A numbered citation reference for inclusion in coaching output.

    These are assembled by the coaching layer after retrieval and reranking.
    The ``index`` matches the ``[N]`` reference markers in the coaching text.

    Attributes
    ----------
    index:
        1-based citation number matching ``[N]`` markers in coaching text.
    title:
        Paper or document title.
    authors:
        Author list.  Must be a list[str].
    year:
        Publication year, or None if unknown.
    doi:
        DOI string, or None.
    chunk_text_excerpt:
        Short excerpt from the cited chunk for UI tooltip display.
    """

    index: int
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    chunk_text_excerpt: str
