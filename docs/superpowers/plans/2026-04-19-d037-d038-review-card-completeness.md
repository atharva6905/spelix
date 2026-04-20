# D-037 + D-038 Review Card Completeness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two FR-ADMN-12 review-card gaps: (D-038) extend the `entry_type` CHECK constraint + `EntryTypeLiteral` + distillation prompt to include `compensation` so the pre-existing forward-compatible UI banner can actually fire, and (D-037) surface the top 2 nearest approved Coach Brain entries on the review card via an on-demand similarity endpoint (replacing the current single `nearest_entry_id` line).

**Architecture:**
- **D-038** is a pure schema widening. Alembic migration 012 drops + recreates two CHECK constraints (`ck_coach_brain_entries_entry_type`, `ck_coach_brain_candidates_entry_type`) to include `'compensation'`. `EntryTypeLiteral` gains the new value; `extract.py` prompt enumerates it; the React `CoachBrainCandidate.entry_type` union gains it; the `as string` cast in `AdminCoachBrainCandidatesPage.tsx:190` is dropped. The banner already renders when `entry_type === "compensation"` — no UI additions.
- **D-037** adds one GET endpoint. `CandidateReviewService.get_similar_entries` re-embeds the candidate's contextual text via Cohere (`SEARCH_DOCUMENT`, same input type as `lifecycle_decision`), queries Qdrant `coach_brain` filtered by `exercise` + `status ∈ {'active','seed'}`, takes the top 2 hits, joins Qdrant point IDs back to `coach_brain_entries` rows for content preview, and returns `[{id, content, exercise, phase, entry_type, cosine_sim}]`. Frontend fetches the list on candidate change and renders it in place of the current single-line "Closest existing entry" block. No schema change, no stored-embedding column — the Cohere embed cost is negligible (one 256-token embed per card view).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, Cohere embed v4, Qdrant async client, React 19, Vitest, pytest.

**Requirements:** FR-ADMN-12 (completeness — top 2 similar + compensation banner routing). Size: S (D-037) + S (D-038). Parent: P3-006.

---

## File Structure

**New files:**
- `backend/alembic/versions/012_add_compensation_entry_type.py` — migration
- `backend/tests/unit/test_migration_012_compensation.py` — constraint test (inserts `entry_type='compensation'`)
- `backend/tests/unit/test_candidate_review_get_similar.py` — service test for D-037
- Plan lives at `docs/superpowers/plans/2026-04-19-d037-d038-review-card-completeness.md` (this file).

**Modified files:**
- `backend/app/schemas/coach_brain.py` — extend `EntryTypeLiteral`
- `backend/app/models/coach_brain_entry.py` — CHECK constraint string
- `backend/app/models/coach_brain_candidate.py` — CHECK constraint string
- `backend/app/distillation/extract.py` — LLM prompt enumerates `compensation`
- `backend/app/schemas/candidate_review.py` — `SimilarEntry` + `SimilarEntriesResponse`
- `backend/app/services/candidate_review.py` — `CandidateReviewService.get_similar_entries`
- `backend/app/api/v1/admin.py` — `GET /coach-brain/candidates/{id}/similar` route
- `backend/tests/unit/test_admin_candidates_api.py` — route tests
- `frontend/src/api/admin.ts` — TS union + `SimilarEntry` + `getCoachBrainCandidateSimilar`
- `frontend/src/pages/AdminCoachBrainCandidatesPage.tsx` — drop `as string` cast; replace single-nearest block with `SimilarEntriesList` component
- `frontend/src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx` — drop cast in existing compensation test; add similar-entries rendering test
- `backlog.md` — mark D-037 + D-038 done with PR SHA
- `decisions.md` — ADR if a non-trivial trade-off surfaces (re-embed-on-demand vs. stored embedding). Expected: no ADR; the choice is trivially bounded by "ship D-037 in S size" scope.

---

## Ship Order

D-038 first (Tasks 1–5) — schema widening unblocks any downstream D-037 tests that want to stub `compensation` candidates. D-037 follows (Tasks 6–12). Both ship in one PR to keep the FR-ADMN-12 closure atomic.

---

### Task 1: Migration 012 — extend both `entry_type` CHECK constraints

**Files:**
- Create: `backend/alembic/versions/012_add_compensation_entry_type.py`
- Test: `backend/tests/unit/test_migration_012_compensation.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_migration_012_compensation.py
"""D-038: coach_brain_candidates + coach_brain_entries must accept entry_type='compensation'."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_candidates_accept_compensation_entry_type(db_session: AsyncSession) -> None:
    # After migration 012 the CHECK constraint permits 'compensation'.
    await db_session.execute(
        text(
            """
            INSERT INTO coach_brain_candidates
            (id, exercise, phase, entry_type, content, trigger_tags,
             source_analysis_ids, eval_scores, lifecycle_decision,
             contradiction_flag, review_status)
            VALUES
            (:id, 'squat', 'descent', 'compensation',
             'knee valgus compensates for weak hip abduction',
             '{}', '{}', '{"faithfulness": 0.9}'::jsonb,
             'ADD', false, 'pending')
            """
        ),
        {"id": uuid.uuid4()},
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_entries_accept_compensation_entry_type(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO coach_brain_entries
            (id, content, exercise, phase, entry_type, status,
             confirmation_count, source_analysis_ids, trigger_tags, metadata)
            VALUES
            (:id, 'quad-dominant ascent compensates for posterior-chain weakness',
             'squat', 'ascent', 'compensation', 'seed',
             0, '{}', '{}', '{}'::jsonb)
            """
        ),
        {"id": uuid.uuid4()},
    )
    await db_session.flush()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_migration_012_compensation.py -xvs`
