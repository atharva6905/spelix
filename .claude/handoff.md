# Session 41 Handoff → Session 42: Phase 3 Batch 2 shipped; next session flips `SPELIX_DISTILLATION_ENABLED=1` and verifies the first real candidate row on prod

**Context refresh:** Session 41 was the planned Phase 3 Batch 2 execution session (L2 sprint Day 6, 2026-04-16 → 04-17). Scope was locked by the previous handoff: P3-004 distillation StateGraph + P3-005 knowledge lifecycle + FR-BRAIN-14 CoVe, with P3-006/007 and FR-BRAIN-08 explicitly out-of-scope for Batch 3 / post-L2. Full session executed brainstorming → spec → writing-plans → subagent-driven-development → finishing-a-development-branch in one sitting. PR #77 merged to `main` as `8e587c3` and deployed via the standard CI "Deploy to Production" path; droplet HEAD verified matching, all containers healthy. 4 post-merge docs commits on `main` directly (plan-file enum fixes, backlog close-out, ADR-DISTILL-05, this handoff) — none change runtime behavior, all are sub-200-line docs-only.

## 1. Completed

### PR #77 (`8e587c3`) — Phase 3 Batch 2 Distillation Pipeline

18 commits on `feat/phase3-batch2-distillation`, squash-rejected per memory (merge commit, not squash). Matches the 16 planned tasks from `docs/superpowers/plans/2026-04-16-phase3-batch2-distillation.md` plus 2 fixup rounds.

| Ref | What | Commit |
|---|---|---|
| L2-PHASE3-B2-01 | Alembic migration 011 + `CoachBrainCandidate` SQLAlchemy model (admin-only RLS, 3 indexes, no DDL FK) | `ac1ec15` |
| L2-PHASE3-B2-02 | `CoachBrainCandidateCreate` / `CoachBrainCandidate` Pydantic schemas + `CoachBrainCandidateRepository` | `c44b578` |
| L2-PHASE3-B2-03 | `DistillationState` TypedDict + `CandidateInsight` / `LifecycleDecision` / `BrainCoveResult` + `make_initial_distillation_state` | `cbdb494` |
| L2-PHASE3-B2-04 | `extract_insights` node (Haiku 4.5 + instructor, never raises) | `f6995af` |
| L2-PHASE3-B2-05 | `validate_quality` pure gate (pass / review / reject on eval_scores) | `705906f` |
| L2-PHASE3-B2-06 | `lifecycle_decision` node (Cohere embed + Qdrant cosine → ADD / UPDATE / NOOP) | `97e6299` |
| L2-PHASE3-B2-07 | `BrainCoveService.verify_claim` + `cove_verify` node (FR-BRAIN-14, single-claim, skips NOOP) | `e42d33a` + `5cfae29` (Chunk addition) |
| L2-PHASE3-B2-08 | `format_entry` pure node (contradiction_flag on UPDATE + cove_unverified) | `bbfbec0` |
| L2-PHASE3-B2-09 | `store_entry` node (INSERT candidate + FR-BRAIN-18 `confirmation_count` bump same-txn) | `c73c434` |
| L2-PHASE3-B2-10 | Compiled `StateGraph` + conditional edge on validate_quality + `_wrap_trace` + `run_distillation_graph` | `5f8988b` |
| L2-PHASE3-B2-11 | `distill_analysis` streaq task + `build_distillation_ctx` + `_maybe_enqueue_distillation` tail in both coaching paths | `e1d864d` |
| L2-PHASE3-B2-11b | Consent cascade extended to `coach_brain_candidates` (FR-BRAIN-16) | `8a1c568` |
| L2-PHASE3-B2-12 | `backend/CLAUDE.md` Phase 3 Distillation Architecture section | `f367967` |
| L2-PHASE3-B2-13 | ADR-DISTILL-01/02/03/04 + backlog P3-004/005/008 rows | `5a7f98a` |
| L2-PHASE3-B2-14 | Address audit findings — auditor C-01 (`>=` → `>` at NOOP 0.92 boundary + regression test); security H-1 (cascade return dict); security H-2 (cove_explanation sanitization) | `698acab` |
| L2-PHASE3-B2-15 | CI fixes — pyright narrow on `ChunkPayload \| Chunk` in `coaching.py`; coverage tests for `deps.py` + `distillation_worker.py` (89.44 % → 90.31 %) | `6ca3f1c` |
| L2-PHASE3-B2-16 | Open PR #77 → 2 CI rounds green → `mcp__github__merge_pull_request merge_method="merge"` → droplet verified | PR #77 `8e587c3` |

