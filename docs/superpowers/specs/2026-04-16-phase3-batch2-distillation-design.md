# Phase 3 Batch 2 — Distillation Pipeline Design

**Status:** approved 2026-04-16, handed off to writing-plans
**Owners:** main agent + `spelix-langgraph-engineer` (execution)
**SRS:** FR-BRAIN-06 (Must), FR-BRAIN-14 (Should), FR-BRAIN-17 (Must)
**Backlog:** P3-004, P3-005
**Deferred from batch:** FR-BRAIN-08 (auto-triage — post-L2, blocks on 50+ human-reviewed candidates in prod)
**Out of scope (Batch 3):** P3-006 review queue UI, P3-007 reasoning sidebar
**Sprint window:** L2 Days 13-16 per `STRATEGY.md`, ~4 days
**Branch:** `feat/phase3-batch2-distillation`

---

## 1. Goal

Turn completed, high-quality coaching analyses into reviewable candidate
`CoachBrainEntry` records via an async LangGraph `StateGraph` that never
blocks the user-facing coaching SSE. Ship CoVe verification against
`papers_rag` and the ADD/UPDATE/NOOP cosine lifecycle against existing
approved entries. Feature-flag gated. The review-queue UI that promotes
candidates to `coach_brain_entries.status='active'` ships in Batch 3.

## 2. Non-goals

- Expert review queue UI (Batch 3, P3-006).
- Reasoning sidebar on `ResultsPage` (Batch 3, P3-007).
- FR-BRAIN-08 auto-triage (deferred — open `P3-008` post-L2; blocks on
  ≥ 50 human-reviewed candidates for threshold calibration per SRS
  "start conservative" guidance).
- Changes to the Phase 3 coaching agent graph (`app/agents/`) — distillation
  is a separate compiled graph with a different lifecycle per ADR-BRAIN-07.
- Any change to `coach_brain_entries` retrieval filters (`status='active'`
  stays the retrieval predicate).
- Frontend work.

## 3. Design decisions (confirmed with user 2026-04-16)

### 3.1 Candidate storage: new `coach_brain_candidates` table (NOT extend existing)

**Decision:** ship a new Postgres table `coach_brain_candidates` rather than
adding a `candidate` status value to `coach_brain_entries`.

**Why:**
- `coach_brain_entries.status` CHECK is currently `IN ('seed','active','deprecated')`.
  The retrieval path (`DualCollectionOrchestrator._retrieve`) filters on
  `status='active'`. Adding `'candidate'` risks accidental leakage if any
  future filter change drops the status predicate.