Expected: FAIL with `CheckViolationError: new row for relation "coach_brain_candidates" violates check constraint "ck_coach_brain_candidates_entry_type"` (and the same for entries).

- [ ] **Step 3: Write the Alembic migration**

```python
# backend/alembic/versions/012_add_compensation_entry_type.py
"""Add 'compensation' to entry_type CHECK constraints on coach_brain_* tables.

Revision ID: 012_compensation_entry_type
Revises: 011_coach_brain_candidates
Create Date: 2026-04-19

D-038 / FR-ADMN-12: the review-card UI already renders a "biomechanics
reviewer required" banner forward-compatibly when entry_type == 'compensation'
(AdminCoachBrainCandidatesPage.tsx:190). This migration widens the DB
CHECK constraints on both the candidates table (migration 011) and the
entries table (migration 004) so the distillation pipeline can actually
produce compensation-typed rows.

No backfill — the constraint is a pure widening; existing rows all match
the original four values.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "012_compensation_entry_type"
down_revision = "011_coach_brain_candidates"
branch_labels = None
depends_on = None


_NEW_VALUES = "('cue','correction','principle','drill','compensation')"
_OLD_VALUES = "('cue','correction','principle','drill')"


def upgrade() -> None:
    # coach_brain_candidates
    op.drop_constraint(
        "ck_coach_brain_candidates_entry_type",
        "coach_brain_candidates",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coach_brain_candidates_entry_type",
        "coach_brain_candidates",
        f"entry_type IN {_NEW_VALUES}",
    )

    # coach_brain_entries
    op.drop_constraint(
        "ck_coach_brain_entries_entry_type",
        "coach_brain_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coach_brain_entries_entry_type",
        "coach_brain_entries",
        f"entry_type IN {_NEW_VALUES}",
    )


def downgrade() -> None:
    # Downgrade ASSUMES no 'compensation' rows exist. If they do, the
    # DROP CONSTRAINT + ADD CONSTRAINT will fail on ADD — the operator must
    # DELETE or re-label those rows first. This is an intentional fail-loud.
    op.drop_constraint(
        "ck_coach_brain_candidates_entry_type",
        "coach_brain_candidates",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coach_brain_candidates_entry_type",
        "coach_brain_candidates",
        f"entry_type IN {_OLD_VALUES}",
    )

    op.drop_constraint(
        "ck_coach_brain_entries_entry_type",
        "coach_brain_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coach_brain_entries_entry_type",
        "coach_brain_entries",
        f"entry_type IN {_OLD_VALUES}",
    )
```

- [ ] **Step 4: Apply the migration**

Run: `cd backend && uv run alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade 011_coach_brain_candidates -> 012_compensation_entry_type`

- [ ] **Step 5: Re-run the test — expect PASS**

Run: `uv run pytest tests/unit/test_migration_012_compensation.py -xvs`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/012_add_compensation_entry_type.py \
        backend/tests/unit/test_migration_012_compensation.py
git commit -m "feat(models): add 'compensation' to entry_type CHECK constraint (D-038)"
```

---

### Task 2: Extend `EntryTypeLiteral` + model CheckConstraint strings

**Files:**
- Modify: `backend/app/schemas/coach_brain.py:59-64`
- Modify: `backend/app/models/coach_brain_entry.py:29-32`
- Modify: `backend/app/models/coach_brain_candidate.py:30-33`
- Test: existing Pydantic validation tests in `backend/tests/unit/test_schemas_coach_brain.py` (extend or add one)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/test_schemas_coach_brain.py` (or create if absent):

```python
def test_coach_brain_entry_create_accepts_compensation() -> None:
    from app.schemas.coach_brain import CoachBrainEntryCreate

    entry = CoachBrainEntryCreate(
        content="Quad-dominant ascent compensates for posterior-chain weakness",
        exercise="squat",
        phase="ascent",
        entry_type="compensation",
    )
    assert entry.entry_type == "compensation"


def test_coach_brain_candidate_create_accepts_compensation() -> None:
    from app.schemas.coach_brain_candidate import CoachBrainCandidateCreate

    candidate = CoachBrainCandidateCreate(
        exercise="squat",
        phase="descent",
        entry_type="compensation",
        content="Knee valgus compensates for weak hip abduction",
        source_analysis_ids=[],
        lifecycle_decision="ADD",
    )
    assert candidate.entry_type == "compensation"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_schemas_coach_brain.py -k compensation -xvs`
Expected: FAIL with `pydantic_core._pydantic_core.ValidationError: 1 validation error ... Input should be 'cue', 'correction', 'principle' or 'drill'`.

- [ ] **Step 3: Update `EntryTypeLiteral`**

Edit `backend/app/schemas/coach_brain.py:59-64` from:

```python
EntryTypeLiteral = Literal[
    "cue",
    "correction",
    "principle",
    "drill",
]
```

to:

```python
EntryTypeLiteral = Literal[
    "cue",
    "correction",
    "principle",
    "drill",
    "compensation",
]
```

- [ ] **Step 4: Update the SQLAlchemy CheckConstraint strings**

Edit `backend/app/models/coach_brain_entry.py:29-32`:

```python
# before
"entry_type IN ('cue','correction','principle','drill')",
name="ck_coach_brain_entries_entry_type",
# after
"entry_type IN ('cue','correction','principle','drill','compensation')",
name="ck_coach_brain_entries_entry_type",
```