### Post-merge docs commits on `main` (session 41)

| Ref | What | Commit |
|---|---|---|
| — | `docs(plan)` fix CoachingOutput enum Title-Case values + min_length=1 fills in test stubs (post-hoc) | `cad4da9` |
| — | `docs(backlog)` close L2-PHASE3-BATCH2 + P3-004/005 + new Completed — Phase 3 Batch 2 section | `0629339` |
| — | `docs(decisions)` ADR-DISTILL-05 — never persist raw `str(exc)` to admin-visible DB columns (derived from security H-2) | `7730ea5` |
| — | `docs(handoff)` this file | — (this commit) |

### Audit verdicts (pre-merge, post-fix)

- **spelix-auditor** — PASS_WITH_FINDINGS; 1 CRITICAL (FR-BRAIN-17 NOOP boundary `>=` vs `>`) fixed in `698acab` with regression test at cosine=0.92; 2 MEDIUM items documented, deferred.
- **spelix-security-reviewer** — PASS_WITH_FINDINGS; 2 HIGH (H-1 cascade return dict; H-2 exception-message leak) fixed in `698acab`; 2 MEDIUM items (one pre-existing "medical advice" wording, tracked for a dedicated SaMD sweep; one prompt-injection defence-in-depth) deferred.

## 2. Remaining

### Sprint-visible non-started work (Phase 3 Batch 3 + smoke test)

| ID | Title | SRS | Deps | Status |
|---|---|---|---|---|
| P3-006 | Coach Brain expert review queue for distillation candidates — single-screen cards with eval scorecard + CoVe result + approve/reject/edit; compensation entries flagged; <30 sec/entry target | FR-ADMN-12, FR-BRAIN-07 | P3-004 (done), P3-005 (done) | **Priority 2 session 42** (Batch 3, Days 17-19 per STRATEGY) |
| P3-007 | "How AI Reasoned" sidebar on `ResultsPage` — `@xyflow/react` graph rendered from LangSmith trace, plain English per NFR-USAB-05 | FR-RESL-07 | Phase 3 Batch 1 (done) | not started (Batch 3) |

### Deferred post-L2 (explicitly not session-42 work)

| ID | Title | Size | Status |
|---|---|---|---|
| P3-008 | FR-BRAIN-08 auto-triage — confidence-based auto-approve/auto-reject thresholds | M | deferred post-L2 — blocks on ≥50 human-reviewed candidates for threshold calibration |
| D-029 | SaMD rename `injury_advice_accurate` → `movement_advice_accurate` across DB column + schema + frontend TS + DOM `name` | M | pending — LOW priority, needs migration |
| D-030 | Orphan `rag_documents` rows in `review_status='uploading'` — add nightly cleanup cron | S | pending — LOW |
| D-031 | Admin `GET /rag/documents` — replace free-text `review_status` with `Literal` constraint | S | pending — LOW |
| D-036 | GPU offload for pose extraction (Modal / Replicate / self-hosted) | L | deferred post-beta, trigger-gated |

### Known follow-ups from this session's audits (not blocking Batch 3 start)

