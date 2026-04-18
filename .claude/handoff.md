# Session 46 Handoff → Session 47: M-04 + M-05 Coach Brain maintenance bundle shipped to prod (PR #85)

**Context refresh:** Session 46 (2026-04-18, L2 Sprint Day 10) closed session 45's Priority 2 — the M-04/M-05 maintenance bundle from backlog `## Discovered backlog items (post-L2 follow-ups)`. Both fixes shipped in one PR, auto-deployed, prod re-embed script executed cleanly on the droplet, and a Playwright MCP E2E upload through the admin account verified the coaching pipeline still completes. Two finding-class discoveries surfaced during E2E — both filed as new D-### backlog rows rather than re-opened against M-04/M-05, because the fixes each did exactly what the backlog asked; the observed symptoms turned out to have different root causes.

## 1. Completed

### PR #85 (`a0a86fc`) — M-04 re-embed Coach Brain seeds + M-05 bump BrainCoveService max_tokens

Merged via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash). 5 commits preserved (feat + quality-review fixup for M-04, test + impl for M-05, audit-finding fixup). Plan at `docs/superpowers/plans/2026-04-18-priority2-m04-m05-maintenance-bundle.md`.

| Ref | What | Commit |
|---|---|---|
| L2-M04-01 | New oneoff script `backend/scripts/oneoff/reembed_coach_brain_seeds.py` — loads seed rows + calls `BrainEmbeddingService.embed_and_upsert_batch` | `28404a7` |
| L2-M04-02a | Code-review fixup #1: move `engine.dispose()` out of session context + add `try/finally` around embed call | `b8b88b5` |
| L2-M05-01 | TDD failing test `test_verify_claim_uses_adequate_max_tokens` | `7d2b3c1` |
| L2-M05-02 | Impl: `cove_brain.py` question `max_tokens=256→512` + answer `max_tokens=512→2048` with rationale comments | `66e255d` |
| L2-M04-M05-audit-fix | Audit-finding fixup #2: single outer `try/finally` (auditor H-01); `assert len(point_ids) == len(schema_entries)` invariant (M-04); strip `str(exc)` from stderr prints (security LOW-1 + LOW-2); assert `model == _HAIKU_MODEL` in test (M-01) | `a1f0f78` |
| L2-M04-M05-PR | PR #85 → CI 6/6 green → audits PASS_WITH_FINDINGS (all actionable items fixed inline; H-02 + M-03 deferred as D-045 + D-046) → merge (`merge`, NOT squash) → Deploy to Production 39s → droplet HEAD match + containers healthy → prod re-embed executed → Playwright E2E verified | `a0a86fc` (merge) |

### Audit verdicts (pre-merge)

- **spelix-auditor** — PASS_WITH_FINDINGS. 0 CRITICAL, 2 HIGH (H-01 fixed in `a1f0f78`, H-02 deferred → D-045 — pre-existing FR-BRAIN-03 `embedding_text` Qdrant payload gap, not introduced by this PR), 4 MEDIUM (M-01/M-04 fixed in `a1f0f78`; M-02 no-action by auditor; M-03 deferred → D-046 shared HAIKU_MODEL constant). All actionable findings addressed pre-merge.
- **spelix-security-reviewer** — PASS_WITH_FINDINGS. 0 CRITICAL, 0 HIGH, 2 LOW (both ADR-DISTILL-05-style `str(exc)` leakage hygiene findings, both fixed in `a1f0f78`). 7/7 core security checks PASS (secret exposure, SQL injection, ADR-DISTILL-05 compliance in `cove_brain.py`, JWT/auth scope, RLS, SaMD language, Qdrant payload injection).

### Prod re-embed (2026-04-18 05:02 UTC)

Ran `docker cp` to install the script into `spelix-backend-1:/app/scripts/oneoff/`, then `docker exec` to run it.