Edit `backend/app/models/coach_brain_candidate.py:30-33` with the same change for `ck_coach_brain_candidates_entry_type`.

- [ ] **Step 5: Re-run the test — expect PASS**

Run: `uv run pytest tests/unit/test_schemas_coach_brain.py -k compensation -xvs`
Expected: 2 passed.

- [ ] **Step 6: Full backend test suite — no regressions**

Run: `uv run pytest tests/unit -x`
Expected: 1649+ passing (Phase 3 Batch 3 baseline), 0 failing. If any literal-shape test fails, update the expected set in that test.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/coach_brain.py \
        backend/app/models/coach_brain_entry.py \
        backend/app/models/coach_brain_candidate.py \
        backend/tests/unit/test_schemas_coach_brain.py
git commit -m "feat(schemas): add 'compensation' to EntryTypeLiteral + SQLAlchemy CHECK (D-038)"
```

---

### Task 3: Update distillation extract prompt to enumerate `compensation`

**Files:**
- Modify: `backend/app/distillation/extract.py:43-46`
- Test: `backend/tests/unit/test_distillation_extract.py` (add additive case)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/test_distillation_extract.py`:

```python
@pytest.mark.asyncio
async def test_extract_accepts_compensation_entry_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-038: the extract prompt must accept compensation-typed insights
    from the LLM so the distillation pipeline can produce the rows the
    UI banner expects."""
    from app.distillation import extract
    from app.distillation.state import CandidateInsight
    from app.schemas.coaching import CoachingOutput

    class _FakeClient:
        async def generate(self, **kwargs: object) -> list[CandidateInsight]:
            return [
                CandidateInsight(
                    content="Knee valgus compensates for weak hip abduction — cue hip external rotation.",
                    exercise="squat",
                    phase="descent",
                    entry_type="compensation",
                    trigger_tags=["knee_valgus", "hip_abduction"],
                    confidence_score=0.82,
                )
            ]

    # Replace the module-level extraction helper with the fake client.
    monkeypatch.setattr(
        extract,
        "_extract_insights_via_instructor",
        lambda **kw: _FakeClient().generate(**kw),
    )

    state = {
        "coaching_output": CoachingOutput(
            summary="", strengths=[], issues=[], correction_plan=[],
            disclaimer="", confidence_level="High", dimension_addressed="safety",
        ),
        "exercise_type": "squat",
        "retrieved_papers_contexts": [],
    }
    out = await extract.extract_insights(state, anthropic_client=None)
    assert out["candidates"][0].entry_type == "compensation"
```

- [ ] **Step 2: Run it — expect fail until prompt is updated**

Run: `uv run pytest tests/unit/test_distillation_extract.py -k compensation -xvs`
Expected: either FAIL (prompt-validator rejects) or PASS (if the Literal is already the only gate). Either way, the test is additive — once Steps 3–4 land it must PASS.

- [ ] **Step 3: Update the extract prompt**

Edit `backend/app/distillation/extract.py:43-46`:

```python
# before
"(setup|descent|bottom|ascent|lockout|general|null), entry_type "
"(cue|correction|principle|drill), trigger_tags (e.g. knee_cave, "

# after
"(setup|descent|bottom|ascent|lockout|general|null), entry_type "
"(cue|correction|principle|drill|compensation), trigger_tags (e.g. knee_cave, "
```

Immediately after the enumerated list line, add a one-line clarifier:

```python
'When the insight describes a multi-step causal chain where one weakness '
'drives a secondary error (e.g. "knee valgus compensates for weak hip '
'abduction"), tag entry_type="compensation". Biomechanics reviewers '
'will gate these separately (FR-ADMN-12).',
```

- [ ] **Step 4: Re-run — expect PASS**

Run: `uv run pytest tests/unit/test_distillation_extract.py -k compensation -xvs`
Expected: 1 passed.

- [ ] **Step 5: Full distillation tests — no regressions**

Run: `uv run pytest tests/unit/test_distillation_* -x`
Expected: all existing distillation tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/distillation/extract.py \
        backend/tests/unit/test_distillation_extract.py
git commit -m "feat(distillation): extract prompt enumerates 'compensation' entry_type (D-038)"
```

---

### Task 4: Frontend TS union + drop cast + existing test cleanup

**Files:**
- Modify: `frontend/src/api/admin.ts:247-265`
- Modify: `frontend/src/pages/AdminCoachBrainCandidatesPage.tsx:190`
- Modify: `frontend/src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx:137-146`

- [ ] **Step 1: Update the test to remove the `as unknown as` cast**

Edit `frontend/src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx:137-146`:

```tsx
// before
{ ...candidate, entry_type: "compensation" as unknown as typeof candidate.entry_type }

// after
{ ...candidate, entry_type: "compensation" }
```

- [ ] **Step 2: Run the test — expect TYPE ERROR**

Run: `cd frontend && npx tsc --noEmit`
Expected: `Type '"compensation"' is not assignable to type '"cue" | "correction" | "principle" | "drill"'.` on the test file.

- [ ] **Step 3: Widen the TS union**

Edit `frontend/src/api/admin.ts:247-265` — change `entry_type` in `CoachBrainCandidate`:

```ts
// before
entry_type: "cue" | "correction" | "principle" | "drill";

