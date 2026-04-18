# Session 47 Handoff → Session 48: D-045 Coach Brain query enrichment shipped to prod (PR #87)

**Context refresh:** Session 47 (2026-04-18, L2 Sprint Day 10, same calendar day as session 46) closed session 46's Priority 2 D-045. Investigation falsified all four backlog hypotheses, isolated the actual root cause (bench-specific query/seed-corpus vocabulary mismatch), shipped a 30-LOC fix, verified end-to-end on prod via fresh Playwright upload of the same fixture session 46 used. `retrieval_source` flipped from `papers_only_fallback` → `coach_brain_primary`. ADR-BRAIN-09 added to capture the design choice.

## 1. Completed

### PR #87 (`811a6c3`) — D-045 enrich coach_brain retrieval query with seed-corpus vocabulary

Merged via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash). 2 commits preserved (impl + audit-finding fixup).

| Ref | What | Commit |
|---|---|---|
| L2-D045-01 | New read-only diagnostic `backend/scripts/oneoff/diagnose_coach_brain_retrieval.py` — measures Cohere Rerank 4.0 scores along live agent retrieval path for 4 query variants per exercise (current Q1, vocab-rich Q2, rep-context Q3, self-query ceiling Q4) with FR-BRAIN-05 threshold classification. | `607b193` |
| L2-D045-02 | TDD failing test `test_retrieve_coach_brain_query_includes_seed_corpus_vocabulary` — asserts per-exercise queries contain seed-corpus-overlapping high-signal tokens. | `607b193` |
| L2-D045-03 | Impl: `_COACH_BRAIN_QUERY_VOCAB: dict[str, str]` constant in `tools.py` + `.strip()`-appended to query via `.get(exercise_type, "")`. | `607b193` |
| L2-D045-04 | Audit-finding fixup: H-02 additive test for unknown-exercise graceful degradation; M-01 `logger.warning` when vocab tail is empty. | `a084e06` |
| L2-D045-PR | PR #87 → CI 6/6 green on `607b193` and after fixup `a084e06` → spelix-auditor PASS_WITH_FINDINGS (H-01 falsified against runtime + prod DB; H-02/M-01 fixed inline; H-03 documented in ADR-BRAIN-09) → spelix-security-reviewer PASS clean → merge → Deploy to Production green → droplet HEAD `811a6c3` + containers fresh + healthy → Playwright E2E on prod (bench fixture) flipped retrieval_source → screenshot saved | `811a6c3` (merge) |

### Diagnostic findings (rerank scores per FR-BRAIN-05 thresholds 0.65 hybrid / 0.82 primary)

| Exercise | Q1 current agent | Q2 vocab-rich | Q3 rep-context | Q4 self-query (ceiling) |
|---|---|---|---|---|
| **bench** | **0.319 ❌ fallback** | 0.917 ✅ primary | 0.862 ✅ primary | 0.992 |
| squat | 0.836 ✅ primary | 0.878 ✅ primary | 0.786 ✅ hybrid | 0.992 |
| deadlift | 0.917 ✅ primary | 0.878 ✅ primary | 0.962 ✅ primary | 0.990 |

Bench is uniquely broken (squat/deadlift Q1 already cross 0.82 because their exercise word appears verbatim in seed content). Seed corpus is fine (Q4 ceiling = 0.99 across all three). FR-BRAIN-03 prefix is not the problem (rerank input is raw `content`, no prefix). Falsifies hypotheses (a/b/c/d) from the original D-045 row. Root cause: bench seeds use "bench press"/"elbows"/"scapula" not "bench" alone, so a 5-token agent query lacks lexical overlap.

### Audit verdicts (pre-merge)

- **spelix-auditor** — PASS_WITH_FINDINGS. 1 CRITICAL (C-01 pre-existing SRS FR-BRAIN-04 doc inconsistency vs ADR-BRAIN-08, **not introduced by this PR** — flagged for separate SRS-level resolution). 3 HIGH: H-01 (`"bench"` vs `"bench_press"` key mismatch concern) **falsified** — `app/schemas/analysis.py:16` declares `ExerciseType = Literal["squat","bench","deadlift"]` and prod DB query `SELECT DISTINCT exercise_type FROM analyses` confirmed exactly those three values; H-02 (unknown-exercise fallback test) fixed inline in `a084e06`; H-03 (vocab drift risk) documented as accepted in ADR-BRAIN-09. 5 MEDIUM: M-01 fixed inline; M-02/M-04/M-05 no-action (commentary); M-03 (sys.path mutation in oneoff) low-risk for `scripts/oneoff/` and not addressed.
- **spelix-security-reviewer** — PASS clean. 0 CRITICAL, 0 HIGH. Confirmed: no secret exposure (no API key/DSN printed); ADR-DISTILL-05 compliance on the new diagnostic script (`type(exc).__name__` only, no `str(exc)`); pure ORM with no SQL injection surface; no Qdrant payload injection from static vocab tail strings; vocab tokens are query-time embedding inputs only (NOT user-facing, no SaMD/FTC violations); no JWT/RLS/auth touch; `logger.warning` logs enum value only, no PII.