```
[reembed] Loaded 24 seed rows from coach_brain_entries
[reembed] Re-embedding 24 entries via Cohere embed-v4.0 (SEARCH_DOCUMENT) with FR-BRAIN-03 prefix...
[reembed] Upserted 24 points to coach_brain collection
  bench: 8 entries
  deadlift: 8 entries
  squat: 8 entries
```

Qdrant coach_brain point count: **26 before / 26 after** — confirmed UUID-match upsert replaces in place (no duplicate points). Exit 0.

### Prod E2E (2026-04-18 05:02–05:08 UTC)

Fresh admin-account upload of `atharva-bench-nw-10s-720p.mp4` on `spelix.app`. Analysis `6aa7b42b-1039-4e1e-a429-5d3f599ae79f`. Screenshot: `e2e/screenshots/m04-m05-post-reembed-prod-verified-6aa7b42b.png`.

| Check | Result |
|---|---|
| Analysis status | `completed` |
| Detected exercise | Bench — flat, 79% confidence |
| Rep count | 1 rep (10s single-rep fixture) |
| Form scores | Overall 7.8 / MovQ 8.0 / Tech 8.5 / P&B 6.2 / Ctrl 10.0 — all populated |
| Console errors (Playwright) | 0 |
| Network 4xx/5xx | 0 |
| `retrieval_source` | `papers_only_fallback` — **unchanged** vs pre-re-embed |
| `degraded_mode` | false |
| `agent_trace_json.nodes_executed` count | 10 |
| Distillation fired | **No** — coaching `faithfulness_passed=false` (faithfulness=0.42) blocked the gate |
| `coach_brain_candidates` rows for this analysis | 0 |

### Additional squat fixture upload (failed pre-pipeline, not an M-04/M-05 defect)

First verification attempt used `atharva-squat.mov` (5-rep, 20.2s). The quality gate rejected with `qg_passed=false` (`quality_gate_rejected`). This fixture is side-view but has body partially out of frame — same `quality_gate_result` shape as other rejected uploads. Not an M-04/M-05 regression. The bench fixture retry (above) is the authoritative verification.

## 2. Remaining

### Session 47 Priority 1 — non-code blockers (unchanged since sessions 30+)

| ID | Title | Status |
|---|---|---|
| — | Kin expert onboarding call (still pending since session 30) — target 10+ papers by 2026-05-03 | open, blocks expert corpus push |
| — | Expert corpus push — first 10 papers via expert portal | blocked on expert call |
| — | Landing page V1 status verification on prod | unclear, needs re-check |

### Session 47 Priority 2 — PR #85 D-### follow-ups (bundle-candidate)

| ID | Title | Size | Source |
|---|---|---|---|
| D-045 | Investigate why `retrieval_source=papers_only_fallback` persists on prod after M-04 re-embed. Hypotheses: Cohere SEARCH_QUERY/SEARCH_DOCUMENT asymmetry; ADR-BRAIN-02 prefix vocabulary mismatch with natural-language queries; seed content too generic; richer FR-BRAIN-03 natural-language template helps on short docs. Start with a diagnostic script that queries coach_brain directly with known seed content and inspects rerank scores. | M | session 46 E2E |
| D-046 | Extract `_HAIKU_MODEL` to `app/constants.py` — currently duplicated in `cove_brain.py`, `extract.py`, + `cove.py`. Drift risk. | S | auditor M-03 |
| D-047 | Additive test in `test_distillation_cove_brain.py` for the pre-fix M-05 failure mode via stubbed `ValidationError` side effect. Prevents silent regression if max_tokens ever gets reduced below 2048. | S | code-reviewer suggestion |
| D-048 | Apply M-05-style max_tokens bump to coaching-path `app/services/cove.py::CoveVerificationService`. Session 46 prod E2E showed output_tokens 1024→2048→3072 all truncated — identical failure mode to BrainCoveService pre-fix. Coaching-path still succeeds (gracefully falls back) but `eval_scores.cove_verified=false` gets persisted spuriously. | S | session 46 E2E |
| D-049 | Pydantic `Citation` serializer warning spam in worker logs on every coaching call with citations. Non-functional but noisy. Root cause likely dict-vs-model mismatch in instructor deserialization. | S | session 46 worker log |

