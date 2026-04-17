# Phase 3 Batch 2 — Distillation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the async distillation pipeline (FR-BRAIN-06/14/17) that turns completed, high-scoring coaching analyses into reviewable `coach_brain_candidates` rows with CoVe verification against `papers_rag` and ADD/UPDATE/NOOP cosine lifecycle against existing approved entries. Feature-flag gated. Zero blocking of coaching SSE.

**Architecture:** New `backend/app/distillation/` package with a standalone compiled `StateGraph` — different lifecycle from the real-time coaching agent per ADR-BRAIN-07. New `coach_brain_candidates` table (admin-only, separate from live `coach_brain_entries` retrieval). Invoked via a new streaq task `distill_analysis` enqueued at the tail of `process_analysis` when `SPELIX_DISTILLATION_ENABLED=1`. Slim `BrainCoveService` reuses 3 of 4 prompt builders from `app/services/cove.py` for single-claim verification.

**Tech Stack:** LangGraph ≥0.2.50 (already installed), Cohere embed-v4 (existing client), Qdrant (existing wrapper), Claude Haiku 4.5 + Sonnet 4.6 via instructor + Anthropic SDK, streaq 6.4.0, SQLAlchemy 2.0 async, Alembic.

**Reference spec:** `docs/superpowers/specs/2026-04-16-phase3-batch2-distillation-design.md`

**Branch:** `feat/phase3-batch2-distillation`. Create worktree before Task 0.

**Stop-loss:** per STRATEGY.md §Stop-Loss Triggers — if this batch slips past May 3 by more than 3 days, drop Batch 2 entirely (agent core from Batch 1 is non-negotiable; distillation is an L2 nice-to-have that Phase 3 Batch 3 review queue depends on but the product can ship without).

---

## File Structure

### Created

- `backend/alembic/versions/011_coach_brain_candidates.py` — migration adding the new table + indexes (admin-only RLS).
- `backend/app/models/coach_brain_candidate.py` — SQLAlchemy 2.0 model.
- `backend/app/schemas/coach_brain_candidate.py` — Pydantic v2 schemas (`CoachBrainCandidateCreate`, `CoachBrainCandidate`).
- `backend/app/repositories/coach_brain_candidate.py` — `CoachBrainCandidateRepository` with `create`, `list_pending`, `get_by_id`.
- `backend/app/distillation/__init__.py` — package marker.
- `backend/app/distillation/state.py` — `DistillationState` TypedDict + `CandidateInsight`, `LifecycleDecision`, `BrainCoveResult` Pydantic models + `make_initial_distillation_state`.
- `backend/app/distillation/extract.py` — `extract_insights` node.
- `backend/app/distillation/validate.py` — `validate_quality` node (pure).
- `backend/app/distillation/lifecycle.py` — `lifecycle_decision` node.
- `backend/app/distillation/cove_brain.py` — `BrainCoveService.verify_claim` (single-claim CoVe).
- `backend/app/distillation/cove_node.py` — `cove_verify` node that wraps the service.
- `backend/app/distillation/format.py` — `format_entry` node (pure).
- `backend/app/distillation/store.py` — `store_entry` node (DB transaction).
- `backend/app/distillation/graph.py` — `build_distillation_graph()`, `run_distillation_graph()`, `_wrap_trace`.
- `backend/app/workers/distillation_worker.py` — `distill_analysis` task body.
- `backend/tests/unit/test_distillation_state.py`
- `backend/tests/unit/test_distillation_extract.py`
- `backend/tests/unit/test_distillation_validate.py`
- `backend/tests/unit/test_distillation_lifecycle.py`
- `backend/tests/unit/test_distillation_cove_brain.py`
- `backend/tests/unit/test_distillation_format.py`
- `backend/tests/unit/test_distillation_store.py`
- `backend/tests/integration/test_distillation_graph_e2e.py`
- `backend/tests/integration/test_distillation_worker_e2e.py`

### Modified

- `backend/app/models/__init__.py` — export `CoachBrainCandidate` model.
- `backend/app/schemas/__init__.py` — export new schemas.
- `backend/app/workers/streaq_worker.py` — add `@worker.task(timeout=300)` wrapper for `distill_analysis`.
- `backend/app/workers/analysis_worker.py` — enqueue `distill_analysis` at tail of `_run_pipeline` when `SPELIX_DISTILLATION_ENABLED=1` AND `eval_scores.overall >= 0.6`.
- `backend/CLAUDE.md` — new "Phase 3 Distillation Architecture" section + env-var row for `SPELIX_DISTILLATION_ENABLED`.
- `decisions.md` — append ADR-DISTILL-01/02/03.
- `backlog.md` — mark P3-004, P3-005 done on merge; add P3-008 (FR-BRAIN-08 deferred).
- `backend/tests/unit/test_analysis_worker.py` (if exists; else integration variant) — regression: enqueue gate under flag off/on + eval floor.

### Deleted

None. Imperative coaching path stays as fallback — distillation is additive.

---

## Task 0: Worktree + Baseline

**Files:**
- None (environment-only)

- [ ] **Step 1: Create isolated worktree**

Run: `git worktree add ../spelix-phase3-batch2 -b feat/phase3-batch2-distillation main`
Expected: new worktree at `../spelix-phase3-batch2` on the new branch.

- [ ] **Step 2: cd into worktree and confirm baseline tests pass**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest -x -q --ignore=tests/e2e`
Expected: 1539+ passing, 19 skipped, 0 failing (per session 40 handoff).

- [ ] **Step 3: Confirm ruff + pyright clean**

Run: `cd ../spelix-phase3-batch2/backend && uv run ruff check . && uv run pyright`
Expected: zero errors.

- [ ] **Step 4: Confirm alembic head matches repo state**

Run: `cd ../spelix-phase3-batch2/backend && uv run alembic current`
Expected: `010_add_timing_json (head)`.

---

## Task 1: Alembic Migration 011 + SQLAlchemy Model

**Files:**
- Create: `backend/alembic/versions/011_coach_brain_candidates.py`
- Create: `backend/app/models/coach_brain_candidate.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Delegate migration authoring to `spelix-migration` agent**

Per root `CLAUDE.md`, any Alembic change must be produced by the `spelix-migration` subagent. Invoke with:

> "Use the `spelix-migration` agent to generate migration `011_coach_brain_candidates` that creates the `coach_brain_candidates` table per section 4.1 of `docs/superpowers/specs/2026-04-16-phase3-batch2-distillation-design.md`. Do not modify `coach_brain_entries` in this migration. Include RLS admin-only policy. Down migration drops table + indexes."

Expected: the agent writes `backend/alembic/versions/011_coach_brain_candidates.py` with `revision = "011_coach_brain_candidates"`, `down_revision = "010_add_timing_json"`, all columns and CHECK constraints from spec §4.1, three indexes, and RLS `CREATE POLICY coach_brain_candidates_admin_all ON coach_brain_candidates FOR ALL TO service_role USING (true)` (admin-only — RLS denies non-admin by default without an explicit user policy).

- [ ] **Step 2: Apply the migration**

Run: `cd ../spelix-phase3-batch2/backend && uv run alembic upgrade head`
Expected: `alembic current` reports `011_coach_brain_candidates (head)`.

- [ ] **Step 3: Write SQLAlchemy model**

Create `backend/app/models/coach_brain_candidate.py`:

```python
"""SQLAlchemy model for the coach_brain_candidates table.

Maps to migration 011. Distillation pipeline INSERTs rows here; expert
review promotes them to coach_brain_entries (Batch 3). FR-BRAIN-16
cascade target via source_analysis_ids GIN index.
"""

import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, CheckConstraint, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, gen_uuid


class CoachBrainCandidate(TimestampMixin, Base):
    __tablename__ = "coach_brain_candidates"
    __table_args__ = (
        CheckConstraint(
            "exercise IN ('squat','bench','deadlift')",
            name="ck_coach_brain_candidates_exercise",
        ),
        CheckConstraint(
            "phase IS NULL OR phase IN ('setup','descent','bottom','ascent','lockout','general')",
            name="ck_coach_brain_candidates_phase",
        ),
        CheckConstraint(
            "entry_type IN ('cue','correction','principle','drill')",
            name="ck_coach_brain_candidates_entry_type",
        ),
        CheckConstraint(
            "lifecycle_decision IN ('ADD','UPDATE','NOOP')",
            name="ck_coach_brain_candidates_lifecycle",
        ),
        CheckConstraint(
            "review_status IN ('pending','approved','rejected','superseded')",
            name="ck_coach_brain_candidates_review_status",
        ),
        Index(
            "ix_cbc_review_status_created",
            "review_status",
            "created_at",
        ),
        Index(
            "ix_cbc_source_analysis_ids",
            "source_analysis_ids",
            postgresql_using="gin",
        ),
        Index(
            "ix_cbc_nearest_entry_id",
            "nearest_entry_id",
            postgresql_where="nearest_entry_id IS NOT NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    exercise: Mapped[str] = mapped_column(String(30), nullable=False)
    phase: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    source_analysis_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3), nullable=True)
    eval_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    cove_verified: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    cove_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cove_trace: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    lifecycle_decision: Mapped[str] = mapped_column(String(10), nullable=False)
    nearest_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    nearest_cosine_sim: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    contradiction_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    rejected_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    promoted_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
```

- [ ] **Step 4: Export from models package**

Append to `backend/app/models/__init__.py`:

```python
from app.models.coach_brain_candidate import CoachBrainCandidate  # noqa: F401
```

- [ ] **Step 5: Verify model imports cleanly**

Run: `cd ../spelix-phase3-batch2/backend && uv run python -c "from app.models.coach_brain_candidate import CoachBrainCandidate; print(CoachBrainCandidate.__tablename__)"`
Expected: `coach_brain_candidates`.

- [ ] **Step 6: Run ruff + pyright on new files**

Run: `cd ../spelix-phase3-batch2/backend && uv run ruff check app/models/coach_brain_candidate.py && uv run pyright app/models/coach_brain_candidate.py`
Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/alembic/versions/011_coach_brain_candidates.py backend/app/models/coach_brain_candidate.py backend/app/models/__init__.py && git commit -m "feat(models): add coach_brain_candidates table + model (P3-004)"
```

---

## Task 2: Pydantic Schemas + Repository

**Files:**
- Create: `backend/app/schemas/coach_brain_candidate.py`
- Create: `backend/app/repositories/coach_brain_candidate.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: Write Pydantic schemas**

Create `backend/app/schemas/coach_brain_candidate.py`:

```python
"""Pydantic v2 schemas for coach_brain_candidates.

CoachBrainCandidateCreate is the write model used by the distillation
store_entry node. CoachBrainCandidate is the read model used by the
Batch 3 review queue.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.coach_brain import (
    EntryTypeLiteral,
    ExerciseLiteral,
    PhaseLiteral,
)

LifecycleLiteral = Literal["ADD", "UPDATE", "NOOP"]
ReviewStatusLiteral = Literal["pending", "approved", "rejected", "superseded"]


class CoachBrainCandidateCreate(BaseModel):
    """Write model for a newly distilled candidate."""

    exercise: ExerciseLiteral
    phase: PhaseLiteral | None = None
    entry_type: EntryTypeLiteral
    content: str
    trigger_tags: list[str] = Field(default_factory=list)
    source_analysis_ids: list[uuid.UUID] = Field(min_length=1)
    confidence_score: float | None = None
    eval_scores: dict[str, Any] = Field(default_factory=dict)
    cove_verified: bool | None = None
    cove_explanation: str | None = None
    cove_trace: dict[str, Any] | None = None
    lifecycle_decision: LifecycleLiteral
    nearest_entry_id: uuid.UUID | None = None
    nearest_cosine_sim: float | None = None
    contradiction_flag: bool = False
    review_status: ReviewStatusLiteral = "pending"


class CoachBrainCandidate(BaseModel):
    """Read model matching the coach_brain_candidates table row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exercise: ExerciseLiteral
    phase: PhaseLiteral | None
    entry_type: EntryTypeLiteral
    content: str
    trigger_tags: list[str]
    source_analysis_ids: list[uuid.UUID]
    confidence_score: float | None
    eval_scores: dict[str, Any]
    cove_verified: bool | None
    cove_explanation: str | None
    cove_trace: dict[str, Any] | None
    lifecycle_decision: LifecycleLiteral
    nearest_entry_id: uuid.UUID | None
    nearest_cosine_sim: float | None
    contradiction_flag: bool
    review_status: ReviewStatusLiteral
    rejected_reason: str | None
    promoted_entry_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Append to schemas package exports**

Append to `backend/app/schemas/__init__.py`:

```python
from app.schemas.coach_brain_candidate import (  # noqa: F401
    CoachBrainCandidate,
    CoachBrainCandidateCreate,
)
```

- [ ] **Step 3: Write the failing repository test**

Create `backend/tests/unit/test_coach_brain_candidate_repo.py`:

```python
"""Unit tests for CoachBrainCandidateRepository."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.coach_brain_candidate import CoachBrainCandidateRepository
from app.schemas.coach_brain_candidate import CoachBrainCandidateCreate


@pytest.mark.asyncio
async def test_create_inserts_row(db_session: AsyncSession) -> None:
    repo = CoachBrainCandidateRepository(db_session)
    create = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Drive the knees out as you descend to stay stacked.",
        trigger_tags=["knee_cave"],
        source_analysis_ids=[uuid.uuid4()],
        lifecycle_decision="ADD",
    )
    created = await repo.create(create)
    assert created.id is not None
    assert created.review_status == "pending"
    assert created.lifecycle_decision == "ADD"


@pytest.mark.asyncio
async def test_list_pending_returns_only_pending(db_session: AsyncSession) -> None:
    repo = CoachBrainCandidateRepository(db_session)
    a = await repo.create(
        CoachBrainCandidateCreate(
            exercise="squat",
            entry_type="cue",
            content="cue A",
            source_analysis_ids=[uuid.uuid4()],
            lifecycle_decision="ADD",
        )
    )
    await repo.create(
        CoachBrainCandidateCreate(
            exercise="squat",
            entry_type="cue",
            content="cue B",
            source_analysis_ids=[uuid.uuid4()],
            lifecycle_decision="UPDATE",
            review_status="superseded",
        )
    )
    pending = await repo.list_pending()
    ids = [p.id for p in pending]
    assert a.id in ids
    assert all(p.review_status == "pending" for p in pending)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_coach_brain_candidate_repo.py -v`
Expected: ModuleNotFoundError: `app.repositories.coach_brain_candidate`.

- [ ] **Step 5: Implement the repository**

Create `backend/app/repositories/coach_brain_candidate.py`:

```python
"""Repository for coach_brain_candidates table.