// after
entry_type: "cue" | "correction" | "principle" | "drill" | "compensation";
```

- [ ] **Step 4: Drop the `as string` cast on the banner**

Edit `frontend/src/pages/AdminCoachBrainCandidatesPage.tsx:190` from:

```tsx
{(candidate.entry_type as string) === "compensation" && (
```

to:

```tsx
{candidate.entry_type === "compensation" && (
```

- [ ] **Step 5: Re-run typecheck + tests**

Run:
```bash
cd frontend && npx tsc --noEmit
npx vitest run src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx
```
Expected: 0 TS errors; existing compensation-banner test + all other AdminCoachBrainCandidatesPage tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/admin.ts \
        frontend/src/pages/AdminCoachBrainCandidatesPage.tsx \
        frontend/src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx
git commit -m "feat(admin): widen entry_type union + drop banner cast (D-038)"
```

---

### Task 5: Backlog + ADR hygiene for D-038

**Files:**
- Modify: `backlog.md:467`

- [ ] **Step 1: Flip D-038 row status**

Edit `backlog.md:467` — change the status cell from `open` to `done — <sha>` after Task 4 commit. Pull the SHA with `git rev-parse HEAD`.

- [ ] **Step 2: No ADR**

D-038 is a pure schema widening that matches the SRS definition of "CoachBrainEntry ... entry_type (cue/heuristic/compensation)" (SRS.md:108) — no design trade-off to record. Skip `/adr`.

- [ ] **Step 3: Commit**

```bash
git add backlog.md
git commit -m "chore(backlog): close D-038 — compensation entry_type shipped"
```

---

## D-037 — top 2 similar approved entries on review card

### Task 6: `CandidateReviewService.get_similar_entries` — failing test

**Files:**
- Create: `backend/tests/unit/test_candidate_review_get_similar.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_candidate_review_get_similar.py
"""D-037: CandidateReviewService.get_similar_entries returns top N approved
entries by cosine similarity, joined back to Postgres for content preview."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.coach_brain_candidate import CoachBrainCandidate
from app.schemas.candidate_review import SimilarEntry
from app.services.candidate_review import (
    CandidateNotFound,
    CandidateReviewService,
)


def _make_candidate(**overrides: object) -> CoachBrainCandidate:
    base = dict(
        id=uuid.uuid4(),
        exercise="squat",
        phase="descent",
        entry_type="cue",
        content="drive knees out at the bottom",
        trigger_tags=["knee_valgus"],
        source_analysis_ids=[],
        confidence_score=0.8,
        eval_scores={"faithfulness": 0.9},
        cove_verified=True,
        cove_explanation="",
        cove_trace=[],
        lifecycle_decision="ADD",
        nearest_entry_id=None,
        nearest_cosine_sim=None,
        contradiction_flag=False,
        review_status="pending",
        created_at="2026-04-19T00:00:00Z",
        updated_at="2026-04-19T00:00:00Z",
    )
    base.update(overrides)
    return CoachBrainCandidate(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_similar_entries_returns_top_2_ordered_by_cosine() -> None:
    candidate = _make_candidate()
    e1_id, e2_id = uuid.uuid4(), uuid.uuid4()

    candidate_repo = MagicMock()
    candidate_repo.get_by_id = AsyncMock(return_value=candidate)

    entry_repo = MagicMock()
    entry_repo.get_by_id = AsyncMock(
        side_effect=lambda eid: MagicMock(
            id=eid,
            content=f"entry-{eid}",
            exercise="squat",
            phase="descent",
            entry_type="cue",
        )
    )

    brain_embedding = MagicMock()
    brain_embedding.build_contextual_text = MagicMock(return_value="ctx text")

    cohere = MagicMock()
    cohere.embed_batch = AsyncMock(return_value=[[0.1] * 1024])

    hit1 = MagicMock(id=str(e1_id), score=0.88)
    hit2 = MagicMock(id=str(e2_id), score=0.81)
    qdrant = MagicMock()
    qdrant.query_points = AsyncMock(return_value=MagicMock(points=[hit1, hit2]))

    svc = CandidateReviewService(
        db=MagicMock(),
        candidate_repo=candidate_repo,
        entry_repo=entry_repo,
        brain_embedding=brain_embedding,
    )
    svc._cohere_client = cohere  # type: ignore[attr-defined]
    svc._qdrant_client = qdrant  # type: ignore[attr-defined]

    result = await svc.get_similar_entries(candidate_id=candidate.id, limit=2)

    assert [r.id for r in result] == [e1_id, e2_id]
    assert result[0].cosine_sim == pytest.approx(0.88)
    assert result[1].cosine_sim == pytest.approx(0.81)
    # Qdrant filter must pin exercise AND status ∈ {active, seed}
    call = qdrant.query_points.await_args
    assert call.kwargs["collection"] == "coach_brain" or call.args[0] == "coach_brain"
    assert call.kwargs["limit"] == 2


@pytest.mark.asyncio
async def test_get_similar_entries_raises_when_candidate_missing() -> None:
    candidate_repo = MagicMock()
    candidate_repo.get_by_id = AsyncMock(return_value=None)

    svc = CandidateReviewService(
        db=MagicMock(),
        candidate_repo=candidate_repo,
        entry_repo=MagicMock(),
        brain_embedding=MagicMock(),
    )
    svc._cohere_client = MagicMock()  # type: ignore[attr-defined]
    svc._qdrant_client = MagicMock()  # type: ignore[attr-defined]

    with pytest.raises(CandidateNotFound):
        await svc.get_similar_entries(candidate_id=uuid.uuid4(), limit=2)


@pytest.mark.asyncio
async def test_get_similar_entries_empty_qdrant_returns_empty_list() -> None:
    candidate = _make_candidate()
    candidate_repo = MagicMock()
    candidate_repo.get_by_id = AsyncMock(return_value=candidate)

    brain_embedding = MagicMock()
    brain_embedding.build_contextual_text = MagicMock(return_value="ctx")

    cohere = MagicMock()
    cohere.embed_batch = AsyncMock(return_value=[[0.1] * 1024])

    qdrant = MagicMock()
    qdrant.query_points = AsyncMock(return_value=MagicMock(points=[]))

    svc = CandidateReviewService(
        db=MagicMock(),
        candidate_repo=candidate_repo,
        entry_repo=MagicMock(),
        brain_embedding=brain_embedding,
    )
    svc._cohere_client = cohere  # type: ignore[attr-defined]
    svc._qdrant_client = qdrant  # type: ignore[attr-defined]

    result = await svc.get_similar_entries(candidate_id=candidate.id, limit=2)
    assert result == []
```

- [ ] **Step 2: Run the test — expect fail**

Run: `uv run pytest tests/unit/test_candidate_review_get_similar.py -xvs`
Expected: FAIL with `AttributeError: 'CandidateReviewService' object has no attribute 'get_similar_entries'` (or equivalent — the method does not exist yet and neither does `SimilarEntry`).

---

### Task 7: `SimilarEntry` + `SimilarEntriesResponse` schemas

**Files:**
- Modify: `backend/app/schemas/candidate_review.py`

- [ ] **Step 1: Add the schemas**

Append to `backend/app/schemas/candidate_review.py`:

```python
class SimilarEntry(BaseModel):
    """One nearest approved/seed Coach Brain entry surfaced on the review card.

    D-037 / FR-ADMN-12: the reviewer needs to see up to 2 existing entries
    that already cover similar ground, so they can spot near-duplicates
    before promoting a new candidate.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    exercise: ExerciseLiteral
    phase: PhaseLiteral | None
    entry_type: EntryTypeLiteral
    cosine_sim: float


class SimilarEntriesResponse(BaseModel):
    items: list[SimilarEntry]
```

- [ ] **Step 2: Run the test — still failing on the service method, schemas importable**

Run: `uv run pytest tests/unit/test_candidate_review_get_similar.py -xvs`
Expected: import of `SimilarEntry` now succeeds; the AttributeError on `get_similar_entries` remains.

---

### Task 8: Implement `CandidateReviewService.get_similar_entries`

**Files:**
- Modify: `backend/app/services/candidate_review.py`

- [ ] **Step 1: Update the service constructor to accept `cohere_client` + `qdrant_client`**

In `backend/app/services/candidate_review.py`, add the two clients to `__init__`:

```python
def __init__(
    self,
    db: AsyncSession,
    candidate_repo: CoachBrainCandidateRepository,
    entry_repo: CoachBrainRepository,
    brain_embedding: BrainEmbeddingService,
    cohere_client: Any | None = None,
    qdrant_client: Any | None = None,
) -> None:
    self._db = db
    self._candidate_repo = candidate_repo
    self._entry_repo = entry_repo
    self._brain_embedding = brain_embedding
    self._cohere_client = cohere_client
    self._qdrant_client = qdrant_client
```

The existing approve/reject paths do not touch these — they stay optional, constructed-at-DI-time for the similar endpoint only.

- [ ] **Step 2: Add the new method**

Append to the class:

```python
async def get_similar_entries(
    self,
    *,
    candidate_id: uuid.UUID,
    limit: int = 2,
) -> list["SimilarEntry"]:
    """Return top-N nearest active/seed Coach Brain entries for a candidate.

    FR-ADMN-12 (D-037): reviewer sees up to 2 existing entries closest to
    the pending candidate so near-duplicates are obvious pre-approve.

    Re-embeds the candidate's contextual text on demand rather than storing
    the insight embedding — distillation runs daily at low volume and the
    Cohere call is cheap (<10 ms, <0.01¢) per card view. Avoids a schema
    change during the L2 sprint.
    """
    from qdrant_client import models as qdrant_models

    from app.schemas.candidate_review import SimilarEntry
    from app.schemas.coach_brain import CoachBrainEntryCreate
    from app.services.cohere_client import EmbedInputType
    from app.services.qdrant import COLLECTION_COACH_BRAIN

    candidate = await self._candidate_repo.get_by_id(candidate_id)
    if candidate is None:
        raise CandidateNotFound(str(candidate_id))

    proxy = CoachBrainEntryCreate(
        content=candidate.content,
        exercise=candidate.exercise,
        phase=candidate.phase,
        entry_type=candidate.entry_type,
        trigger_tags=list(candidate.trigger_tags or []),
    )
    ctx_text = self._brain_embedding.build_contextual_text(proxy)

    [vector] = await self._cohere_client.embed_batch(
        [ctx_text], input_type=EmbedInputType.SEARCH_DOCUMENT
    )

    # FR-BRAIN-05 cold-start: both active and seed are retrievable.
    query_filter = qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="exercise",
                match=qdrant_models.MatchValue(value=candidate.exercise),
            ),
            qdrant_models.FieldCondition(
                key="status",
                match=qdrant_models.MatchAny(any=["active", "seed"]),
            ),
        ]
    )
    response = await self._qdrant_client.query_points(
        collection=COLLECTION_COACH_BRAIN,
        query=vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=False,
    )
    hits = list(response.points)

    results: list[SimilarEntry] = []
    for hit in hits:
        entry_id = uuid.UUID(hit.id) if isinstance(hit.id, str) else hit.id
        entry = await self._entry_repo.get_by_id(entry_id)
        if entry is None:
            # Qdrant/Postgres drift — skip the orphan silently; it's not
            # reviewer-relevant and the log line is enough.
            logger.warning(
                "get_similar_entries: Qdrant hit %s missing in Postgres",
                entry_id,
            )
            continue
        results.append(
            SimilarEntry(
                id=entry.id,
                content=entry.content,
                exercise=entry.exercise,
                phase=entry.phase,
                entry_type=entry.entry_type,
                cosine_sim=float(hit.score),
            )
        )
    return results
```

- [ ] **Step 3: Run the service test — expect PASS**

Run: `uv run pytest tests/unit/test_candidate_review_get_similar.py -xvs`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/candidate_review.py \
        backend/app/schemas/candidate_review.py \
        backend/tests/unit/test_candidate_review_get_similar.py
git commit -m "feat(candidate-review): add get_similar_entries service method (D-037)"
```

---

### Task 9: FastAPI route `GET /coach-brain/candidates/{id}/similar`

**Files:**
- Modify: `backend/app/api/v1/admin.py`
- Modify: `backend/tests/unit/test_admin_candidates_api.py`

- [ ] **Step 1: Write the failing route test**

Append to `backend/tests/unit/test_admin_candidates_api.py`:

```python
@pytest.mark.asyncio
async def test_list_similar_entries_returns_top_2(
    async_client, admin_token, monkeypatch
):
    from app.services.candidate_review import CandidateReviewService
    from app.schemas.candidate_review import SimilarEntry
    import uuid

    e1_id, e2_id = uuid.uuid4(), uuid.uuid4()
    cand_id = uuid.uuid4()

    async def fake_similar(self, *, candidate_id, limit=2):
        assert candidate_id == cand_id
        assert limit == 2
        return [
            SimilarEntry(
                id=e1_id, content="knees out", exercise="squat",
                phase="descent", entry_type="cue", cosine_sim=0.88,
            ),
            SimilarEntry(
                id=e2_id, content="push the floor apart", exercise="squat",
                phase="ascent", entry_type="cue", cosine_sim=0.81,
            ),
        ]

    monkeypatch.setattr(
        CandidateReviewService, "get_similar_entries", fake_similar
    )

    resp = await async_client.get(
        f"/api/v1/admin/coach-brain/candidates/{cand_id}/similar",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["cosine_sim"] == 0.88
    assert body["items"][1]["id"] == str(e2_id)


@pytest.mark.asyncio
async def test_list_similar_entries_404_on_missing_candidate(
    async_client, admin_token, monkeypatch
):
    from app.services.candidate_review import (
        CandidateNotFound, CandidateReviewService,
    )

    async def fake_similar(self, *, candidate_id, limit=2):
        raise CandidateNotFound(str(candidate_id))

    monkeypatch.setattr(
        CandidateReviewService, "get_similar_entries", fake_similar
    )

    import uuid
    resp = await async_client.get(
        f"/api/v1/admin/coach-brain/candidates/{uuid.uuid4()}/similar",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_similar_entries_requires_admin(async_client):
    import uuid
    resp = await async_client.get(
        f"/api/v1/admin/coach-brain/candidates/{uuid.uuid4()}/similar",
    )
    assert resp.status_code in (401, 403)
```

- [ ] **Step 2: Run it — expect fail**

Run: `uv run pytest tests/unit/test_admin_candidates_api.py -k similar -xvs`
Expected: 3 fails, all `404 Not Found` at the route (route doesn't exist yet).

- [ ] **Step 3: Wire the Cohere + Qdrant clients into `_get_review_service`**

Edit `backend/app/api/v1/admin.py:467-498` to pass the two clients into the service constructor:

```python
async def _get_review_service(
    db: AsyncSession = Depends(get_db),
) -> CandidateReviewService:
    cand_repo = CoachBrainCandidateRepository(db)
    entry_repo = CoachBrainRepository(db)
    try:
        cohere = get_cohere_client()
        qdrant = await get_qdrant_client()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "VECTOR_STORE_UNAVAILABLE",
                    "message": "Vector store client unavailable. Retry later.",
                    "detail": None,
                }
            },
        ) from exc
    brain_embedding = BrainEmbeddingService(
        cohere_client=cohere,
        qdrant_client=qdrant,  # type: ignore[arg-type]
    )
    return CandidateReviewService(
        db=db,
        candidate_repo=cand_repo,
        entry_repo=entry_repo,
        brain_embedding=brain_embedding,
        cohere_client=cohere,
        qdrant_client=qdrant,
    )
```

- [ ] **Step 4: Add the route**

Append after the reject route in `backend/app/api/v1/admin.py`:

```python
@router.get(
    "/coach-brain/candidates/{candidate_id}/similar",
    response_model=SimilarEntriesResponse,
)
async def list_similar_entries_for_candidate(
    candidate_id: UUID,
    limit: int = Query(2, ge=1, le=5),
    user: CurrentUser = Depends(get_admin_user),
    service: CandidateReviewService = Depends(_get_review_service),
) -> SimilarEntriesResponse:
    """FR-ADMN-12 (D-037): top N existing approved entries nearest to this
    pending candidate, so the reviewer can spot near-duplicates before promoting.
    """
    try:
        items = await service.get_similar_entries(
            candidate_id=candidate_id, limit=limit
        )
    except CandidateNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Candidate not found.",
                    "detail": None,
                }
            },
        )
    return SimilarEntriesResponse(items=items)
