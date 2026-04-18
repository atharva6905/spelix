# Session 45 Handoff → Session 46: D-040 hybrid rep detection + D-041 degenerate scoring guard shipped to prod (PR #84)

**Context refresh:** Session 45 (2026-04-18, L2 Sprint Day 9) closed out session 44's Priority 1. The original ADR-REPDET-01 plan was pure `scipy.signal.find_peaks`; mid-session fixture calibration with user hand-counts disproved that approach (over-counted by 3–4× on noisy real-video signals) and we pivoted to a **hybrid** detector: state machine primary + peak/valley fallback. D-041 degenerate-scoring guard shipped alongside. Both shipped in PR #84 (`bc17250`), auto-deployed via CI, verified on prod with a fresh admin-account upload of the session-44 regression fixture — went from **0 reps → 1 rep**, form scores cleanly populated, no "Very Low + 10.0" contradiction.

## 1. Completed

### PR #84 (`bc17250`) — D-040 hybrid rep detection + D-041 degenerate scoring guard

Merged via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash). 7 commits preserved to show the learning path (pure peak/valley → empirical calibration → hybrid pivot). Plan at `docs/superpowers/plans/2026-04-17-d040-d041-rep-detection-and-degenerate-scoring.md`.

| Ref | What | Commit |
|---|---|---|
| L2-D040-01 | Initial pure peak/valley rewrite (superseded) | `f237ccf` |
| L2-D040-02 | Test-file update for peak/valley semantics (delete 8, update 3, add 4) | `109abfc` |
| L2-D040-03 | `_BENCH_*_L` clarifying comment | `b15f770` |
| L2-D041-01 | D-041 `_is_degenerate_scoring_input` guard + Step 9b short-circuit + 6 tests | `a7477f0` |
| L2-D040-05 | D-040 smoke script | `41100b8` |
| L2-D040-06 | **Hybrid pivot** — state machine primary + peak/valley fallback + `TestHybridStateMachineWins` | `dffa59e` |
| L2-D040-07 | Auditor-finding fixes (H-2 asymmetric hysteresis comment, M-3 smoke docstring, M-4 probe_duration_seconds patch, M-5 signal_processing.py landmark comment) | `e35b86d` |
| L2-D040-08 | PR #84 → CI 6/6 green → merge (merge, NOT squash) → Deploy to Production auto-run → droplet HEAD match + containers healthy → Playwright E2E verified on prod | `bc17250` (merge) |

### Fixture hand-count ground truth (established this session)

User provided hand counts for all 6 in-repo fixtures:

| fixture | duration | hand | pre-PR prod (state-machine) | pure peak/valley | hybrid |
|---|---|---|---|---|---|
| `atharva-bench-nw-10s-720p.mp4` | 10 s | 1 | 0 ❌ | 1 ✓ | **1 ✓** |
| `atharva-bench-nw-10s.mp4` | 10 s | 1 | 0 ❌ | 1 ✓ | **1 ✓** |
| `atharva-bench-no-weight.mov` | 22.5 s | 5 | 0 ❌ | 7 🟡 | **7** (over-by-2, was unusable) |
| `atharva-bench.mov` (loaded) | 23 s | 5 | 13 🟡 | 21 ⚠ | **13** (SM wins = current prod, no regression) |
| `atharva-squat.mov` | 20.2 s | 5 | 5 ✓ | 14 ⚠ | **5 ✓** |
| `atharva-deadlift.mov` | 25.8 s | 5 | 5 ✓ | 4 🟡 | **5 ✓** |

Hybrid = strict Pareto improvement over prod: 3 partial-lockout fixtures unlocked, 0 regressions.

### Post-merge docs commits on `main` (session 45)

| What | Commit |
|---|---|
| `docs(backlog,handoff)` — close D-040/D-041 with `bc17250` SHA + register D-042 (ThresholdConfig wiring), D-043 (<20° prominence test), D-044 (bench.mov signal-quality investigation) + session 45 handoff → 46 | **pending — commit this after session close** |

### Audit verdicts (pre-merge)

- **spelix-auditor** — PASS_WITH_FINDINGS. 0 CRITICAL, 2 HIGH (H-2 fixed in `e35b86d`, H-1 deferred → D-042), 5 MEDIUM (M-3/M-4/M-5 fixed in `e35b86d`, M-1 declined, M-2 deferred → D-043). All actionable findings addressed pre-merge.
- **spelix-security-reviewer** — PASS. 0 findings across 7 checks (SaMD language FR-SCOR-09, JWT/auth scope, RLS, secrets, error leakage, injection, FR-SCOR-10 confidence label).