### Session 47 Priority 3 — D-### follow-ups from PR #84 (unchanged from session 45)

| ID | Title | Size | Source |
|---|---|---|---|
| D-042 | Wire `_PROMINENCE_DEG` + `_STANDING_THRESHOLD` + `_DEPTH_THRESHOLD` + `_MIN_REP_DURATION_S` through `ThresholdConfig` (FR-SCOR-11) | S | auditor H-1 |
| D-043 | Additive test: partial descent with <20° prominence in `test_rep_detection.py` | S | auditor M-2 |
| D-044 | Investigate `atharva-bench.mov` 13-rep over-count (pre-existing; MediaPipe flicker / Savgol over-smoothing) | M | session 45 |

### Session 47 Priority 4 — P3-007 D-### bundle (unchanged from sessions 44+)

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
- `uv run pytest -x -q --ignore=tests/e2e` → **1694 passed, 25 skipped, 0 failed** (baseline 1693 + 1 M-05 TDD test).
- `uv run ruff check .` — clean.
- `uv run pyright app/` — **0 errors, 0 warnings, 0 informations**.
- New/updated test files: `test_distillation_cove_brain.py` (+1 test for `max_tokens` + `model` kwarg introspection).
- **Known failures:** none.

**Frontend** (local run, pre-merge):
- `npx tsc --noEmit` — 0 errors (not re-run full vitest on this docs-only-adjacent PR).

**CI on PR #85** (head `a1f0f78` after fixup, run `24597166061`): all 6 gate checks green — Backend Lint 36s, Backend Tests 1m55s, Frontend Lint 26s, Frontend Tests 1m32s, Secret Scanning 13s, Vercel pass. **Deploy to Production on main (merge commit `a0a86fc`) also green in 39s.**

## 4. Key learnings captured in this session

1. **The FR-BRAIN-03 contextualized prefix was already being applied before M-04.** `BrainEmbeddingService.embed_and_upsert_batch` has called `build_contextual_text` since P2-024 landed, and the seed script called `embed_and_upsert_batch` from day 1. The backlog hypothesis ("current seeds were embedded with raw content only") was incorrect. The re-embed still ran cleanly and produced 24 identical upserts, so nothing was broken — but it also did not flip `retrieval_source` off `papers_only_fallback` because the missing-prefix hypothesis was wrong. The true cause is something else — filed as D-045.
2. **Two CoVe services coexist and both have max_tokens issues.** `app/distillation/cove_brain.py::BrainCoveService` (M-05 target — now 2048 tokens, verified) is distinct from `app/services/cove.py::CoveVerificationService` (coaching-path, still at ~3072 and still truncating per the session 46 prod E2E logs). ADR-DISTILL-03 established the separation deliberately; the M-05 fix correctly only touches the distillation service. D-048 tracks the coaching-path counterpart.
3. **Prod container layout mismatch** — the runtime `spelix-backend-1` container has `/app/app/...` (no `backend/` prefix, no `scripts/` subtree). Scripts are not in the Docker image and are not volume-mounted; the plan assumed `/app/backend/scripts/oneoff/...` based on the repo layout, which does not exist on the droplet. Workaround: `docker exec -u root mkdir -p /app/scripts/oneoff && docker cp ~deploy/spelix/backend/scripts/oneoff/X.py spelix-backend-1:/app/scripts/oneoff/X.py` — the script's `sys.path` patch then correctly puts `/app` on the path. Any future oneoff plan should specify this workflow, not the in-repo path. Worth a `backend/CLAUDE.md` gotcha entry but deferred until we see this twice.

## 5. Blockers