### Prod E2E (2026-04-18 06:08–06:14 UTC)

Fresh upload of `atharva-bench-nw-10s-720p.mp4` (same fixture session 46 used) on `spelix.app`. Analysis `de316a7a-b4fd-4fb4-afc4-a1d6be596fa2`. Screenshot: `e2e/screenshots/d045-post-fix-bench-coach-brain-primary-de316a7a.png`.

| Check | Session 46 (pre-fix `6aa7b42b`) | Session 47 (post-fix `de316a7a`) |
|---|---|---|
| Analysis status | `completed` | `completed` |
| `retrieval_source` | `papers_only_fallback` ❌ | **`coach_brain_primary`** ✅ |
| `degraded_mode` | false | false |
| Console errors | 0 | 0 |
| Network 4xx/5xx | 0 | 0 |

### Carry-over (D-045 NOT a panacea — these are still open)

| Symptom on `de316a7a` | Same on `6aa7b42b` (session 46)? | Tracking ID |
|---|---|---|
| `eval_scores.faithfulness=0.0` | yes | D-048 (coaching-path CoVe truncation) |
| `eval_scores.cove_verified=false` | yes | D-048 |
| `eval_scores.overall=null` | yes | M-06 (Phase 4 `overall` population) |
| `agent_trace_json.converged=false` | yes | possibly D-048-related |

D-045 fixed retrieval routing — coaching-path quality gates remain blocked behind D-048 + M-06.

## 2. Remaining

### Session 48 Priority 1 — non-code blockers (unchanged since sessions 30+)

| ID | Title | Status |
|---|---|---|
| — | Kin expert onboarding call (still pending since session 30) — target 10+ papers by 2026-05-03 | open, blocks expert corpus push |
| — | Expert corpus push — first 10 papers via expert portal | blocked on expert call |
| — | Landing page V1 status verification on prod | unclear, needs re-check |

### Session 48 Priority 2 — PR #85 + #87 D-### follow-ups (bundle-candidate)

| ID | Title | Size | Source |
|---|---|---|---|
| D-048 | Apply M-05-style max_tokens bump to coaching-path `app/services/cove.py::CoveVerificationService`. Session 46 prod E2E showed output_tokens 1024→2048→3072 all truncated; **session 47 D-045 verification reproduced the exact same failure on `de316a7a` post-D-045 fix** — proves D-048 is independent of retrieval routing and is the next blocker on `eval_scores.cove_verified=true`. | S | session 46 + session 47 |
| D-046 | Extract `_HAIKU_MODEL` to `app/constants.py` — currently duplicated in `cove_brain.py`, `extract.py`, + `cove.py`. Drift risk. | S | auditor M-03 |
| D-047 | Additive test in `test_distillation_cove_brain.py` for the pre-fix M-05 failure mode via stubbed `ValidationError` side effect. | S | code-reviewer suggestion |
| D-049 | Pydantic `Citation` serializer warning spam in worker logs on every coaching call with citations. | S | session 46 worker log |

### Session 48 Priority 3 — PR #84 D-### follow-ups (unchanged from sessions 45+)

| ID | Title | Size | Source |
|---|---|---|---|
| D-042 | Wire `_PROMINENCE_DEG` + `_STANDING_THRESHOLD` + `_DEPTH_THRESHOLD` + `_MIN_REP_DURATION_S` through `ThresholdConfig` (FR-SCOR-11) | S | auditor H-1 |
| D-043 | Additive test: partial descent with <20° prominence in `test_rep_detection.py` | S | auditor M-2 |
| D-044 | Investigate `atharva-bench.mov` 13-rep over-count (pre-existing; MediaPipe flicker / Savgol over-smoothing) | M | session 45 |

### Session 48 Priority 4 — P3-007 D-### bundle (unchanged from sessions 44+)

| ID | Title | Size |
|---|---|---|
| D-### | Full focus trap inside AgentReasoningSidebar | S |
| D-### | Adaptive-mode reasoner-loop UI polish | M |
| D-### | CoVe iteration drill-down pane | M |
| D-### | LangSmith run link-out from summary header | S |
| D-### | Sanitize `NodeEvent.error` in `serialize_trace_for_storage` (strip `/tmp/...` paths) | S |

