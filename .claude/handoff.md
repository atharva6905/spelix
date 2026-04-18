# Session 48 Handoff → Session 49: D-048 coaching-path CoVe max_tokens bump shipped to prod (PR #88)

**Context refresh:** Session 48 (2026-04-18, L2 Sprint Day 10, same calendar day as sessions 46 + 47) closed D-048 — the analog of session 46's M-05 brain-path max_tokens fix, applied to the coaching-path `CoveVerificationService`. TDD-gated 3-commit PR, auditor + security-reviewer clean, E2E on prod with the same bench fixture sessions 46 + 47 used. `eval_scores.faithfulness` flipped 0.0 → 0.92, `cove_iterations` went from empty/broken (silent instructor crash) to 2 iterations × 26 total answers with real source-cited reasoning. `cove_verified=false` persists but for a legitimate new reason — filed as D-050.

## 1. Completed

### PR #88 (`4ef4091`) — D-048 bump CoveVerificationService max_tokens across all 4 CoVe steps

Merged via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash). 3 commits preserved.

| Ref | What | Commit |
|---|---|---|
| L2-D048-01 | TDD failing tests: `test_cove_max_tokens_meets_headroom_happy_path` + `test_cove_max_tokens_meets_headroom_revision_path` in `backend/tests/unit/test_cove.py`. Call-kwargs introspection on mocked `instructor.chat.completions.create` asserting floors of `>= 1024` (claim + question), `>= 4096` (verification answers), `>= 3072` (Sonnet revision). | `8113499` |
| L2-D048-02 | Impl: 6× `max_tokens=` bumps in `backend/app/services/cove.py` with inline `# D-048:` comments. Line 262 + 286 `ClaimList` 512→1024, line 315 `VerificationQuestions` 512→1024, line 328 `VerificationAnswers` 1024→**4096** (blow-out path), line 371 + 389 Sonnet `CoachingOutput` 2048→3072. | `4146ac7` |
| L2-D048-03 | Code-review fix-up: restore cost-impact rationale in Steps 1/2 comments ("cf. Step 3 at 4096") so asymmetric 2×/4× budget bumps are self-explanatory in-source; add defensive `calls[2]` Step 3 assertion in revision-path test so Step 3 budget contract is guarded independently in each test. | `d056848` |
| L2-D048-PR | PR #88 → CI 6/6 green on `d056848` (Backend Lint 39s, Backend Tests 1m54s, Frontend Lint 25s, Frontend Tests 1m18s, Secret Scanning 11s, Vercel pass) → spelix-auditor PASS_WITH_FINDINGS (0 CRITICAL, 0 HIGH, 3 MEDIUM all non-blocking — M-01 style, M-02 → D-051, M-03 post-merge docs) → spelix-security-reviewer PASS clean on all 8 checks → merge → Deploy to Production 37s on `4ef4091` → droplet HEAD `/home/deploy/spelix` at `4ef4091` + containers healthy (backend + redis healthy, worker up) → Playwright E2E on prod bench fixture flipped faithfulness 0.0 → 0.92. | `4ef4091` (merge) |

### Prod E2E (2026-04-18 07:38–07:44 UTC) — D-048 fix verified

Fresh upload of `atharva-bench-nw-10s-720p.mp4` (same fixture sessions 46 + 47 used) on `spelix.app` under admin test account. Analysis `bfbed270-1117-4a8a-8246-6d2dc9391781`. Screenshot: `e2e/screenshots/d048-post-fix-cove-verified-bfbed270.png`.

| Metric | Session 46 (`6aa7b42b`, pre-M04/M05) | Session 47 (`de316a7a`, post-D-045) | Session 48 (`bfbed270`, post-D-048) |
|---|---|---|---|
| analysis status | completed | completed | completed |
| `retrieval_source` | `papers_only_fallback` ❌ | `coach_brain_primary` ✅ | `coach_brain_primary` ✅ |
| `degraded_mode` | false | false | false |
| `eval_scores.faithfulness` | **`0.0`** ❌ | **`0.0`** ❌ | **`0.92`** ✅ |
| `eval_scores.cove_verified` | `false` (silent crash) | `false` (silent crash) | `false` (legit — see note below) |
| `eval_scores.overall` | null | null | null (Phase 4 — tracked as M-06) |
| `cove_iterations` count | 0 / empty (instructor retry crash) | 0 / empty | **2** (11 + 15 real answers with source citations) |
| `converged` | false | false | false |
| console errors | 0 | 0 | 0 |
| 4xx/5xx | 0 | 0 | 0 |