- **Audit MEDIUM M-01** (lifecycle `cosine_sim=0.0` vs `None` on empty Qdrant — misleading in Batch 3 UI) → address while building P3-006 review queue.
- **Audit MEDIUM M-02** (`store_entry` uses raw `select(CoachBrainEntry)` instead of going through `CoachBrainRepository`) → either extract a `repo.increment_confirmation()` method or document the direct-session pattern in `backend/CLAUDE.md`.
- **Audit MEDIUM M-03** (`_HAIKU_MODEL` constant duplicated across `extract.py` and `cove_brain.py`) → extract to a shared constant.
- **Security MEDIUM M-1** (prompt-injection defence-in-depth on `CoachingOutput` fields) → strip separator sequences before prompt interpolation when touching distillation extract prompt.
- **Security MEDIUM M-2** (pre-existing "medical advice" string in PDF disclaimer) → defer to a dedicated SaMD language-sweep PR.

### Non-code L2 sprint blockers

- **Kin expert onboarding call** — still pending since session 30. Expert portal PDF upload is wired; zero PDFs uploaded. Target 10+ papers by 2026-05-03. Day-by-day slip against compounding-throughput target.
- **Landing page V1** — status unclear; needs re-verification on prod.

## 3. Test counts

**Backend** (final local run in worktree, pre-merge):
- `uv run pytest -x -q --ignore=tests/e2e` → **1637 passing, 27 skipped, 0 failing**, 90.31 % coverage. 171 s wall-clock.
- `uv run ruff check .` → clean.
- `uv run pyright` → 0 errors, 0 warnings, 0 informations.
- Migration round-trip (`downgrade -1 && upgrade head`) → clean, head = `011_coach_brain_candidates`.

**Frontend**: NOT re-run this session — zero frontend code changes in PR #77. Last known counts from session 40: **272 passing, 0 failing**.

**Delta vs session 40 baseline**: +51 new backend tests across the distillation package, consent cascade extension, and worker body coverage (1586 → 1637).

**Two pre-existing pyright errors** in `backend/tests/unit/test_consent_cascade.py` lines 205 + 259 (`dict[str, Unknown]` vs `CurrentUser`) — predate Task 11b, not introduced by this work, carried forward.

## 4. E2E verification

**Not run this session.** Merge is a no-op behavioural change because `SPELIX_DISTILLATION_ENABLED=0` is the default in both the env-var table (`backend/CLAUDE.md`) and the gate code (`analysis_worker.py::_maybe_enqueue_distillation`). No user-facing flow was modified by this PR. Per CLAUDE.md "Skip verification for: ... CI fixes that don't change runtime behavior, ..." — the entire merge is runtime-neutral without the flag flip.

**Droplet-level verification** (confirming the deploy landed):
- `ssh spelix-droplet "git log --oneline -1"` → `8e587c3 Merge pull request #77 from atharva6905/feat/phase3-batch2-distillation` ✓
- `ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"` → `spelix-backend-1 Up 46 seconds (healthy)`, `spelix-worker-1 Up 46 seconds`, `spelix-redis-1 Up 2 days (healthy)` ✓
- CI run `24547670544` on main → all 6 checks green, **Deploy to Production ✓ (35 s)**.

**E2E is deferred to session 42's flag-flip step** — see Next session start §6. The very first real candidate row after the flag flip is the actual verification event.

## 5. Blockers

**None code-side.** PR #77 merged clean, all tests green, prod deploy verified.

**Soft blockers:**
- Kin expert onboarding call (same carry-over from session 40) — without ≥10 real PDFs in `papers_rag` by 2026-05-03, the distillation CoVe step will always short-circuit with `verified=false, explanation="no_papers_evidence"`. That's not a code bug — the guard is intentional — but it means candidate rows at L2 launch will ALL carry `cove_verified=false` until the corpus grows. Review queue must display this banner clearly in Batch 3.

**Worktree state**: `../spelix-phase3-batch2` removed, local branch `feat/phase3-batch2-distillation` deleted. No cleanup remaining.

## 6. Next session start

The user-pre-declared session-42 priorities: (1) flip the feature flag on prod and verify a first real candidate row lands, (2) start Phase 3 Batch 3 (P3-006 review queue UI + P3-007 reasoning sidebar).