All DB access for candidates passes through this class. Distillation
store_entry node uses `create`; Batch 3 admin UI uses `list_pending`
+ `get_by_id`.
"""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coach_brain_candidate import CoachBrainCandidate as CoachBrainCandidateRow
from app.schemas.coach_brain_candidate import (
    CoachBrainCandidate,
    CoachBrainCandidateCreate,
)


class CoachBrainCandidateRepository:
    """DB access layer for coach_brain_candidates."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, create: CoachBrainCandidateCreate) -> CoachBrainCandidate:
        row = CoachBrainCandidateRow(
            exercise=create.exercise,
            phase=create.phase,
            entry_type=create.entry_type,
            content=create.content,
            trigger_tags=create.trigger_tags,
            source_analysis_ids=create.source_analysis_ids,
            confidence_score=create.confidence_score,
            eval_scores=create.eval_scores,
            cove_verified=create.cove_verified,
            cove_explanation=create.cove_explanation,
            cove_trace=create.cove_trace,
            lifecycle_decision=create.lifecycle_decision,
            nearest_entry_id=create.nearest_entry_id,
            nearest_cosine_sim=create.nearest_cosine_sim,
            contradiction_flag=create.contradiction_flag,
            review_status=create.review_status,
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return CoachBrainCandidate.model_validate(row)

    async def list_pending(self, limit: int = 100) -> Sequence[CoachBrainCandidate]:
        stmt = (
            select(CoachBrainCandidateRow)
            .where(CoachBrainCandidateRow.review_status == "pending")
            .order_by(CoachBrainCandidateRow.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return [CoachBrainCandidate.model_validate(r) for r in result.scalars().all()]

    async def get_by_id(self, candidate_id: uuid.UUID) -> CoachBrainCandidate | None:
        stmt = select(CoachBrainCandidateRow).where(CoachBrainCandidateRow.id == candidate_id)
        result = await self._db.execute(stmt)
        row = result.scalars().one_or_none()
        return CoachBrainCandidate.model_validate(row) if row is not None else None
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_coach_brain_candidate_repo.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/schemas/coach_brain_candidate.py backend/app/schemas/__init__.py backend/app/repositories/coach_brain_candidate.py backend/tests/unit/test_coach_brain_candidate_repo.py && git commit -m "feat(repo): coach_brain_candidate schemas + repository (P3-004)"
```

---

## Task 3: `DistillationState` + Data Models

**Files:**
- Create: `backend/app/distillation/__init__.py`
- Create: `backend/app/distillation/state.py`
- Create: `backend/tests/unit/test_distillation_state.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_distillation_state.py`:

```python
"""Unit tests for distillation state scaffolding."""

import uuid

from app.distillation.state import (
    BrainCoveResult,
    CandidateInsight,
    LifecycleDecision,
    make_initial_distillation_state,
)


def test_make_initial_state_defaults() -> None:
    analysis_id = uuid.uuid4()
    state = make_initial_distillation_state(
        analysis_id=analysis_id,
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )
    assert state["analysis_id"] == analysis_id
    assert state["candidates"] == []
    assert state["decisions"] == []
    assert state["cove_results"] == []
    assert state["formatted"] == []
    assert state["stored_ids"] == []
    assert state["trace"] == []
    assert state["validation_decision"] == "pass"  # placeholder until validate_quality runs
    assert state["eval_scores"] == {"overall": 0.9, "correctness": 0.85}


def test_candidate_insight_shape() -> None:
    ci = CandidateInsight(
        content="Drive knees out as you descend.",
        exercise="squat",
        phase="descent",
        entry_type="cue",
        trigger_tags=["knee_cave"],
        confidence_score=0.9,
    )
    assert ci.content.startswith("Drive")
    assert ci.trigger_tags == ["knee_cave"]


def test_lifecycle_decision_shape() -> None:
    d = LifecycleDecision(
        decision="UPDATE", nearest_entry_id=uuid.uuid4(), cosine_sim=0.81
    )
    assert d.decision == "UPDATE"


def test_brain_cove_result_shape() -> None:
    r = BrainCoveResult(verified=True, explanation="supported by [1]", trace=[])
    assert r.verified is True


def _stub_coaching_output():
    from app.schemas.coaching import CoachingOutput

    return CoachingOutput(
        summary="s",
        strengths=[],
        issues=[],
        correction_plan=[],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="high",
        dimension_addressed="safety",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_state.py -v`
Expected: `ModuleNotFoundError: app.distillation`.

- [ ] **Step 3: Create package marker**

Create `backend/app/distillation/__init__.py` with a docstring only:

```python
"""Standalone distillation pipeline (Phase 3 Batch 2).

A compiled LangGraph StateGraph that runs async after each completed
coaching analysis and emits candidate coach_brain entries for expert
review. Distinct lifecycle from the Phase 3 coaching agent per
ADR-BRAIN-07.
"""
```

- [ ] **Step 4: Implement state module**

Create `backend/app/distillation/state.py`:

```python
"""DistillationState TypedDict + supporting Pydantic models.

Three models (CandidateInsight, LifecycleDecision, BrainCoveResult)
live here because they are the lingua franca of the pipeline — every
node reads or writes at least one of them.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

from app.schemas.coach_brain import EntryTypeLiteral, ExerciseLiteral, PhaseLiteral
from app.schemas.coach_brain_candidate import CoachBrainCandidateCreate
from app.schemas.coaching import CoachingOutput
from app.schemas.rag import RetrievedContext


ValidationDecision = Literal["pass", "review", "reject"]
LifecycleLabel = Literal["ADD", "UPDATE", "NOOP"]


class CandidateInsight(BaseModel):
    """One extracted coaching insight prior to lifecycle routing."""

    content: str = Field(min_length=1)
    exercise: ExerciseLiteral
    phase: PhaseLiteral | None = None
    entry_type: EntryTypeLiteral
    trigger_tags: list[str] = Field(default_factory=list)
    confidence_score: float | None = None


class LifecycleDecision(BaseModel):
    """Output of the lifecycle_decision node for one CandidateInsight."""

    decision: LifecycleLabel
    nearest_entry_id: uuid.UUID | None = None
    cosine_sim: float = 0.0


class BrainCoveResult(BaseModel):
    """Output of BrainCoveService.verify_claim for one candidate."""

    verified: bool
    explanation: str
    trace: list[dict[str, Any]] = Field(default_factory=list)


class DistillationState(TypedDict):
    # inputs
    analysis_id: uuid.UUID
    exercise_type: str
    coaching_output: CoachingOutput
    retrieved_papers_contexts: list[RetrievedContext]
    eval_scores: dict[str, Any]

    # working set
    candidates: list[CandidateInsight]
    validation_decision: ValidationDecision
    decisions: list[LifecycleDecision]
    cove_results: list[BrainCoveResult]
    formatted: list[CoachBrainCandidateCreate]

    # output
    stored_ids: list[uuid.UUID]
    trace: list[dict[str, Any]]


def make_initial_distillation_state(
    *,
    analysis_id: uuid.UUID,
    exercise_type: str,
    coaching_output: CoachingOutput,
    retrieved_papers_contexts: list[RetrievedContext],
    eval_scores: dict[str, Any],
) -> DistillationState:
    """Construct a DistillationState with safe defaults for every field."""
    return DistillationState(
        analysis_id=analysis_id,
        exercise_type=exercise_type,
        coaching_output=coaching_output,
        retrieved_papers_contexts=retrieved_papers_contexts,
        eval_scores=eval_scores,
        candidates=[],
        validation_decision="pass",
        decisions=[],
        cove_results=[],
        formatted=[],
        stored_ids=[],
        trace=[],
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_state.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/distillation/__init__.py backend/app/distillation/state.py backend/tests/unit/test_distillation_state.py && git commit -m "feat(distillation): state scaffolding + data models (P3-004)"
```

---

## Task 4: `extract_insights` Node

**Files:**
- Create: `backend/app/distillation/extract.py`
- Create: `backend/tests/unit/test_distillation_extract.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_distillation_extract.py`:

```python
"""Unit tests for the extract_insights distillation node."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.distillation.extract import ExtractedInsights, extract_insights
from app.distillation.state import CandidateInsight, make_initial_distillation_state
from app.schemas.coaching import CoachingOutput, Issue


@pytest.mark.asyncio
async def test_extract_insights_returns_candidates_from_llm() -> None:
    state = _state_with_coaching_output(
        CoachingOutput(
            summary="Good depth, slight knee cave on rep 2.",
            strengths=["Consistent tempo"],
            issues=[
                Issue(rep_number=2, joint="knee", description="knees cave inward at bottom",
                      severity="Medium"),
            ],
            correction_plan=["Drive knees out as you descend."],
            recommended_cues=["Spread the floor"],
            citations=[],
            safety_warnings=[],
            confidence_level="high",
            dimension_addressed="safety",
            disclaimer=_disclaimer(),
            raw_prompt_tokens=0,
            raw_completion_tokens=0,
        )
    )
    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        return_value=ExtractedInsights(
            candidates=[
                CandidateInsight(
                    content="Drive knees out as you descend.",
                    exercise="squat",
                    phase="descent",
                    entry_type="cue",
                    trigger_tags=["knee_cave"],
                    confidence_score=0.9,
                ),
            ]
        )
    )
    update = await extract_insights(
        state,
        anthropic_client=anthropic_client,
        instructor_client=instructor_client,
    )
    assert len(update["candidates"]) == 1
    assert update["candidates"][0].content.startswith("Drive knees")


@pytest.mark.asyncio
async def test_extract_insights_empty_output_returns_empty() -> None:
    state = _state_with_coaching_output(_empty_coaching_output())
    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        return_value=ExtractedInsights(candidates=[]),
    )
    update = await extract_insights(
        state,
        anthropic_client=anthropic_client,
        instructor_client=instructor_client,
    )
    assert update["candidates"] == []


@pytest.mark.asyncio
async def test_extract_insights_llm_error_returns_empty_safely() -> None:
    state = _state_with_coaching_output(_empty_coaching_output())
    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError("boom"),
    )
    update = await extract_insights(
        state,
        anthropic_client=anthropic_client,
        instructor_client=instructor_client,
    )
    assert update["candidates"] == []


def _state_with_coaching_output(co):
    return make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=co,
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )


def _empty_coaching_output():
    return CoachingOutput(
        summary="",
        strengths=[],
        issues=[],
        correction_plan=[],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="low",
        dimension_addressed="safety",
        disclaimer=_disclaimer(),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )


def _disclaimer():
    return (
        "This feedback is for educational purposes only and is not a "
        "substitute for in-person coaching or medical advice."
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_extract.py -v`
Expected: `ModuleNotFoundError: app.distillation.extract`.

- [ ] **Step 3: Implement the node**

Create `backend/app/distillation/extract.py`:

```python
"""extract_insights — Haiku-extractive distillation node.

Reads a completed CoachingOutput and emits falsifiable, reusable
coaching candidates tagged with exercise, phase, entry_type, and
trigger_tags. Never raises — any LLM failure returns an empty list.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from app.distillation.state import CandidateInsight, DistillationState
from app.schemas.coaching import CoachingOutput

logger = logging.getLogger(__name__)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024


class ExtractedInsights(BaseModel):
    """instructor response model for the extraction call."""

    candidates: list[CandidateInsight]


def _build_extraction_prompt(coaching_output: CoachingOutput, exercise_type: str) -> str:
    lines: list[str] = [
        "You are a coaching insight extractor. From the coaching feedback "
        "below, extract atomic reusable coaching insights suitable for a "
        "knowledge base.",
        "",
        f"Exercise: {exercise_type}",
        "",
        "Rules:",
        "- Only include insights you could verify against biomechanics "
        "literature. Skip subjective observations.",
        "- Each insight must be 5-25 words and phrase-complete.",
        "- Prefer verbatim or near-verbatim coaching language from the "
        "feedback — do NOT invent new cues.",
        "- Tag each insight with: exercise (squat|bench|deadlift), phase "
        "(setup|descent|bottom|ascent|lockout|general|null), entry_type "
        "(cue|correction|principle|drill), trigger_tags (e.g. knee_cave, "
        "forward_lean).",
        "- If there is nothing worth distilling, return an empty list.",
        "",
        f"Coaching summary: {coaching_output.summary}",
        "",
        "Issues identified:",
    ]
    for issue in coaching_output.issues:
        lines.append(
            f"- Rep {issue.rep_number} ({issue.joint}, {issue.severity}): "
            f"{issue.description}"
        )
    lines.append("")
    lines.append("Correction plan:")
    for cue in coaching_output.correction_plan:
        lines.append(f"- {cue}")
    if coaching_output.recommended_cues:
        lines.append("")
        lines.append("Recommended cues:")
        for cue in coaching_output.recommended_cues:
            lines.append(f"- {cue}")
    return "\n".join(lines)


async def extract_insights(
    state: DistillationState,
    *,
    anthropic_client: Any,
    instructor_client: Any,
) -> dict[str, Any]:
    """Extract candidate insights from the coaching output.

    Returns a partial state dict — LangGraph merges it into the running
    state. On any LLM failure we log and return an empty candidate list
    so the downstream graph short-circuits cleanly.
    """
    try:
        extracted: ExtractedInsights = await instructor_client.chat.completions.create(
            model=_HAIKU_MODEL,
            max_tokens=_MAX_TOKENS,
            response_model=ExtractedInsights,
            messages=[
                {
                    "role": "user",
                    "content": _build_extraction_prompt(
                        state["coaching_output"], state["exercise_type"]
                    ),
                }
            ],
        )
        return {"candidates": list(extracted.candidates)}
    except Exception as exc:  # noqa: BLE001 — must never raise
        logger.warning(
            "extract_insights failed (%s: %s) — returning empty candidate list",
            type(exc).__name__,
            exc,
        )
        return {"candidates": []}
```

- [ ] **Step 4: Run tests**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_extract.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/distillation/extract.py backend/tests/unit/test_distillation_extract.py && git commit -m "feat(distillation): extract_insights node (P3-004)"
```

---

## Task 5: `validate_quality` Node

**Files:**
- Create: `backend/app/distillation/validate.py`
- Create: `backend/tests/unit/test_distillation_validate.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_distillation_validate.py`:

```python
"""Unit tests for validate_quality — pure function, no LLM."""

import uuid

import pytest

from app.distillation.state import make_initial_distillation_state
from app.distillation.validate import validate_quality
from app.schemas.coaching import CoachingOutput


@pytest.mark.parametrize(
    ("overall", "correctness", "expected"),
    [
        (0.9, 0.85, "pass"),
        (0.85, 0.8, "pass"),           # boundary
        (0.85, 0.79, "review"),        # correctness just below gate
        (0.7, 0.7, "review"),
        (0.6, 0.6, "review"),          # boundary
        (0.59, 0.6, "reject"),
        (0.3, 0.9, "reject"),
    ],
)
@pytest.mark.asyncio
async def test_validate_quality_gate_matrix(
    overall: float, correctness: float, expected: str
) -> None:
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": overall, "correctness": correctness},
    )
    update = await validate_quality(state)
    assert update["validation_decision"] == expected


@pytest.mark.asyncio
async def test_validate_quality_missing_scores_rejects() -> None:
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={},
    )
    update = await validate_quality(state)
    assert update["validation_decision"] == "reject"


def _stub_coaching_output():
    return CoachingOutput(
        summary="s",
        strengths=[],
        issues=[],
        correction_plan=[],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="high",
        dimension_addressed="safety",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_validate.py -v`
Expected: `ModuleNotFoundError: app.distillation.validate`.

- [ ] **Step 3: Implement the node**

Create `backend/app/distillation/validate.py`:

```python
"""validate_quality — pure gate node.

Reads eval_scores from the triggering analysis and emits one of three
decisions:
- pass:   overall >= 0.85 AND correctness >= 0.8  (high-quality, route
          all candidates to lifecycle → CoVe → store as pending review)
- review: 0.6 <= overall < 0.85                   (still distill, but
          flag eval_tier=low for Batch 3 display priority)
- reject: overall < 0.6 or missing                (END; no candidates
          written — avoids polluting the review queue with noise)

FR-BRAIN-06 threshold definition.
"""

from __future__ import annotations

from typing import Any

from app.distillation.state import DistillationState

_OVERALL_PASS = 0.85
_CORRECTNESS_PASS = 0.80
_OVERALL_REVIEW_FLOOR = 0.60


async def validate_quality(state: DistillationState) -> dict[str, Any]:
    """Decide whether candidates proceed, proceed-for-review, or reject."""
    eval_scores = state.get("eval_scores") or {}
    overall = eval_scores.get("overall")
    correctness = eval_scores.get("correctness")

    if overall is None or overall < _OVERALL_REVIEW_FLOOR:
        return {"validation_decision": "reject"}

    if (
        overall >= _OVERALL_PASS
        and correctness is not None
        and correctness >= _CORRECTNESS_PASS
    ):
        return {"validation_decision": "pass"}

    return {"validation_decision": "review"}
```

- [ ] **Step 4: Run tests**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_validate.py -v`
Expected: 8 passed (7 parametrized + 1 missing-scores).

- [ ] **Step 5: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/distillation/validate.py backend/tests/unit/test_distillation_validate.py && git commit -m "feat(distillation): validate_quality gate node (P3-004)"
```

---

## Task 6: `lifecycle_decision` Node (FR-BRAIN-17)

**Files:**
- Create: `backend/app/distillation/lifecycle.py`
- Create: `backend/tests/unit/test_distillation_lifecycle.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_distillation_lifecycle.py`:

```python
"""Unit tests for lifecycle_decision — embed + Qdrant cosine routing."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.distillation.lifecycle import lifecycle_decision
from app.distillation.state import CandidateInsight, make_initial_distillation_state
from app.schemas.coaching import CoachingOutput


def _state_with_candidates(candidates: list[CandidateInsight]):
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )
    state["candidates"] = candidates
    state["validation_decision"] = "pass"
    return state


def _stub_candidate():
    return CandidateInsight(
        content="Drive knees out as you descend.",
        exercise="squat",
        phase="descent",
        entry_type="cue",
        trigger_tags=["knee_cave"],
    )


def _mock_brain_embedding(vector):
    svc = MagicMock()
    svc.build_contextual_text = MagicMock(return_value="stub contextual text")
    return svc


def _mock_cohere(vector):
    c = MagicMock()
    c.embed_batch = AsyncMock(return_value=[vector])
    return c


def _mock_qdrant(nearest_id, score):
    q = MagicMock()
    if nearest_id is None:
        q.search = AsyncMock(return_value=[])
    else:
        hit = MagicMock()
        hit.id = str(nearest_id)
        hit.score = score
        q.search = AsyncMock(return_value=[hit])
    return q


@pytest.mark.asyncio
async def test_lifecycle_noop_when_cosine_above_092() -> None:
    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(nearest, 0.95),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert len(update["decisions"]) == 1
    assert update["decisions"][0].decision == "NOOP"
    assert update["decisions"][0].nearest_entry_id == nearest


@pytest.mark.asyncio
async def test_lifecycle_update_when_cosine_in_075_092() -> None:
    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(nearest, 0.81),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert update["decisions"][0].decision == "UPDATE"


@pytest.mark.asyncio
async def test_lifecycle_add_when_cosine_below_075() -> None:
    nearest = uuid.uuid4()
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(nearest, 0.6),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert update["decisions"][0].decision == "ADD"


@pytest.mark.asyncio
async def test_lifecycle_add_when_empty_qdrant() -> None:
    state = _state_with_candidates([_stub_candidate()])
    update = await lifecycle_decision(
        state,
        cohere_client=_mock_cohere([0.0] * 1024),
        qdrant_client=_mock_qdrant(None, 0.0),
        brain_embedding_svc=_mock_brain_embedding([0.0] * 1024),
    )
    assert update["decisions"][0].decision == "ADD"
    assert update["decisions"][0].nearest_entry_id is None


def _stub_coaching_output():
    return CoachingOutput(
        summary="s",
        strengths=[],
        issues=[],
        correction_plan=[],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="high",
        dimension_addressed="safety",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_lifecycle.py -v`
Expected: `ModuleNotFoundError: app.distillation.lifecycle`.

- [ ] **Step 3: Implement the node**

Create `backend/app/distillation/lifecycle.py`:

```python
"""lifecycle_decision — FR-BRAIN-17 cosine routing.

For each CandidateInsight, embed via Cohere (SEARCH_DOCUMENT), search
the Qdrant coach_brain collection filtered by exercise + status=active,
and decide:
  cosine > 0.92 → NOOP (knowledge already exists)
  0.75 <= cosine <= 0.92 → UPDATE (confirm existing entry)
  cosine < 0.75 → ADD (novel; route to review queue)

Empty Qdrant (cold start or no matches) → ADD with nearest_entry_id=None.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import models as qdrant_models

from app.distillation.state import (
    CandidateInsight,
    DistillationState,
    LifecycleDecision,
)
from app.schemas.coach_brain import CoachBrainEntryCreate
from app.services.cohere_client import EmbedInputType
from app.services.qdrant import COLLECTION_COACH_BRAIN

logger = logging.getLogger(__name__)

_NOOP_THRESHOLD = 0.92
_UPDATE_FLOOR = 0.75


def _build_proxy_entry(candidate: CandidateInsight) -> CoachBrainEntryCreate:
    """Build a throwaway CoachBrainEntryCreate purely to reuse BrainEmbeddingService.build_contextual_text."""
    return CoachBrainEntryCreate(
        content=candidate.content,
        exercise=candidate.exercise,
        phase=candidate.phase,
        entry_type=candidate.entry_type,
        trigger_tags=candidate.trigger_tags,
    )


async def lifecycle_decision(
    state: DistillationState,
    *,
    cohere_client: Any,
    qdrant_client: Any,
    brain_embedding_svc: Any,
) -> dict[str, Any]:
    """Route each candidate to ADD / UPDATE / NOOP via cosine similarity."""
    candidates: list[CandidateInsight] = state.get("candidates") or []
    if not candidates:
        return {"decisions": []}

    texts = [
        brain_embedding_svc.build_contextual_text(_build_proxy_entry(c))
        for c in candidates
    ]
    vectors = await cohere_client.embed_batch(
        texts, input_type=EmbedInputType.SEARCH_DOCUMENT
    )

    decisions: list[LifecycleDecision] = []
    for candidate, vector in zip(candidates, vectors, strict=True):
        exercise_filter = qdrant_models.FieldCondition(
            key="exercise",
            match=qdrant_models.MatchValue(value=candidate.exercise),
        )
        status_filter = qdrant_models.FieldCondition(
            key="status",
            match=qdrant_models.MatchValue(value="active"),
        )
        query_filter = qdrant_models.Filter(must=[exercise_filter, status_filter])

        try:
            hits = await qdrant_client.search(
                collection_name=COLLECTION_COACH_BRAIN,
                query_vector=vector,
                query_filter=query_filter,
                limit=1,
                with_payload=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "lifecycle_decision: qdrant search failed (%s) — treating as ADD",
                exc,
            )
            hits = []

        if not hits:
            decisions.append(LifecycleDecision(decision="ADD", nearest_entry_id=None, cosine_sim=0.0))
            continue

        top = hits[0]
        nearest_id = uuid.UUID(top.id) if isinstance(top.id, str) else top.id
        score = float(top.score)

        if score >= _NOOP_THRESHOLD:
            label = "NOOP"
        elif score >= _UPDATE_FLOOR:
            label = "UPDATE"
        else:
            label = "ADD"

        decisions.append(
            LifecycleDecision(decision=label, nearest_entry_id=nearest_id, cosine_sim=score)
        )

    return {"decisions": decisions}
```

- [ ] **Step 4: Run tests**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_lifecycle.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/distillation/lifecycle.py backend/tests/unit/test_distillation_lifecycle.py && git commit -m "feat(distillation): lifecycle_decision node FR-BRAIN-17 (P3-005)"
```

---

## Task 7: `BrainCoveService` + `cove_verify` Node (FR-BRAIN-14)

**Files:**
- Create: `backend/app/distillation/cove_brain.py`
- Create: `backend/app/distillation/cove_node.py`
- Create: `backend/tests/unit/test_distillation_cove_brain.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_distillation_cove_brain.py`:

```python
"""Unit tests for BrainCoveService.verify_claim (single-claim CoVe)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.distillation.cove_brain import BrainCoveService
from app.schemas.rag import Chunk, RetrievedContext


def _stub_context(text: str) -> RetrievedContext:
    chunk = Chunk(
        id="c1",
        document_id="d1",
        text=text,
        title="Schoenfeld 2010",
        year=2010,
        collection="papers_rag",
    )
    return RetrievedContext(chunk=chunk, score=0.9, collection="papers_rag")


class _StubQuestionOutput(MagicMock):
    pass


class _StubAnswerOutput(MagicMock):
    pass


@pytest.mark.asyncio
async def test_verify_claim_supported_returns_verified_true() -> None:
    from app.distillation.cove_brain import _VerificationQuestion, _VerificationAnswerOut

    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        side_effect=[
            _VerificationQuestion(question="Does knee-out cueing reduce valgus collapse?"),
            _VerificationAnswerOut(answer="Yes", reasoning="Schoenfeld 2010 reports reduced valgus."),
        ]
    )
    svc = BrainCoveService(anthropic_client=anthropic_client, instructor_client=instructor_client)
    result = await svc.verify_claim(
        claim="Drive knees out as you descend.",
        contexts=[_stub_context("Knee-out cueing reduced valgus collapse in trained lifters.")],
    )
    assert result.verified is True
    assert "Schoenfeld" in result.explanation