```

And import `SimilarEntriesResponse` at the top:

```python
from app.schemas.candidate_review import (
    ApproveRequest,
    ApproveResponse,
    CandidateListItem,
    PendingQueueStats,
    RejectRequest,
    RejectResponse,
    SimilarEntriesResponse,
)
```

- [ ] **Step 5: Re-run — expect PASS**

Run: `uv run pytest tests/unit/test_admin_candidates_api.py -k similar -xvs`
Expected: 3 passed.

- [ ] **Step 6: Run the full admin test file — no regressions**

Run: `uv run pytest tests/unit/test_admin_candidates_api.py -x`
Expected: full file green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/admin.py \
        backend/tests/unit/test_admin_candidates_api.py
git commit -m "feat(admin): GET /coach-brain/candidates/{id}/similar returns top 2 (D-037)"
```

---

### Task 10: Frontend API client for the new endpoint

**Files:**
- Modify: `frontend/src/api/admin.ts`
- Modify: `frontend/src/api/__tests__/admin-candidates.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/api/__tests__/admin-candidates.test.ts`:

```ts
describe("getCoachBrainCandidateSimilar", () => {
  it("fetches top 2 similar entries", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        items: [
          {
            id: "aaa", content: "knees out", exercise: "squat",
            phase: "descent", entry_type: "cue", cosine_sim: 0.88,
          },
          {
            id: "bbb", content: "push floor apart", exercise: "squat",
            phase: "ascent", entry_type: "cue", cosine_sim: 0.81,
          },
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { getCoachBrainCandidateSimilar } = await import("@/api/admin");
    const resp = await getCoachBrainCandidateSimilar("c1");

    expect(resp.items).toHaveLength(2);
    expect(resp.items[0].cosine_sim).toBe(0.88);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/admin/coach-brain/candidates/c1/similar"),
      expect.any(Object),
    );
  });
});
```