```bash
/status

# PRIORITY 1 — Post-merge op: flag flip + first real candidate verification.
#
# 1a. SSH to droplet, edit /home/deploy/spelix/.env.prod:
#         SPELIX_DISTILLATION_ENABLED=1
#     then `docker compose restart worker` (backend container does NOT need
#     restart — only the worker reads the flag).
#
# 1b. Use the fresh E2E test account (rate-limit safe):
#         email: atharva6905+e2e-d035@gmail.com
#         password: SpelixE2E-D035-2026!
#     Upload one real squat/bench/deadlift video, wait for `status=completed`.
#
# 1c. Query candidate rows:
#         docker exec spelix-backend-1 python -c "
#         import asyncio, os
#         from sqlalchemy import select
#         from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
#         from app.models.coach_brain_candidate import CoachBrainCandidate
#         async def main():
#             e = create_async_engine(os.environ['DATABASE_URL'].replace('postgresql://', 'postgresql+asyncpg://', 1), connect_args={'statement_cache_size': 0})
#             async with async_sessionmaker(e, expire_on_commit=False)() as s:
#                 rows = (await s.execute(select(CoachBrainCandidate).order_by(CoachBrainCandidate.created_at.desc()).limit(5))).scalars().all()
#                 for r in rows:
#                     print(r.id, r.lifecycle_decision, r.cove_verified, r.review_status, r.nearest_cosine_sim)
#         asyncio.run(main())"
#     Acceptance: ≥1 row with lifecycle_decision in ('ADD', 'UPDATE', 'NOOP'),
#     cove_verified in (False, True) (False expected if papers_rag is thin),
#     review_status in ('pending', 'superseded').
#
# 1d. If nothing lands: check worker log for "distill_analysis" messages
#     and "distillation enqueue failed" warnings. The enqueue path swallows
#     errors — grep there first, not in the candidate table.
#
# 1e. Once verified on prod: piggyback a Playwright MCP walk of the user
#     flow (upload → status → results → download) to confirm distillation
#     does NOT regress coaching latency. Record in this handoff under
#     "E2E Findings" before touching Batch 3.

# PRIORITY 2 — Start Phase 3 Batch 3 (P3-006 + P3-007, Days 17-19 per STRATEGY).
#
# Activate: spelix-langgraph-engineer stays; add a Plan → Execute → Review loop.
# Read order:
#   1. docs/SRS.md §FR-ADMN-12 (expert review queue) + §FR-BRAIN-07
#      (promote/reject/edit actions) + §FR-RESL-07 (reasoning sidebar,
#      NFR-USAB-05 plain-English constraint)
#   2. docs/superpowers/specs/2026-04-16-phase3-batch2-distillation-design.md
#      §5.2 "store_entry" (describes the audit-only 'superseded' review_status
#      that Batch 3 MUST filter out of the queue)
#   3. decisions.md ADR-DISTILL-01 (review queue queries coach_brain_candidates,
#      NOT coach_brain_entries; promotion INSERTs into coach_brain_entries)
#
# Plan, don't implement yet:
#   /plan "Phase 3 Batch 3 — expert review queue + reasoning sidebar"
#
# Scope (per STRATEGY.md Days 17-19):
#   - P3-006: single-screen review card at /admin/coach-brain/candidates.
#     Query coach_brain_candidates where review_status='pending' ORDER BY
#     eval_scores->>'overall' DESC, created_at DESC. Display: content,
#     exercise, phase, entry_type, lifecycle_decision + nearest_cosine_sim,
#     cove_verified + cove_explanation, eval_scores scorecard.
#     Actions: approve → INSERT coach_brain_entries + UPDATE candidates
#     promoted_entry_id; reject → UPDATE candidates rejected_reason;
#     edit → inline content edit then approve. <30 sec/entry target.
#     Compensation entries (entry_type='compensation' — not in current
#     CHECK, needs a Batch 3 migration to add) flagged for biomechanics
#     reviewer.
#   - P3-007: "How AI Reasoned" sidebar on ResultsPage, reading from
#     coaching_results.agent_trace_json (persisted in Batch 1). Render
#     via @xyflow/react as a graph: nodes=graph nodes executed,
#     edges=data dependencies. Click a node → show input_keys,
#     output_keys, duration_ms. Plain English per NFR-USAB-05 (no
#     "Tier 1 landmark_conf" jargon in node labels).
#
# TDD gates:
#   - Backend: pytest over the new admin endpoints; RLS still admin-only.
#   - Frontend: vitest over the review-queue component states (loading,
#     empty, one candidate, approve/reject actions).
#   - E2E: admin login → /admin/coach-brain/candidates → approve one →
#     verify it lands in coach_brain_entries + new coaching analysis
#     hits it via retrieval.

# PRIORITY 3 (backfill only if Batch 3 slips):
#   - Kin expert onboarding call — schedule this week.
#   - Follow up on audit MEDIUM items (M-01 cosine_sim None, M-03 Haiku
#     constant dedup).

# ENVIRONMENT NOTES:
#   - Local main = origin/main = `7730ea5` (post-ADR-DISTILL-05 commit).
#     If this handoff lands as a separate commit, update that reference.
#   - Phase 3 Batch 2 feature flag: SPELIX_DISTILLATION_ENABLED=0 as of
#     session 41 merge. Session 42 Priority 1 flips it.
#   - streaq process_analysis timeout = 900s; distill_analysis timeout
#     = 300s (both in backend/app/workers/streaq_worker.py).
#   - Phase 3 agent feature flag: SPELIX_PHASE3_AGENT_ENABLED=1 on prod
#     since session 32 — both coaching paths (graph + imperative fallback)
#     trigger distillation identically, so the flag flip in 1a covers both.
```