- Matches the session-40 handoff directive ("NOT `coach_brain` — expert
  approval promotes in Batch 3").
- Batch 3 promotion becomes a simple INSERT into `coach_brain_entries`
  (with `status='active'`) + UPDATE on the candidate row
  (`review_status='approved'`, `promoted_entry_id` pointer).
- Easier RLS: candidates are admin-only; active entries are service-role
  readable for retrieval.

### 3.2 Invocation: new streaq task, NOT `asyncio.create_task`

**Decision:** add `distill_analysis(analysis_id)` as a streaq task in
`backend/app/workers/distillation_worker.py`, enqueued from the end of
`process_analysis` after coaching + eval persist. Timeout 300 s.

**Why:** retries + isolation + heartbeat visibility. `asyncio.create_task`
inside `process_analysis` loses all three and hides distillation errors
behind the concurrency=1 MediaPipe worker lifecycle. streaq already runs
with a single worker, so distillation queues up behind subsequent analyses
rather than racing them — acceptable for L2 beta volume.

### 3.3 Feature-flag rollout

`SPELIX_DISTILLATION_ENABLED=0` default at merge. Same pattern as Batch 1's
`SPELIX_PHASE3_AGENT_ENABLED`. Post-merge op: flip on for one analysis,
inspect `coach_brain_candidates` row, flip globally. Rollback is `=0`.

### 3.4 CoVe reuse strategy

**Decision:** add a slim `BrainCoveService` (or `cove_brain.py`) that reuses
3 of 4 prompt builders from `app/services/cove.py` but accepts a single
coaching *claim string* (the candidate's `content`) instead of a full
`CoachingOutput`. Do NOT refactor `CoveVerificationService` — keep the
coaching-path service untouched for Phase 2 stability.

**Why:** the existing service's claim-extraction step expects summary +
issues + correction_plan; distillation candidates are already atomic
cues. Running the full 4-step loop against a 12-word cue is overkill and
would often extract zero claims. A single-claim verifier matches
FR-BRAIN-14's "cross-checking coaching claims against papers_rag content
before promotion."

### 3.5 Contradiction handling (FR-BRAIN-17 edge case)

**Decision:** a candidate CAN deprecate an existing `coach_brain_entries`
row only when ALL of:
- `cosine_sim` falls in UPDATE band (0.75–0.92),
- CoVe verification fails for the new candidate (`cove_verified=false`),
- the existing entry's `confirmation_count < 3`,
- a new `deprecation_is_proposal` flag is set (admin confirms in Batch 3).

In Batch 2, contradiction detection writes `contradiction_flag=true` on
the candidate and records the target `updated_entry_id` but does **NOT**
auto-deprecate the existing entry. Expert review makes that call.

**Why:** auto-deprecating active coaching entries on the basis of a single
unverified candidate is a footgun (the SRS even warns "sycophancy"
failure mode in Section 3.3). Gate behind review until Batch 3 ships the
UI to approve or reject deprecations.

## 4. Schema (Alembic migration 011)

### 4.1 New table `coach_brain_candidates`

```sql
CREATE TABLE coach_brain_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exercise VARCHAR(30) NOT NULL
        CHECK (exercise IN ('squat','bench','deadlift')),
    phase VARCHAR(30)
        CHECK (phase IN ('setup','descent','bottom','ascent','lockout','general')),
    entry_type VARCHAR(30) NOT NULL
        CHECK (entry_type IN ('cue','correction','principle','drill')),
    content TEXT NOT NULL,
    trigger_tags TEXT[] NOT NULL DEFAULT '{}',
    source_analysis_ids UUID[] NOT NULL,            -- length 1 on insert
    confidence_score NUMERIC(4,3),
    eval_scores JSONB NOT NULL DEFAULT '{}',        -- copy from analysis.eval_scores
    cove_verified BOOLEAN,                          -- null until cove_verify node runs
    cove_explanation TEXT,
    cove_trace JSONB,
    lifecycle_decision VARCHAR(10) NOT NULL
        CHECK (lifecycle_decision IN ('ADD','UPDATE','NOOP')),
    nearest_entry_id UUID,                          -- cosine-nearest for UPDATE/NOOP audit
    nearest_cosine_sim NUMERIC(5,4),                -- the actual similarity value
    contradiction_flag BOOLEAN NOT NULL DEFAULT false,
    review_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending','approved','rejected','superseded')),
    rejected_reason TEXT,
    promoted_entry_id UUID,                         -- set by Batch 3 on approve
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_cbc_review_status_created ON coach_brain_candidates(review_status, created_at DESC);
CREATE INDEX ix_cbc_source_analysis_ids ON coach_brain_candidates USING GIN (source_analysis_ids);
CREATE INDEX ix_cbc_nearest_entry_id ON coach_brain_candidates(nearest_entry_id) WHERE nearest_entry_id IS NOT NULL;
```

**RLS:** admin-role only (deny by default). Users MUST NOT see raw candidates.

### 4.2 No change to `coach_brain_entries` in this migration

Contradiction flagging writes metadata on the candidate row. The deprecate
action lives in Batch 3.

### 4.3 Down migration

Drops table + indexes cleanly — no data migration needed because no rows
exist pre-merge.

## 5. Graph structure

Package path: `backend/app/distillation/` (new, sibling of `app/agents/`).

```
START
  │
  ▼
extract_insights       # Haiku: CoachingOutput → list[CandidateInsight]
  │
  ▼
validate_quality       # pure: inspect analysis.eval_scores
  │
  ├─────────────► END (reject) when overall < 0.6
  │
  ▼
lifecycle_decision     # per candidate: embed + Qdrant cosine; ADD/UPDATE/NOOP
  │
  ├─────────────► END when every candidate is NOOP
  │
  ▼
cove_verify            # per non-NOOP candidate: BrainCoveService
  │
  ▼
format_entry           # pure: build CoachBrainCandidateCreate models
  │
  ▼
store_entry            # Postgres INSERTs + UPDATE confirmation_count on source entries
  │
  ▼
END
```

Every node is wrapped by `_wrap_trace` (copy from `app/agents/graph.py`)
so each emits a `NodeEvent` into `state['distillation_trace']`. The final
trace JSONB is persisted on each candidate row (truncated to 8 KB, same
pattern as Batch 1) for admin debugging in Batch 3.

### 5.1 State (`DistillationState` TypedDict)

```python
class DistillationState(TypedDict):
    # inputs
    analysis_id: uuid.UUID
    exercise_type: str
    coaching_output: CoachingOutput
    retrieved_papers_contexts: list[RetrievedContext]    # reuse from agent_trace
    eval_scores: dict[str, Any]

    # working
    candidates: list[CandidateInsight]
    validation_decision: Literal["pass", "review", "reject"]
    decisions: list[LifecycleDecision]                   # per-candidate
    cove_results: list[BrainCoveResult]                  # aligned with decisions
    formatted: list[CoachBrainCandidateCreate]

    # output
    stored_ids: list[uuid.UUID]
    trace: list[dict[str, Any]]
```

### 5.2 Node-by-node behavior

**`extract_insights`** — Claude Haiku 4.5 + instructor, response model
`ExtractedInsights(candidates: list[CandidateInsight])`. Input: the full
`CoachingOutput` summary + issues + correction_plan + recommended_cues.
Returns empty list if nothing extractable — downstream short-circuits.

**`validate_quality`** — no LLM. Pure decision:
- `overall ≥ 0.85 AND correctness ≥ 0.8` → `"pass"` (candidates flow to
  lifecycle; post-CoVe they reach the queue with `review_status='pending'`).
- `0.6 ≤ overall < 0.85` → `"review"` (same flow but we mark
  `eval_tier='low'` in metadata to raise display priority in Batch 3).
- `overall < 0.6` → `"reject"` (END; no candidates written).

**`lifecycle_decision`** — for each candidate:
1. `BrainEmbeddingService.build_contextual_text` → Cohere embed-v4
   `SEARCH_DOCUMENT` → 1024-d vector.
2. Qdrant `coach_brain` search: top-1 with `exercise` + `status='active'`
   filters, return `(nearest_id, cosine_sim)`. Empty result
   → `cosine_sim=0.0` forces ADD.
3. Apply FR-BRAIN-17 thresholds: `>0.92 NOOP`, `0.75–0.92 UPDATE`,
   `<0.75 ADD`.

**`cove_verify`** — for each `decision != NOOP` candidate:
1. Reuse `retrieved_papers_contexts` if the state carries them from the
   triggering analysis (they already exist in `coaching_results.retrieved_sources_json`).
   Else, run a fresh `retrieval_svc.hybrid_search(candidate.content,
   collection="papers_rag", top_k=5, rerank=True)`.
2. Call `BrainCoveService.verify_claim(claim=candidate.content,
   contexts=papers_contexts)`. The slim service:
   - Skips claim-extraction (the candidate IS the claim).
   - Generates exactly one verification question via Haiku.
   - Verifies against papers via Haiku using the existing verification
     prompt builder.
   - Returns `BrainCoveResult(verified: bool, explanation: str,
     trace: list[dict])`.
3. CoVe failure never blocks storage — it only flips `cove_verified=false`
   on the candidate. Review queue in Batch 3 surfaces this prominently.

**`format_entry`** — pure function: pack `CandidateInsight` +
`LifecycleDecision` + `BrainCoveResult` + `eval_scores` +
`contradiction_flag` into a `CoachBrainCandidateCreate` Pydantic model
ready for DB insert.

**`store_entry`** — single transaction per candidate:
1. If `lifecycle_decision='NOOP'`: write zero rows; emit a structured
   log line with `{analysis_id, nearest_entry_id, cosine_sim}` for
   eventual telemetry.
2. If `lifecycle_decision='ADD'`: `INSERT INTO coach_brain_candidates`
   with `review_status='pending'` so it appears in Batch 3's review queue.
3. If `lifecycle_decision='UPDATE'`: same transaction does BOTH —
   (a) `INSERT INTO coach_brain_candidates` with
   `review_status='superseded'` (audit-only, never shown in review queue
   whose filter is `review_status='pending'`), AND (b) `UPDATE
   coach_brain_entries SET confirmation_count = confirmation_count + 1,
   source_analysis_ids = array_append(source_analysis_ids,
   :analysis_id), updated_at = now() WHERE id = :nearest_entry_id`.
   FR-BRAIN-18 satisfied. Transaction rollback on either statement
   leaves both sides untouched.

**Note on `BrainEmbeddingService` reuse:** `build_contextual_text`
currently accepts only `CoachBrainEntry | CoachBrainEntryCreate`. The
`lifecycle_decision` node constructs a throwaway `CoachBrainEntryCreate`
from the `CandidateInsight` fields (content, exercise, phase,
entry_type) purely for the contextual-text step — no DB write. This is
cheap and keeps `BrainEmbeddingService` untouched.

## 6. Packages and files

### 6.1 Created

- `backend/alembic/versions/011_coach_brain_candidates.py` — migration.
- `backend/app/models/coach_brain_candidate.py` — SQLAlchemy model.
- `backend/app/schemas/coach_brain_candidate.py` — Pydantic v2 schemas:
  `CoachBrainCandidateCreate`, `CoachBrainCandidate`,
  `CoachBrainCandidateReview` (latter placeholder for Batch 3).
- `backend/app/repositories/coach_brain_candidate.py` — repo with `create`,
  `list_pending`, `get_by_id`.
- `backend/app/distillation/__init__.py`
- `backend/app/distillation/state.py` — `DistillationState`,
  `CandidateInsight`, `LifecycleDecision`, `BrainCoveResult`.
- `backend/app/distillation/nodes.py` — five node functions + `_wrap_trace`.
- `backend/app/distillation/graph.py` — `build_distillation_graph()`,
  `run_distillation_graph()` entry point.
- `backend/app/distillation/cove_brain.py` — `BrainCoveService` (single-claim).
- `backend/app/workers/distillation_worker.py` — `distill_analysis` body
  (pulls deps from deps-builder helpers already in `analysis_worker.py`).
- Unit + integration tests listed in §8.

### 6.2 Modified

- `backend/app/workers/streaq_worker.py` — new `@worker.task(timeout=300)`
  wrapper `distill_analysis`.
- `backend/app/workers/analysis_worker.py` — tail of `_run_pipeline`:
  when `SPELIX_DISTILLATION_ENABLED=1` AND coaching + eval succeeded AND
  `analysis.eval_scores.get("overall", 0) >= 0.6`, enqueue
  `distill_analysis`. Swallow enqueue errors as warnings (distillation
  failure must NEVER fail the user-facing analysis).
- `backend/app/models/__init__.py` — export new model.
- `backend/app/schemas/__init__.py` — export new schemas.
- `backend/CLAUDE.md` — new "Phase 3 Distillation Architecture" section
  + env-var row for `SPELIX_DISTILLATION_ENABLED` + gotcha entries.
- `decisions.md` — three new ADRs (see §10).
- `backlog.md` — mark P3-004 and P3-005 done on merge; add P3-008 row
  (FR-BRAIN-08 auto-triage, deferred post-L2).

## 7. Feature-flag rollout

1. Merge with `SPELIX_DISTILLATION_ENABLED=0` (no behavioural change).
2. Deploy via the standard CI "Deploy to Production" step.
3. Op step: set `SPELIX_DISTILLATION_ENABLED=1` on the droplet's
   `.env.prod`, restart `spelix-worker-1`.
4. Trigger one test-account analysis, wait for `status=completed`,
   verify a row appears in `coach_brain_candidates` within 30 s of
   coaching completion. Inspect `lifecycle_decision`, `cove_verified`,
   `cove_explanation`.
5. If the candidate looks sane, leave flag on. If not, flag off,
   inspect worker logs, fix, repeat.

Rollback is `SPELIX_DISTILLATION_ENABLED=0` + worker restart. No data
migration needed — existing candidates remain but no new ones appear.

## 8. Tests (TDD-first, spelix-tdd agent)

### Unit

- `test_distillation_state.py` — `DistillationState` TypedDict construction,
  `make_initial_state` safe defaults.
- `test_distillation_extract_insights.py` — synthetic `CoachingOutput`
  → N candidates with correct fields; empty output → empty list; LLM
  error → safe default (empty list, logged).
- `test_distillation_validate_quality.py` — gate matrix: `overall=0.9,
  correctness=0.85` → pass; `overall=0.7` → review; `overall=0.5` →
  reject.
- `test_distillation_lifecycle.py` — mock Qdrant to return fixed cosine;
  0.95 → NOOP, 0.80 → UPDATE, 0.60 → ADD, empty → ADD. Contradiction
  flag path.
- `test_distillation_cove_brain.py` — `BrainCoveService.verify_claim` happy
  path (Yes answer → verified=true), No answer → verified=false,
  empty contexts → verified=false+explanation="no_papers_evidence",
  LLM error → safe default.
- `test_distillation_format_entry.py` — pure function, aligned-list
  zipping, contradiction propagation, eval_scores copy.
- `test_distillation_store_entry.py` — INSERT happens; UPDATE path
  writes confirmation bump; NOOP path writes zero rows; transaction
  rollback on INSERT failure leaves source entry untouched.

### Integration

- `test_distillation_graph_e2e.py` — real `DistillationState` + real
  Postgres + mocked Cohere/Qdrant/Anthropic; asserts (a) candidates
  land in `coach_brain_candidates` NEVER in `coach_brain_entries`;
  (b) UPDATE path writes confirmation_count bump in same transaction;
  (c) `distillation_trace` is truncated to ≤ 8 KB.

### E2E

- `test_distillation_worker_e2e.py` — streaq test harness enqueues
  `distill_analysis` with a completed-analysis fixture; asserts DB
  state after `await`.

### Regression

- `test_analysis_worker.py` — new case: when `SPELIX_DISTILLATION_ENABLED=0`,
  `distill_analysis.enqueue` is NEVER called. When `=1` and `eval_scores`
  prefilter fails, still not called. When `=1` and enqueue raises, the
  user-facing analysis still transitions to `completed`.

Coverage target: ≥ 90 % on new code (repo-wide is 90 % already).

## 9. Risks + mitigations

| Risk | Mitigation |
|---|---|
| LLM-driven extraction hallucinates coaching cues that never appeared in the output | Extract step's prompt requires verbatim or near-verbatim quote from `CoachingOutput`; validate each candidate's content appears (via fuzzy match ≥ 0.7) in the source. |
| Qdrant `coach_brain` is empty at L2 launch → every candidate ADDs | Expected behaviour; cosine-sim fallback returns 0.0 → ADD. Seed corpus from Phase 2 (24 entries) partially mitigates this. |
| CoVe flags every candidate as unverified because papers_rag is thin (~30 papers target for L2) | Empty-contexts guard returns `verified=false` with explanation `no_papers_evidence`. Review queue displays this clearly in Batch 3. |
| Distillation task clogs streaq queue and delays user analyses | Enqueue only runs AFTER the parent analysis reaches `completed` and user has already received the coaching output. streaq `concurrency=1` means distillation runs when the next analysis is also queued — acceptable at L2 volume (<10 analyses/day). If this starts hurting p95 we split to a distillation-specific queue later. |
| Distillation error path fails the parent analysis | `analysis_worker.py` enqueue wrapped in try/except; enqueue failures logged as WARNING, never raised. |
| Migration 011 runs but feature flag flipped off — orphan empty table | Zero rows, zero cost. Fine. |
| CoVe reuse against a thin papers_rag corpus flags too many false negatives | Metrics dashboard (Batch 3 admin) shows CoVe pass rate; if < 30 % after 2 weeks, tune thresholds or fall back to "CoVe optional" for candidates under `lifecycle_decision='ADD'`. |

## 10. ADRs to write inline with the PR

- **ADR-DISTILL-01** — Candidate storage: new `coach_brain_candidates`
  table, not status extension of `coach_brain_entries`. Cites §3.1.
- **ADR-DISTILL-02** — Invocation: streaq task, not `asyncio.create_task`.
  Cites §3.2.
- **ADR-DISTILL-03** — CoVe slim `BrainCoveService` for single-claim
  verification; existing `CoveVerificationService` unchanged. Cites §3.4.

## 11. Exit criteria (PR merge)

- Backend test suite green (target: 1580+ passing, 0 failing, ≥ 90 %
  coverage).
- `alembic upgrade head` applied in the same session as the migration file.
- `ruff check` + `pyright` clean.
- `spelix-auditor` run returns 0 CRITICAL findings for the batch.
- `spelix-security-reviewer` run confirms RLS admin-only on the new
  table and no PII-like columns added.
- PR opened against `main`, CI green, merge via
  `mcp__github__merge_pull_request` with `merge_method="merge"` (never
  squash).
- Post-merge: "Deploy to Production" green; feature flag left at `0`.
- Op step deferred to next session: flip flag on one test analysis,
  verify candidate row.

## 12. Next step

Invoke `superpowers:writing-plans` against this spec to produce the
task-by-task implementation plan at
`docs/superpowers/plans/2026-04-16-phase3-batch2-distillation.md`.