### Deferred follow-ups from earlier sessions (unchanged)

| ID | Title | Status |
|---|---|---|
| D-037 | Surface top-2 similar existing approved entries on P3-006 review card | open |
| D-038 | Add `compensation` to `coach_brain_candidates.entry_type` CHECK constraint | open |
| D-039 | Re-run CoVe after admin content edit on approve | D-048 helps but doesn't fully close this |
| P3-008 | FR-BRAIN-08 auto-triage — blocks on ≥50 human-reviewed candidates | deferred post-L2 |
| D-029 | SaMD rename `injury_advice_accurate` → `movement_advice_accurate` | LOW |
| D-030 | Orphan `rag_documents` cleanup cron | LOW |
| D-031 | Admin `GET /rag/documents` Literal constraint | LOW |
| D-036 | GPU offload for pose extraction | post-beta |
| M-06 | Phase 4 `overall` population → audit faithfulness fallback sites | Phase 4 |

## 3. Test counts

**Backend** (final local run, post-audit-fix pre-merge):
- `uv run pytest -x -q --ignore=tests/e2e` → **1696 passed, 25 skipped, 0 failed** (1694 baseline + 2 new tests).
- `uv run ruff check .` — clean.
- `uv run pyright app/` — **0 errors, 0 warnings, 0 informations**.
- New/updated test file: `test_agents_tools.py` (+2 tests: vocabulary assertion + unknown-exercise graceful-degradation).
- **Known failures:** none.

**Frontend** (no frontend changes in this PR — vitest not re-run beyond CI which passed in 1m22s).

**CI on PR #87** — both head commits green:
- `607b193` (initial): all 6 gates pass on run `24598320869` (Backend Lint 36s, Backend Tests 1m54s, Frontend Lint 23s, Frontend Tests 1m16s, Secret Scanning 15s, Vercel pass).
- `a084e06` (audit-fixup): all 6 gates pass on run `24598408857`.
- Merge commit `811a6c3` Deploy to Production green on run `24598457531`.

## 4. Key learnings captured in this session

1. **The Cohere Rerank cross-encoder bottleneck is on the QUERY side, not the document side.** ADR-BRAIN-02's contextualized prefix shapes dense candidate retrieval but never reaches the reranker (because `coach_brain` payload stores raw `content` not prefixed `text`). For small corpora (~8 docs per exercise filter), all docs surface as candidates anyway, so dense quality doesn't matter — only rerank scores do. And rerank scores are bounded by query lexical surface area. ADR-BRAIN-09 captures the resulting design rule: agent retrieval queries need vocabulary enrichment, not just exercise-type/variant tokens.

2. **The diagnostic script pattern is reusable.** `backend/scripts/oneoff/diagnose_coach_brain_retrieval.py` is generic enough to drop in for any future "why does Coach Brain not surface?" or "why is paper retrieval thin?" question — just swap the queries, add Q5 candidates, re-run on prod via the same `docker exec spelix-backend-1 /app/.venv/bin/python /app/scripts/oneoff/...` pattern. Worth keeping in the repo (already committed).