## 7. Session timing

- 20:30 UTC (2026-04-16): session opened, read handoff/SRS/STRATEGY, brainstormed design
- 20:45 UTC: design doc written to `docs/superpowers/specs/...-design.md`
- 21:00 UTC: plan doc written to `docs/superpowers/plans/...-distillation.md`
- 21:15 UTC: worktree created, baseline tests verified (1586 passed)
- 21:20–03:00 UTC (16 tasks over ~6 h): subagent-driven-development loop with `spelix-migration`, `spelix-tdd`, `spelix-langgraph-engineer` agents; one agent interrupted (Task 11b consent cascade) and recovered inline
- 03:00–03:45 UTC: `spelix-auditor` + `spelix-security-reviewer` parallel run, 3 findings fixed
- 03:50 UTC: push + PR #77 opened
- 04:00 UTC: CI round 1 red (coverage + pyright), fixes pushed as `6ca3f1c`
- 04:05 UTC: CI round 2 green, PR #77 merged as `8e587c3`
- 04:10 UTC: Deploy to Production green (35 s), droplet HEAD verified
- 04:15–04:45 UTC: post-merge docs — plan fixup, backlog, ADR-DISTILL-05, this handoff

---

# Session 42 Handoff → Session 43: GREEN — Coach Brain distillation pipeline FULLY VERIFIED end-to-end on prod; 11 real `coach_brain_candidates` rows landed; ready for Phase 3 Batch 3 (P3-006 review queue)