- [ ] **Step 2: Run it — expect fail**

Run: `cd frontend && npx vitest run src/api/__tests__/admin-candidates.test.ts -t "getCoachBrainCandidateSimilar"`
Expected: FAIL with `getCoachBrainCandidateSimilar is not a function`.

- [ ] **Step 3: Add types + fetch helper**

Append to `frontend/src/api/admin.ts`:

```ts
export interface SimilarEntry {
  id: string;
  content: string;
  exercise: "squat" | "bench" | "deadlift";
  phase:
    | "setup"
    | "descent"
    | "bottom"
    | "ascent"
    | "lockout"
    | "general"
    | null;
  entry_type:
    | "cue"
    | "correction"
    | "principle"
    | "drill"
    | "compensation";
  cosine_sim: number;
}

export interface SimilarEntriesResponse {
  items: SimilarEntry[];
}

export async function getCoachBrainCandidateSimilar(
  id: string,
  limit = 2,
): Promise<SimilarEntriesResponse> {
  return adminFetch<SimilarEntriesResponse>(
    `/api/v1/admin/coach-brain/candidates/${id}/similar?limit=${limit}`,
  );
}
```

- [ ] **Step 4: Re-run — expect PASS**

Run: `cd frontend && npx vitest run src/api/__tests__/admin-candidates.test.ts -t "getCoachBrainCandidateSimilar"`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/admin.ts \
        frontend/src/api/__tests__/admin-candidates.test.ts