**Why `cove_verified=false` persists even though D-048 works**: With CoVe now actually running (not crashing), the verifier honestly reports `Uncertain` on claims like "elbow angle 38° at the bottom", "eccentric 5.16s", "ascent 1.28s" — because research sources describe optimal RANGES (45–75° elbow, 2s eccentric), not THIS lifter's measured values. Principle-level claims ("45–75° is optimal", "J-curve bar path is correct", "2s is target tempo") all answer Yes with explicit source citations. So convergence requires either (a) all-principle claims (i.e. the claim extractor skips numerical measurements) or (b) a scoring change that treats Uncertain-on-measurements differently from Uncertain-on-principles. Tracked as **D-050** follow-up.

### Audit verdicts (pre-merge)

- **spelix-auditor** (PR #88) — PASS_WITH_FINDINGS. 0 CRITICAL, 0 HIGH. 3 MEDIUM: M-01 patch-style inconsistency in pre-existing `test_cove.py` (use `patch("app.services.cove.instructor.from_anthropic", return_value=...)` vs. `patch("app.services.cove.instructor")`) — future standardization, not this PR's concern. M-02 `_run_cove_loop` `else` branch revision (`iteration == max_iterations`) is structurally identical to the `if` branch and untested by `max_tokens` floor → filed as new backlog row **D-051**. M-03 `backlog.md` D-048 row not flipped to `done` in the same commit as the code → acceptable per session-46 M-04/M-05 precedent that deferred backlog + ADR updates to a post-merge docs commit, but auditor correctly flagged the CLAUDE.md protocol drift. Closed in this handoff commit.
- **spelix-security-reviewer** (PR #88) — PASS clean. 0 CRITICAL, 0 HIGH. All 8 checks passed: no new user-facing strings (no SaMD/FTC drift); `logger.exception` on line 241 and `logger.info` on line 275 unchanged; top-level `try/except` invariant preserved (returns `CoveResult(cove_verified=False, ..., trace=[{"error": str(exc)}])`); no secret exposure; no JWT/RLS/auth touch; no new prompt-injection surface (changes are numeric literals only); new tests patch `instructor.from_anthropic` → no real Anthropic calls, no `ANTHROPIC_API_KEY` reads; ADR-DISTILL-05 style preserved (`str(exc)` is coaching-path convention; `type(exc).__name__` applies only to brain path per `cove_brain.py`).

## 2. Remaining

### Session 49 Priority 1 — non-code blockers (unchanged)

| ID | Title | Status |
|---|---|---|
| — | Kin expert onboarding call (still pending since session 30) — target 10+ papers by 2026-05-03 | open, blocks expert corpus push, 15 days to L2 deadline |
| — | Expert corpus push — first 10 papers via expert portal | blocked on expert call |
| — | Landing page V1 status verification on prod | unclear, needs re-check |

### Session 49 Priority 2 — D-### follow-up bundle (candidate)

| ID | Title | Size | Source |
|---|---|---|---|
| D-050 | Refine `CoveVerificationService` claim-extraction prompt to focus on PRINCIPLE-level claims rather than lifter-specific MEASUREMENT claims. Currently `cove_verified=true` is effectively unreachable whenever coaching cites measured values (see E2E table above). | S | session 48 prod E2E on `bfbed270` |
| D-046 | Extract `_HAIKU_MODEL` into shared `app/constants.py` — duplicated in `cove_brain.py`, `extract.py`, and `cove.py`. Drift risk. | S | auditor M-03 on PR #85 |
| D-047 | Additive test in `test_distillation_cove_brain.py` for pre-fix M-05 failure mode via stubbed `ValidationError` side_effect. | S | code-reviewer on PR #85 |
| D-049 | `Citation` Pydantic serializer warning spam in worker logs on every coaching call with citations. Visible every prod run (session 48 worker log confirmed). Non-functional. | S | sessions 46 + 48 worker logs |
| D-051 | Additive regression test for `_run_cove_loop` `else` branch (`iteration == max_iterations`) in `test_cove.py` via `max_iterations=1` + "No" answer. The `if` branch is covered; the structurally-identical `else` branch at `cove.py:389` is not. | S | auditor M-02 on PR #88 |

### Session 49 Priority 3 — PR #84 D-### follow-ups (carry-over unchanged)

| ID | Title | Size | Source |
|---|---|---|---|
| D-042 | Wire `_PROMINENCE_DEG` + `_STANDING_THRESHOLD` + `_DEPTH_THRESHOLD` + `_MIN_REP_DURATION_S` through `ThresholdConfig` (FR-SCOR-11) | S | auditor H-1 |
| D-043 | Additive test: partial descent with <20° prominence in `test_rep_detection.py` | S | auditor M-2 |
| D-044 | Investigate `atharva-bench.mov` 13-rep over-count (MediaPipe flicker / Savgol over-smoothing) | M | session 45 |

### Session 49 Priority 4 — P3-007 D-### bundle (carry-over unchanged)

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
| D-039 | Re-run CoVe after admin content edit on approve | D-048 partially addresses (CoVe now runs); D-050 needed for reliable `cove_verified=true` |
| P3-008 | FR-BRAIN-08 auto-triage — blocks on ≥50 human-reviewed candidates | deferred post-L2 |
| D-029 | SaMD rename `injury_advice_accurate` → `movement_advice_accurate` | LOW |
| D-030 | Orphan `rag_documents` cleanup cron | LOW |
| D-031 | Admin `GET /rag/documents` Literal constraint | LOW |
| D-036 | GPU offload for pose extraction | post-beta |
| M-06 | Phase 4 `overall` population → audit faithfulness fallback sites | Phase 4 |

## 3. Test counts

**Backend** (final local run pre-push):
- `uv run pytest -x -q --ignore=tests/e2e` → **1698 passed, 25 skipped, 0 failed** (1696 baseline + 2 new D-048 tests).
- `uv run ruff check .` — clean.
- `uv run pyright app/` — **0 errors, 0 warnings, 0 informations**.
- New/updated test file: `backend/tests/unit/test_cove.py` (+2 tests + 1 defensive `calls[2]` assertion in revision-path test).
- **Known failures:** none.

**Frontend**: `npx tsc --noEmit` — 0 errors. vitest not re-run beyond CI (passed in 1m18s on PR head).

**CI on PR #88**:
- `d056848` (final head): all 6 gates pass on run `24599757535` (Backend Lint 39s, Backend Tests 1m54s, Frontend Lint 25s, Frontend Tests 1m18s, Secret Scanning 11s, Vercel pass).
- Merge commit `4ef4091` Deploy to Production green in 37s on run `24599902469`.

## 4. Key learnings captured in this session

1. **Budget contract tests are the right shape for numeric LLM config.** The two new tests use `>= 1024` / `>= 4096` / `>= 3072` floor assertions with call-kwargs introspection — locking in the minimum budget as a contract without over-specifying. A future regression that drops `max_tokens` back to 1024 on Step 3 would fail the test immediately; a future increase (say to 8192) would not. This is the correct asymmetry: prevent regression, allow headroom.

2. **Fixing the crash surfaces the next bug.** Sessions 46 + 47 observed `faithfulness=0.0` and `cove_verified=false`. With D-048 lifting the max_tokens ceiling, the CoVe loop actually runs — and immediately exposes a claim-extraction design issue: the extractor pulls lifter-specific numerical measurements ("38° elbow angle", "5.16s descent") as "falsifiable claims" that research sources inherently cannot confirm. `cove_verified=true` requires all-Yes convergence; as long as claim-extraction includes measured values, convergence is structurally unreachable. Filed as D-050. This is the typical arc: fix the visible layer, observe the next layer. Worth remembering for similar "prod metric stuck at 0" debugging — don't declare victory on the flip; read the downstream metric to confirm the new value is load-bearing.

3. **The ADR-COVE-01 family is new.** Session 46's ADR-DISTILL-06 was scoped to the distillation-path `BrainCoveService` per ADR-DISTILL-03's scope separation. The coaching-path `CoveVerificationService` needed its own ADR family (ADR-COVE-01) rather than extending ADR-DISTILL-06. Future ADRs for the coaching-path CoVe loop (claim-extraction refinement, threshold calibration, etc.) should continue in this family.

4. **Prod oneoff pattern still works.** The `ssh spelix-droplet "docker exec spelix-backend-1 ..."` workflow from sessions 46 + 47 continues to be the right way to poke at prod state, but this session didn't need it — E2E + Supabase SQL MCP was sufficient. The `/app/.venv/bin/python` gotcha documented in session 47 handoff section 4 remains valid for future investigations.

5. **Agent-driven workflow per `superpowers:subagent-driven-development`**: 9-task plan executed with 3 dispatched subagents (spelix-tdd implementer, spec reviewer, code quality reviewer — plus audits via spelix-auditor + spelix-security-reviewer). Implementer completed the TDD gate + bump in ~9 min; code-review fix-up round took ~3 min. Two-stage review (spec then quality) caught one Important issue (truncated Step 1/2 comments) that neither the implementer's self-review nor the auditor flagged — justifies the extra review loop.

## 5. Blockers

**Code-side:** none — PR #88 shipped, verified on prod, screenshot captured, handoff + ADR + backlog + D-050/D-051 written. D-046 through D-051 + D-042/D-043/D-044 are bundle-ready for next session.

### Non-code blockers (carry-over, unchanged)

- **Kin expert onboarding call** still pending since session 30. 15 days to 2026-05-03 L2 deadline. Each day of slip compounds against landing readiness.

### Worktree / branch state

- Feature branch `fix/d048-coaching-cove-max-tokens` merged on origin; can be deleted via `git push origin --delete fix/d048-coaching-cove-max-tokens` when cleanup is desired.
- Local `main` at `4ef4091` (PR #88 merge commit) — will advance after the session 48 docs commit.
- Pre-existing `M frontend/src/api/__tests__/beta.test.ts` modification carried from session 47 is still in the working tree (unrelated to D-048, noted in session 47 handoff).

## 6. E2E Findings — D-048 verification

- **Analysis UUID:** `bfbed270-1117-4a8a-8246-6d2dc9391781` (bench fixture, admin test account, fresh upload).
- **Screenshot:** `e2e/screenshots/d048-post-fix-cove-verified-bfbed270.png`.
- **Pre-fix `faithfulness`:** `0.0` on both session-46 `6aa7b42b` AND session-47 `de316a7a` (the D-045 retrieval fix alone was NOT sufficient).
- **Post-fix `faithfulness`:** **`0.92`** — 92% of claims faithfully grounded in retrieved sources. Matches the magnitude we'd expect from a correctly-running CoVe loop against the Coach Brain + papers retrieval.
- **Pre-fix `cove_iterations`:** 0 or empty (service crashed on instructor `ValidationError`, error swallowed by top-level `try/except`).
- **Post-fix `cove_iterations`:** 2 iterations, **11 + 15 = 26 real verification answers** with source-cited reasoning. Examples:
  - iter1 Q: "Do optimal elbow positioning guidelines recommend angles ranging from 45–75° from the torso?" A: **Yes** — "Source 1 explicitly states 'Optimal elbow angle is 45–75° from the torso depending on grip width,' and Source 4 confirms this same range."
  - iter1 Q: "Did the eccentric phase duration measure 5.16 seconds?" A: **Uncertain** — "The retrieved evidence contains no specific performance data, metrics, or numerical measurements of descent duration for any lifter."
  - iter2 Q: "Does research evidence support that a bar path with a slight diagonal J-curve optimizes the lever arm through the entire bench press?" A: **Yes** — "Source 5 explicitly describes the correct bar path as 'a slight diagonal arc — lowering to the lower sternum/nipple line and pressing back toward the face to lockout over the shoulder joint'."
- **`cove_verified` still false:** NOT a D-048 regression. The Uncertain-on-measurement pattern is the new blocker for `cove_verified=true`. Tracked as D-050.

## 7. Next session start

```bash
/status

# PRIORITY 1 — Non-code blockers
#   - Kin expert onboarding call (target: 10+ papers by 2026-05-03, 15 days left)
#   - Expert corpus push: first 10 papers via expert portal
#   - Landing page V1 prod verification

# PRIORITY 2 — D-### follow-up bundle (candidate)
#   - D-050 claim-extraction prompt refinement (principle vs measurement) — new highest-impact
#     bug, surfaced by the D-048 fix working correctly
#   - D-046 hoist _HAIKU_MODEL to shared constant
#   - D-047 additive ValidationError regression test for BrainCoveService
#   - D-049 Citation serializer warning cleanup (visible in session 48 worker logs)
#   - D-051 additive test for cove.py `else` branch Step 4 revision

# PRIORITY 3 — PR #84 D-### follow-ups (unchanged)
#   - D-042 wire rep-detection knobs through ThresholdConfig
#   - D-043 partial-descent <20° prominence test
#   - D-044 atharva-bench.mov signal-quality investigation

# PRIORITY 4 — P3-007 D-### bundle (unchanged)

# ENVIRONMENT NOTES:
#   - Local main = 4ef4091 (PR #88 merge) — will advance after session 48 docs commit
#   - SPELIX_DISTILLATION_ENABLED=1 on prod since session 42
#   - SPELIX_PHASE3_AGENT_ENABLED=1 on prod since session 32
#   - Test admin account: atharva6905+admin-p3006@gmail.com /
#     SpelixAdmin-P3006-Test-2026! (UUID cb18c043-5a16-4990-a3d3-02ed4890bf56).
#     Now owns 6 analyses — the newest is session 48 bfbed270 (bench,
#     post-D-048 verification with faithfulness=0.92).
#   - Qdrant coach_brain: 26 points (24 seeds + 2 from earlier distillation runs).
#   - Droplet deploy dir is /home/deploy/spelix (NOT /srv/spelix — session 48 
#     debug note, update root CLAUDE.md if you rely on the old path).
```