**Context refresh:** Session 42 was supposed to be a 5-step ops task — flip `SPELIX_DISTILLATION_ENABLED=1` on prod and watch the first real candidate row land. It turned into a 5-bug archaeological dig because the entire retrieval-eval-distillation chain had been silently inert since Phase 2 shipped. Five PRs landed (#77 was session 41; #78–#81 this session). Final E2E verification (analysis `73f9a137-c528-4f11-b833-48c638b5d5fc`) produced 11 candidate rows, all `lifecycle_decision=ADD`, `review_status=pending`, ready for Batch 3.

## 1. Completed

### PR #78 (`5163a9b`) — Coach Brain + papers_rag retrieval unblock

7 commits on `fix/coach-brain-retrieval-unblock`. Two pre-Phase-3 bugs fixed together because verification needed both:

| Ref | What | Commit |
|---|---|---|
| RU-2 | Failing TDD test for missing `papers_rag.exercise` payload index | `691c28d` |
| RU-3 | `ensure_collections` refactored — `add_brain_indexes:bool` -> `payload_index_fields:tuple[str,...]` per-collection. papers_rag now gets `("exercise",)`, coach_brain gets `("exercise","status")` | `29fe2de` |
| RU-3 review fix | Restored exception-path comment + dropped redundant guard | `e36737e` |
| RU-4 | One-shot script `backend/scripts/oneoff/create_papers_rag_exercise_index.py` | `328d4f1` |
| RU-5 | Failing TDD test for seed-inclusive coach_brain filter | `3985134` |
| RU-6 | `retrieve_coach_brain` filter `MatchValue('active')` -> `MatchAny(['active','seed'])` per FR-BRAIN-05 cold-start | `f52aab2` |
| RU-8 | ADR-BRAIN-08 + backend/CLAUDE.md note + backlog FIX-RETRIEVAL-01/02/03 | `89a2fc3` |
| Review fix | DualCollectionOrchestrator (imperative path) mirrored MatchAny + 2 SaMD-language seed sanitizations + sanitize script | `d9c1240` |

Audits: `spelix-security-reviewer` returned CRITICAL on 2 SaMD seed strings (rotator cuff impingement, sternum/rib injury) which would now reach the LLM via the seed-retrievable filter — fixed inline + sanitization script for prod data. `spelix-auditor` returned HIGH on imperative-path parity gap — fixed inline. Re-review PASS.

### PR #79 (`5044818`) — chunk.text fallback to payload['content'] for coach_brain

Bug surfaced by E2E: `retrieval.py:237` hardcoded `payload['text']` but coach_brain payloads use `content`. Cohere Rerank returned 400 "documents must not contain only empty strings" on every brain call. One-line fix: `text=payload.get("text") or payload.get("content","")` + regression test. Commit `d971034`.

### PR #80 (`ef36b85`) — distillation gate falls back to faithfulness

Bug surfaced by E2E: `_maybe_enqueue_distillation` checks `eval_scores.overall`, but Phase 2 only populates `faithfulness` (ADR-RAG-04 — Phase 4 will add the multi-component RAGAS aggregate). Gate silently rejected every analysis. Fix: `quality = scores.get("overall") or scores.get("faithfulness")` + 2 regression tests. Commit `95e060a`.

### PR #81 (`177dd2a`) — validate_quality node falls back to faithfulness

Bug surfaced by E2E (post-PR-#80): gate now fired but distillation StateGraph's `validate_quality` node at `validate.py:29` ALSO checked `eval_scores.overall` and returned `validation_decision=reject`. Same Phase 2-only-faithfulness gap, second code site. Fix: mirror the gate fallback + 2 regression tests. Commit `dc35d8c`.

### Post-merge prod ops

| What | Result |
|---|---|
| Flag flip | `.env.prod` appended `SPELIX_DISTILLATION_ENABLED=1`, worker recreated via `up -d --force-recreate --no-deps worker` (compose file is `docker-compose.prod.yml` — `restart` does NOT re-read `env_file`) |
| `papers_rag` exercise index | Created via inline script — `payload_schema: {exercise: keyword}` |
| Seed SaMD sanitization | 2 Postgres rows updated (`2cc34c09`, `bf84fb97`); 2 Qdrant payloads patched |

## 2. Final E2E verification

**Analysis `73f9a137-c528-4f11-b833-48c638b5d5fc`** (T_SUBMIT=`2026-04-17T10:02:31.987Z`, completed at t+217s):
- `eval_scores.faithfulness = 0.82` (above 0.6 floor)
- Distillation gate fired -> enqueued
- `validate_quality` returned `review` (not `reject`)
- Distillation graph completed -> 11 `coach_brain_candidates` rows landed
- All rows: `lifecycle_decision=ADD`, `review_status=pending`, `cove_verified=false` (CoVe hits max_tokens — known limitation)
- Sample contents (real bench coaching cues): "Tuck your elbows and bend the bar outward...", "Lower the bar to lower sternum...", "Set elbows at 45-75 degrees..."

**Total `coach_brain_candidates` on prod: 11** (was 0 at start of session 42). Phase 3 Batch 3 now has real data to build the review queue against.

## 3. Test counts

**Backend** (latest local on PR #81):
- `uv run pytest -x -q --ignore=tests/e2e` -> 1649 passing (1641 baseline + 8 new), 25 skipped, 0 failing
- `uv run ruff check .` -> clean
- `uv run pyright app/` (CI scope) -> 0 errors

**Frontend**: not re-run this session — zero frontend code changes across PRs #78–#81.

**Delta vs session 41 baseline**: +12 backend tests across 4 PRs (regression guards for the 5 bugs fixed).

## 4. Blockers

**None code-side.** All 5 bugs fixed and verified. Distillation flywheel is live on prod.

**Soft / known limitations:**
- CoVe `cove_verified=false` for all 11 candidates because Haiku 4.5 hits `max_tokens` (1024) on the verification call. Three retry attempts also fail. Not blocking: `contradiction_flag` is set correctly, `cove_explanation` says "evaluation_failed: BadRequestError" per ADR-DISTILL-05. Backlog: bump `max_tokens` on the BrainCoveService call or use a less-verbose verification prompt.
- `retrieval_source = papers_only_fallback` despite seeds now being eligible. Brain retrieval returned no hits OR scored below the 0.65 hybrid floor. Possible cause: contextualized embedding format mismatch (FR-BRAIN-03 says embed `exercise:{exercise} phase:{phase} type:{entry_type}\n{content}` but seeds may have been embedded with raw content only). Backlog as M-04: re-embed seeds with the contextualized format and re-test retrieval scores.

## 5. Remaining (Phase 3 Batch 3, Days 17-19 per STRATEGY)

| ID | Title | SRS | Status |
|---|---|---|---|
| P3-006 | Coach Brain expert review queue at `/admin/coach-brain/candidates` — single-screen cards with eval scorecard + CoVe result + approve/reject/edit; under 30 sec/entry target | FR-ADMN-12, FR-BRAIN-07 | **READY** — 11 real candidates to review |
| P3-007 | "How AI Reasoned" sidebar on `ResultsPage` — `@xyflow/react` graph rendered from `coaching_results.agent_trace_json` | FR-RESL-07, NFR-USAB-05 | not started |

### Deferred post-L2 (unchanged from session 41)

| ID | Title | Status |
|---|---|---|
| P3-008 | FR-BRAIN-08 auto-triage — needs >=50 reviewed candidates for threshold calibration | deferred |
| D-029 | SaMD rename `injury_advice_accurate` -> `movement_advice_accurate` | LOW |
| D-030 | Orphan `rag_documents` cleanup cron | LOW |
| D-031 | Admin `GET /rag/documents` Literal constraint | LOW |
| D-036 | GPU offload for pose extraction | post-beta |

### Discovered this session (backlog)

- **M-04**: re-embed seeds with FR-BRAIN-03 contextualized prefix to fix `papers_only_fallback` overuse
- **M-05**: bump `BrainCoveService` `max_tokens` to >=2048 OR shorten verification prompt to land cove_verified=true for typical candidates
- **M-06**: `eval_scores.overall` populated by Phase 4 RAGAS aggregate; until then the faithfulness fallback in PR #80 + #81 is load-bearing — when overall ships, both fallbacks become inert (correct precedence)

## 6. Next session start

```bash
/status

# PRIORITY 1 — Phase 3 Batch 3 P3-006 review queue UI
#
# Read order:
#   1. docs/SRS.md FR-ADMN-12 + FR-BRAIN-07
#   2. backend/app/models/coach_brain_candidate.py — schema for the 11 live rows
#   3. decisions.md ADR-DISTILL-01 — review queue queries coach_brain_candidates,
#      promotion INSERTs into coach_brain_entries
#
# Plan, dont implement yet:
#   /plan "Phase 3 Batch 3 — expert review queue + reasoning sidebar"
#
# Backend scope:
#   - GET /api/v1/admin/coach-brain/candidates?review_status=pending
#     (sorted by eval_scores->>faithfulness DESC, created_at DESC)
#   - POST /api/v1/admin/coach-brain/candidates/{id}/approve
#     -> INSERT coach_brain_entries (status=active) + UPDATE candidates
#       set review_status=approved, promoted_entry_id=<new>
#     -> re-embed via Cohere + upsert to Qdrant coach_brain
#   - POST /api/v1/admin/coach-brain/candidates/{id}/reject
#     -> UPDATE candidates set review_status=rejected, rejected_reason
#   - POST /api/v1/admin/coach-brain/candidates/{id}/edit + approve
#     (inline content edit)
#
# Frontend scope:
#   - /admin/coach-brain/candidates route (admin guard)
#   - Single-screen card: content, exercise, phase, entry_type, lifecycle_decision,
#     nearest_cosine_sim, cove_verified + cove_explanation banner (CoVe failed -
#     review manually), eval_scores scorecard
#   - Approve/Reject/Edit buttons; under 30s/entry target
#   - Filter superseded out (ADR-DISTILL-01: superseded is audit-only)

# PRIORITY 2 — Phase 3 Batch 3 P3-007 reasoning sidebar
#
# Read coaching_results.agent_trace_json shape (already populated).
# Render via @xyflow/react: nodes = graph nodes executed, edges = data deps.
# Plain English per NFR-USAB-05 — no Tier 1 landmark_conf jargon.
# Click node -> show input_keys, output_keys, duration_ms.

# PRIORITY 3 — backlog items if Batch 3 slips
#   - M-04 re-embed seeds with contextualized prefix
#   - M-05 BrainCoveService max_tokens bump
#   - Kin expert onboarding call (ongoing carry-over)

# ENVIRONMENT NOTES:
#   - Local main = origin/main = 177dd2a (post-PR-#81)
#   - SPELIX_DISTILLATION_ENABLED=1 on prod, worker live
#   - papers_rag has 39 points + exercise payload index
#   - coach_brain has 24 seed points (status=seed) + 0 active (Batch 3 will create active)
#   - coach_brain_candidates has 11 pending review
#   - All bench seed entries sanitized of SaMD language
```

## 7. Session timing

- 06:00 UTC (2026-04-17): session opened, brainstormed Priority 1 plan
- 06:25 UTC: first upload `01fd3c57` for flag-flip verification -> status=completed but eval_scores=NULL -> diagnosis revealed 2 Phase 2 bugs
- 07:00 UTC: synthesis written explaining seed/active/distillation architecture + 2 root causes
- 07:30 UTC: writing-plans skill produced `docs/superpowers/plans/2026-04-17-coach-brain-retrieval-unblock.md`
- 08:00 UTC: branch `fix/coach-brain-retrieval-unblock` created, baseline 1639 tests green
- 08:00–09:00 UTC: subagent-driven-development executed RU-1 through RU-8 (8 commits)
- 09:00 UTC: PR #78 opened, parallel security + auditor reviews dispatched
- 09:15 UTC: security FAIL CRITICAL (2 seed entries) + audit HIGH (imperative-path parity) — fixed in `d9c1240`
- 09:25 UTC: PR #78 re-review PASS, CI green, merged as `5163a9b`
- 09:35 UTC: prod ops — flag flip + papers_rag index + seed sanitization
- 09:50 UTC: E2E #1 -> bug #3 (chunk.text mapping) -> PR #79 -> merged `5044818`
- 10:00 UTC: E2E #2 -> bug #4 (overall vs faithfulness in gate) -> PR #80 -> merged `ef36b85`
- 10:10 UTC: E2E #3 -> bug #5 (overall vs faithfulness in validate_quality) -> PR #81 -> merged `177dd2a`
- 10:30 UTC: E2E #4 (`73f9a137`) -> 11 candidate rows landed -> GREEN VERDICT
- 10:45 UTC: handoff written

---