git commit -m "feat(admin): frontend client for similar-entries endpoint (D-037)"
```

---

### Task 11: `SimilarEntriesList` on review card

**Files:**
- Modify: `frontend/src/pages/AdminCoachBrainCandidatesPage.tsx`
- Modify: `frontend/src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx`

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx`:

```tsx
it("renders top 2 similar entries on the review card", async () => {
  vi.mocked(getCoachBrainCandidateSimilar).mockResolvedValueOnce({
    items: [
      {
        id: "e1", content: "drive knees out at the bottom",
        exercise: "squat", phase: "descent", entry_type: "cue",
        cosine_sim: 0.88,
      },
      {
        id: "e2", content: "push the floor apart", exercise: "squat",
        phase: "ascent", entry_type: "cue", cosine_sim: 0.81,
      },
    ],
  });

  renderWithRouter(<AdminCoachBrainCandidatesPage />);

  await waitFor(() =>
    expect(screen.getByText(/drive knees out at the bottom/i)).toBeTruthy(),
  );
  expect(screen.getByText(/push the floor apart/i)).toBeTruthy();
  // cosine values are rendered to 3 decimals
  expect(screen.getByText(/0\.880/)).toBeTruthy();
  expect(screen.getByText(/0\.810/)).toBeTruthy();
});

it("renders nothing when no similar entries are returned", async () => {
  vi.mocked(getCoachBrainCandidateSimilar).mockResolvedValueOnce({ items: [] });
  renderWithRouter(<AdminCoachBrainCandidatesPage />);
  await waitFor(() => expect(screen.queryByText(/similar entries/i)).toBeNull());
});
```

Add `getCoachBrainCandidateSimilar` to the existing `vi.mock("@/api/admin", ...)` block and set a default resolved value of `{ items: [] }` so the other tests don't break.

- [ ] **Step 2: Run it — expect fail**

Run: `cd frontend && npx vitest run src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx`
Expected: the new tests fail; existing tests should still pass (the default mock returns `{items: []}` and the list renders nothing).

- [ ] **Step 3: Add `SimilarEntriesList` component + wire into CandidateCard**

In `frontend/src/pages/AdminCoachBrainCandidatesPage.tsx`:

Add imports:
```tsx
import {
  getCoachBrainCandidateSimilar,
  type SimilarEntry,
} from "@/api/admin";
```