@pytest.mark.asyncio
async def test_verify_claim_unsupported_returns_verified_false() -> None:
    from app.distillation.cove_brain import _VerificationQuestion, _VerificationAnswerOut

    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        side_effect=[
            _VerificationQuestion(question="Does breath holding improve bench press 1RM?"),
            _VerificationAnswerOut(answer="No", reasoning="No evidence in provided sources."),
        ]
    )
    svc = BrainCoveService(anthropic_client=anthropic_client, instructor_client=instructor_client)
    result = await svc.verify_claim(
        claim="Holding breath increases bench press 1RM by 20%.",
        contexts=[_stub_context("Unrelated discussion of hip hinge mechanics.")],
    )
    assert result.verified is False


@pytest.mark.asyncio
async def test_verify_claim_empty_contexts_skips_llm() -> None:
    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock()
    svc = BrainCoveService(anthropic_client=anthropic_client, instructor_client=instructor_client)
    result = await svc.verify_claim(claim="any claim", contexts=[])
    assert result.verified is False
    assert result.explanation == "no_papers_evidence"
    instructor_client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_verify_claim_llm_error_returns_safe_default() -> None:
    anthropic_client = MagicMock()
    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    svc = BrainCoveService(anthropic_client=anthropic_client, instructor_client=instructor_client)
    result = await svc.verify_claim(
        claim="any claim",
        contexts=[_stub_context("something")],
    )
    assert result.verified is False
    assert "boom" in result.explanation or "evaluation_failed" in result.explanation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_cove_brain.py -v`
Expected: `ModuleNotFoundError: app.distillation.cove_brain`.

- [ ] **Step 3: Implement `BrainCoveService`**

Create `backend/app/distillation/cove_brain.py`:

```python
"""BrainCoveService — single-claim CoVe verifier for distillation candidates.

Slim variant of app/services/cove.py's CoveVerificationService. Skips
claim extraction (the candidate content IS the claim), generates one
verification question, and verifies against retrieved papers_rag
contexts. Never raises — any failure returns BrainCoveResult(verified=
false, explanation=<detail>).

Cites FR-BRAIN-14. The full CoachingOutput-oriented CoveVerificationService
remains untouched for the Phase 2 coaching path.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel

from app.distillation.state import BrainCoveResult
from app.schemas.rag import RetrievedContext

logger = logging.getLogger(__name__)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"


class _VerificationQuestion(BaseModel):
    question: str


class _VerificationAnswerOut(BaseModel):
    answer: Literal["Yes", "No", "Uncertain"]
    reasoning: str


def _build_question_prompt(claim: str) -> str:
    return (
        "Generate exactly ONE yes/no verification question that can be answered "
        "using peer-reviewed biomechanics evidence to test the following "
        "coaching claim. The question must be specific, concrete, and testable.\n\n"
        f"Claim: {claim}"
    )


def _build_verify_prompt(question: str, contexts: list[RetrievedContext]) -> str:
    evidence_text = "\n\n".join(
        f"[Source {i + 1}] {ctx.chunk.title} ({ctx.chunk.year or 'n.d.'}):\n{ctx.chunk.text}"
        for i, ctx in enumerate(contexts)
    )
    return (
        "You are an independent verifier. Using ONLY the retrieved evidence "
        "below, answer the question with Yes, No, or Uncertain. Do NOT rely "
        "on any external knowledge — only the provided sources.\n\n"
        f"Retrieved evidence:\n{evidence_text}\n\n"
        f"Question: {question}\n\n"
        "Provide answer (Yes/No/Uncertain) and a one-sentence reasoning "
        "citing the source number."
    )


class BrainCoveService:
    """Single-claim Chain-of-Verification service for distillation."""

    def __init__(self, *, anthropic_client: Any, instructor_client: Any) -> None:
        self._anthropic_client = anthropic_client
        self._instructor_client = instructor_client

    async def verify_claim(
        self,
        *,
        claim: str,
        contexts: list[RetrievedContext],
    ) -> BrainCoveResult:
        """Verify one coaching claim against retrieved papers_rag contexts."""
        if not contexts:
            return BrainCoveResult(
                verified=False,
                explanation="no_papers_evidence",
                trace=[{"claim": claim, "skipped_reason": "no_papers_evidence"}],
            )

        try:
            question_out = await self._instructor_client.chat.completions.create(
                model=_HAIKU_MODEL,
                max_tokens=256,
                response_model=_VerificationQuestion,
                messages=[{"role": "user", "content": _build_question_prompt(claim)}],
            )
            answer_out = await self._instructor_client.chat.completions.create(
                model=_HAIKU_MODEL,
                max_tokens=512,
                response_model=_VerificationAnswerOut,
                messages=[
                    {
                        "role": "user",
                        "content": _build_verify_prompt(question_out.question, contexts),
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "BrainCoveService.verify_claim failed (%s: %s)",
                type(exc).__name__,
                exc,
            )
            return BrainCoveResult(
                verified=False,
                explanation=f"evaluation_failed: {type(exc).__name__}: {exc}",
                trace=[{"claim": claim, "error": str(exc)}],
            )

        verified = answer_out.answer == "Yes"
        return BrainCoveResult(
            verified=verified,
            explanation=answer_out.reasoning,
            trace=[
                {
                    "claim": claim,
                    "question": question_out.question,
                    "answer": answer_out.answer,
                    "reasoning": answer_out.reasoning,
                }
            ],
        )
```

- [ ] **Step 4: Run the BrainCoveService tests**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_cove_brain.py -v`
Expected: 4 passed.

- [ ] **Step 5: Implement the `cove_verify` node**

Create `backend/app/distillation/cove_node.py`:

```python
"""cove_verify node — calls BrainCoveService per non-NOOP candidate.

For each (candidate, decision) pair where decision != NOOP, run
BrainCoveService.verify_claim against the analysis's already-retrieved
papers_rag contexts. NOOP candidates are skipped with a placeholder
BrainCoveResult so downstream indexing stays aligned.

CoVe failures never block storage — they just mark the candidate
cove_verified=false, which Batch 3's review UI surfaces prominently.
"""

from __future__ import annotations

from typing import Any

from app.distillation.state import BrainCoveResult, DistillationState


async def cove_verify(
    state: DistillationState,
    *,
    cove_service: Any,
) -> dict[str, Any]:
    """Run single-claim CoVe for every non-NOOP candidate."""
    candidates = state.get("candidates") or []
    decisions = state.get("decisions") or []
    contexts = state.get("retrieved_papers_contexts") or []

    results: list[BrainCoveResult] = []
    for candidate, decision in zip(candidates, decisions, strict=True):
        if decision.decision == "NOOP":
            results.append(BrainCoveResult(verified=True, explanation="noop_skip", trace=[]))
            continue
        r = await cove_service.verify_claim(claim=candidate.content, contexts=contexts)
        results.append(r)

    return {"cove_results": results}
```

- [ ] **Step 6: Add an inline test for the `cove_verify` node**

Append to `backend/tests/unit/test_distillation_cove_brain.py`:

```python
# ---- cove_verify node tests ----


@pytest.mark.asyncio
async def test_cove_verify_skips_noop_candidates() -> None:
    from unittest.mock import AsyncMock, MagicMock
    import uuid as _uuid

    from app.distillation.cove_node import cove_verify
    from app.distillation.state import (
        CandidateInsight,
        LifecycleDecision,
        make_initial_distillation_state,
    )
    from app.schemas.coaching import CoachingOutput

    co = CoachingOutput(
        summary="s",
        strengths=[],
        issues=[],
        correction_plan=[],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="high",
        dimension_addressed="safety",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )
    state = make_initial_distillation_state(
        analysis_id=_uuid.uuid4(),
        exercise_type="squat",
        coaching_output=co,
        retrieved_papers_contexts=[_stub_context("evidence text")],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )
    state["candidates"] = [
        CandidateInsight(
            content="C1", exercise="squat", phase="descent", entry_type="cue"
        ),
        CandidateInsight(
            content="C2", exercise="squat", phase="descent", entry_type="cue"
        ),
    ]
    state["decisions"] = [
        LifecycleDecision(decision="ADD", nearest_entry_id=None, cosine_sim=0.1),
        LifecycleDecision(decision="NOOP", nearest_entry_id=_uuid.uuid4(), cosine_sim=0.95),
    ]
    svc = MagicMock()
    svc.verify_claim = AsyncMock(
        return_value=BrainCoveResult(verified=True, explanation="ok", trace=[])
    )
    update = await cove_verify(state, cove_service=svc)
    assert len(update["cove_results"]) == 2
    assert update["cove_results"][1].explanation == "noop_skip"
    assert svc.verify_claim.await_count == 1
```

Add the required import at the top of that test file:

```python
from app.distillation.state import BrainCoveResult
```

- [ ] **Step 7: Run tests**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_cove_brain.py -v`
Expected: 5 passed.

- [ ] **Step 8: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/distillation/cove_brain.py backend/app/distillation/cove_node.py backend/tests/unit/test_distillation_cove_brain.py && git commit -m "feat(distillation): BrainCoveService + cove_verify node FR-BRAIN-14 (P3-004)"
```

---

## Task 8: `format_entry` Node

**Files:**
- Create: `backend/app/distillation/format.py`
- Create: `backend/tests/unit/test_distillation_format.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_distillation_format.py`:

```python
"""Unit tests for format_entry — pure zip-and-pack function."""

import uuid

import pytest

from app.distillation.format import format_entry
from app.distillation.state import (
    BrainCoveResult,
    CandidateInsight,
    LifecycleDecision,
    make_initial_distillation_state,
)
from app.schemas.coaching import CoachingOutput


def _state_with(candidates, decisions, cove_results, analysis_id=None, eval_scores=None):
    state = make_initial_distillation_state(
        analysis_id=analysis_id or uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores=eval_scores or {"overall": 0.9, "correctness": 0.85},
    )
    state["candidates"] = candidates
    state["decisions"] = decisions
    state["cove_results"] = cove_results
    state["validation_decision"] = "pass"
    return state


def _candidate(content="C1"):
    return CandidateInsight(
        content=content,
        exercise="squat",
        phase="descent",
        entry_type="cue",
        trigger_tags=["knee_cave"],
        confidence_score=0.9,
    )


@pytest.mark.asyncio
async def test_format_entry_add_produces_pending_row() -> None:
    state = _state_with(
        [_candidate()],
        [LifecycleDecision(decision="ADD", nearest_entry_id=None, cosine_sim=0.4)],
        [BrainCoveResult(verified=True, explanation="supported", trace=[{"q": "?"}])],
    )
    update = await format_entry(state)
    formatted = update["formatted"]
    assert len(formatted) == 1
    row = formatted[0]
    assert row.lifecycle_decision == "ADD"
    assert row.review_status == "pending"
    assert row.cove_verified is True
    assert row.contradiction_flag is False
    assert row.source_analysis_ids == [state["analysis_id"]]
    assert row.eval_scores == {"overall": 0.9, "correctness": 0.85}


@pytest.mark.asyncio
async def test_format_entry_update_produces_superseded_row() -> None:
    nearest = uuid.uuid4()
    state = _state_with(
        [_candidate()],
        [LifecycleDecision(decision="UPDATE", nearest_entry_id=nearest, cosine_sim=0.81)],
        [BrainCoveResult(verified=True, explanation="ok", trace=[])],
    )
    update = await format_entry(state)
    row = update["formatted"][0]
    assert row.lifecycle_decision == "UPDATE"
    assert row.review_status == "superseded"
    assert row.nearest_entry_id == nearest


@pytest.mark.asyncio
async def test_format_entry_noop_produces_no_row() -> None:
    state = _state_with(
        [_candidate()],
        [LifecycleDecision(decision="NOOP", nearest_entry_id=uuid.uuid4(), cosine_sim=0.95)],
        [BrainCoveResult(verified=True, explanation="noop_skip", trace=[])],
    )
    update = await format_entry(state)
    assert update["formatted"] == []


@pytest.mark.asyncio
async def test_format_entry_contradiction_flag_set() -> None:
    nearest = uuid.uuid4()
    state = _state_with(
        [_candidate()],
        [LifecycleDecision(decision="UPDATE", nearest_entry_id=nearest, cosine_sim=0.80)],
        [BrainCoveResult(verified=False, explanation="contradicts", trace=[])],
    )
    update = await format_entry(state)
    row = update["formatted"][0]
    assert row.contradiction_flag is True
    assert row.cove_verified is False


def _stub_coaching_output():
    return CoachingOutput(
        summary="s",
        strengths=[],
        issues=[],
        correction_plan=[],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="high",
        dimension_addressed="safety",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_format.py -v`
Expected: `ModuleNotFoundError: app.distillation.format`.

- [ ] **Step 3: Implement the node**

Create `backend/app/distillation/format.py`:

```python
"""format_entry — pure function that packs Pydantic write models.