3. **`/app/.venv/bin/python` not `python` for prod oneoffs.** The base `/usr/local/bin/python` in the container has none of the project deps. Always use the venv interpreter. (Session 46 reembed script worked because the worker's invocation used the venv via the streaq entrypoint; standalone exec needs the explicit path.) Worth a `backend/CLAUDE.md` gotcha entry next time we hit this.

4. **Auditor H-01 was wrong but worth checking.** The auditor flagged a possible `"bench"` vs `"bench_press"` key mismatch in `_COACH_BRAIN_QUERY_VOCAB`. I had to verify against `ExerciseType` Literal in the schema AND query prod DB before declaring it false. Per `superpowers:verification-before-completion`, "should be fine" doesn't cut it. Cost: ~2 min. Saved: shipping a real bug if H-01 had turned out to be true. Pattern worth keeping: when an audit finding is plausible, run a 30-second verification before dismissing.

5. **Ship D-045 changes to anything that touches retrieval, not just coach_brain.** `retrieve_papers` in the same file uses an even more generic query `"{exercise} {variant} technique coaching biomechanics"`. Papers_rag has many docs so a low-relevance match still produces a top result — but the retrieval quality is almost certainly suboptimal. Not urgent (papers always returns SOMETHING), but worth noting if a future RAG investigation suggests papers retrieval also drifts. Could file as D-### follow-up if observed.

## 5. Blockers

**Code-side:** none — PR #87 shipped, verified on prod, screenshots captured. D-046 through D-049 + D-042/D-043/D-044 are bundle-ready for next session. D-048 is now the highest-impact remaining bug (proven still active on `de316a7a`).

### Non-code blockers (carry-over from earlier sessions, unchanged)

- **Kin expert onboarding call** still pending since session 30. 15 days to 2026-05-03 L2 deadline. Each day of slip compounds against landing readiness.
- **`papers_only_fallback` over-use** — RESOLVED for bench by D-045. Squat and deadlift were already routing through Coach Brain pre-fix per the diagnostic. This blocker is now closed.

### Worktree / branch state

- Feature branch `fix/d045-coach-brain-query-enrichment` merged on origin; can be deleted via `git push origin --delete fix/d045-coach-brain-query-enrichment` when cleanup is desired.
- Local `main` at `811a6c3` (PR #87 merge commit). Origin `main` matches.

## 6. E2E Findings — D-045 verification

- **Analysis UUID:** `de316a7a-b4fd-4fb4-afc4-a1d6be596fa2` (bench fixture, admin test account, fresh upload).
- **Screenshot:** `e2e/screenshots/d045-post-fix-bench-coach-brain-primary-de316a7a.png`.
- **Pre-fix `retrieval_source`:** `papers_only_fallback` (session 46 baseline `6aa7b42b`).
- **Post-fix `retrieval_source`:** **`coach_brain_primary`** — flip confirmed via direct Postgres SELECT on `coaching_results.agent_trace_json`. Coaching pipeline completes cleanly: analysis status `completed`, 0 console errors, 0 network 4xx/5xx.
- **Coach Brain candidates created this session:** unknown (didn't query `coach_brain_candidates` directly — distillation may not have fired due to D-048 coaching-path CoVe failure persisting `faithfulness=0.0`).
- **D-048 still active:** Same `cove_trace` truncation symptom as session 46 — `eval_scores.faithfulness=0.0` and `cove_verified=false` on `de316a7a`. Not a D-045 regression. Tracked as D-048 (top of Priority 2 next session).

## 7. Next session start

```bash
/status

# PRIORITY 1 — Non-code blockers
#   - Kin expert onboarding call (target: 10+ papers by 2026-05-03)
#   - Expert corpus push: first 10 papers via expert portal
#   - Landing page V1 prod verification

# PRIORITY 2 — PR #85 + #87 D-### follow-ups (bundle-candidate)
#   - D-048 M-05-style max_tokens bump on coaching-path CoveVerificationService
#     (S; tops priority — proven active on de316a7a, blocks faithfulness/cove_verified)
#   - D-046 hoist _HAIKU_MODEL to shared constant (S)
#   - D-047 additive ValidationError regression test for BrainCoveService (S)
#   - D-049 Citation serializer warning cleanup (S)

# PRIORITY 3 — PR #84 D-### follow-ups
#   - D-042 wire rep-detection knobs through ThresholdConfig (S)
#   - D-043 partial-descent <20° prominence test (S)
#   - D-044 atharva-bench.mov signal-quality investigation (M)

# PRIORITY 4 — P3-007 D-### bundle
#   - Focus trap for AgentReasoningSidebar (~15 LOC, a11y)
#   - Sanitize NodeEvent.error in serialize_trace_for_storage (security MED)
#   - LangSmith run link-out from summary header (S)
#   - CoVe iteration drill-down pane (M)
#   - Adaptive-mode reasoner-loop UI polish (M)

# ENVIRONMENT NOTES:
#   - Local main = 811a6c3 (PR #87 merge). Origin main same.
#   - SPELIX_DISTILLATION_ENABLED=1 on prod since session 42
#   - SPELIX_PHASE3_AGENT_ENABLED=1 on prod since session 32
#   - Test admin account: atharva6905+admin-p3006@gmail.com /
#     SpelixAdmin-P3006-Test-2026! (UUID cb18c043-5a16-4990-a3d3-02ed4890bf56).
#     Now owns 5 analyses — session 44 cea2312b (0 reps pre-fix),
#     session 45 f36f8367 (1 rep post-D-040/D-041),
#     session 46 adbad4bf (squat, quality_gate_rejected),
#     session 46 6aa7b42b (bench, retrieval_source=papers_only_fallback),
#     session 47 de316a7a (bench, retrieval_source=coach_brain_primary post-D-045).
#   - Qdrant coach_brain: 26 points (24 seeds, UUID-match upsertable via re-embed script).
#   - Oneoff scripts on prod: NOT in the Docker image. Use the docker cp
#     workflow into /app/scripts/oneoff/ AND invoke via /app/.venv/bin/python
#     (not the system python, which lacks deps).
#   - D-045 diagnostic script lives in repo at backend/scripts/oneoff/
#     diagnose_coach_brain_retrieval.py — re-runnable for any future RAG
#     retrieval investigation.
```