Replace the `{candidate.nearest_entry_id && (...)}` block at lines 268-278 with a new component invocation:

```tsx
<SimilarEntriesList candidateId={candidate.id} />
```

Add the component at the bottom of the file:

```tsx
function SimilarEntriesList({ candidateId }: { candidateId: string }) {
  const [items, setItems] = useState<SimilarEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getCoachBrainCandidateSimilar(candidateId, 2)
      .then((resp) => {
        if (!cancelled) setItems(resp.items);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  if (loading) {
    return (
      <p className="mb-2 text-xs text-gray-500">Loading similar entries...</p>
    );
  }
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="mb-3">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Similar existing entries
      </p>
      <ul className="space-y-2">
        {items.map((e) => (
          <li
            key={e.id}
            className="rounded-md border border-gray-200 bg-gray-50 p-2 text-xs text-gray-800"
          >
            <p className="mb-1 line-clamp-2">{e.content}</p>
            <p className="font-mono text-[10px] text-gray-500">
              {e.exercise}
              {e.phase ? ` • ${e.phase}` : ""} • {e.entry_type} • cosine{" "}
              {e.cosine_sim.toFixed(3)}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Re-run — expect PASS**

Run: `cd frontend && npx vitest run src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx`
Expected: all tests pass (including the two new ones).

- [ ] **Step 5: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/AdminCoachBrainCandidatesPage.tsx \
        frontend/src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx
git commit -m "feat(admin): render top 2 similar entries on review card (D-037)"
```

---

### Task 12: Backlog close + PR + E2E verify

**Files:**
- Modify: `backlog.md:466`

- [ ] **Step 1: Close D-037**

Edit `backlog.md:466` — flip status from `open` to `done — <sha>` with the commit SHA from Task 11.

- [ ] **Step 2: Final lint + test sweep**

Run:
```bash
cd backend && uv run ruff check . && uv run pyright app/
uv run pytest -x --cov=app
cd ../frontend && npx tsc --noEmit && npx vitest run
```
Expected: ruff clean; pyright 0 errors in `app/`; backend `≥1651 passing`; frontend `≥180 passing`.

- [ ] **Step 3: Commit + push branch**

```bash
git add backlog.md
git commit -m "chore(backlog): close D-037 + D-038 — review card completeness"
git push -u origin feat/d037-d038-review-card-completeness
```

- [ ] **Step 4: Open PR via GitHub MCP**

```text
Title: feat(admin): review-card completeness (D-037 + D-038)

Body:
## Summary
- D-038: add 'compensation' to entry_type CHECK constraint + EntryTypeLiteral +
  distillation extract prompt; drop the forward-compat `as string` cast in the
  review-card banner.
- D-037: new GET /api/v1/admin/coach-brain/candidates/{id}/similar endpoint
  returning top 2 nearest active/seed Coach Brain entries by cosine; frontend
  renders them inline on the review card.

## Test plan
- [x] backend unit tests (new: test_migration_012_compensation.py,
      test_candidate_review_get_similar.py; extended: test_admin_candidates_api.py,
      test_distillation_extract.py, test_schemas_coach_brain.py)
- [x] frontend unit tests (extended: AdminCoachBrainCandidatesPage.test.tsx,
      admin-candidates.test.ts)
- [x] alembic upgrade head local
- [ ] Playwright E2E on prod: navigate /admin/coach-brain/candidates, confirm
      (a) two "Similar existing entries" rows with cosine tags render per card,
      (b) banner fires when a compensation candidate is produced (distillation
      will emit one the next time a video produces a compensation-shaped cue).
```

- [ ] **Step 5: Wait for CI, merge (merge commit, not squash), wait for Deploy to Production**

See root `CLAUDE.md` "Checkpoint Workflow" + "Post-Merge Deployment".

- [ ] **Step 6: Playwright MCP E2E on prod**

Walk the happy path:
1. `browser_navigate` → `https://spelix.app/admin/coach-brain/candidates`
2. `browser_snapshot` — confirm "Similar existing entries" header + up to 2 rows with `cosine 0.xyz` tags
3. `browser_console_messages` level=error — expect none
4. Screenshot to `e2e/screenshots/d037-similar-entries-<sha>.png`
5. For the compensation banner: either (a) approve a test candidate through the distillation flag-on path until one with `entry_type='compensation'` appears, or (b) manually insert a compensation-typed candidate via `mcp__supabase__execute_sql` and refresh the page, screenshot the orange banner.

- [ ] **Step 7: Handoff note**

Write to `.claude/handoff.md` — list D-037 + D-038 completed with PR SHA, E2E screenshots, any follow-ups.

---

## Self-Review Checklist (run after writing, before executing)

- **Spec coverage:** FR-ADMN-12 wording requires "top 2 similar existing approved entries" (covered by Tasks 6–11) and "Compensation entries flagged with `requires_technical_review` and routed to biomechanics-qualified reviewers" (covered by Tasks 1–4; routing is the banner — no separate role exists yet). ✓
- **Placeholder scan:** every step contains actual code or exact commands. No TBDs, no "similar to Task N", no "add appropriate error handling". ✓
- **Type consistency:** `SimilarEntry` used identically in schema (Task 7), service (Task 8), route (Task 9), frontend client (Task 10), UI (Task 11). `getCoachBrainCandidateSimilar` named identically in Task 10 and Task 11. `entry_type="compensation"` added to Literal (Task 2) before the extract prompt references it (Task 3) and before frontend TS union (Task 4). Migration 012 runs before any schema test in Task 1. ✓

---

Plan complete. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