Aligned-iteration (candidates, decisions, cove_results). NOOP decisions
are dropped entirely — no row written. UPDATE decisions emit a
candidate row with review_status='superseded' (audit-only, not in
review queue). ADD decisions emit review_status='pending'.

Contradiction flag: set when decision='UPDATE' AND cove_verified=false.
"""

from __future__ import annotations

from typing import Any

from app.distillation.state import DistillationState
from app.schemas.coach_brain_candidate import CoachBrainCandidateCreate


async def format_entry(state: DistillationState) -> dict[str, Any]:
    """Zip candidates/decisions/cove_results into CoachBrainCandidateCreate rows."""
    candidates = state.get("candidates") or []
    decisions = state.get("decisions") or []
    cove_results = state.get("cove_results") or []
    analysis_id = state["analysis_id"]
    eval_scores = state.get("eval_scores") or {}

    formatted: list[CoachBrainCandidateCreate] = []
    for candidate, decision, cove in zip(
        candidates, decisions, cove_results, strict=True
    ):
        if decision.decision == "NOOP":
            continue

        contradiction = (
            decision.decision == "UPDATE" and cove.verified is False
        )
        review_status = "superseded" if decision.decision == "UPDATE" else "pending"

        formatted.append(
            CoachBrainCandidateCreate(
                exercise=candidate.exercise,
                phase=candidate.phase,
                entry_type=candidate.entry_type,
                content=candidate.content,
                trigger_tags=candidate.trigger_tags,
                source_analysis_ids=[analysis_id],
                confidence_score=candidate.confidence_score,
                eval_scores=eval_scores,
                cove_verified=cove.verified,
                cove_explanation=cove.explanation,
                cove_trace={"trace": cove.trace},
                lifecycle_decision=decision.decision,
                nearest_entry_id=decision.nearest_entry_id,
                nearest_cosine_sim=decision.cosine_sim,
                contradiction_flag=contradiction,
                review_status=review_status,
            )
        )
    return {"formatted": formatted}
```

- [ ] **Step 4: Run tests**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_format.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/distillation/format.py backend/tests/unit/test_distillation_format.py && git commit -m "feat(distillation): format_entry node (P3-004)"
```

---

## Task 9: `store_entry` Node

**Files:**
- Create: `backend/app/distillation/store.py`
- Create: `backend/tests/unit/test_distillation_store.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_distillation_store.py`:

```python
"""Unit tests for store_entry — DB transaction writes."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.distillation.state import make_initial_distillation_state
from app.distillation.store import store_entry
from app.models.coach_brain_candidate import CoachBrainCandidate
from app.models.coach_brain_entry import CoachBrainEntry
from app.schemas.coach_brain_candidate import CoachBrainCandidateCreate
from app.schemas.coaching import CoachingOutput


def _stub_coaching_output():
    return CoachingOutput(
        summary="s",
        strengths=[],
        issues=[],
        correction_plan=[],
        recommended_cues=[],
        citations=[],
        safety_warnings=[],
        confidence_level="high",
        dimension_addressed="safety",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )


def _state_with_formatted(rows: list[CoachBrainCandidateCreate]):
    state = make_initial_distillation_state(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.9, "correctness": 0.85},
    )
    state["formatted"] = rows
    return state


@pytest.mark.asyncio
async def test_store_entry_add_inserts_row(db_session: AsyncSession) -> None:
    row = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Drive knees out.",
        source_analysis_ids=[uuid.uuid4()],
        lifecycle_decision="ADD",
    )
    state = _state_with_formatted([row])
    update = await store_entry(state, db_session=db_session)
    assert len(update["stored_ids"]) == 1
    found = (await db_session.execute(
        select(CoachBrainCandidate).where(CoachBrainCandidate.id == update["stored_ids"][0])
    )).scalar_one()
    assert found.review_status == "pending"


@pytest.mark.asyncio
async def test_store_entry_update_bumps_confirmation_count(db_session: AsyncSession) -> None:
    seed = CoachBrainEntry(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="seed",
        trigger_tags=["knee_cave"],
        confirmation_count=2,
        source_analysis_ids=[],
        status="active",
    )
    db_session.add(seed)
    await db_session.flush()

    source_analysis = uuid.uuid4()
    row = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="Drive knees out.",
        source_analysis_ids=[source_analysis],
        lifecycle_decision="UPDATE",
        nearest_entry_id=seed.id,
        nearest_cosine_sim=0.81,
        review_status="superseded",
    )
    state = _state_with_formatted([row])
    await store_entry(state, db_session=db_session)

    await db_session.refresh(seed)
    assert seed.confirmation_count == 3
    assert source_analysis in seed.source_analysis_ids


