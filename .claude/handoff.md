# Session 51 Handoff → Session 52: D-044 investigation closed out as deferred-post-L2 (PR #98)

**Context refresh (session 51, 2026-04-19, L2 Sprint Day 13):** D-044 investigated and deferred. 4-commit PR (3 investigation scripts + ADR-REPDET-03 + backlog-deferral). No production code changed. Merged at `fbb7611`; deploy-to-production green. Revised root-cause interpretation captured in ADR-REPDET-03: the 13 detected motions on `atharva-bench.mov` correspond to 5 working reps + ~8 setup/re-grip/rack motions; detector is faithful, not broken. Re-scoped as new backlog row D-056 (post-L2: distinguish working-reps from non-working bar motions via velocity/dwell/ROM-consistency features). Parameter-tuning path and Tier-1 visibility-gating path both empirically rejected with data.

## 1. Completed

### PR #98 (`fbb7611`) — D-044 investigation closeout

Merged via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash). 4 commits preserved.

| Ref | What | Commit |
|---|---|---|
| L2-D044-INV-01 | `backend/scripts/oneoff/diagnose_rep_detection_d044.py` — per-fixture pose extract + raw/smoothed angle stats + SM-vs-PV split + matplotlib plot to `/tmp/d044-<stem>.png`. Operator-run. (Subagent: spelix-cv-engineer.) | `95be9ba` |
| L2-D044-INV-02 | `backend/scripts/oneoff/sweep_rep_detection_d044.py` — 640-combo grid over `(savgol_window ∈ {7,11,15,21}, polyorder ∈ {2,3}, prominence ∈ {20,25,30,35,40}, min_rep_s ∈ {0.5,0.75,1.0,1.5})`. Writes `/tmp/d044-sweep.csv`. Operator-run. | `f402e97` |
| L2-D044-INV-03 | `backend/scripts/oneoff/prototype_visibility_gate.py` — Tier-1 `sigmoid(visibility) * sigmoid(presence)` masking + linear-interp prototype at thresholds {0.25, 0.30, 0.35, 0.40}. Caches MediaPipe extraction per fixture. Operator-run. | `5b92e3e` |
| L2-D044-INV-04 | ADR-REPDET-03 appended to `decisions.md` (findings, 7 rejected alternatives, consequences). `backlog.md` D-044 row flipped `open → deferred-post-L2`; new D-056 successor row added (post-L2 design work: velocity/dwell/ROM-consistency rep classifier). | `c3007bc` |
| L2-D044-PR | PR #98 → CI 6/6 green (Backend Lint 36s, Backend Tests 1m51s, Frontend Lint 28s, Frontend Tests 1m26s, Secret Scanning 13s, Vercel pass) → merge → Deploy to Production green on `fbb7611` → worktree `../spelix-d044` removed → remote branch `fix/d044-bench-over-count` deleted. No prod E2E run (docs-only, no behavioural change). | `fbb7611` (merge) |

### Investigation data points captured in ADR-REPDET-03