### Prod E2E (2026-04-18 02:47 UTC)

Fresh admin-account upload of `atharva-bench-nw-10s-720p.mp4` on `spelix.app`. Analysis `f36f8367-ee53-4ae6-b91a-614fcb2d394e`. Screenshot: `e2e/screenshots/d040-d041-post-merge-prod-verified.png`.

| Check | Result |
|---|---|
| Rep count | **1 rep** (was 0 session 44) — D-040 fallback working |
| Confidence label | "Low" — NOT "Very Low" (real Tier 5 from 1 detected rep, not 0.0 fallback) |
| Form scores | Overall 7.8 / MovQ 8.0 / Tech 8.5 / P&B 5.2 / Ctrl 10.0 — all populated |
| No "Very Low + 10.0" contradiction | ✓ (D-041 guard path not needed because D-040 upstream fix removed 0-rep input) |
| Coaching feedback rendered | ✓ summary + 3 strengths + 3 issues + 5 correction items + 5 cues + 4 citations |
| Console errors (Playwright) | 0 |
| Network 4xx/5xx | 0 |

## 2. Remaining

### Session 46 Priority 1 — non-code blockers (carry-over from sessions 30+)

| ID | Title | Status |
|---|---|---|
| — | Kin expert onboarding call (still pending since session 30) — target 10+ papers by 2026-05-03 | open, blocks expert corpus push |
| — | Expert corpus push — first 10 papers via expert portal | blocked on expert call |
| — | Landing page V1 status verification on prod | unclear, needs re-check |

### Session 46 Priority 2 — M-04 / M-05 maintenance bundle (~1–2h)

| ID | Title | Why |
|---|---|---|
| M-04 | Re-embed Coach Brain seeds with FR-BRAIN-03 contextualized prefix | Fixes `papers_only_fallback` overuse observed live on session 44 P3-007 E2E |
| M-05 | Bump `BrainCoveService.max_tokens` to ≥2048 OR shorten verification prompt | Unblocks D-039 (re-run CoVe after admin content edit) |

### Session 46 Priority 3 — D-### follow-ups from PR #84

| ID | Title | Size | Source |
|---|---|---|---|
| D-042 | Wire `_PROMINENCE_DEG` + `_STANDING_THRESHOLD` + `_DEPTH_THRESHOLD` + `_MIN_REP_DURATION_S` through `ThresholdConfig` (FR-SCOR-11) | S | auditor H-1 |
| D-043 | Additive test: partial descent with <20° prominence in `test_rep_detection.py` | S | auditor M-2 |
| D-044 | Investigate `atharva-bench.mov` 13-rep over-count (pre-existing; likely MediaPipe flicker or Savgol over-smoothing) | M | session 45 calibration |

### Session 46 Priority 4 — P3-007 D-### follow-ups (from session 44)

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
| D-039 | Re-run CoVe after admin content edit on approve | blocks on M-05 |
| P3-008 | FR-BRAIN-08 auto-triage — blocks on ≥50 human-reviewed candidates | deferred post-L2 |
| D-029 | SaMD rename `injury_advice_accurate` → `movement_advice_accurate` | LOW |
| D-030 | Orphan `rag_documents` cleanup cron | LOW |
| D-031 | Admin `GET /rag/documents` Literal constraint | LOW |
| D-036 | GPU offload for pose extraction | post-beta |
| M-06 | Phase 4 `overall` population → audit faithfulness fallback sites | Phase 4 |

## 3. Test counts

**Backend** (final local run, post-audit-fix pre-merge):
- `uv run pytest -x -q --ignore=tests/e2e` → **1693 passed, 25 skipped, 0 failed** (baseline 1690; +1 D-040 hybrid distinguishing test + 6 D-041 − churn = +3 net).
- `uv run ruff check .` — clean.
- `uv run pyright app/` — **0 errors, 0 warnings, 0 informations**.
- New/updated test files: `test_rep_detection.py` (40→41 tests; +5 new, −8 deleted, 3 updated); `test_pipeline.py` (+6 new D-041 tests).
- **Known failures:** none.

**Frontend** (local run, pre-merge):
- `npx vitest run` — 332/333 passed (1 `AdminPage.test.tsx` timeout flake under heavy-suite load; passes 24/24 in isolation). Unrelated to this PR.
- `npx tsc --noEmit` — 0 errors.

**CI on PR #84** (merge-commit run `24594795597`): all 6 gate checks green on main — Backend Lint 34s, Backend Tests 2m3s, Frontend Lint 27s, Frontend Tests 1m29s (AdminPage flake did NOT recur on CI), Secret Scanning 15s, Vercel green. **Deploy to Production: success.**

