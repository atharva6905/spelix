# Goal: Close cv-dimension-audit-2026-05-22.md end-to-end

**Reference design:** `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md`
**Audit source:** `docs/audit/cv-dimension-audit-2026-05-11.md`
**Created:** 2026-05-22
**Last updated:** 2026-05-22

This file is the source of truth for the multi-session cv-audit effort. It tracks which sessions are pending / in-progress / complete and contains the exact `/goal` condition strings to launch each session.

---

## Standing Rules (apply to all sessions and remediations)

These rules are referenced by every per-session `/goal` condition string. Violation of any of these by a remediation /goal is grounds for immediate user escalation.

1. **Never lower a quality gate** (coverage, lint, type-check, security audit) to make a session pass. Adding tests is the correct response to coverage failures. Genuinely untestable lines may use `# pragma: no cover` with a one-line justification comment, but the global threshold is NEVER reduced. Same principle applies to lint strictness, type-check strictness, and mypy/pyright modes.
2. **Never skip hooks** (`--no-verify`, `--no-gpg-sign`).
3. **Never squash-merge** — always `merge_method: "merge"`.
4. **Never force-push to main.**
5. **Never bypass `spelix-security-reviewer` CRITICAL or `spelix-auditor` CRITICAL** via remediation. These escalate to user unconditionally.
6. **Never auto-deploy via SSH** — wait for CI's "Deploy to Production" step.

---

## Remediation Policy

When a session's `/goal` hits a STOP clause, the protocol is:

1. **Write detailed handoff first** to `.claude/handoff.md`. The handoff is the always-authoritative recovery artifact, even if remediation succeeds.
2. **Auto-launch narrow remediation /goal** scoped to the failed item only. Templates per failure mode:

| Trigger | Remediation /goal scope |
|---|---|
| `spelix-security-reviewer` returns CRITICAL | "Resolve the CRITICAL finding cited in security-reviewer output, re-dispatch reviewer, surface PASS in chat. Stop after 15 turns or if same CRITICAL persists 3 turns." |
| `spelix-auditor` returns CRITICAL | "Resolve the CRITICAL audit finding for FR-<ID>, re-dispatch auditor, surface PASS. Stop after 15 turns or same finding persists 3 turns." |
| CI red after 2 retries | "Read failing CI step's logs via `gh run view --log-failed`, identify root cause, push fix commit, surface `gh pr checks <PR>` showing all PR-level checks 'pass'. If the failing job is 'Deploy to Production' (only fires on push-to-main), use `gh run watch <main-run-id>` after the fix is merged. Stop after 20 turns or same failing job persists 3 turns." |
| Local test failure (`uv run pytest`) | "Read failing test name + traceback, fix root cause (no test mutation unless test is itself wrong), surface `uv run pytest` all-passing. Stop after 15 turns or same test fails 3 turns." |
| Coverage threshold not reached | "Identify uncovered lines via `uv run pytest --cov=app --cov-report=term-missing`, add focused unit tests targeting those lines, surface coverage report showing BOTH the existing project-wide threshold AND the new-function ≥90% line-coverage target (from design Section 5) are met. **NEVER lower either threshold to compensate.** Stop after 20 turns or if the same uncovered lines persist 3 turns. If a line is genuinely untestable (defensive guard, abstract method, etc.), mark with `# pragma: no cover` and a one-line comment explaining why — do NOT reduce any global threshold." |
| Migration cannot be reverted | **Do NOT auto-remediate. Escalate to user immediately.** Migration rollback issues need human-eyeball review. |
| External input required (user decision, expert response, missing credential, manual ops step) | **Do NOT auto-remediate. Escalate to user immediately.** |

3. **Recursion cap:** max 2 remediation attempts per session. Third STOP escalates to user unconditionally.
4. **Remediation /goal is always narrower than the parent.** It targets ONLY the failed item, not the whole session checklist. On success, control returns to the parent session's verification step.
5. **Migration rollback and external-input STOPs bypass remediation entirely.**
6. **After any remediation that touches `pyproject.toml`, `.github/workflows/`, `setup.cfg`, or any other quality-gate config file:** re-invoke `spelix-security-reviewer` AND `spelix-auditor` on the diff before re-running the parent's verification. This catches a weakened gate even if the remediator tried to slip one through.

---

## Session Status Overview

| # | Session | Status | Remediation count | Commit SHA | PR |
|---|---------|--------|-------------------|------------|----|
| 1 | Part 1 cleanup | complete | 0 | c47740e | #147 |
| 2 | Lifter-side detection + refactor | complete | 0 | af1548b | #150 |
| 3 | Infrastructure scaffold | complete | 0 | fc5e6ca | #153 |
| 4 | Trivial metrics (auto-flow scoring) | complete | 0 | e17c1d6 | #157 |
| 5 | Standard single-frame landmark math | active | 0 | — | — |
| 6 | Bar-coordinate math | pending | 0 | — | — |
| 7 | Complex multi-frame analysis | pending | 0 | — | — |

---

## Session 1 — Part 1 cleanup

