# Session 49 Handoff → Session 50: D-050 CoVe claim-extraction refinement shipped to prod (PR #90)

**Context refresh:** Session 49 (2026-04-18, L2 Sprint Day 11, same calendar day as sessions 46 + 47 + 48) closed D-050 — the claim-extraction prompt refinement follow-up surfaced by session 48's D-048 fix working correctly. 4-commit PR via subagent-driven-development (spelix-coaching-engineer + spec-reviewer + code-quality-reviewer + one review fix-up). Auditor PASS_WITH_FINDINGS (0 CRITICAL / 0 HIGH), security-reviewer PASS, E2E on prod with the same bench fixture sessions 46–48 used. **Core D-050 goal achieved — all extracted claims are now principle-shaped**, zero lifter-specific measurements. `faithfulness` dropped 0.92 → 0.82 (still above 0.8 gate). `cove_verified=false` persists for a NEW reason — filed as D-052.

## 1. Completed

### PR #90 (`6c41953`) — D-050 refine CoveVerificationService claim-extraction prompt to principle-level only

Merged via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash). 4 commits preserved.

| Ref | What | Commit |
|---|---|---|
| L2-D050-01 | TDD failing tests: 3 new tests appended to `backend/tests/unit/test_cove.py` — `test_claim_extraction_prompt_emphasises_principle_level` (asserts "principle" + "measurement" + SKIP markers), `test_claim_extraction_prompt_includes_worked_examples` (asserts ≥2 example markers + "extract"), `test_claim_extraction_prompt_still_references_falsifiability` (regression guard on "falsifiable"/"testable"/"research" vocabulary). | `e2d74e6` |
| L2-D050-02 | Impl: rewrite `_build_claim_extraction_prompt` body in `backend/app/services/cove.py` (lines 109-166) with the refined prompt — explicit PRINCIPLE-vs-MEASUREMENT distinction, SKIP directive for measurements, translate-not-invent rule with elbow-38° example, 4 worked `Coaching says / Extract:` example blocks. Signature, call sites, max_tokens, model, and response schema UNCHANGED. | `647450a` |
| L2-D050-03 | Live-API smoke script `backend/scripts/oneoff/smoke_cove_claim_extraction_d050.py` — operator qualitative-gate tool, calls real Haiku 4.5 against a synthetic `CoachingOutput` matching session 48 bench shape. Not run in CI. | `7cab235` |
| L2-D050-04 | Code-review fix-up: tighten the `Extract:` label assertion from `assert "extract" in lowered` (too weak — passes on the prompt's opening "extracting" word) to `assert lowered.count("extract:") >= 2` (requires the worked-example labels). | `9d6a447` |
| L2-D050-PR | PR #90 → CI 6/6 green on `9d6a447` (Backend Lint 35s, Backend Tests 2m14s, Frontend Lint 24s, Frontend Tests 1m23s, Secret Scanning 10s, Vercel pass) → spelix-auditor PASS_WITH_FINDINGS (0 CRITICAL, 0 HIGH, 3 MEDIUM all non-blocking — M-01/M-02 deferred ADR+backlog to this docs commit, M-03 SaMD-exclusion test suggestion) → spelix-security-reviewer PASS clean on all 8 checks → merge → Deploy to Production 37s on `6c41953` → droplet HEAD `/home/deploy/spelix` at `6c41953` + containers healthy (backend + redis healthy, worker up) → Playwright E2E on prod bench fixture. | `6c41953` (merge) |

### Prod E2E (2026-04-18 20:03–20:12 UTC) — D-050 fix verified

Fresh upload of `atharva-bench-nw-10s-720p.mp4` (same fixture sessions 46 + 47 + 48 used) on `spelix.app` under admin test account. Analysis `c46023c9-b098-4083-9c19-dad174b14a04`. Screenshot: `e2e/screenshots/d050-post-fix-results-c46023c9.png`.

| Metric | Session 46 (`6aa7b42b`, pre-M04/M05) | Session 48 (`bfbed270`, post-D-048) | Session 49 (`c46023c9`, post-D-050) |
|---|---|---|---|
| analysis status | completed | completed | completed |
| `retrieval_source` | `papers_only_fallback` ❌ | `coach_brain_primary` ✅ | `coach_brain_primary` ✅ |
| `degraded_mode` | false | false | false |
| `eval_scores.faithfulness` | **`0.0`** ❌ | **`0.92`** ✅ | **`0.82`** (above 0.8 gate) |
| `eval_scores.cove_verified` | `false` (silent crash) | `false` (measurement Uncertains) | `false` (hallucinated-inversion No) |
| `cove_iterations` count | 0 / empty | 2 | 2 |
| iter1 / iter2 claim count | n/a | 11 / 15 | **9 / 8** (tighter) |
| Claim-shape (Gate C) | n/a | 9/15 measurements → Uncertain | **0/8 measurements, 7/8 principles → Yes** ✅ |
| console errors / 4xx-5xx | 0 | 0 | 0 |

**Gate A (cove_verified=true): FAIL** — still false. But not for the pre-D-050 reason (measurement-Uncertain) — for a NEW reason (extractor inverts/invents principles). See D-052 below.

**Gate B (faithfulness≥0.85): MARGINAL** — 0.82. Still above the 0.80 RAGAS gate (`faithfulness_passed=true`). Plan's "acceptable 0.5–0.85" band — the drop reflects a denominator-shift (fewer measurement-Uncertain claims to average over), not a quality loss.

**Gate C (principle-shaped claims): PASS** ✅ — all 17 claims across both iterations are principle-level statements about biomechanics (not about THIS lifter's measured values). Representative examples:
- iter 1: "The optimal elbow angle from the torso during the descent of the bench press is 45–75°." → **Yes**, "Source 1 explicitly states..."
- iter 2: "The recommended eccentric phase duration for bench press is approximately 2 seconds." → **Yes**, "Source 2 states 'Control the eccentric at a consistent tempo — aim for a 2-second descent.'"
- iter 2: "At lockout, the bar should be directly over the shoulder joint with elbows fully extended and scapular retraction maintained." → **Yes**, "Source 3 explicitly states..."

Compare to session 48 `bfbed270` which had claims like "Did the eccentric phase duration measure 5.16 seconds?" (measurement, Uncertain) — these are gone. **Core D-050 goal accomplished.**

### Why `cove_verified=false` persists — new root cause for D-052

Iteration 2 on `c46023c9` reached **7/8 Yes** but the single No blocked convergence:

- Q: "Does an excessively slow eccentric phase make it harder to maintain consistent bar path control and hit the correct touch point on the chest?"
- A: **No** — "Source 2 states that a rushed (FAST) descent reduces time under tension and makes it harder to hit the correct touch point, not a SLOW descent."

The extractor INVERTED the source's direction (fast-descent is bad → extracted as "slow-descent is bad"). Iteration 1 additionally invented three principles not in the coaching output:
- "minimum of 60°" (coaching never stated a minimum)
- "60–100° reference range" (not in coaching or sources)
- "stretch-shortening cycle disruption from extreme eccentric" (not in sources)

The refined prompt's `"do not invent a principle that was not written"` rule is too soft — it catches bare-measurement-to-invented-principle but does NOT catch inversions or extrapolations of stated principles. **D-052** will add an explicit inversion-guard + a before/after worked example for inverted-principle hallucination.

### Audit verdicts (pre-merge)

- **spelix-auditor** (PR #90) — PASS_WITH_FINDINGS. 0 CRITICAL / 0 HIGH. 3 MEDIUM:
  - M-01: ADR-COVE-02 not yet in `decisions.md` at PR time. Landed in this docs close-out commit per plan (matches session-48 D-048 precedent). Closed.
  - M-02: D-050 backlog row still `open` at PR time. Flipped to `done` in this docs close-out commit. Closed.
  - M-03: Optional test hardening — add `test_claim_extraction_prompt_excludes_samd_vocabulary` asserting the prompt excludes "injury risk" / "injury prevention" (user-facing forbidden forms). Non-blocking suggestion. Not filed as its own D-### — low value given the CLAUDE.md-level constraint declaration already in `cove.py` line 9, and the existing code-review process would catch any drift.
- **spelix-security-reviewer** (PR #90) — PASS clean. 0 CRITICAL / 0 HIGH. All 8 checks passed: no user-facing string additions (the prompt is internal), no SaMD/FTC drift, error-handling invariants preserved (`verify()` top-level try/except byte-identical to pre-PR), no new logging that could leak coaching content, no secret exposure (`ANTHROPIC_API_KEY` read via `os.getenv` in smoke script), no JWT/RLS/auth touch, no new prompt-injection surface (f-string surface unchanged from pre-PR), test mocking safe (pure string assertions, no API calls), ADR-COVE-01 style preserved.

### Worker log observations (non-blocking, D-049 + new D-053)

- **D-049** Pydantic `Citation` serializer warnings still present on every coaching call with citations (visible on `c46023c9` run). Non-functional — coaching still completes. D-049 row remains `open`.
- **D-053** (new): distillation lifecycle_decision logs show `qdrant search failed ('AsyncQdrantClient' object has no attribute 'search') — treating as ADD` warnings for every candidate promotion check. Known gotcha per `backend/CLAUDE.md` — the `qdrant-client` API has shifted, `AsyncQdrantClient.search` is deprecated/removed. Currently silent-fallback to `ADD` means every candidate passes the "no similar existing" check, over-admitting duplicates to the review queue. Migrate to `query_points` or the new API. Filed as D-053 in backlog.

## 2. Remaining

### Session 50 Priority 1 — non-code blockers (unchanged)

| ID | Title | Status |
|---|---|---|
| — | Kin expert onboarding call (still pending since session 30) — target 10+ papers by 2026-05-03 | open, blocks expert corpus push, **14 days to L2 deadline** |
| — | Expert corpus push — first 10 papers via expert portal | blocked on expert call |
| — | Landing page V1 status verification on prod | unclear, needs re-check |

### Session 50 Priority 2 — D-### follow-up bundle (candidate)

| ID | Title | Size | Source |
|---|---|---|---|
| D-052 | **Tighten D-050 prompt with inversion-guard**. Session 49 E2E showed iteration 2 reached 7/8 Yes but the one No was an inverted-direction hallucination ("slow eccentric is bad" — source actually says fast-descent is bad). Iter 1 also invented "minimum 60°" / "60–100° range" / "stretch-shortening cycle" claims not in the coaching. Add explicit inversion/extrapolation guard + negative worked example. | S | session 49 prod E2E on `c46023c9` |
| D-053 | **Distillation lifecycle_decision `AsyncQdrantClient.search` API drift**. Silent fallback to `ADD` over-admits duplicates. Migrate to `query_points`. Visible every distillation run in worker logs. | M | session 49 worker log |
| D-046 | Hoist `_HAIKU_MODEL` to shared `app/constants.py`. | S | auditor M-03 on PR #85 |
| D-047 | Additive test in `test_distillation_cove_brain.py` for pre-fix M-05 failure mode via stubbed `ValidationError`. | S | code-reviewer on PR #85 |
| D-049 | `Citation` Pydantic serializer warning spam in worker logs on every coaching call (confirmed still present in session 49 worker log). Non-functional. | S | sessions 46 + 48 + 49 worker logs |
| D-051 | Additive regression test for `_run_cove_loop` else-branch (`iteration == max_iterations`) via `max_iterations=1` + "No" answer. The `if` branch is covered; the structurally-identical `else` branch at `cove.py:389` is not. | S | auditor M-02 on PR #88 |

### Session 50 Priority 3 — PR #84 D-### follow-ups (carry-over unchanged)

| ID | Title | Size | Source |
|---|---|---|---|
| D-042 | Wire `_PROMINENCE_DEG` + `_STANDING_THRESHOLD` + `_DEPTH_THRESHOLD` + `_MIN_REP_DURATION_S` through `ThresholdConfig` (FR-SCOR-11) | S | auditor H-1 |
| D-043 | Additive test: partial descent with <20° prominence in `test_rep_detection.py` | S | auditor M-2 |
| D-044 | Investigate `atharva-bench.mov` 13-rep over-count (MediaPipe flicker / Savgol over-smoothing) | M | session 45 |

### Session 50 Priority 4 — P3-007 D-### bundle (carry-over unchanged)

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
| D-039 | Re-run CoVe after admin content edit on approve | D-048 partially addresses (CoVe runs); D-050 improved claim shape; D-052 needed for reliable `cove_verified=true` |
| P3-008 | FR-BRAIN-08 auto-triage — blocks on ≥50 human-reviewed candidates | deferred post-L2 |
| D-029 | SaMD rename `injury_advice_accurate` → `movement_advice_accurate` | LOW |
| D-030 | Orphan `rag_documents` cleanup cron | LOW |
| D-031 | Admin `GET /rag/documents` Literal constraint | LOW |
| D-036 | GPU offload for pose extraction | post-beta |
| M-06 | Phase 4 `overall` population → audit faithfulness fallback sites | Phase 4 |

## 3. Test counts

**Backend** (post-merge local):
- Baseline pre-session-49: 1698 passed, 25 skipped.
- Post-D-050: **1701 passed, 25 skipped, 0 failed** (+3 D-050 prompt-structure tests).
- `uv run ruff check .` — clean.
- `uv run pyright app/` — **0 errors, 0 warnings, 0 informations**.
- New/updated test file: `backend/tests/unit/test_cove.py` (+107 lines, 3 new tests, 1 assertion tightened in fix-up).
- **Known failures:** none.

**Frontend**: `npx tsc --noEmit` — 0 errors. vitest passed on PR head in 1m23s.

**CI on PR #90**:
- `9d6a447` (final head): all 6 gates pass on run `24602908124` (Backend Lint 35s, Backend Tests 2m14s, Frontend Lint 24s, Frontend Tests 1m23s, Secret Scanning 10s, Vercel pass).
- Merge commit `6c41953` Deploy to Production green in 37s on run `24612712882`.

## 4. Key learnings captured in this session

1. **Fixing the claim-shape surfaces the next failure mode.** Sessions 46–48 observed `faithfulness=0.0` (crash), then `faithfulness=0.92` + `cove_verified=false` (measurement claims → Uncertain). Session 49 (D-050) fixed the measurement-claim problem (all claims now principle-shaped) but immediately exposed a hallucination pattern: the extractor inverts the source's direction and invents principles not in the coaching. This is the typical arc — fix the visible layer, observe the next. The refined prompt's `"do not invent a principle that was not written"` rule turned out to be too soft for inversions; D-052 will tighten it. Worth remembering that each prompt-refinement round may need another round.

2. **Two-stage subagent review caught one genuine Important issue.** The spec-compliance reviewer passed 6/6 checks, but the code-quality reviewer found a test-assertion gap the implementer's self-review missed: `assert "extract" in lowered` passed whether or not the worked-example `Extract:` labels existed (because the prompt's opening "extracting" verb satisfied the substring). Tightened to `assert lowered.count("extract:") >= 2` via a one-line fix-up commit. This justifies the two-stage review loop on prompt-only PRs where unit-test-and-compile gates alone can miss subtle semantic test weakness.

3. **D-050 was a prompt-only diff — still shipped the full 5-gate workflow.** 3 files, +308/-7 lines, no `max_tokens` / model / signature changes. Subagent-driven-development scaled down gracefully for this small change: single implementer dispatch for Tasks 1-4 (branch + TDD + impl + smoke), spec reviewer → APPROVED, code-quality reviewer → APPROVED after fix-up, spelix-auditor + spelix-security-reviewer both PASS. Full workflow took ~40 minutes including CI + deploy + prod E2E.

4. **The `faithfulness` denominator-shift is expected when you filter claim shape.** Session 48 `faithfulness=0.92` covered 11+15 claims (many measurement-Uncertain). Session 49 `faithfulness=0.82` covers 9+8 principle-only claims. Fewer claims in the denominator amplifies the impact of any single low-faith claim — 0.92 → 0.82 is not a quality regression, it's a denominator artifact. The D-050 plan's "acceptable 0.5–0.85 band" correctly anticipated this.

5. **Prod oneoff SSH debugging pattern stayed dormant this session.** Worker log inspection via `ssh spelix-droplet "docker logs spelix-worker-1 --since 10m"` was sufficient to diagnose the stuck-processing symptom (turned out to be just slow CV stage, not actually stuck). The `docker exec spelix-backend-1 /app/.venv/bin/python` path (documented in session 47 handoff) was not needed.

## 5. Blockers

**Code-side:** none — PR #90 shipped, verified on prod, screenshot captured, handoff + ADR-COVE-02 + backlog + D-052/D-053 written. D-046 through D-053 + D-042/D-043/D-044 are bundle-ready for next session.

### Non-code blockers (carry-over, unchanged)

- **Kin expert onboarding call** still pending since session 30. **14 days to 2026-05-03 L2 deadline.** Each day of slip compounds against landing readiness.

### Worktree / branch state

- Feature branch `fix/d050-cove-claim-extraction-principles` merged on origin; can be deleted via `git push origin --delete fix/d050-cove-claim-extraction-principles` when cleanup is desired.
- Docs branch `docs/d050-closeout` for this handoff commit — will be merged shortly.
- Local `main` at `6c41953` (PR #90 merge commit) — will advance after this docs close-out PR merges.
- Pre-existing `M frontend/src/api/__tests__/beta.test.ts` modification carried from session 47 is still in the working tree (unrelated, noted since session 47).

## 6. E2E Findings — D-050 verification

- **Analysis UUID:** `c46023c9-b098-4083-9c19-dad174b14a04` (bench fixture, admin test account, fresh upload post-D-050).
- **Screenshot:** `e2e/screenshots/d050-post-fix-results-c46023c9.png`.
- **Pre-fix (`bfbed270`, post-D-048):** `faithfulness=0.92`, `cove_verified=false`, claims mostly measurement-Uncertain.
- **Post-fix (`c46023c9`, post-D-050):** `faithfulness=0.82` (above 0.8 gate), `cove_verified=false` (new reason — see below), claims 100% principle-shaped, iter 2 reached 7/8 Yes.
- **Claim-shape comparison (iter 2):**
  - Pre-fix examples (measurement-Uncertain): "Did the eccentric phase duration measure 5.16 seconds?" → Uncertain.
  - Post-fix examples (principle-Yes): "Is the recommended eccentric phase duration for bench press approximately 2 seconds?" → **Yes**, "Source 2 states 'Control the eccentric at a consistent tempo — aim for a 2-second descent.'"
- **Remaining Gate-A blocker (D-052):** iteration 2's single No was "an excessively slow eccentric makes bar path control harder" — extractor INVERTED source 2's fast-descent finding. Iter 1 additionally invented `minimum 60°`, `60–100° range`, `stretch-shortening cycle` principles not present in the coaching output. The translate-not-invent rule needs an inversion-guard.

## 7. Next session start

```bash
/status

# PRIORITY 1 — Non-code blockers
#   - Kin expert onboarding call (target: 10+ papers by 2026-05-03, 14 days left)
#   - Expert corpus push: first 10 papers via expert portal
#   - Landing page V1 prod verification

# PRIORITY 2 — D-### follow-up bundle (candidate)
#   - D-052 tighten D-050 prompt with inversion-guard — new highest-impact bug,
#     surfaced by D-050 working correctly on principle-shape
#   - D-053 fix distillation AsyncQdrantClient.search API drift (silent ADD fallback)
#   - D-046 hoist _HAIKU_MODEL to shared constant
#   - D-047 additive ValidationError regression test for BrainCoveService
#   - D-049 Citation serializer warning cleanup (still visible in session 49 worker logs)
#   - D-051 additive test for cove.py `else` branch Step 4 revision

# PRIORITY 3 — PR #84 D-### follow-ups (unchanged)
#   - D-042 wire rep-detection knobs through ThresholdConfig
#   - D-043 partial-descent <20° prominence test
#   - D-044 atharva-bench.mov signal-quality investigation

# PRIORITY 4 — P3-007 D-### bundle (unchanged)

# ENVIRONMENT NOTES:
#   - Local main = 6c41953 (PR #90 merge) — will advance after session 49 docs commit
#   - SPELIX_DISTILLATION_ENABLED=1 on prod since session 42
#   - SPELIX_PHASE3_AGENT_ENABLED=1 on prod since session 32
#   - Test admin account: atharva6905+admin-p3006@gmail.com /
#     SpelixAdmin-P3006-Test-2026! (UUID cb18c043-5a16-4990-a3d3-02ed4890bf56).
#     Now owns 7 analyses — the newest is session 49 c46023c9 (bench,
#     post-D-050 verification with faithfulness=0.82 + principle-only claims).
#   - Qdrant coach_brain: 26 points (24 seeds + 2 from earlier distillation runs).
#   - Droplet deploy dir is /home/deploy/spelix (NOT /srv/spelix).
```