- atharva-bench.mov baseline: SM=13, PV=21, hybrid=13. GT=5. 4 of 13 rep detections have invalid negative `min_angle` (Savgol polynomial overshoot below [0°, 180°]).
- atharva-bench-nw-10s-720p.mp4: SM=0, PV=1, hybrid=1. GT=1. Clean signal (raw elbow [37.7, 153.0]).
- atharva-squat.mov: SM-path 5, hybrid=5. GT=5. (Earlier "squat=12" was my diagnostic-script bug — hardcoded elbow angle instead of hip.)
- atharva-deadlift.mov: SM=0 (elbow stays above 160° standing threshold — expected for deadlift where arms don't flex), PV=4 via elbow-angle-computed-on-deadlift (wrong angle but shows stable signal). Sweep script used correct hip angle → hybrid=5 ✓.
- Sweep result: 0/640 combos land 5/1/5/5 exactly. 0/640 get bench ≤ 7 with squat=5 AND deadlift=5 exactly.
- Visibility prototype: Tier-1 confidence on bench.mov ranges 0.25–0.49 (mean 0.37). Low-angle frames mean 0.258 vs mid-range 0.373 — weak correlation. Thresholds 0.30/0.35 leave bench at 13; 0.40 drops bench to 8 but regresses squat to 4.

### Plan file on main

`docs/superpowers/plans/2026-04-18-d044-atharva-bench-over-count.md` — the investigation plan written earlier today. UNCOMMITTED on main (plan was superseded by ADR-REPDET-03 as the canonical record). Untracked; safe to delete or leave — harmless either way. Not committed to keep the PR history clean.

## 2. Remaining

### Session 52 Priority 1 — non-code blockers (unchanged, critical path for L2)

| ID | Title | Status |
|---|---|---|
| — | Kin expert onboarding call (pending since session 30) — target 10+ papers by 2026-05-03 | open, blocks expert corpus push, **13 days to L2 deadline** |
| — | Expert corpus push — first 10 papers via expert portal | blocked on expert call |
| — | Landing page V1 status verification on prod | unclear, needs re-check |

### Session 52 Priority 2 — D-### maintenance bundle (all S, zero-risk, ~2h single PR)

Replaces old Session 50/51 P2 scope (D-052 ✅ + D-053 ✅ already shipped). Six items below could land as one bundled PR.

| ID | Title | Size | Deps | Source |
|---|---|---|---|---|
| D-046 | Hoist `_HAIKU_MODEL = "claude-haiku-4-5-20251001"` into shared constant (currently duplicated in `app/distillation/cove_brain.py` + `extract.py`; `app/services/cove.py` has its own) | S | — | auditor M-03 on PR #85 |
| D-047 | Additive coverage test in `test_distillation_cove_brain.py` for pre-fix M-05 failure mode via stubbed `ValidationError` → `BrainCoveResult.explanation == "evaluation_failed: ValidationError"` | S | — | code-reviewer on PR #85 |
| D-049 | `Citation` Pydantic serializer warning spam in worker logs on every coaching call with citations. Non-functional. | S | — | sessions 46 + 48 + 49 + 50 worker logs |
| D-051 | Additive regression test for `_run_cove_loop` else-branch (`iteration == max_iterations`) via `max_iterations=1` + "No" answer. Structural coverage of `cove.py:389`. | S | — | auditor M-02 on PR #88 |
| D-054 | Narrow the `except Exception` catch in `lifecycle_decision` to emit `logger.error` for Qdrant 4xx auth failures (sustained 401/403 currently invisible at WARNING-only severity). Keep broad fallback intact. | S | — | security-reviewer on PR #94 |
| D-055 | Add `testpaths = ["tests"]` under `[tool.pytest.ini_options]` in `backend/pyproject.toml` so `scripts/oneoff/` smoke/diagnostic scripts can't be accidentally collected. | S | — | auditor M-01 on PR #92 |

### Session 52 Priority 3 — PR #84 D-### follow-ups (D-044 closed via deferral this session)

| ID | Title | Size | Deps | Status |
|---|---|---|---|---|
| D-042 | Wire `_PROMINENCE_DEG` + `_STANDING_THRESHOLD` + `_DEPTH_THRESHOLD` + `_MIN_REP_DURATION_S` through `ThresholdConfig` (FR-SCOR-11) | S | — | open |
| D-043 | Additive test: partial descent with <20° prominence in `test_rep_detection.py` must return 0 reps | S | — | open |
| D-044 | `atharva-bench.mov` 13-rep over-count investigation | M | — | **deferred-post-L2** (session 51, ADR-REPDET-03) |
| D-056 | **Post-L2 successor to D-044** — distinguish working reps from non-working bar motions (velocity/dwell-time/ROM-consistency features, possibly ML classifier) | L | — | open-post-L2 |

### Session 52 Priority 4 — P3-007 D-### bundle (carry-over unchanged)

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
| D-039 | Re-run CoVe after admin content edit on approve | partially addressed by D-048/D-050/D-052 |
| P3-008 | FR-BRAIN-08 auto-triage — blocks on ≥50 human-reviewed candidates | deferred post-L2 |
| D-029 | SaMD rename `injury_advice_accurate` → `movement_advice_accurate` | LOW |
| D-030 | Orphan `rag_documents` cleanup cron | LOW |
| D-031 | Admin `GET /rag/documents` Literal constraint | LOW |
| D-036 | GPU offload for pose extraction | post-beta |
| M-06 | Phase 4 `overall` population → audit faithfulness fallback sites | Phase 4 |

## 3. Test counts

**Backend** (post-merge local; no production code changed this session):
- **1704 passed, 27 skipped, 0 failed** (unchanged from post-D-053 baseline session 50).
- `uv run ruff check .` — clean.
- `uv run pyright app/` — 0 errors, 0 warnings, 0 informations.
- **No new tests.** Investigation scripts are operator-run; no CI collection.
- **Known failures:** none.

**Frontend:**
- `npx tsc --noEmit` — 0 errors (unchanged).
- vitest — passed on PR head in 1m26s (unchanged).
- **Known failures:** none.

**CI on PR #98:**
- `c3007bc` (PR head): 6/6 gates pass.
- Merge commit `fbb7611` Deploy to Production green.

## 4. E2E verification

**SKIPPED — docs-only session.** No user-facing feature merged; no prod behavioural change. `rep_detection.py`, `signal_processing.py`, API endpoints, frontend components all untouched.

## 5. Blockers

**Code-side:** none — PR #98 shipped, deployed, verified via CI.

### Non-code blockers (carry-over, unchanged)

- **Kin expert onboarding call** still pending since session 30. **13 days to 2026-05-03 L2 deadline.** Each day of slip compounds against landing readiness.

### Worktree / branch state

- `fix/d044-bench-over-count` branch: merged (`fbb7611`), remote branch deleted, worktree `../spelix-d044` removed.
- Untracked `docs/superpowers/plans/2026-04-18-d044-atharva-bench-over-count.md` on main — superseded by ADR-REPDET-03; can be deleted or left. Harmless either way.
- Pre-existing `M frontend/src/api/__tests__/beta.test.ts` modification carried from session 47 is still in the working tree (unrelated, noted since session 47).

## 6. Key learnings captured in this session

1. **The systematic-debugging "Iron Law" saved time.** Plan wrote 4 hypotheses (A prominence, B distance, C fallback trigger, D savgol) BEFORE running any code. First diagnostic on atharva-bench.mov immediately invalidated A/B/C (peak/valley fallback didn't fire — SM produced 13). Then the sweep invalidated D at scale (0/640 combos hit target). Then the visibility-gate prototype invalidated a new Hypothesis F. Total investigation time: ~3 hours of MediaPipe wall time. Total wasted code changes: 0. Compare to "guess-and-check" mode where each hypothesis failure would have required its own PR/revert cycle.

2. **Plan-written-before-evidence-gathered has limits.** The 4 hypotheses in the plan were plausible but all wrong — the real root cause was not in the plan at all. Lesson: when writing investigation plans, the hypothesis section is scaffolding, not prediction. The plan's value is structuring the evidence-gathering pipeline; the actual hypothesis picks only after diagnostics run.

3. **Parameter sweeps are cheap compared to serial hypothesis testing.** 640 combos in one script run vs. 4-10 separate PR cycles. Even at 30 min MediaPipe-extraction-per-fixture cost, the sweep paid off by exhaustively proving NO parameter combo works. Without it, we would likely have shipped `w=11` (13→12) as a "partial fix" and called D-044 done.

4. **Deferred is a valid outcome.** The right framing is not "we failed to fix D-044" but "we re-scoped the problem from 1-hour parameter tweak to a design-level classifier (D-056)". ADR-REPDET-03 captures the 7 rejected alternatives so post-L2 reviewer does not retread any of them.

5. **Tier-1 visibility scores on real video are much lower than CLAUDE.md's UI-label bands imply.** `sigmoid(visibility) × sigmoid(presence)` on atharva-bench.mov ranges 0.25–0.49. The CLAUDE.md thresholds (≥0.80 High, 0.65–0.79 Moderate, 0.50–0.64 Low, <0.50 Very Low) imply real videos should produce mostly High/Moderate confidence. They don't — real videos land uniformly in "Very Low" territory. Either the formula is wrong (maybe visibility/presence are already post-sigmoid in current MediaPipe versions?) or the UI labels need recalibration. Filed as observation in ADR-REPDET-03; not investigated further. **This is worth a look in the post-L2 confidence-calibration pass.**

## 7. Next session start

```bash
/status

# PRIORITY 1 — Non-code blockers (unchanged — critical path for L2 launch)
#   - Kin expert onboarding call (target: 10+ papers by 2026-05-03, 13 days left)
#   - Expert corpus push: first 10 papers via expert portal
#   - Landing page V1 prod verification

# PRIORITY 2 — D-### maintenance bundle (all S, zero-risk, ~2h bundled PR)
#   - D-046 hoist _HAIKU_MODEL to shared constant
#   - D-047 additive ValidationError regression test for BrainCoveService
#   - D-049 Citation serializer warning cleanup (still visible in prod worker logs)
#   - D-051 additive test for cove.py `else` branch Step 4 revision
#   - D-054 narrow lifecycle_decision except-catch: logger.error for Qdrant 4xx auth
#   - D-055 add testpaths = ["tests"] to backend/pyproject.toml

# PRIORITY 3 — PR #84 D-### follow-ups (D-044 closed via deferral session 51)
#   - D-042 wire rep-detection knobs through ThresholdConfig (FR-SCOR-11)
#   - D-043 partial-descent <20° prominence test
#   - D-056 post-L2 design work: working-rep-vs-non-working-motion classifier

# PRIORITY 4 — P3-007 D-### bundle (unchanged)

# ENVIRONMENT NOTES:
#   - Local main = fbb7611 (PR #98 merge — D-044 investigation closeout).
#     Prior: 701dc77 (PR #96 D-054/D-055 backlog rows), 5f06ae3 (PR #95 D-053 docs),
#     88fb0ae (PR #94 D-053 code).
#   - No env flag changes in session 51.
#   - SPELIX_DISTILLATION_ENABLED=1 on prod since session 42 (unchanged).
#   - SPELIX_PHASE3_AGENT_ENABLED=1 on prod since session 32 (unchanged).
#   - Test admin account: atharva6905+admin-p3006@gmail.com /
#     SpelixAdmin-P3006-Test-2026! (UUID cb18c043-5a16-4990-a3d3-02ed4890bf56).
#     Owns 9 analyses (unchanged from session 50 — no new analyses ingested session 51).
#   - Qdrant coach_brain: 26 points (24 seeds + 2 from pre-D-053 distillation) (unchanged).
#   - Droplet deploy dir is /home/deploy/spelix (NOT /srv/spelix).
#   - Backend test baseline: 1704 passed, 27 skipped, 0 failed (unchanged).
#   - Untracked on main: docs/superpowers/plans/2026-04-18-d044-atharva-bench-over-count.md
#     (investigation plan, superseded by ADR-REPDET-03 — delete or keep, both safe).
```