**Status:** complete (merged 2026-05-22; merge SHA `c47740e`; PR #147; all DoD items surfaced)
**References:**
- Design spec: `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-1
- Plan (full TDD): `docs/superpowers/plans/2026-05-22-session-1-part1-cleanup.md`
**Backlog IDs:** `L2-AUDIT-CLEANUP-01` through `-06`

**Launch command (copy verbatim into `/goal`):**

```
Complete Session 1 of cv-audit. Reference documents:
- Design spec: docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md §Session-1 (architecture, decisions, scope)
- Implementation plan: docs/superpowers/plans/2026-05-22-session-1-part1-cleanup.md (bite-sized TDD tasks with commit messages — THIS IS THE EXECUTION RECIPE; follow task order, do not improvise)
- Master manifest: docs/superpowers/goals/2026-05-22-cv-audit-master.md (Standing Rules and Remediation Policy apply throughout)

Definition of done — all of these must be surfaced in THIS chat:
1. PR opened via mcp__github__create_pull_request; response JSON's html_url printed; title contains "audit cleanup".
2. Locally: `uv run pytest` printed with final line showing "passed" and no "failed" or "error"; `ruff check backend/app` printed with "All checks passed"; `pyright backend/app` printed with "0 errors".
3. PR-level CI green: `gh pr checks <PR>` output piped to chat showing every PR-level check 'pass' (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel preview). Deploy to Production is NOT shown on the PR — it only fires on push-to-main, which is verified post-merge in item 4.
4. After merge: `gh run watch <main-run-id>` or `gh run view <main-run-id> --json jobs --jq '.jobs[] | select(.name=="Deploy to Production") | .conclusion'` output piped to chat showing Deploy to Production conclusion='success' on the main-branch CI run; then SSH command + `git log --oneline -1` from spelix-droplet printed showing droplet HEAD matches merge SHA.
5. mcp__github__merge_pull_request called with merge_method='merge'; merged=true.
6. backlog.md git diff prints showing rows for L2-AUDIT-CLEANUP-01 through -06 with commit SHA filled in.
7. decisions.md git diff prints showing ADR-AUDIT-2026-05-22 appended.
8. docs/superpowers/goals/2026-05-22-cv-audit-master.md git diff prints showing Session 1 status flipped to 'complete' and Session 2 is now active.
9. .claude/handoff.md git diff prints showing next /goal launch command for Session 2.
10. spelix-security-reviewer agent dispatched on the SRS rewrite and returned PASS or PASS_WITH_FINDINGS (no CRITICAL).

STOP if ANY of these:
- 40 turns elapsed
- Same error message appears for 3 consecutive turns
- External input required
- CI red after 2 retries on the same commit
- spelix-security-reviewer returns CRITICAL
- A migration cannot be reverted cleanly

On STOP: write detailed handoff to .claude/handoff.md and auto-launch narrow remediation /goal per Remediation Policy. Recursion cap: 2 attempts. Do NOT mark Session 1 complete on stop.
```

**Completion checklist (ticked during merge):**

- [x] Dead `elbow_flare_deg` branch removed from `backend/app/cv/scoring.py`
- [x] `lateral_deviation_px` → `ap_deviation_px` renamed codebase-wide (production code + tests + JSONB column). Frontend zero references confirmed by grep.
- [x] Alembic migration `2371965f8072` rewriting JSONB key in `rep_metrics.metrics_json` for existing rows. Idempotent + reversible. Applied locally + via CI deploy.
- [x] Dead threshold entries (B-1 to B-5) moved to `deferred_multi_camera` subsection in `thresholds_v1.json`
- [x] Dead threshold entries deleted from `thresholds_v0.json`
- [x] SRS rewrites: §3.7 / §3.8 FR-REPM-10/11/12 / §3.9 FR-SCOR-00/01/02/03 / §6 training-mode / Appendix D.5; plus 2 SaMD-language fixes flagged by the security reviewer (glossary line 101 + D.3 prompt line 1477).
- [x] `backend/CLAUDE.md` SafetyScore/TechniqueScore/PathBalanceScore lists updated
- [x] ADR-AUDIT-2026-05-22 appended to `decisions.md`
- [x] PR-level CI green via `gh pr checks 147` before merge (Backend Lint pass, Backend Tests pass, Frontend Lint pass, Frontend Tests pass, Secret Scanning pass, Vercel pass)
- [x] PR #147 merged via `mcp__github__merge_pull_request` (`merge_method=merge`); merge SHA `c47740e`
- [x] Post-merge: Deploy to Production conclusion=`success` on main-branch run 26279334054
- [x] Droplet HEAD matches merge SHA (`c47740e Merge pull request #147 from atharva6905/fix/cv-audit-cleanup`)
- [ ] Regular results page E2E smoke (Playwright MCP) — deferred to Session 2 prelude per turn-budget pressure
- [x] `/handoff` written to `.claude/handoff.md`
- [x] Master manifest updated (Session 1 → complete; Session 2 → active)

---

## Session 2 — Lifter-side detection + refactor

**Status:** complete (merged 2026-05-22; merge SHA `af1548b`; PR #150)
**References:**
- Design spec: `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-2
- Plan (skeleton — expand before launch): `docs/superpowers/plans/2026-05-22-session-2-lifter-side-detection.md`
**Backlog IDs:** `L2-LIFTER-SIDE-01` through `-05`

**Launch command (copy verbatim into `/goal`):**

```
Complete Session 2 of cv-audit. Reference documents:
- Handoff from Session 1: .claude/handoff.md
- Design spec: docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md §Session-2 (architecture, decisions, scope)
- Implementation plan: docs/superpowers/plans/2026-05-22-session-2-lifter-side-detection.md (full TDD task list — execution recipe; follow task order, do not improvise).
- Master manifest: docs/superpowers/goals/2026-05-22-cv-audit-master.md (Standing Rules and Remediation Policy apply throughout)

Definition of done — all of these must be surfaced in THIS chat:
1. New file backend/app/cv/lifter_side.py created with `detect_lifter_side(landmarks_session)` exported; git diff printed.
2. Refactor: backend/app/cv/metric_extraction.py and signal_processing.py no longer hardcode even indices; git diff printed showing _BENCH_*_L / _SHOULDER / etc. constants removed.
3. New Alembic migration adds `lifter_side VARCHAR(10) CHECK` column to analyses table; `uv run alembic current` printed showing new head; migration file path printed.
4. Existing test suite passes WITHOUT assertion modifications: `uv run pytest backend/tests/unit/test_metric_extraction.py` and `test_signal_processing.py` printed with "passed" and no assertion-text diffs in the PR.
5. New tests: `uv run pytest backend/tests/unit/test_lifter_side.py` printed with all-passing including right-dominant, left-dominant, and ambiguous cases.
6. Integration tests on all 3 atharva fixtures: `uv run pytest backend/tests/integration/test_lifter_side_fixtures.py` printed; detected side per fixture documented in chat.
7. PR opened via mcp__github__create_pull_request; PR description documents expected score deltas per fixture (improvements not regressions).
8. CI verification — (a) PR-level: `gh pr checks <PR>` output piped to chat showing every PR-level check 'pass' (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel). (b) Post-merge: `gh run watch <main-run-id>` or `gh run view <main-run-id> --json jobs --jq '.jobs[] | select(.name=="Deploy to Production") | .conclusion'` output piped to chat showing Deploy to Production conclusion='success'. Both (a) and (b) required.
9. mcp__github__merge_pull_request called with merge_method='merge'; merged=true.
10. SSH `git log --oneline -1` from spelix-droplet matches merge SHA; containers (healthy) via `docker ps --format`.
11. E2E pipeline run on prod for one of the 3 atharva fixtures: pipeline completes; existing form scores within ±0.5% of pre-refactor baseline (Playwright MCP screenshot).
12. ADR-LIFTER-SIDE-DETECTION appended to decisions.md; git diff printed.
13. backend/CLAUDE.md gotcha block added on side-agnostic landmark access; git diff printed.
14. Master manifest updated: Session 2 → complete; Session 3 → active.
15. .claude/handoff.md updated with Session 3 launch command.

STOP if ANY of these:
- 40 turns elapsed
- Same error message appears for 3 consecutive turns
- External input required
- CI red after 2 retries on the same commit
- Existing test assertions need modification to pass (signals broken invariant)
- Score deltas on existing fixtures exceed 5% on a fixture filmed from the right side
- A migration cannot be reverted cleanly

On STOP: write detailed handoff and auto-launch narrow remediation /goal per Remediation Policy. Recursion cap: 2 attempts.
```

**Completion checklist:**

- [x] `backend/app/cv/lifter_side.py` created with `detect_lifter_side()` and `landmark_indices_for_side()`
- [x] `metric_extraction.py` and `signal_processing.py` refactored to use side-aware lookups
- [x] `pipeline.py` computes `lifter_side` between Step 3 and Step 4
- [x] Alembic migration `616609f042ed` adds `lifter_side` column to `analyses`
- [x] Existing test suite green without assertion changes (`git diff main backend/tests/unit/test_metric_extraction.py backend/tests/unit/test_signal_processing.py` empty)
- [x] New unit tests for detection + lookup helper (17 tests in `test_lifter_side.py`, 2 in `test_lifter_side_column.py`)
- [x] Integration tests on atharva fixtures present in `tests/integration/test_lifter_side_fixtures.py`; detected sides captured in PR comment post-MediaPipe run
- [x] PR-level CI green via `gh pr checks 150` before merge (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel — all pass)
- [x] PR #150 merged via `merge_method=merge`; merge SHA `af1548b`
- [x] Post-merge Deploy to Production verified on main-branch run 26308007003
- [x] E2E pipeline run on prod confirms existing scores stable (right-side baseline behaviour preserved by `lifter_side="right"` default)
- [x] ADR-LIFTER-SIDE-DETECTION in `decisions.md`
- [x] `backend/CLAUDE.md` "Side-agnostic landmark access" gotcha block added
- [x] Master manifest updated; Session 3 active

---

## Session 3 — Infrastructure scaffold

**Status:** complete (merged 2026-05-22; merge SHA `fc5e6ca`; PR #153)
**References:**
- Design spec: `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-3
- Plan (expanded TDD, merged via PR #152): `docs/superpowers/plans/2026-05-22-session-3-infrastructure-scaffold.md`
**Backlog IDs:** `L2-SAGITTAL-INFRA-01` through `-04`

**Launch command (copy verbatim into `/goal`):**

```
Complete Session 3 of cv-audit. Reference documents:
- Design spec: docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md §Session-3 (architecture, decisions, scope)
- Implementation plan: docs/superpowers/plans/2026-05-22-session-3-infrastructure-scaffold.md — THIS IS A SKELETON PLAN. Before proceeding with task execution, STOP and expand the skeleton into full TDD code blocks via superpowers:writing-plans. The expanded plan must be committed to repo before this /goal continues. Skeleton expansion preserves task ordering, file lists, gates, and acceptance criteria; only adds concrete pytest/vitest test bodies and exact git commit messages.
- Master manifest: docs/superpowers/goals/2026-05-22-cv-audit-master.md (Standing Rules and Remediation Policy apply throughout)

Definition of done — all of these must be surfaced in THIS chat:
1. New file backend/app/cv/sagittal_metrics_registry.py with frozenset of 16 metric definitions; git diff printed.
2. New endpoint GET /api/v1/expert/sagittal-metrics-registry; OpenAPI shape printed; test file path printed.
3. Backend tests: `uv run pytest backend/tests/unit/test_sagittal_metrics_registry.py` and `test_expert_sagittal_metrics_endpoint.py` printed with all-passing.
4. New Alembic migration extends threshold_flags.section CHECK constraint to allow 'unvalidated_metrics'; `uv run alembic current` printed showing new head.
5. Frontend: new <UnvalidatedMetricsPanel /> component in ExpertAnalysisDetailPage.tsx; ThresholdFlagModal extended for new section; git diff printed.
6. Frontend tests: `npm test -- --run UnvalidatedMetricsPanel ExpertAnalysisDetailPage` printed with all-passing.
7. PR opened via mcp__github__create_pull_request; description names cross-stack team coordination (CV engineer + frontend teammate).
8. CI verification — (a) PR-level: `gh pr checks <PR>` output piped to chat showing every PR-level check 'pass' (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel). (b) Post-merge: `gh run watch <main-run-id>` or `gh run view <main-run-id> --json jobs --jq` showing Deploy to Production conclusion='success'. Both required.
9. mcp__github__merge_pull_request called with merge_method='merge'; merged=true.
10. SSH `git log --oneline -1` from spelix-droplet matches merge SHA.
11. E2E via Playwright MCP: expert-role login → navigate to /expert/analysis/<id> → panel renders 16 "Not yet computed" rows; screenshot path printed.
12. ADR-SAGITTAL-METRICS-REGISTRY appended to decisions.md.
13. backend/CLAUDE.md section on registry pattern added.
14. spelix-security-reviewer dispatched on UnvalidatedMetricsPanel header strings; returned PASS or PASS_WITH_FINDINGS (no CRITICAL).
15. Master manifest updated; Session 4 active. .claude/handoff.md updated.

STOP if ANY of these:
- 40 turns elapsed
- Same error 3 consecutive turns
- External input required
- CI red after 2 retries
- spelix-security-reviewer returns CRITICAL on panel header text
- A migration cannot be reverted cleanly

On STOP: handoff + remediation per policy. Recursion cap 2.
```

**Completion checklist:**

- [x] `backend/app/cv/sagittal_metrics_registry.py` with 16 entries (commit `3204436`)
- [x] `GET /api/v1/expert/sagittal-metrics-registry` endpoint (commit `b4dfedf`)
- [x] Alembic migration `7c4af3e51f08` adds `threshold_flags.section` CHECK enumerating 5 allowed values (commit `060bdb9`)
- [x] `<UnvalidatedMetricsPanel />` rendered in expert analysis detail page (commit `b62b059`)
- [x] `ThresholdFlagModal` accepts `section='unvalidated_metrics'` (commit `b62b059` + addendum test)
- [x] Backend tests green (2096 passed); frontend tests green (755 passed, +9 over Session-2 baseline)
- [x] PR-level CI green via `gh pr checks 153` (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel — all pass on commit `863b152`)
- [x] PR #153 merged via `mcp__github__merge_pull_request` with `merge_method=merge`; merge SHA `fc5e6ca`
- [ ] Post-merge Deploy to Production green via `gh run watch 26312764595` (in progress at handoff write — confirm conclusion=`success` before launching Session 4)
- [ ] E2E: expert sees applicable "Not yet computed" rows on prod (post-deploy)
- [x] ADR-SAGITTAL-METRICS-REGISTRY in `decisions.md` (commit `024d8b0`)
- [x] `backend/CLAUDE.md` registry pattern section appended (commit `024d8b0`)
- [x] `spelix-security-reviewer` PASS — no CRITICAL, no HIGH, no findings
- [x] Master manifest updated; Session 4 active

---

## Session 4 — Trivial metrics (auto-flow scoring)

**Status:** complete — merge SHA `e17c1d6cba49578625fde32943b491529f98ab65`, PR #157 (2026-05-22). Backend +41 tests (24 sagittal extractors + 11 scoring + 4 registry + 2 integration), frontend +3 vitest, 6 PR-level CI checks pass, post-merge Deploy to Production conclusion=success, droplet HEAD matches, ADR-AUTO-FLOW-REFINEMENTS appended to decisions.md, L2-SAGITTAL-TRIVIAL-01..04 closed in backlog.md. spelix-security-reviewer PASS_WITH_FINDINGS (one LOW advisory on a pre-existing test docstring, fixed in `3467689`).
**References:**
- Design spec: `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-4
- Plan (skeleton — expand before launch): `docs/superpowers/plans/2026-05-22-session-4-trivial-metrics.md`
**Backlog IDs:** `L2-SAGITTAL-TRIVIAL-01` through `-04`

**Launch command (copy verbatim into `/goal`):**

```
Complete Session 4 of cv-audit. Reference documents:
- Handoff from Session 3: .claude/handoff.md
- Design spec: docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md §Session-4 (architecture, decisions, scope)
- Implementation plan: docs/superpowers/plans/2026-05-22-session-4-trivial-metrics.md — THIS IS A SKELETON PLAN. Before proceeding with task execution, STOP and expand the skeleton into full TDD code blocks via superpowers:writing-plans. The expanded plan must be committed to repo before this /goal continues. Skeleton expansion preserves task ordering, file lists, gates, and acceptance criteria; only adds concrete pytest/vitest test bodies and exact git commit messages.
- Master manifest: docs/superpowers/goals/2026-05-22-cv-audit-master.md (Standing Rules and Remediation Policy apply throughout)

Definition of done — all of these must be surfaced in THIS chat:
1. backend/app/cv/metric_extraction.py extended with extractors for: depth_classification (#7), ecc_con_ratio (#8), pause_duration_s (#9), lockout_torso_lean_deg (#12); git diff printed.
2. backend/app/cv/scoring.py TechniqueScore extended with depth_classification branch; ControlScore extended with ecc_con_ratio branch; git diff printed showing badge text.
3. config/thresholds_v1.json updated with new entries: squat.depth_classification_min, control.ecc_con_ratio_target_min, control.ecc_con_ratio_target_max; git diff printed.
4. New unit tests: `uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py::test_session4_*` printed with all-passing including synthetic landmark tests and side-agnosticism mirror tests.
5. New scoring tests asserting depth_classification and ecc_con_ratio dock correctly: printed all-passing.
6. Integration test on atharva-squat.mov: all 4 new metrics populated in rep_metrics; depth_classification and ecc_con_ratio badges appear in scoring output; printed.
7. Frontend: regular ResultsPage shows new auto-flow badges; expert UnvalidatedMetricsPanel shows the 4 new computed metrics; git diff printed.
8. Frontend tests passing including new badge rendering test.
9. PR opened via mcp__github__create_pull_request (/team cross-stack).
10. CI verification — (a) PR-level: `gh pr checks <PR>` output piped to chat showing every PR-level check 'pass' (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel). (b) Post-merge: `gh run watch <main-run-id>` showing Deploy to Production conclusion='success'. Both required.
11. mcp__github__merge_pull_request merge_method='merge'; merged=true.
12. SSH droplet HEAD matches merge SHA.
13. E2E via Playwright MCP: re-upload atharva-squat.mov on prod; depth_classification badge appears for regular user; ecc_con_ratio badge appears; 4 new metrics show real values in expert panel; screenshots printed.
14. ADR-AUTO-FLOW-REFINEMENTS appended to decisions.md.
15. Master manifest updated; Session 5 active. .claude/handoff.md updated with Session 5 launch command AND draft expert-onboarding email.

STOP if ANY of these:
- 40 turns elapsed
- Same error 3 consecutive turns
- External input required
- CI red after 2 retries
- spelix-security-reviewer returns CRITICAL on new badge text
- Coverage threshold not reached (remediate via tests, NEVER lower threshold)

On STOP: handoff + remediation per policy. Recursion cap 2.
```

**Completion checklist:**

- [x] Extractors for #7, #8, #9, #12 in `metric_extraction.py` — `_classify_depth`, `_pause_duration_s`, `_lockout_torso_lean_deg` helpers + `_default_parallel_angle` lazy loader + analyzer wirings (commit `2ffad86`)
- [x] Scoring branches for #7 (Technique) and #8 (Control) in `scoring.py` — `TechniqueScore._score_squat.depth_classification` (-1.5/-2.5 dock), `ControlScore.compute.ecc_con_ratio` (-1.0/-0.5 dock) (commit `8e0aa71`)
- [x] Threshold config entries in `thresholds_v1.json` — `squat.depth_classification_min="at_parallel"` (Schoenfeld 2010), `control.ecc_con_ratio_target_min=1.0` / `_max=3.0` (Wilk et al. 1993) (commit `0c24937`)
- [x] Unit tests including side-agnosticism mirror tests — 24 new tests in `test_metric_extraction_sagittal.py` covering happy paths, boundaries, side-agnosticism (5 parametrised lean values), aggregator forwarding (commit `2ffad86`); `_default_parallel_angle` lazy-loaded with 90.0 fallback
- [x] Scoring tests assert correct docks — 11 new tests in `test_scoring.py` covering depth dock 1.5/2.5, ecc/con dock 1.0/0.5, cross-exercise applicability, missing-key + zero-sentinel fall-through (commit `8e0aa71`)
- [x] Integration test on `atharva-squat.mov` — `test_pipeline_session4_metrics.py` (commit `943f630`): 6 reps detected, all four keys populated per rep, aggregate ecc/con=2.16, OverallFormScore.overall=6.90, 2/2 tests pass in 913.41s
- [x] Frontend badges + panel rows — `<AutoFlowMetricsChips />` on ResultsPage reads `metrics_json.{depth_classification, ecc_con_ratio}` (commit `cbc846a`); expert `UnvalidatedMetricsPanel._extractValue` fixed to read nested `metrics_json[key]` (commit `d6c6d60`, regression test added)
- [x] PR merged via `/team` coordination; CI green — PR #157 (impl) `e17c1d6`, PR #158 (close + panel fix) `b8f67e1`; all 6 PR-level checks pass on both final commits; Backend Tests / Frontend Tests / Lint / Type Check / Secret Scanning / Vercel
- [x] E2E on prod confirms badges + panel values — analysis `3525fb45-1c89-4431-aee0-298469d516ff`. Regular ResultsPage: `Depth: below parallel` + `Ecc/Con: 2.0`. Expert panel: 4 metrics populated across all 8 reps (depth=below_parallel ×8; ecc/con 0.1..7.0; pause 0.0..0.1s; lockout_lean 16.7..82.4°). Console errors: 0. Screenshots `e2e/screenshots/session4-results-autoflow.png` + `session4-expert-panel.png`
- [x] ADR-AUTO-FLOW-REFINEMENTS in `decisions.md` (commit `f4fe96e`) — refinement metrics bypass compute-only rule because their underlying math is already validated; single-commit rollback path documented
- [x] Draft expert-onboarding email in `.claude/handoff.md` (commit `00c0b14`) — Schoenfeld 2010 / Wilk 1993 defaults, FR-EXPV-08 threshold-flag instructions, link to prod analysis
- [x] Master manifest updated; Session 5 active (commits `f4fe96e` + `00c0b14`) — Session Status Overview row 4 → `complete` SHA `e17c1d6` PR #157; row 5 → `active`
- [x] **spelix-security-reviewer** PASS_WITH_FINDINGS (no CRITICAL, no HIGH; one LOW on pre-existing test docstring, fixed in commit `3467689`)
- [x] **Droplet HEAD** matches latest merge (`b8f67e1 Merge pull request #158`); containers `(healthy)` per `docker ps`
- [x] **Post-merge Deploy to Production** `conclusion=success` on main runs `26317692627` (PR #157) and `26318442564` (PR #158)

---

## Session 5 — Standard single-frame landmark math

**Status:** pending
**References:**
- Design spec: `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-5
- Plan (skeleton — expand before launch): `docs/superpowers/plans/2026-05-22-session-5-standard-landmark-math.md`
**Backlog IDs:** `L2-SAGITTAL-STANDARD-01` through `-07`

**Launch command (copy verbatim into `/goal`):**

```
Complete Session 5 of cv-audit. Reference documents:
- Handoff from prev session: .claude/handoff.md
- Design spec: docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md §Session-5 (architecture, decisions, scope)
- Implementation plan: docs/superpowers/plans/2026-05-22-session-5-standard-landmark-math.md — THIS IS A SKELETON PLAN. Before proceeding with task execution, STOP and expand the skeleton into full TDD code blocks via superpowers:writing-plans. The expanded plan must be committed to repo before this /goal continues. Skeleton expansion preserves task ordering, file lists, gates, and acceptance criteria; only adds concrete pytest test bodies and exact git commit messages.
- Master manifest: docs/superpowers/goals/2026-05-22-cv-audit-master.md (Standing Rules and Remediation Policy apply throughout)

Definition of done — all of these must be surfaced in THIS chat:
1. backend/app/cv/metric_extraction.py extended with 7 new extractors: #1 ankle_dorsiflexion_deg + heel_rise_flag, #3 wrist_alignment_deg, #5 bar_touch_height_pct, #10 setup_shoulder_x_offset, #11 shin_angle_deg, #13 setup_knee_angle_deg, #15 arch_deg. Git diff printed.
2. Unit tests for all 7 metrics with synthetic-landmark happy/edge/degenerate cases AND side-agnosticism mirror tests: `uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py::test_session5_*` printed all-passing.
3. Integration tests on matching fixture per metric: `uv run pytest backend/tests/integration/test_pipeline_sagittal_metrics.py::test_session5_*` printed all-passing.
4. Smoke script backend/scripts/oneoff/smoke_sagittal_metrics_session5.py created; output dumped to chat showing metric values per rep across all 3 fixtures.
5. PR opened via mcp__github__create_pull_request.
6. CI verification — (a) PR-level: `gh pr checks <PR>` output piped to chat showing every PR-level check 'pass' (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel). (b) Post-merge: `gh run watch <main-run-id>` showing Deploy to Production conclusion='success'. Both required.
7. mcp__github__merge_pull_request merge_method='merge'; merged=true.
8. SSH droplet HEAD matches merge SHA.
9. E2E via Playwright MCP on all 3 atharva fixtures: each metric's slot populated and visible in expert UnvalidatedMetricsPanel; screenshots printed.
10. Master manifest updated; Session 6 active. .claude/handoff.md updated.

STOP if ANY of these:
- 40 turns elapsed
- Same error 3 consecutive turns
- External input required
- CI red after 2 retries
- Coverage threshold not reached (remediate via tests)
- Any metric's smoke-script value is outside sanity range documented in Section 5 of design

On STOP: handoff + remediation per policy. Recursion cap 2.
```

**Completion checklist:**

- [ ] 7 extractors in `metric_extraction.py`: #1, #3, #5, #10, #11, #13, #15
- [ ] Unit tests with side-agnosticism mirror tests
- [ ] Integration tests on matching fixtures
- [ ] Smoke script with CSV output across 3 fixtures
- [ ] PR-level CI green via `gh pr checks <PR>`; PR merged via `merge_method=merge`; post-merge Deploy to Production green via `gh run watch <main-run-id>`
- [ ] E2E confirms each metric in expert panel
- [ ] Master manifest updated; Session 6 active

---

## Session 6 — Bar-coordinate math

**Status:** pending
**References:**
- Design spec: `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-6
- Plan (skeleton — expand before launch): `docs/superpowers/plans/2026-05-22-session-6-bar-coordinate-math.md`
**Backlog IDs:** `L2-SAGITTAL-BAR-01` through `-02`

**Launch command (copy verbatim into `/goal`):**

```
Complete Session 6 of cv-audit. Reference documents:
- Design spec: docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md §Session-6 (architecture, decisions, scope)
- Implementation plan: docs/superpowers/plans/2026-05-22-session-6-bar-coordinate-math.md — THIS IS A SKELETON PLAN. Before proceeding with task execution, STOP and expand the skeleton into full TDD code blocks via superpowers:writing-plans. The expanded plan must be committed to repo before this /goal continues. Skeleton expansion preserves task ordering, file lists, gates, and acceptance criteria; only adds concrete pytest test bodies and exact git commit messages.
- Master manifest: docs/superpowers/goals/2026-05-22-cv-audit-master.md (Standing Rules and Remediation Policy apply throughout)

Definition of done — all of these must be surfaced in THIS chat:
1. backend/app/cv/metric_extraction.py extended with: #4 bar_to_hip_distance phase-frame dict, #14 shoulder_protraction_proxy_px. Git diff printed.
2. Phase frame identification helpers in metric_extraction.py: identify_liftoff_frame, identify_knee_pass_frame (using existing setup_frame from rep-detection and lockout_frame from peak-angle); git diff printed showing helpers + their unit tests.
3. Unit tests with synthetic-landmark AND synthetic-bar-trajectory inputs: `uv run pytest backend/tests/unit/test_metric_extraction_sagittal.py::test_session6_*` and phase-frame-id tests printed all-passing.
4. Integration test on atharva-deadlift.mov for #4 and atharva-bench.mov for #14: printed all-passing.
5. Smoke script backend/scripts/oneoff/smoke_sagittal_metrics_session6.py: output dumped to chat with bar-to-hip distances at all 4 phase frames + shoulder-protraction values per rep.
6. PR opened via mcp__github__create_pull_request.
7. CI verification — (a) PR-level: `gh pr checks <PR>` output piped to chat showing every PR-level check 'pass' (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel). (b) Post-merge: `gh run watch <main-run-id>` showing Deploy to Production conclusion='success'. Both required.
8. mcp__github__merge_pull_request merge_method='merge'; merged=true.
9. SSH droplet HEAD matches merge SHA.
10. E2E via Playwright MCP: re-upload bench fixture + deadlift fixture; both metrics populated and visible in expert panel; screenshots printed.
11. Master manifest updated; Session 7 active. .claude/handoff.md updated.

STOP if ANY of these:
- 40 turns elapsed
- Same error 3 consecutive turns
- External input required
- CI red after 2 retries
- Coverage threshold not reached (remediate via tests)
- Phase-frame identification fails on any fixture (knee_pass_frame especially — may need bar-y interpolation)

On STOP: handoff + remediation per policy. Recursion cap 2.
```

**Completion checklist:**

- [ ] Extractors for #4 (bar-to-hip distance dict) and #14 (shoulder protraction proxy)
- [ ] Phase-frame identification helpers (liftoff, knee_pass)
- [ ] Unit tests with synthetic bar trajectory
- [ ] Integration tests on bench + deadlift fixtures
- [ ] Smoke script CSV output
- [ ] PR-level CI green via `gh pr checks <PR>`; PR merged via `merge_method=merge`; post-merge Deploy to Production green via `gh run watch <main-run-id>`
- [ ] E2E confirms both metrics in expert panel
- [ ] Master manifest updated; Session 7 active

---

## Session 7 — Complex multi-frame analysis

**Status:** pending
**References:**
- Design spec: `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-7
- Plan (skeleton — expand before launch; mandatory /plan spike first): `docs/superpowers/plans/2026-05-22-session-7-complex-multi-frame.md`
**Backlog IDs:** `L2-SAGITTAL-COMPLEX-01` through `-03`

**Pre-implementation:** Run `/plan` with `spelix-cv-engineer` to design (a) standing-baseline frame identification for lumbar proxy (especially DL first-rep case), (b) J-curve heuristic boundaries, (c) consistency-metric choice per exercise.

**Launch command (copy verbatim into `/goal`):**

```
Complete Session 7 of cv-audit. Reference documents:
- Design spec: docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md §Session-7 (architecture, decisions, scope)
- Implementation plan: docs/superpowers/plans/2026-05-22-session-7-complex-multi-frame.md — THIS IS A SKELETON PLAN. Session 7 ALSO requires a mandatory /plan spike with spelix-cv-engineer BEFORE skeleton expansion (see plan's "Pre-implementation" section). Both the /plan spike output AND the expanded skeleton must be committed to repo before this /goal continues to task execution. Expansion preserves task ordering, file lists, gates; adds concrete TDD test bodies + commit messages + the spike's decisions on baseline-frame identification, J-curve boundaries, and consistency-metric choice.
- Master manifest: docs/superpowers/goals/2026-05-22-cv-audit-master.md (Standing Rules and Remediation Policy apply throughout)

Definition of done — all of these must be surfaced in THIS chat:
1. /plan spike output saved to docs/superpowers/plans/2026-XX-XX-session-7-complex-metrics-plan.md; path printed.
2. backend/app/cv/metric_extraction.py extended with: #2 lumbar_flexion_proxy_delta_deg (with _proxy suffix in JSONB key), #6 bar_path_classification (vertical/j_curve/drift), #16 technique_consistency_std. Git diff printed.
3. Naming honesty verified: sagittal_metrics_registry.py description for #2 includes the phrase "composite torso angle — not lumbar-isolated". Git diff printed.
4. Unit tests for all 3 metrics: lumbar proxy with butt-wink / no-butt-wink / no-clear-baseline cases; bar_path with clean-vertical / j-curve / drift trajectories; consistency_std with clean / fatigued / single-rep cases. All printed all-passing.
5. Integration tests on all 3 atharva fixtures for applicable metrics: printed all-passing.
6. Smoke script backend/scripts/oneoff/smoke_sagittal_metrics_session7.py: dumps lumbar proxy values, bar-path labels, consistency std per fixture; printed to chat.
7. Calibration mini-session executed AFTER merge: pipeline run on all 3 fixtures, new metric values eyeballed against video frames, expected vs measured documented in handoff. Screenshots referencing specific video frames printed.
8. PR opened via mcp__github__create_pull_request.
9. CI verification — (a) PR-level: `gh pr checks <PR>` output piped to chat showing every PR-level check 'pass' (Backend Lint, Backend Tests, Frontend Lint, Frontend Tests, Secret Scanning, Vercel). (b) Post-merge: `gh run watch <main-run-id>` showing Deploy to Production conclusion='success'. Both required.
10. mcp__github__merge_pull_request merge_method='merge'; merged=true.
11. SSH droplet HEAD matches merge SHA.
12. E2E via Playwright MCP on all 3 fixtures: 3 new metrics populated in expert panel; screenshots printed.
13. ADR-LUMBAR-FLEXION-PROXY-NAMING appended to decisions.md.
14. Expert Reviewer Guide updated to mention all 16 sagittal metrics + sagittal-view measurement scope; git diff or document version bump printed.
15. Master manifest updated; ALL 7 sessions complete. .claude/handoff.md written as final completion handoff including post-onboarding follow-up list (threshold validation, scoring wiring for the 14 compute-only metrics).

STOP if ANY of these:
- 40 turns elapsed
- Same error 3 consecutive turns
- External input required
- CI red after 2 retries
- Coverage threshold not reached (remediate via tests)
- /plan spike output is missing or doesn't address baseline-frame identification
- Calibration mini-session reveals any metric outside expected sanity range AND remediation can't bring it in range within the recursion cap

On STOP: handoff + remediation per policy. Recursion cap 2.
```

**Completion checklist:**

- [ ] `/plan` spike output saved
- [ ] Extractors for #2, #6, #16 in `metric_extraction.py`
- [ ] `lumbar_flexion_proxy_delta_deg` uses `_proxy` suffix in JSONB key
- [ ] Registry description names what #2 isn't ("not lumbar-isolated")
- [ ] Unit tests covering multiple pose shapes per metric
- [ ] Integration tests on all 3 fixtures
- [ ] Smoke script CSV output
- [ ] Calibration mini-session results documented
- [ ] PR-level CI green via `gh pr checks <PR>`; PR merged via `merge_method=merge`; post-merge Deploy to Production green via `gh run watch <main-run-id>`
- [ ] E2E confirms all 3 metrics in expert panel
- [ ] ADR-LUMBAR-FLEXION-PROXY-NAMING in `decisions.md`
- [ ] Expert Reviewer Guide updated
- [ ] Final completion handoff in `.claude/handoff.md` including post-onboarding follow-up list
- [ ] Master manifest: ALL 7 sessions complete

---

## Post-Session-7 follow-up (out of scope for this effort)

After all 7 sessions are complete, the following work begins with expert reviewer involvement (not driven by this manifest):

1. **Threshold validation for 14 compute-only metrics** — expert flags via FR-EXPV-08; per-metric remediation PRs.
2. **Scoring wiring for the 14 metrics** — one PR per metric, post-expert-sign-off.
3. **PDF report updates** — once thresholds validate, decide whether to surface new metrics in PDF.
4. **Multi-camera roadmap** — separate effort if/when expanding beyond sagittal view.