**Code-side:** none — PR #85 shipped and verified on prod. D-045 through D-049 captured as follow-ups; none block any in-flight L2 sprint work.

### Non-code blockers (carry-over from earlier sessions, unchanged)

- **Kin expert onboarding call** still pending since session 30. 15 days to 2026-05-03 L2 deadline. Each day of slip compounds against landing readiness.
- **`papers_only_fallback` over-use on prod retrieval** remains (D-045 replaces M-04's original hypothesis). Coach Brain retrieval is still dark on prod — seeds are eligible but not scoring high enough to cross the 0.65 rerank threshold.

### Worktree / branch state

- Feature branch `fix/m04-m05-coach-brain-reembed-cove-tokens` merged on origin; can be deleted via `git push origin --delete fix/m04-m05-coach-brain-reembed-cove-tokens` when cleanup is desired.
- Local `main` at `a0a86fc` (PR #85 merge commit). Origin `main` matches.

## 6. E2E Findings — M-04 / M-05 verification

- **Analysis UUID:** `6aa7b42b-1039-4e1e-a429-5d3f599ae79f` (bench fixture, admin test account).
- **Screenshot:** `e2e/screenshots/m04-m05-post-reembed-prod-verified-6aa7b42b.png`.
- **Pre-re-embed `retrieval_source`:** known from session 42 prod observation — `papers_only_fallback`.
- **Post-re-embed `retrieval_source`:** still `papers_only_fallback` (see D-045). Coaching pipeline itself completes cleanly: analysis status `completed`, all form scores populated, 0 console errors, 0 network 4xx/5xx.
- **`coach_brain_candidates` rows created this session:** 0 (distillation did not fire because coaching `eval_scores.faithfulness_passed=false`). M-05 therefore not exercised on prod this session — unit-test-verified only. Will be exercised on first subsequent distillation-eligible run.
- **Observed coaching-path CoVe failure:** `cove_trace` shows three retries at 1024→2048→3072 all truncated — that's the `CoveVerificationService` (coaching path), NOT the `BrainCoveService` (distillation path that M-05 targeted). Tracked as D-048.

## 7. Next session start

```bash
/status

# PRIORITY 1 — Non-code blockers
#   - Kin expert onboarding call (target: 10+ papers by 2026-05-03)
#   - Expert corpus push: first 10 papers via expert portal
#   - Landing page V1 prod verification

# PRIORITY 2 — PR #85 D-### follow-ups (bundle-candidate)
#   - D-045 investigate papers_only_fallback root cause (M — tops priority because it blocks retrieval)
#   - D-046 hoist _HAIKU_MODEL to shared constant (S)
#   - D-047 additive ValidationError regression test for BrainCoveService (S)
#   - D-048 M-05-style max_tokens bump on coaching-path CoveVerificationService (S)
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
#   - Local main = a0a86fc (PR #85 merge). Origin main same.
#   - SPELIX_DISTILLATION_ENABLED=1 on prod since session 42
#   - SPELIX_PHASE3_AGENT_ENABLED=1 on prod since session 32
#   - Test admin account: atharva6905+admin-p3006@gmail.com /
#     SpelixAdmin-P3006-Test-2026! (UUID cb18c043-5a16-4990-a3d3-02ed4890bf56).
#     Now owns 4 analyses — session 44 cea2312b (0 reps pre-fix),
#     session 45 f36f8367 (1 rep post-D-040/D-041 fix),
#     session 46 adbad4bf (squat, quality_gate_rejected),
#     session 46 6aa7b42b (bench, completed post-M04/M05).
#     Re-use for future verification.
#   - Qdrant coach_brain: 26 points (24 seeds, UUID-match upsertable via re-embed script).
#   - Oneoff scripts path on prod: scripts are NOT in the Docker image. Use
#     `docker exec -u root mkdir -p /app/scripts/oneoff && docker cp ...`
#     to install into the running container before running.
```
