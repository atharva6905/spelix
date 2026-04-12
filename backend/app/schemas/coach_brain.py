"""Canonical Pydantic v2 schemas for Coach Brain entries.

Implements P2-023 (FR-BRAIN-01).

Column names and CHECK constraint values are derived from Alembic migration
004_phase2_rag_coach_brain — that file is the single source of truth.

Four schemas are defined:

CoachBrainEntry
    Full read model matching the ``coach_brain_entries`` table row.
    Used wherever a complete entry is returned from the DB or Qdrant.

CoachBrainEntryCreate
    Write model for inserting new entries.  ``id``, ``created_at``, and
    ``updated_at`` are absent — generated server-side.  All other nullable or
    defaulted fields have sensible Python defaults so callers need only supply
    the four required fields (content, exercise, phase, entry_type).

CoachBrainEntryUpdate
    Partial-update model.  Every field is Optional so callers can PATCH any
    subset.  Downstream code calls ``model_dump(exclude_none=True)`` to build
    the SET clause.

CoachBrainPayload
    Qdrant point payload schema.  Mirrors the subset of fields stored as
    Qdrant payload metadata alongside the dense+sparse vectors.  ``id`` is a
    ``str`` (UUID string) because Qdrant returns payload values as JSON
    primitives.  Analogous to ``ChunkPayload`` in ``app.schemas.rag``.

    Fields that are indexed in Qdrant (``exercise``, ``status``) carry the
    same Literal constraints as the DB model so accidental mismatches are
    caught at schema-validation time rather than at query time.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constraint literals — mirrors migration 004 CHECK constraints exactly
# ---------------------------------------------------------------------------

ExerciseLiteral = Literal["squat", "bench", "deadlift"]

PhaseLiteral = Literal[
    "setup",
    "descent",
    "bottom",
    "ascent",
    "lockout",
    "general",
]

EntryTypeLiteral = Literal[
    "cue",
    "correction",
    "principle",
    "drill",
]

StatusLiteral = Literal["seed", "active", "deprecated"]


# ---------------------------------------------------------------------------
# CoachBrainEntry — full read model (matches coach_brain_entries table)
# ---------------------------------------------------------------------------


class CoachBrainEntry(BaseModel):
    """Full Coach Brain entry read model.

    Matches the ``coach_brain_entries`` table as created in migration 004.
    Returned from repository queries and passed to the embedding pipeline.

    Attributes
    ----------
    id:
        Primary key UUID.
    content:
        The coaching insight text.  Column is ``content`` (NOT
        ``coaching_action`` — that name appeared in an earlier spec draft).
    exercise:
        Barbell exercise type.  CHECK: squat | bench | deadlift.
    phase:
        Movement phase.  CHECK: setup | descent | bottom | ascent | lockout |
        general.  ``None`` is NOT accepted here — use ``CoachBrainEntryCreate``
        for partial data.
    entry_type:
        Coaching category.  CHECK: cue | correction | principle | drill.
    status:
        Lifecycle state.  CHECK: seed | active | deprecated.  NOT
        pending/approved/rejected (those values are rejected).
    confirmation_count:
        Number of analyses that have confirmed this pattern (FR-BRAIN-18).
    source_analysis_ids:
        UUID list of analyses that contributed this entry.  Withdrawal cascade
        target (FR-BRAIN-16).  Stays empty for seed entries.
    trigger_tags:
        Text tags for categorical routing (e.g. ``["knee_cave",
        "forward_lean"]``).  Stored as ``ARRAY(Text)`` in Postgres.
    confidence_score:
        Optional confidence 0.000–1.000 (Numeric(4,3)).  ``None`` until scored.
    metadata:
        Freeform JSONB for provenance, review notes, external references.
    created_at:
        Row creation timestamp (timezone-aware).
    updated_at:
        Last update timestamp (timezone-aware).
    """

    id: uuid.UUID
    content: str
    exercise: ExerciseLiteral
    phase: PhaseLiteral
    entry_type: EntryTypeLiteral
    status: StatusLiteral
    confirmation_count: int = Field(ge=0)
    source_analysis_ids: list[uuid.UUID]
    trigger_tags: list[str]
    confidence_score: float | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# CoachBrainEntryCreate — write model (no server-generated fields)
# ---------------------------------------------------------------------------


class CoachBrainEntryCreate(BaseModel):
    """Write model for inserting a new Coach Brain entry.

    ``id``, ``created_at``, and ``updated_at`` are absent — the DB generates
    them via ``server_default``.  All other fields that have DB server defaults
    carry matching Python defaults so callers only need the four required fields.

    Required:
        content, exercise, entry_type.

    Optional (with defaults):
        phase — defaults to None (general entries may omit phase)
        status — defaults to "seed"
        confirmation_count — defaults to 0
        source_analysis_ids — defaults to []
        trigger_tags — defaults to []
        confidence_score — defaults to None
        metadata — defaults to {}
    """

    content: str
    exercise: ExerciseLiteral
    phase: PhaseLiteral | None = None
    entry_type: EntryTypeLiteral
    status: StatusLiteral = "seed"
    confirmation_count: int = Field(default=0, ge=0)
    source_analysis_ids: list[uuid.UUID] = Field(default_factory=list)
    trigger_tags: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CoachBrainEntryUpdate — partial update model
# ---------------------------------------------------------------------------


class CoachBrainEntryUpdate(BaseModel):
    """Partial update model for PATCH operations.

    Every field is Optional so callers can update any subset.  Use
    ``model_dump(exclude_none=True)`` to build the SET clause — fields that
    were not supplied remain ``None`` and must be excluded.
    """

    content: str | None = None
    exercise: ExerciseLiteral | None = None
    phase: PhaseLiteral | None = None
    entry_type: EntryTypeLiteral | None = None
    status: StatusLiteral | None = None
    confirmation_count: int | None = Field(default=None, ge=0)
    source_analysis_ids: list[uuid.UUID] | None = None
    trigger_tags: list[str] | None = None
    confidence_score: float | None = None
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# CoachBrainPayload — Qdrant point payload schema
# ---------------------------------------------------------------------------


class CoachBrainPayload(BaseModel):
    """Qdrant point payload schema for the ``coach_brain`` collection.

    Stored as the JSON payload alongside the 1024-dim dense vector and BM25
    sparse vector in Qdrant.  Analogous to ``ChunkPayload`` in
    ``app.schemas.rag``.

    ``id`` is a ``str`` (UUID string representation) because Qdrant serialises
    payload values as JSON primitives and returns them as strings, not as
    ``uuid.UUID`` objects.

    The ``exercise`` and ``status`` fields have Qdrant keyword payload indexes
    (created in ``QdrantClientWrapper._create_brain_indexes``).  The Literal
    constraints here mirror those indexes so validation catches accidental
    invalid values before a point is upserted.

    Attributes
    ----------
    id:
        UUID string of the ``coach_brain_entries`` row.
    content:
        The coaching insight text (used for BM25 sparse retrieval).
    exercise:
        Barbell exercise type — indexed in Qdrant for fast filtering.
    phase:
        Movement phase or None for general entries.
    entry_type:
        Coaching category.
    status:
        Lifecycle state — indexed in Qdrant.  Only ``active`` entries are
        retrieved during coaching; the retrieval layer filters on this field.
    confirmation_count:
        Confirmation count at index time (used for score boosting in Phase 3).
    trigger_tags:
        Text tags for categorical routing.
    """

    id: str
    content: str
    exercise: ExerciseLiteral
    phase: PhaseLiteral | None = None
    entry_type: EntryTypeLiteral
    status: StatusLiteral
    confirmation_count: int = Field(ge=0)
    trigger_tags: list[str]