**Coverage:** not re-measured this session. Phase 2 gate baseline 90.31%. This PR touches only `rep_detection.py`, `signal_processing.py` (comment), `pipeline.py` — all well-covered by the 1693-test suite.

## 4. Key learnings captured in this session

1. **Pure `find_peaks` is insufficient for real-video rep detection.** State-machine's absolute thresholds absorb MediaPipe landmark flicker and Savgol over-smoothing artefacts that create phantom mid-range valleys. Peak/valley alone over-counts 3–4× on loaded-bench / squat videos at any tested prominence 20°–80°, and at any clamping / percentile-sanity filter combination tested.
2. **Hybrid (state-machine first, peak/valley fallback) is the right shape.** Preserves known-good prod behaviour on lockout lifts while catching partial-lockout cases the state machine can't see. Test: `TestHybridStateMachineWins::test_hybrid_prefers_state_machine_over_peak_valley` distinguishes hybrid from pure peak/valley using a synthetic signal where both paths produce different answers.
3. **D-041 mostly fires as backup, not primary.** Once D-040 correctly detects 1 rep on partial-lockout clips, session confidence lands in "Low" (not "Very Low") so D-041's `< 0.50` guard never triggers. D-041 remains important for the truly-poseless / Very-Low-quality case and the `rep_metrics=[]` short-circuit.
4. **Signal-quality issue on `atharva-bench.mov` pre-exists and is unchanged.** 13-rep over-count is on main since before this PR. D-044 captures the investigation follow-up — suspected MediaPipe landmark flicker or Savgol `window=7, polyorder=3` over-smoothing.

## 5. Blockers

**Code-side:** none — D-040 + D-041 shipped and verified on prod. D-042/D-043/D-044 captured as follow-ups.

### Non-code blockers (carry-over from earlier sessions, unchanged)

- **Kin expert onboarding call** still pending since session 30. 15 days to 2026-05-03 L2 deadline. Each day of slip compounds against landing readiness.
- **`papers_only_fallback` over-use on prod retrieval** (M-04 — FR-BRAIN-03 contextualized-prefix mismatch). Coach Brain content effectively dark in prod until M-04 ships.

### Worktree / branch state

- Feature branch `fix/d040-d041-rep-detection-and-degenerate-scoring` merged on origin; can be deleted via `git push origin --delete fix/d040-d041-rep-detection-and-degenerate-scoring` when cleanup is desired.
- Local `main` at `bc17250` (PR #84 merge commit). Origin `main` matches.

## 6. Next session start

```bash
/status

# PRIORITY 1 — Non-code blockers
#   - Kin expert onboarding call (target: 10+ papers by 2026-05-03)
#   - Expert corpus push: first 10 papers via expert portal
#   - Landing page V1 prod verification

# PRIORITY 2 — M-04 / M-05 maintenance bundle (~1-2h)
#   - M-04 re-embed Coach Brain seeds with FR-BRAIN-03 contextualized prefix
#   - M-05 bump BrainCoveService.max_tokens to 2048 OR shorten verification prompt

# PRIORITY 3 — PR #84 D-### follow-ups (smallest first, bundle-candidate)
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
#   - Local main = bc17250 (PR #84 merge). Origin main same.
#   - SPELIX_DISTILLATION_ENABLED=1 on prod since session 42
#   - SPELIX_PHASE3_AGENT_ENABLED=1 on prod since session 32
#   - Test admin account: atharva6905+admin-p3006@gmail.com /
#     SpelixAdmin-P3006-Test-2026! (UUID cb18c043-5a16-4990-a3d3-02ed4890bf56).
#     Now owns 2 analyses — cea2312b (session 44, 0 reps pre-fix) and
#     f36f8367 (session 45, 1 rep post-fix). Re-use for future verification.
#   - @xyflow/react@12.10.2 in frontend deps (session 44).
#   - scipy>=1.17.1 in backend deps (new rep-detection dependency).
#   - Hand-counted fixture ground truth:
#       atharva-bench-nw-10s-720p.mp4 = 1 rep (session 45, truncated)
#       atharva-bench-nw-10s.mp4      = 1 rep (same source)
#       atharva-bench-no-weight.mov   = 5 reps (full length)
#       atharva-bench.mov             = 5 reps (loaded; algorithm gives 13)
#       atharva-squat.mov             = 5 reps (algorithm gives 5)
#       atharva-deadlift.mov          = 5 reps (algorithm gives 5)
```
