# FR-BRAIN-17 Tombstone Contradicted Entries — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the distillation pipeline UPDATE path encounters a candidate with `contradiction_flag=True`, tombstone the nearest existing `coach_brain_entries` row and skip the `confirmation_count` bump so contradicted Coach Brain entries stop being served at inference time.

**Architecture:** Modify `app/distillation/store.py` only. Reuse the established FR-BRAIN-16 tombstone pattern (`status='deprecated'` + `extra_metadata['rejected_reason']` JSONB merge) — no migration needed. The same `store_entry` function continues to INSERT the candidate row for audit; only the side-effect on the existing entry changes when `contradiction_flag=True`.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, asyncpg, pytest-asyncio. No new dependencies.

---

## Context — why this change exists

**SRS FR-BRAIN-17** (`docs/SRS.md`): "Entries contradicted by new evidence are flagged with `status=rejected`, `rejected_reason='contradicted_by_{new_entry_id}'`."

**Auditor finding H-01 (2026-04-27 spelix-auditor sweep)**: `app/distillation/store.py:65-82` UPDATE path bumps `confirmation_count` on the nearest entry but never tombstones it when `contradiction_flag=True`. Contradicted entries continue serving stale or incorrect cues at inference time.

**Auditor finding M-01 (same sweep)**: When `contradiction_flag=True` on the UPDATE path, the code increments `confirmation_count` BEFORE the contradiction is recorded — adding spurious confirmation evidence to a row that's about to be rejected. M-01 is co-fixed with H-01 in the same function.

**Schema reality (validated 2026-04-27)**: `coach_brain_entries.status` CHECK constraint allows only `('seed','active','deprecated')` — NOT `'rejected'`. There is no `rejected_reason` column on `coach_brain_entries`. The Phase 2 `FR-BRAIN-16` shipped with a documented workaround in `app/repositories/coach_brain.py:94-117`:

```python
async def soft_delete_empty_unconfirmed(self) -> int:
    """...
    FR-BRAIN-16: SRS specifies status='rejected' but the CHECK constraint
    only allows seed/active/deprecated. Using 'deprecated' with metadata
    to capture the reason.
    """
    result = await self._db.execute(
        update(CoachBrainEntry)
        .where(...)
        .values(
            status="deprecated",
            extra_metadata=text(
                "metadata || '{\"rejected_reason\": \"source_consent_withdrawn\"}'::jsonb"
            ),
        )
    )
```

This plan applies the **identical pattern** for FR-BRAIN-17. No migration, no model change, no SRS amendment.

---

## File Structure

| File | Responsibility | Touch |
|------|----------------|-------|
| `backend/app/distillation/store.py` | UPDATE-path tombstone + skip-bump | Modify lines 65-82 |
| `backend/tests/unit/test_distillation_store.py` | Two new pytest-asyncio test cases proving the behavior | Append after line 178 |

No model file changes. No migration. No schema changes. No frontend changes.

---

## Task 1: Tombstone-with-skip-bump

**Files:**
- Modify: `backend/app/distillation/store.py:65-82`
- Test: `backend/tests/unit/test_distillation_store.py` (append two tests)

### Step 1.1 — Write the failing test for the tombstone behavior

- [ ] **Step:** Append to `backend/tests/unit/test_distillation_store.py` after line 178:

```python
@pytest.mark.asyncio
async def test_store_entry_update_with_contradiction_tombstones_existing(
    db_session: AsyncSession,
) -> None:
    """FR-BRAIN-17: UPDATE-path candidate with contradiction_flag=True must
    tombstone the nearest existing coach_brain_entries row.

    The existing row must transition to status='deprecated' and gain
    extra_metadata.rejected_reason='contradicted_by_<candidate_id>'. This
    matches the FR-BRAIN-16 tombstone pattern in
    app/repositories/coach_brain.py:soft_delete_empty_unconfirmed (status
    CHECK constraint allows seed/active/deprecated only).
    """
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
        contradiction_flag=True,
        review_status="superseded",
    )
    state = _state_with_formatted([row])
    update = await store_entry(state, db_session=db_session)

    # Candidate row inserted (audit trail)
    assert len(update["stored_ids"]) == 1
    candidate_id = update["stored_ids"][0]

    # Nearest entry tombstoned via the FR-BRAIN-16 pattern
    await db_session.refresh(seed)
    assert seed.status == "deprecated"
    assert seed.extra_metadata.get("rejected_reason") == f"contradicted_by_{candidate_id}"

    # M-01: contradiction_flag must NOT bump confirmation_count
    assert seed.confirmation_count == 2
    # M-01: contradicted entries also do NOT receive new source_analysis_ids
    assert source_analysis not in seed.source_analysis_ids


@pytest.mark.asyncio
async def test_store_entry_update_without_contradiction_does_not_tombstone(
    db_session: AsyncSession,
) -> None:
    """Regression guard: the existing UPDATE-path (contradiction_flag=False)
    must continue to bump confirmation_count and append source_analysis_ids
    without changing status or metadata.
    """
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
        contradiction_flag=False,
        review_status="superseded",
    )
    state = _state_with_formatted([row])
    await store_entry(state, db_session=db_session)

    await db_session.refresh(seed)
    assert seed.status == "active"
    assert seed.extra_metadata == {} or "rejected_reason" not in seed.extra_metadata
    assert seed.confirmation_count == 3
    assert source_analysis in seed.source_analysis_ids
```

### Step 1.2 — Run the new tests; confirm the contradiction test fails and the regression test passes

- [ ] **Run:**

```bash
cd backend && uv run pytest tests/unit/test_distillation_store.py::test_store_entry_update_with_contradiction_tombstones_existing tests/unit/test_distillation_store.py::test_store_entry_update_without_contradiction_does_not_tombstone -v
```

**Expected:**
- `test_store_entry_update_with_contradiction_tombstones_existing` → **FAIL** (3 assertion failures: `seed.status == "deprecated"` is `"active"`; `seed.extra_metadata.get("rejected_reason")` is `None`; `seed.confirmation_count == 2` is `3`)
- `test_store_entry_update_without_contradiction_does_not_tombstone` → **PASS** (existing behavior covered)

### Step 1.3 — Apply the fix in `store.py`

- [ ] **Modify** `backend/app/distillation/store.py` lines 65-82. Replace the existing UPDATE block:

```python
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
```

with:

```python
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
            if row.contradiction_flag:
                # FR-BRAIN-17: contradicted entries must not accumulate
                # confirmation evidence. Tombstone via the FR-BRAIN-16
                # established pattern — status CHECK allows only
                # seed/active/deprecated, so the contradiction reason
                # lives in extra_metadata as a JSONB merge.
                existing.status = "deprecated"
                merged_metadata = dict(existing.extra_metadata or {})
                merged_metadata["rejected_reason"] = f"contradicted_by_{candidate_row.id}"
                existing.extra_metadata = merged_metadata
            else:
                existing.confirmation_count = (existing.confirmation_count or 0) + 1
                # array_append via list assignment — SQLAlchemy serialises as ARRAY literal.
                existing.source_analysis_ids = list(existing.source_analysis_ids or []) + list(
                    row.source_analysis_ids
                )
            await db_session.flush()
```

### Step 1.4 — Re-run the two new tests; both must pass

- [ ] **Run:**

```bash
cd backend && uv run pytest tests/unit/test_distillation_store.py::test_store_entry_update_with_contradiction_tombstones_existing tests/unit/test_distillation_store.py::test_store_entry_update_without_contradiction_does_not_tombstone -v
```

**Expected:** Both **PASS**.

### Step 1.5 — Run the full distillation_store test file; ensure no regressions

- [ ] **Run:**

```bash
cd backend && uv run pytest tests/unit/test_distillation_store.py -v
```

**Expected:** All 6 tests PASS (4 existing + 2 new).

### Step 1.6 — Run the wider distillation/coach_brain test surface to catch any indirect regressions