@pytest.mark.asyncio
async def test_store_entry_empty_formatted_writes_nothing(db_session: AsyncSession) -> None:
    state = _state_with_formatted([])
    update = await store_entry(state, db_session=db_session)
    assert update["stored_ids"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_store.py -v`
Expected: `ModuleNotFoundError: app.distillation.store`.

- [ ] **Step 3: Implement the node**

Create `backend/app/distillation/store.py`:

```python
"""store_entry — DB transaction: INSERT candidate + conditional UPDATE on source entry.

Every formatted CoachBrainCandidateCreate produces one row in
coach_brain_candidates. When lifecycle_decision='UPDATE', the same
session also bumps the referenced coach_brain_entries row's
confirmation_count and appends the new source_analysis_id
(FR-BRAIN-18).

Both writes share the caller-provided AsyncSession so that a rollback
(raised elsewhere in the pipeline, not here) undoes both. The caller
owns commit/rollback — this node only flushes.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select

from app.distillation.state import DistillationState
from app.models.coach_brain_candidate import CoachBrainCandidate as CoachBrainCandidateRow
from app.models.coach_brain_entry import CoachBrainEntry

logger = logging.getLogger(__name__)


async def store_entry(
    state: DistillationState,
    *,
    db_session: Any,
) -> dict[str, Any]:
    """Persist formatted candidates + apply UPDATE-path confirmation bumps."""
    formatted = state.get("formatted") or []
    if not formatted:
        return {"stored_ids": []}

    stored_ids: list[uuid.UUID] = []

    for row in formatted:
        candidate_row = CoachBrainCandidateRow(
            exercise=row.exercise,
            phase=row.phase,
            entry_type=row.entry_type,
            content=row.content,
            trigger_tags=row.trigger_tags,
            source_analysis_ids=row.source_analysis_ids,
            confidence_score=row.confidence_score,
            eval_scores=row.eval_scores,
            cove_verified=row.cove_verified,
            cove_explanation=row.cove_explanation,
            cove_trace=row.cove_trace,
            lifecycle_decision=row.lifecycle_decision,
            nearest_entry_id=row.nearest_entry_id,
            nearest_cosine_sim=row.nearest_cosine_sim,
            contradiction_flag=row.contradiction_flag,
            review_status=row.review_status,
        )
        db_session.add(candidate_row)
        await db_session.flush()
        stored_ids.append(candidate_row.id)

        if row.lifecycle_decision == "UPDATE" and row.nearest_entry_id is not None:
            stmt = select(CoachBrainEntry).where(CoachBrainEntry.id == row.nearest_entry_id)
            result = await db_session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is None:
                logger.warning(
                    "store_entry: UPDATE-path nearest_entry_id=%s not found; "
                    "candidate %s stored without confirmation bump.",
                    row.nearest_entry_id,
                    candidate_row.id,
                )
                continue
            existing.confirmation_count = (existing.confirmation_count or 0) + 1
            # array_append via list assignment — SQLAlchemy serialises as ARRAY literal.
            existing.source_analysis_ids = list(existing.source_analysis_ids or []) + list(
                row.source_analysis_ids
            )
            await db_session.flush()

    return {"stored_ids": stored_ids}
```

- [ ] **Step 4: Run tests**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/unit/test_distillation_store.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/distillation/store.py backend/tests/unit/test_distillation_store.py && git commit -m "feat(distillation): store_entry node FR-BRAIN-18 (P3-005)"
```

---

## Task 10: Build + Compile the Distillation Graph

**Files:**
- Create: `backend/app/distillation/graph.py`
- Create: `backend/tests/integration/test_distillation_graph_e2e.py`

- [ ] **Step 1: Write the failing integration test**

Create `backend/tests/integration/test_distillation_graph_e2e.py`:

```python
"""End-to-end integration test for the distillation graph."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.distillation.graph import run_distillation_graph
from app.distillation.state import CandidateInsight
from app.models.coach_brain_candidate import CoachBrainCandidate as CoachBrainCandidateRow
from app.schemas.coaching import CoachingOutput, Issue


def _stub_coaching_output():
    return CoachingOutput(
        summary="Good depth, slight knee cave on rep 2.",
        strengths=["Consistent tempo"],
        issues=[Issue(rep_number=2, joint="knee", description="knees cave", severity="Medium")],
        correction_plan=["Drive knees out as you descend."],
        recommended_cues=["Spread the floor"],
        citations=[],
        safety_warnings=[],
        confidence_level="high",
        dimension_addressed="safety",
        disclaimer=(
            "This feedback is for educational purposes only and is not a "
            "substitute for in-person coaching or medical advice."
        ),
        raw_prompt_tokens=0,
        raw_completion_tokens=0,
    )


@pytest.mark.asyncio
async def test_full_graph_end_to_end_add_path(db_session: AsyncSession) -> None:
    from app.distillation.extract import ExtractedInsights

    # Mock: extraction yields one candidate
    instructor_client = MagicMock()
    from app.distillation.cove_brain import _VerificationAnswerOut, _VerificationQuestion

    instructor_client.chat.completions.create = AsyncMock(
        side_effect=[
            ExtractedInsights(
                candidates=[
                    CandidateInsight(
                        content="Drive knees out as you descend.",
                        exercise="squat",
                        phase="descent",
                        entry_type="cue",
                        trigger_tags=["knee_cave"],
                        confidence_score=0.9,
                    )
                ]
            ),
            _VerificationQuestion(question="Does knee-out cueing reduce valgus?"),
            _VerificationAnswerOut(answer="Yes", reasoning="Schoenfeld 2010 supports."),
        ]
    )
    anthropic_client = MagicMock()

    cohere = MagicMock()
    cohere.embed_batch = AsyncMock(return_value=[[0.0] * 1024])

    qdrant = MagicMock()
    qdrant.search = AsyncMock(return_value=[])  # empty coach_brain → ADD

    brain_embedding = MagicMock()
    brain_embedding.build_contextual_text = MagicMock(return_value="ctx")

    analysis_id = uuid.uuid4()
    final_state, trace_payload = await run_distillation_graph(
        analysis_id=analysis_id,
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[_stub_context("Knee-out cueing reduced valgus")],
        eval_scores={"overall": 0.9, "correctness": 0.85},
        anthropic_client=anthropic_client,
        instructor_client=instructor_client,
        cohere_client=cohere,
        qdrant_client=qdrant,
        brain_embedding_svc=brain_embedding,
        cove_service_factory=lambda: _stub_cove_service(instructor_client, anthropic_client),
        db_session=db_session,
    )

    assert final_state["validation_decision"] == "pass"
    assert len(final_state["stored_ids"]) == 1
    assert trace_payload["nodes_executed"][0]["node"] == "extract_insights"

    # Verify candidate row landed in Postgres
    found = (
        await db_session.execute(
            select(CoachBrainCandidateRow).where(
                CoachBrainCandidateRow.id == final_state["stored_ids"][0]
            )
        )
    ).scalar_one()
    assert found.lifecycle_decision == "ADD"
    assert found.review_status == "pending"
    assert found.cove_verified is True


@pytest.mark.asyncio
async def test_graph_rejects_low_eval_scores(db_session: AsyncSession) -> None:
    from app.distillation.extract import ExtractedInsights

    instructor_client = MagicMock()
    instructor_client.chat.completions.create = AsyncMock(
        return_value=ExtractedInsights(candidates=[])
    )

    final_state, _ = await run_distillation_graph(
        analysis_id=uuid.uuid4(),
        exercise_type="squat",
        coaching_output=_stub_coaching_output(),
        retrieved_papers_contexts=[],
        eval_scores={"overall": 0.4, "correctness": 0.3},  # below 0.6 floor
        anthropic_client=MagicMock(),
        instructor_client=instructor_client,
        cohere_client=MagicMock(),
        qdrant_client=MagicMock(),
        brain_embedding_svc=MagicMock(),
        cove_service_factory=lambda: MagicMock(),
        db_session=db_session,
    )
    assert final_state["validation_decision"] == "reject"
    assert final_state["stored_ids"] == []


def _stub_cove_service(instructor_client, anthropic_client):
    from app.distillation.cove_brain import BrainCoveService

    return BrainCoveService(
        anthropic_client=anthropic_client, instructor_client=instructor_client
    )


def _stub_context(text: str):
    from app.schemas.rag import Chunk, RetrievedContext

    chunk = Chunk(
        id="c1",
        document_id="d1",
        text=text,
        title="Stub 2024",
        year=2024,
        collection="papers_rag",
    )
    return RetrievedContext(chunk=chunk, score=0.9, collection="papers_rag")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/integration/test_distillation_graph_e2e.py -v`
Expected: `ImportError: cannot import name 'run_distillation_graph'`.

- [ ] **Step 3: Implement the graph**

Create `backend/app/distillation/graph.py`:

```python
"""Standalone distillation StateGraph (FR-BRAIN-06).

Topology:
  START
    -> extract_insights
    -> validate_quality
         (reject) -> END
         (pass|review) -> lifecycle_decision
    -> cove_verify
    -> format_entry
    -> store_entry
    -> END

Each node is wrapped by `_wrap_trace` (same pattern as
app/agents/graph.py) so NodeEvent rows accumulate in state['trace'].
"""

from __future__ import annotations

import datetime as _dt
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from langgraph.graph import END, START, StateGraph

from app.agents.state import NodeEvent
from app.distillation.cove_node import cove_verify
from app.distillation.extract import extract_insights
from app.distillation.format import format_entry
from app.distillation.lifecycle import lifecycle_decision
from app.distillation.state import DistillationState, make_initial_distillation_state
from app.distillation.store import store_entry
from app.distillation.validate import validate_quality
from app.schemas.coaching import CoachingOutput
from app.schemas.rag import RetrievedContext

logger = logging.getLogger(__name__)

_TRACE_NODE_CAP_BYTES = 8 * 1024


def _wrap_trace(
    node_name: str,
    inner: Callable[[DistillationState], Awaitable[dict[str, Any]]],
) -> Callable[[DistillationState], Awaitable[dict[str, Any]]]:
    async def _wrapped(state: DistillationState) -> dict[str, Any]:
        started_at = _dt.datetime.now(_dt.UTC).isoformat()
        t0 = time.monotonic()
        try:
            update = await inner(state)
        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000.0
            event = NodeEvent(
                node=node_name,
                started_at=started_at,
                duration_ms=duration_ms,
                output_keys=[],
                error=str(exc),
            )
            state["trace"] = [*(state.get("trace") or []), event.model_dump()]
            raise
        duration_ms = (time.monotonic() - t0) * 1000.0
        event = NodeEvent(
            node=node_name,
            started_at=started_at,
            duration_ms=duration_ms,
            output_keys=sorted(update.keys()),
            error=None,
        )
        trace = list(state.get("trace") or [])
        trace.append(event.model_dump())
        merged: dict[str, Any] = dict(update)
        merged["trace"] = trace
        return merged

    return _wrapped


def build_distillation_graph(
    *,
    anthropic_client: Any,
    instructor_client: Any,
    cohere_client: Any,
    qdrant_client: Any,
    brain_embedding_svc: Any,
    cove_service: Any,
    db_session: Any,
) -> Any:
    """Wire the distillation nodes into a compiled StateGraph."""

    async def _extract(state: DistillationState) -> dict[str, Any]:
        return await extract_insights(
            state, anthropic_client=anthropic_client, instructor_client=instructor_client
        )

    async def _validate(state: DistillationState) -> dict[str, Any]:
        return await validate_quality(state)

    async def _lifecycle(state: DistillationState) -> dict[str, Any]:
        return await lifecycle_decision(
            state,
            cohere_client=cohere_client,
            qdrant_client=qdrant_client,
            brain_embedding_svc=brain_embedding_svc,
        )

    async def _cove(state: DistillationState) -> dict[str, Any]:
        return await cove_verify(state, cove_service=cove_service)

    async def _format(state: DistillationState) -> dict[str, Any]:
        return await format_entry(state)

    async def _store(state: DistillationState) -> dict[str, Any]:
        return await store_entry(state, db_session=db_session)

    def _after_validate(state: DistillationState) -> str:
        return "reject" if state.get("validation_decision") == "reject" else "continue"

    builder = StateGraph(DistillationState)
    builder.add_node("extract_insights", _wrap_trace("extract_insights", _extract))
    builder.add_node("validate_quality", _wrap_trace("validate_quality", _validate))
    builder.add_node("lifecycle_decision", _wrap_trace("lifecycle_decision", _lifecycle))
    builder.add_node("cove_verify", _wrap_trace("cove_verify", _cove))
    builder.add_node("format_entry", _wrap_trace("format_entry", _format))
    builder.add_node("store_entry", _wrap_trace("store_entry", _store))

    builder.add_edge(START, "extract_insights")
    builder.add_edge("extract_insights", "validate_quality")
    builder.add_conditional_edges(
        "validate_quality",
        _after_validate,
        {"reject": END, "continue": "lifecycle_decision"},
    )
    builder.add_edge("lifecycle_decision", "cove_verify")
    builder.add_edge("cove_verify", "format_entry")
    builder.add_edge("format_entry", "store_entry")
    builder.add_edge("store_entry", END)

    return builder.compile()


async def run_distillation_graph(
    *,
    analysis_id: uuid.UUID,
    exercise_type: str,
    coaching_output: CoachingOutput,
    retrieved_papers_contexts: list[RetrievedContext],
    eval_scores: dict[str, Any],
    anthropic_client: Any,
    instructor_client: Any,
    cohere_client: Any,
    qdrant_client: Any,
    brain_embedding_svc: Any,
    cove_service_factory: Callable[[], Any],
    db_session: Any,
) -> tuple[DistillationState, dict[str, Any]]:
    """Entry point called from the streaq task.

    Returns (final_state, trace_payload) where trace_payload is the
    shape suitable for future persistence / admin debugging.
    """
    initial = make_initial_distillation_state(
        analysis_id=analysis_id,
        exercise_type=exercise_type,
        coaching_output=coaching_output,
        retrieved_papers_contexts=retrieved_papers_contexts,
        eval_scores=eval_scores,
    )

    graph = build_distillation_graph(
        anthropic_client=anthropic_client,
        instructor_client=instructor_client,
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        brain_embedding_svc=brain_embedding_svc,
        cove_service=cove_service_factory(),
        db_session=db_session,
    )
    final_state = await graph.ainvoke(initial)

    trace_payload: dict[str, Any] = {
        "nodes_executed": final_state.get("trace") or [],
        "validation_decision": final_state.get("validation_decision"),
        "stored_ids": [str(i) for i in (final_state.get("stored_ids") or [])],
        "candidates_count": len(final_state.get("candidates") or []),
        "decisions": [d.model_dump() for d in (final_state.get("decisions") or [])],
    }
    return final_state, trace_payload
```

- [ ] **Step 4: Run the integration test**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/integration/test_distillation_graph_e2e.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/distillation/graph.py backend/tests/integration/test_distillation_graph_e2e.py && git commit -m "feat(distillation): compiled StateGraph + run entry point (P3-004)"
```

---

## Task 11: streaq Task + `analysis_worker` Enqueue Tail

**Files:**
- Create: `backend/app/workers/distillation_worker.py`
- Modify: `backend/app/workers/streaq_worker.py`
- Modify: `backend/app/workers/analysis_worker.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/test_distillation_worker_e2e.py`:

```python
"""Streaq-level E2E: process_analysis tail enqueues distill_analysis."""

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_enqueue_skipped_when_flag_off(db_session: AsyncSession, monkeypatch) -> None:
    monkeypatch.delenv("SPELIX_DISTILLATION_ENABLED", raising=False)
    from app.workers.analysis_worker import _maybe_enqueue_distillation

    enqueue = AsyncMock()
    with patch(
        "app.workers.streaq_worker.distill_analysis.enqueue", enqueue
    ):
        await _maybe_enqueue_distillation(
            analysis_id=uuid.uuid4(),
            eval_scores={"overall": 0.9},
        )
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_skipped_when_eval_below_floor(monkeypatch) -> None:
    monkeypatch.setenv("SPELIX_DISTILLATION_ENABLED", "1")
    from app.workers.analysis_worker import _maybe_enqueue_distillation

    enqueue = AsyncMock()
    with patch(
        "app.workers.streaq_worker.distill_analysis.enqueue", enqueue
    ):
        await _maybe_enqueue_distillation(
            analysis_id=uuid.uuid4(),
            eval_scores={"overall": 0.4},
        )
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_called_when_flag_on_and_eval_above_floor(monkeypatch) -> None:
    monkeypatch.setenv("SPELIX_DISTILLATION_ENABLED", "1")
    from app.workers.analysis_worker import _maybe_enqueue_distillation

    enqueue = AsyncMock()
    with patch(
        "app.workers.streaq_worker.distill_analysis.enqueue", enqueue
    ):
        aid = uuid.uuid4()
        await _maybe_enqueue_distillation(
            analysis_id=aid,
            eval_scores={"overall": 0.7},
        )
    enqueue.assert_awaited_once_with(aid)


@pytest.mark.asyncio
async def test_enqueue_errors_are_swallowed(monkeypatch, caplog) -> None:
    monkeypatch.setenv("SPELIX_DISTILLATION_ENABLED", "1")
    from app.workers.analysis_worker import _maybe_enqueue_distillation

    enqueue = AsyncMock(side_effect=RuntimeError("redis down"))
    with patch(
        "app.workers.streaq_worker.distill_analysis.enqueue", enqueue
    ):
        await _maybe_enqueue_distillation(
            analysis_id=uuid.uuid4(),
            eval_scores={"overall": 0.9},
        )
    assert "redis down" in caplog.text or "distillation enqueue failed" in caplog.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/integration/test_distillation_worker_e2e.py -v`
Expected: ImportError on `_maybe_enqueue_distillation` or `distill_analysis`.

- [ ] **Step 3: Implement the distillation worker body**

Create `backend/app/workers/distillation_worker.py`:

```python
"""distill_analysis task body.

Loads the completed analysis + coaching_result + retrieved sources,
constructs pipeline deps, invokes run_distillation_graph, and persists
the resulting candidate rows (the graph's store_entry node writes via
the provided session; the task manages transaction boundaries).

FR-BRAIN-06. Enqueued from analysis_worker._run_pipeline tail when
SPELIX_DISTILLATION_ENABLED=1 and eval_scores.overall >= 0.6.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.distillation.cove_brain import BrainCoveService
from app.distillation.graph import run_distillation_graph
from app.repositories.analysis import AnalysisRepository
from app.repositories.coaching_result import CoachingResultRepository
from app.schemas.coaching import CoachingOutput
from app.schemas.rag import RetrievedContext

logger = logging.getLogger(__name__)


async def _build_papers_contexts(coaching_result: Any) -> list[RetrievedContext]:
    """Rehydrate papers_rag contexts from coaching_results.retrieved_sources_json."""
    raw = coaching_result.retrieved_sources_json or {}
    ctxs_raw = raw.get("contexts") or []
    contexts: list[RetrievedContext] = []
    for c in ctxs_raw:
        try:
            ctx = RetrievedContext.model_validate(c)
            if ctx.collection == "papers_rag":
                contexts.append(ctx)
        except Exception:  # noqa: BLE001
            continue
    return contexts


async def distill_analysis_body(
    ctx: dict[str, Any],
    analysis_id: uuid.UUID,
) -> dict[str, Any]:
    """Body of the distill_analysis streaq task.

    Expects ctx to carry:
      - db_session_maker: async sessionmaker
      - anthropic_client, instructor_client
      - cohere_client, qdrant_client, brain_embedding_svc
    """
    db_session_maker = ctx["db_session_maker"]
    if db_session_maker is None:
        logger.warning("distill_analysis_body: db_session_maker is None — aborting")
        return {"status": "skipped_no_session"}

    async with db_session_maker() as db_session:
        analysis_repo = AnalysisRepository(db_session)
        coaching_repo = CoachingResultRepository(db_session)

        analysis = await analysis_repo.get_by_id(analysis_id)
        if analysis is None:
            logger.warning("distill_analysis_body: analysis %s not found", analysis_id)
            return {"status": "skipped_no_analysis"}

        coaching_result = await coaching_repo.get_by_analysis_id(analysis_id)
        if coaching_result is None or coaching_result.structured_output_json is None:
            logger.warning(
                "distill_analysis_body: no coaching_result for analysis %s", analysis_id
            )
            return {"status": "skipped_no_coaching"}

        coaching_output = CoachingOutput.model_validate(
            coaching_result.structured_output_json
        )
        papers_contexts = await _build_papers_contexts(coaching_result)
        eval_scores = analysis.eval_scores or {}

        cove_service = BrainCoveService(
            anthropic_client=ctx["anthropic_client"],
            instructor_client=ctx["instructor_client"],
        )

        final_state, trace_payload = await run_distillation_graph(
            analysis_id=analysis_id,
            exercise_type=analysis.exercise_type,
            coaching_output=coaching_output,
            retrieved_papers_contexts=papers_contexts,
            eval_scores=eval_scores,
            anthropic_client=ctx["anthropic_client"],
            instructor_client=ctx["instructor_client"],
            cohere_client=ctx["cohere_client"],
            qdrant_client=ctx["qdrant_client"],
            brain_embedding_svc=ctx["brain_embedding_svc"],
            cove_service_factory=lambda: cove_service,
            db_session=db_session,
        )

        await db_session.commit()

        logger.info(
            "distill_analysis: analysis=%s validation=%s stored=%d",
            analysis_id,
            final_state.get("validation_decision"),
            len(final_state.get("stored_ids") or []),
        )
        return {
            "status": "ok",
            "validation_decision": final_state.get("validation_decision"),
            "stored_ids": [str(i) for i in (final_state.get("stored_ids") or [])],
            "trace_summary": {
                "nodes_count": len(trace_payload.get("nodes_executed") or [])
            },
        }
```

- [ ] **Step 4: Register the streaq task wrapper**

Edit `backend/app/workers/streaq_worker.py` and ADD the following wrapper after the existing `ingest_paper` task:

```python
@worker.task(timeout=300)
async def distill_analysis(
    analysis_id: UUID,
    context: WorkerContext = WorkerDepends(),
) -> dict[str, Any]:
    """Phase 3 Batch 2 distillation pipeline. See distillation_worker.py."""
    from app.workers.distillation_worker import distill_analysis_body as _distill

    ctx = _adapt_ctx(context)
    # Additional deps must be provided by process_analysis when it constructs
    # the task args, or by a centralised deps-builder. The drop-in pattern
    # here mirrors paper_ingestion: the body rebuilds deps from env.
    from app.workers.deps import build_distillation_ctx

    extra = await build_distillation_ctx()
    ctx.update(extra)
    return await _distill(ctx, analysis_id)
```

- [ ] **Step 5: Create the deps builder helper**

Create `backend/app/workers/deps.py` (or append to an existing deps module if one already exists):

```python
"""Worker dependency builder for distillation.

Centralises construction of the heavyweight clients (Anthropic,
instructor, Cohere, Qdrant, BrainEmbeddingService) so task bodies can
stay thin.
"""

from __future__ import annotations

import os
from typing import Any

import anthropic
import instructor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.brain_embedding import BrainEmbeddingService
from app.services.cohere_client import CohereEmbedClient
from app.services.qdrant import QdrantClientWrapper


async def build_distillation_ctx() -> dict[str, Any]:
    """Build the non-session dependencies the distillation body expects."""
    anthropic_client = anthropic.AsyncAnthropic()
    instructor_client = instructor.from_anthropic(anthropic_client)
    cohere_client = CohereEmbedClient()
    qdrant_client = QdrantClientWrapper()
    brain_embedding = BrainEmbeddingService(
        cohere_client=cohere_client, qdrant_client=qdrant_client
    )

    engine = create_async_engine(
        os.environ["DATABASE_URL"], connect_args={"statement_cache_size": 0}
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    return {
        "anthropic_client": anthropic_client,
        "instructor_client": instructor_client,
        "cohere_client": cohere_client.raw_client,  # direct access for embed_batch
        "qdrant_client": qdrant_client.raw_client,
        "brain_embedding_svc": brain_embedding,
        "db_session_maker": session_maker,
    }
```

> **Note:** if `CohereEmbedClient` or `QdrantClientWrapper` do not expose `raw_client` attributes, the integration test will surface that at step 7 and `deps.py` must be adjusted to pass the wrapper directly. Keep the wrapper API consistent with what `lifecycle_decision` expects (calls `.embed_batch` and `.search`).

- [ ] **Step 6: Add `_maybe_enqueue_distillation` helper to `analysis_worker.py`**

In `backend/app/workers/analysis_worker.py`, add this helper function near the top-level helpers (after the existing `_dispatch_coaching` block):

```python
async def _maybe_enqueue_distillation(
    *,
    analysis_id: uuid.UUID,
    eval_scores: dict[str, Any],
) -> None:
    """Phase 3 Batch 2: enqueue the distillation pipeline when gated.

    Gate: SPELIX_DISTILLATION_ENABLED env=1 AND eval_scores.overall >= 0.6.
    Failure is swallowed as a warning — distillation MUST NEVER fail the
    user-facing analysis.
    """
    flag = os.environ.get("SPELIX_DISTILLATION_ENABLED", "0").lower()
    if flag not in ("1", "true", "yes"):
        return
    overall = (eval_scores or {}).get("overall")
    if overall is None or overall < 0.6:
        return
    try:
        # Wrapper lives alongside other task wrappers in streaq_worker.py;
        # body lives in distillation_worker.py (same pattern as process_analysis).
        from app.workers.streaq_worker import distill_analysis as _task

        await _task.enqueue(analysis_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("distillation enqueue failed (%s: %s)", type(exc).__name__, exc)
```

> **Note:** the test in Step 1 patches `app.workers.distillation_worker.distill_analysis.enqueue` — keep that import path working.

- [ ] **Step 7: Wire the helper into the pipeline tail**

In `backend/app/workers/analysis_worker.py`, find the block in `_run_pipeline` (or `process_analysis`) that executes immediately after `analysis.eval_scores` is persisted to the DB (near `analysis.eval_scores = final_state.get("eval_scores")` around line 802). After the `await repo.update(analysis)` call, append:

```python
    await _maybe_enqueue_distillation(
        analysis_id=analysis.id,
        eval_scores=analysis.eval_scores or {},
    )
```

- [ ] **Step 8: Update `backlog.md` progress note**

Run: `cd ../spelix-phase3-batch2 && uv run pytest tests/integration/test_distillation_worker_e2e.py -v`
Expected: 4 passed.

- [ ] **Step 9: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/workers/distillation_worker.py backend/app/workers/streaq_worker.py backend/app/workers/deps.py backend/app/workers/analysis_worker.py backend/tests/integration/test_distillation_worker_e2e.py && git commit -m "feat(worker): distill_analysis streaq task + gated enqueue (P3-004)"
```

---

## Task 11b: Extend consent cascade to new candidates table (FR-BRAIN-16)

**Files:**
- Modify: `backend/app/workers/consent_cascade.py`
- Modify/Create: `backend/tests/integration/test_consent_cascade.py` (extend existing if present)

**Why:** FR-BRAIN-16 requires the consent-withdrawal cascade to remove the withdrawing user's analysis IDs from `source_analysis_ids` arrays across ALL Coach Brain entries. The existing cascade worker only touches `coach_brain_entries`; the new `coach_brain_candidates` table is a second store of `source_analysis_ids` and MUST participate in the cascade.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/integration/test_consent_cascade.py` (or create if absent):

```python
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coach_brain_candidate import CoachBrainCandidate
from app.workers.consent_cascade import cascade_consent_withdrawal


@pytest.mark.asyncio
async def test_cascade_removes_analysis_id_from_candidates(
    db_session: AsyncSession,
) -> None:
    withdrawing_user = uuid.uuid4()
    analysis_id = uuid.uuid4()
    other_analysis = uuid.uuid4()

    # Seed one candidate with only the withdrawing user's analysis
    solo = CoachBrainCandidate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="solo",
        source_analysis_ids=[analysis_id],
        lifecycle_decision="ADD",
    )
    # Seed another with mixed sources
    mixed = CoachBrainCandidate(
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="mixed",
        source_analysis_ids=[analysis_id, other_analysis],
        lifecycle_decision="ADD",
    )
    db_session.add_all([solo, mixed])
    await db_session.flush()

    # Stub analysis IDs lookup to return only `analysis_id` for this user
    ctx = {
        "db_session_maker": lambda: _MockSessionCtxManager(db_session),
        "redis": None,
    }
    # Monkey-patch the user's analysis IDs source if necessary; for this
    # test assume the worker accepts a pre-fetched list.
    await cascade_consent_withdrawal(ctx, str(withdrawing_user), test_analysis_ids=[analysis_id])

    await db_session.refresh(mixed)
    assert analysis_id not in mixed.source_analysis_ids
    assert other_analysis in mixed.source_analysis_ids

    # Solo candidate with no remaining sources should be soft-deleted
    await db_session.refresh(solo)
    assert solo.review_status == "rejected"
    assert solo.rejected_reason == "source_consent_withdrawn"


class _MockSessionCtxManager:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return None
```

> **Note:** if the existing `cascade_consent_withdrawal` signature does not accept `test_analysis_ids`, either add a keyword-only parameter for dependency injection OR adapt the test to seed a real `analyses` row owned by the user so the production code path runs unchanged. Pick whichever matches the existing pattern in `test_consent_cascade.py` when you read it.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/integration/test_consent_cascade.py -v -k candidates`
Expected: failure — the cascade does not touch `coach_brain_candidates` yet.

- [ ] **Step 3: Extend the cascade worker**

In `backend/app/workers/consent_cascade.py`, after the existing block that strips IDs from `coach_brain_entries`, add:

```python
# ---- extend to coach_brain_candidates (FR-BRAIN-16) ----
from sqlalchemy import func, select  # if not already imported at top of module
from app.models.coach_brain_candidate import CoachBrainCandidate

cand_stmt = (
    select(CoachBrainCandidate)
    .where(CoachBrainCandidate.source_analysis_ids.op("&&")(analysis_ids))
)
cand_rows = (await db_session.execute(cand_stmt)).scalars().all()
for row in cand_rows:
    remaining = [aid for aid in row.source_analysis_ids if aid not in analysis_ids]
    if not remaining:
        row.review_status = "rejected"
        row.rejected_reason = "source_consent_withdrawn"
        row.source_analysis_ids = []
    else:
        row.source_analysis_ids = remaining
await db_session.flush()
```

(Adjust variable names `db_session` / `analysis_ids` to match whatever the existing worker function uses — read the surrounding code before inserting.)

- [ ] **Step 4: Run tests**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest tests/integration/test_consent_cascade.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/app/workers/consent_cascade.py backend/tests/integration/test_consent_cascade.py && git commit -m "feat(consent): cascade withdrawal to coach_brain_candidates (FR-BRAIN-16)"
```

---

## Task 12: `backend/CLAUDE.md` Architecture Section

**Files:**
- Modify: `backend/CLAUDE.md`

- [ ] **Step 1: Add "Phase 3 Distillation Architecture" section**

Append a new section to `backend/CLAUDE.md` immediately after the existing "Phase 3 Agent Architecture (FR-AICP-18/19/20)" section:

```markdown
## Phase 3 Distillation Pipeline (FR-BRAIN-06/14/17)

The distillation pipeline lives in `app/distillation/`. It is a SEPARATE
compiled `StateGraph` from the coaching agent per ADR-BRAIN-07 — different
lifecycle, different invocation, different deps. Runs async after
`process_analysis` reaches `completed`; never blocks user-facing coaching.

### Feature flags

| env var | default | meaning |
|---------|---------|---------|
| `SPELIX_DISTILLATION_ENABLED` | `0` | When `1`, `process_analysis` enqueues `distill_analysis` for every completed analysis whose `eval_scores.overall >= 0.6`. When `0`, no distillation runs. |

### Rollout plan

1. Merge with `SPELIX_DISTILLATION_ENABLED=0` (no behavioural change).
2. Post-deploy: flip the flag on for one test-account analysis.
3. Inspect `coach_brain_candidates` row, CoVe result, lifecycle decision.
4. If sane, flip flag on globally. If not, flag off + iterate.

### Graph flow

`START -> extract_insights -> validate_quality -> [reject|continue] -> lifecycle_decision -> cove_verify -> format_entry -> store_entry -> END`

### Storage model

- Candidates land in a **new** `coach_brain_candidates` table
  (migration 011) — NOT in the existing `coach_brain_entries` table.
  Retrieval (`DualCollectionOrchestrator`) remains filtered to
  `coach_brain_entries.status='active'` so unvetted candidates never
  reach live coaching.
- `lifecycle_decision='ADD'` → candidate `review_status='pending'` (Batch 3
  admin queue).
- `lifecycle_decision='UPDATE'` → candidate `review_status='superseded'`
  (audit-only) + same transaction bumps `coach_brain_entries.confirmation_count`
  on the nearest active entry and appends `source_analysis_id`
  (FR-BRAIN-18).
- `lifecycle_decision='NOOP'` → no row written; telemetry log only.

### Gotchas

- Distillation enqueue failures are SWALLOWED as warnings — the parent
  analysis must always finish successfully for the user. Expect the
  occasional warning in worker logs; investigate if persistent.
- The slim `BrainCoveService` (`app/distillation/cove_brain.py`) is
  separate from `app/services/cove.py::CoveVerificationService`. Do NOT
  try to share: the coaching-path service extracts claims from a full
  `CoachingOutput`, whereas the distillation service verifies a single
  already-atomic coaching cue.
- `CoachBrainCandidate.review_status='superseded'` rows are NEVER shown
  in the Batch 3 review UI (filter: `review_status='pending'`). They
  exist purely for provenance — one row per UPDATE confirmation.
- Do NOT extend `coach_brain_entries.status` CHECK to add `'candidate'`.
  The hard separation between the two tables is load-bearing for
  retrieval correctness.
```

- [ ] **Step 2: Commit**

```bash
cd ../spelix-phase3-batch2 && git add backend/CLAUDE.md && git commit -m "docs(backend): phase 3 distillation architecture section"
```

---

## Task 13: ADRs, Backlog, Session Memory

**Files:**
- Modify: `decisions.md`
- Modify: `backlog.md`

- [ ] **Step 1: Append three ADRs to `decisions.md`**

Append to `decisions.md` (never edit existing ADRs — strict append-only):

```markdown
## ADR-DISTILL-01: Candidate storage in a new `coach_brain_candidates` table (Session 41)

**Context:** Phase 3 distillation needs a place to write unvetted entries until expert review promotes them. Options: (a) add `status='candidate'` to `coach_brain_entries` CHECK constraint and rely on retrieval filters; (b) new `coach_brain_candidates` table with a separate lifecycle column.

**Decision:** Option (b). The retrieval path (`DualCollectionOrchestrator`) filters on `status='active'`; extending the enum risks accidental leakage if any future predicate change drops that filter. A separate table also makes RLS admin-only trivially, gives us a distinct primary key space for Batch 3's `promoted_entry_id` pointer, and matches the session-40 handoff directive.

**Consequences:** Two tables to maintain. Batch 3 promotion writes BOTH — `INSERT INTO coach_brain_entries (status='active', ...)` + `UPDATE coach_brain_candidates SET review_status='approved', promoted_entry_id=...`. FR-BRAIN-16 cascade (consent withdrawal) must target both tables' `source_analysis_ids` GIN indexes.

## ADR-DISTILL-02: Invocation via streaq task, not `asyncio.create_task` (Session 41)

**Context:** FR-BRAIN-06 says "Invoked via `asyncio.create_task` (MVP) or task queue job (production)". We are on streaq already; production-grade invocation is cheap.

**Decision:** New `distill_analysis` streaq task, `timeout=300`, enqueued at the tail of `process_analysis` when `SPELIX_DISTILLATION_ENABLED=1` AND `eval_scores.overall >= 0.6`. `asyncio.create_task` loses retries, isolation, and heartbeat visibility; streaq gives all three with zero extra infra.

**Consequences:** Distillation queues up behind subsequent analyses (streaq `concurrency=1`). Acceptable at L2 beta volume (<10 analyses/day). If p95 coaching latency regresses we revisit — a distillation-specific queue is a straightforward next step.

## ADR-DISTILL-03: Slim `BrainCoveService` for single-claim verification (Session 41)

**Context:** FR-BRAIN-14 requires CoVe against `papers_rag` before every Coach Brain promotion. The existing `CoveVerificationService` (P2-014) extracts claims from a full `CoachingOutput`. Distillation candidates are already atomic coaching cues.

**Decision:** Introduce `app/distillation/cove_brain.py::BrainCoveService.verify_claim(claim: str, contexts: list[RetrievedContext])` that skips claim-extraction and generates exactly one verification question per candidate. Reuses the Haiku 4.5 model and prompt style of the coaching-path service. The coaching-path `CoveVerificationService` remains untouched.

**Consequences:** Two CoVe services in the codebase. Acceptable — they have different inputs. Consolidation deferred until one of the services sees zero traffic or the prompt styles drift far enough to justify a common abstraction.
```

- [ ] **Step 2: Update `backlog.md`**

In `backlog.md` §`Batch 2 — Distillation Pipeline`:

- Change P3-004 status from `pending` to `done (PR #<N> → <SHA>)` — placeholder, filled at merge.
- Change P3-005 status from `pending` to `done (PR #<N> → <SHA>)`.

Then add a new row in §`Backlog — Deferred post-L2` (or create that section at the bottom if absent):

```markdown
| P3-008 | FR-BRAIN-08 auto-triage — confidence-based auto-approve/auto-reject thresholds for distilled candidates | M | P3-004, P3-005 | FR-BRAIN-08 | deferred post-L2 — blocks on ≥50 human-reviewed candidates for threshold calibration (per SRS "start conservative") |
```

- [ ] **Step 3: Commit**

```bash
cd ../spelix-phase3-batch2 && git add decisions.md backlog.md && git commit -m "docs(adr): ADR-DISTILL-01/02/03 + backlog update for P3-004/005/008"
```

---

## Task 14: Specialist Audits

**Files:**
- None (read-only agents)

- [ ] **Step 1: Run `spelix-auditor`**

Invoke: > "Use the `spelix-auditor` agent to verify Phase 3 Batch 2 against SRS requirements FR-BRAIN-06, FR-BRAIN-14, FR-BRAIN-17, FR-BRAIN-18, and ADR-BRAIN-07. Focus on: (a) the new `coach_brain_candidates` table meets the payload fields the SRS requires; (b) the graph topology matches FR-BRAIN-06's node ordering; (c) FR-BRAIN-18's confirmation_count semantics are correctly implemented in `store_entry`; (d) no FDA SaMD language (\"injury\", \"diagnose\", \"treat\") anywhere in the distillation prompts or user-facing strings."

Expected: zero CRITICAL findings. HIGH or MEDIUM findings get triaged inline before moving on. If any CRITICAL finding surfaces, fix it in a follow-up commit and re-run the auditor.

- [ ] **Step 2: Run `spelix-security-reviewer`**

Invoke: > "Use the `spelix-security-reviewer` agent to check migration 011 and the new `coach_brain_candidates` repository. Verify: (a) RLS policy is admin-only; (b) no PII columns; (c) `source_analysis_ids` cascade target is indexed (GIN); (d) distillation task does not return raw LLM output to API callers."

Expected: zero CRITICAL findings. Fix any surfaced issues inline.

- [ ] **Step 3: Commit fixes (if any)**

Only commit if the auditors surfaced real issues.

```bash
cd ../spelix-phase3-batch2 && git add -A && git commit -m "fix: <describe audit-surfaced issue>"
```

---

## Task 15: Final Verification + PR

**Files:**
- None (verification only)

- [ ] **Step 1: Full backend test suite**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest -x -q`
Expected: 1580+ passing, 19 skipped, 0 failing. Record the exact count for the PR description.

- [ ] **Step 2: Coverage check**

Run: `cd ../spelix-phase3-batch2/backend && uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=90`
Expected: ≥ 90 % coverage, exit code 0.

- [ ] **Step 3: Static checks**

Run: `cd ../spelix-phase3-batch2/backend && uv run ruff check . && uv run pyright`
Expected: 0 errors.

- [ ] **Step 4: Migration smoke test (re-apply from clean)**

Run: `cd ../spelix-phase3-batch2/backend && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: `alembic current` returns `011_coach_brain_candidates (head)`; no errors.

- [ ] **Step 5: Push branch**

```bash
cd ../spelix-phase3-batch2 && git push -u origin feat/phase3-batch2-distillation
```

- [ ] **Step 6: Open PR via GitHub MCP**

Use `mcp__github__create_pull_request` with:
- title: `feat(distillation): phase 3 batch 2 — distillation pipeline (P3-004/005)`
- body (HEREDOC):

```markdown
## Summary

Phase 3 Batch 2 — the async distillation pipeline that turns completed coaching
analyses into reviewable candidate `coach_brain` entries.

- **FR-BRAIN-06** — standalone LangGraph `StateGraph` with gate on eval scores
- **FR-BRAIN-14** — CoVe verification against `papers_rag` before promotion
- **FR-BRAIN-17** — ADD/UPDATE/NOOP cosine lifecycle
- **FR-BRAIN-18** — confirmation_count bump on UPDATE path

Feature-flag gated (`SPELIX_DISTILLATION_ENABLED`, default `0`). Merge is a
no-op behavioural change.

## ADRs

- ADR-DISTILL-01: new `coach_brain_candidates` table
- ADR-DISTILL-02: streaq task invocation
- ADR-DISTILL-03: slim `BrainCoveService`

## Test plan
- [ ] Local: `uv run pytest -x -q` → 1580+ passing
- [ ] Coverage ≥ 90 %
- [ ] `ruff check .` + `pyright` clean
- [ ] Migration 011 round-trip clean
- [ ] `spelix-auditor` zero CRITICAL
- [ ] `spelix-security-reviewer` zero CRITICAL
- [ ] Post-merge: flip `SPELIX_DISTILLATION_ENABLED=1` on one test analysis, verify candidate row lands with sensible lifecycle_decision + cove_verified.
```

- [ ] **Step 7: Monitor CI**

Use `mcp__github__get_pull_request_status` every few minutes until all checks pass.

- [ ] **Step 8: Merge (merge commit, NEVER squash)**

Use `mcp__github__merge_pull_request` with `merge_method="merge"`.

- [ ] **Step 9: Verify deploy**

1. `mcp__github__get_pull_request_status` must report "Deploy to Production" `pass`.
2. `ssh spelix-droplet "git log --oneline -1"` — must match the merge SHA.
3. `ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"` — all healthy.

- [ ] **Step 10: Post-merge op (deferred or immediate)**

- Set `SPELIX_DISTILLATION_ENABLED=1` on the droplet `.env.prod` ONLY when ready to smoke test. Restart `spelix-worker-1`.
- Trigger one analysis from the E2E test account. After `status=completed`, query:
  ```sql
  SELECT id, lifecycle_decision, cove_verified, review_status
  FROM coach_brain_candidates
  ORDER BY created_at DESC LIMIT 5;
  ```
- If a row landed with sensible values, leave flag on.
- If anything looks off, flip to `0`, restart worker, triage in a follow-up.

---

## Self-Review Checklist (run before handing off)

- [x] Every task has exact file paths.
- [x] Every code step shows the full code.
- [x] Every test step shows the exact expected result.
- [x] No "TBD" or "TODO" in any step.
- [x] Types and method signatures are consistent across tasks
      (`extract_insights(state, *, anthropic_client, instructor_client)`,
      `lifecycle_decision(state, *, cohere_client, qdrant_client, brain_embedding_svc)`,
      `cove_verify(state, *, cove_service)`, `store_entry(state, *, db_session)`).
- [x] Spec coverage: FR-BRAIN-06 (Task 10), FR-BRAIN-14 (Task 7), FR-BRAIN-17 (Task 6),
      FR-BRAIN-18 (Task 9 store_entry confirmation bump), ADR-BRAIN-07 (Task 13
      ADR-DISTILL-01 cites it).
- [x] Explicitly out-of-scope items (P3-006, P3-007, FR-BRAIN-08) appear nowhere in tasks.
- [x] Commits are atomic per task.
- [x] `spelix-migration` agent invoked for Alembic (Task 1), per CLAUDE.md rule.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-16-phase3-batch2-distillation.md`.** Two execution options:

1. **Subagent-Driven (recommended)** — dispatch fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute in this session using executing-plans, batch execution with checkpoints.

Which approach?