- [ ] **Run:**

```bash
cd backend && uv run pytest tests/unit/test_distillation_lifecycle.py tests/unit/test_distillation_store.py tests/unit/test_coach_brain_repository.py tests/unit/test_coach_brain_schema.py tests/unit/test_admin_candidates_api.py tests/unit/test_candidate_review_service.py -v
```

**Expected:** All tests PASS. If any new failure appears, treat it as a real regression — do not silence it; investigate the diff.

### Step 1.7 — Lint + typecheck

- [ ] **Run:**

```bash
cd backend && uv run ruff check app/distillation/store.py tests/unit/test_distillation_store.py
cd backend && uv run pyright app/distillation/store.py
```

**Expected:** Both clean (no errors, no warnings).

### Step 1.8 — Commit

- [ ] **Run:**

```bash
git add backend/app/distillation/store.py backend/tests/unit/test_distillation_store.py
git commit -m "$(cat <<'EOF'
fix(coaching): tombstone contradicted Coach Brain entries on UPDATE path

FR-BRAIN-17 H-01 + M-01: when the distillation pipeline finds a near-duplicate
existing coach_brain_entries row but CoVe verification flags the candidate as
contradicting it, set the existing row's status='deprecated' and record
extra_metadata.rejected_reason='contradicted_by_<candidate_id>' so it stops
being served at inference. Skip confirmation_count bump and source_analysis_ids
append on the contradiction path so spurious confirmation evidence isn't added.

Reuses the FR-BRAIN-16 established workaround from
app/repositories/coach_brain.py:soft_delete_empty_unconfirmed — the
coach_brain_entries.status CHECK constraint allows only seed/active/deprecated,
so the contradiction reason lives in extra_metadata JSONB.
EOF
)"
```

---

## Self-Review

**1. Spec coverage:**
- FR-BRAIN-17 contradiction sentence — Task 1 implements the tombstone (Steps 1.3-1.4)
- M-01 (skip confirmation bump on contradiction) — Task 1 implements the skip via `if/else` branch (Step 1.3)
- Existing FR-BRAIN-17 ADD/UPDATE/NOOP routing in `lifecycle.py` — untouched (validated read-only at `app/distillation/lifecycle.py:96-167`)
- Existing FR-BRAIN-18 confirmation_count semantics — preserved on the non-contradiction UPDATE path (Step 1.3 `else` branch is byte-identical to the prior code)

**2. Placeholder scan:**
- All steps include exact code blocks
- All steps include exact bash commands
- No "TBD", "TODO", or "implement later"

**3. Type consistency:**
- `row.contradiction_flag: bool` — confirmed in `app/models/coach_brain_candidate.py:76` (`Boolean, server_default="false"`)
- `existing.extra_metadata: dict[str, Any]` — confirmed in `app/models/coach_brain_entry.py:57` (`JSONB, server_default="{}"`)
- `existing.status: str` (CHECK seed/active/deprecated) — confirmed in `app/models/coach_brain_entry.py:34, 52`
- `candidate_row.id: uuid.UUID` — confirmed in `app/models/coach_brain_candidate.py:59`
- F-string `f"contradicted_by_{candidate_row.id}"` produces a UUID-stringified suffix — matches the FR-BRAIN-17 literal `'contradicted_by_{new_entry_id}'`

**4. CLAUDE.md compliance:**
- "Apply migrations immediately" — N/A, no migration
- "All JSONB (not JSON) for schema columns" — preserved (`extra_metadata` is already JSONB)
- "Never use 'injury risk' or 'injury prevention'" — N/A, no user-facing strings
- Conventional commit format `fix(coaching): ...` — matches the established scope

---

## Plan complete

Saved to `docs/superpowers/plans/2026-04-27-fr-brain-17-tombstone-contradicted.md`.

Execution: dispatch to `spelix-tdd` subagent (per main agent's plan). The agent reads this file, executes Task 1 step-by-step, then reports back. Main agent reviews diff, runs `/check` + `/test`, and merges via PR.
