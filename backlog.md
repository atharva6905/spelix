# backlog.md — Phase 0, Phase 1 Build, Phase 2 Prep

Phase 0 core build complete (B-001 through B-042). Audit on 2026-04-09 found 67 issues.
Full audit: `docs/phase0-audit.md`. Detailed reports: `docs/audit-{backend,frontend,tests,infra}.md`.

**Phase 1 code-complete 2026-04-10** — all MUST requirements implemented; tests green; transition gate passed.
**Phase 1 production-functional 2026-04-11** — twelve dormant Phase 0 bugs surfaced and fixed across PRs #3–#14 in session 13.
The full upload → worker pipeline → quality gates path now runs end-to-end on `spelix.app`. See B-138–B-149 below
and ADR-027 through ADR-032 in `decisions.md` for the full breakdown.

Backend: **960** tests passing (was 895 at code-complete), 91% coverage. Frontend: **178** tests passing (was 177).
Migration 003 applied to Supabase. Ready for Phase 2 (RAG).

## Completed — L2 Sprint — CV audit Session 2 lifter-side detection + refactor (2026-05-22, session 2)

PR #150 (merge SHA `af1548b`) merged via `mcp__github__merge_pull_request` (`merge_method="merge"`).
Closes `docs/audit/cv-dimension-audit-2026-05-11.md` lifter-side prerequisite for Sessions 4–7.
Backend: 17 new unit tests (`test_lifter_side.py`), 2 migration/model tests (`test_lifter_side_column.py`),
3 integration fixture tests. 59 pre-existing tests for metric_extraction + signal_processing remain
green WITHOUT assertion changes (invariant gate). ruff + pyright clean. Migration `616609f042ed` applied.
ADR-LIFTER-SIDE-DETECTION + `backend/CLAUDE.md` side-agnostic landmark gotcha block added.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-LIFTER-SIDE-01 | Implement `detect_lifter_side(landmarks_session, fps)` + `landmark_indices_for_side(side)` in new `backend/app/cv/lifter_side.py`. Visibility-weighted, anchor-restricted, ambiguous→"right" with WARNING log. | done | M | — | — | `a8ccb6c` | `backend/app/cv/lifter_side.py`, `backend/tests/unit/test_lifter_side.py` |
| L2-LIFTER-SIDE-02 | Add `lifter_side VARCHAR(10) CHECK` column to `analyses` via Alembic migration; update SQLAlchemy model. | done | S | L2-LIFTER-SIDE-01 | — | `ddd2157` | `backend/alembic/versions/616609f042ed_add_lifter_side_to_analyses.py`, `backend/app/models/analysis.py`, `backend/tests/unit/test_lifter_side_column.py` |
| L2-LIFTER-SIDE-03 | Refactor `metric_extraction.py` to delete `_SHOULDER`/`_HIP`/`_KNEE`/`_ANKLE`/`_ELBOW`/`_WRIST` constants and route through `landmark_indices_for_side(lifter_side)` with default `"right"`. Existing test assertions unchanged. | done | M | L2-LIFTER-SIDE-01 | FR-REPM-02, FR-REPM-03 | `ab1d435` | `backend/app/cv/metric_extraction.py` |
| L2-LIFTER-SIDE-04 | Refactor `signal_processing.py::calculate_joint_angles` + `compute_angle_timeseries` to delete `_BENCH_*_L` and `_SQUAT_*_L` constants and route through `landmark_indices_for_side(lifter_side)`. Existing test assertions unchanged. | done | M | L2-LIFTER-SIDE-01 | FR-CVPL-14 | `ab1d435` | `backend/app/cv/signal_processing.py` |
| L2-LIFTER-SIDE-05 | Wire `services/pipeline.py` Step 3.5 to call `detect_lifter_side`, persist on `analyses.lifter_side`, thread into `compute_angle_timeseries` + `extract_rep_metrics`. Expose `lifter_side` on `AnalysisDetail` schema. Update mock factories. | done | M | L2-LIFTER-SIDE-02..04 | — | `ca90307` | `backend/app/services/pipeline.py`, `backend/app/schemas/analysis.py`, `backend/tests/unit/test_analysis_api.py`, `backend/tests/unit/test_analysis_crud.py`, `backend/tests/integration/test_lifter_side_fixtures.py` |

## Completed — L2 Sprint — CV audit Part 1 cleanup (2026-05-22, session 1)

PR #147 (merge SHA `c47740e`) merged via `mcp__github__merge_pull_request` (`merge_method="merge"`).
Closes `docs/audit/cv-dimension-audit-2026-05-11.md` items A-1, B-1 through B-5,
C-1 through C-11, D-5, E-1. Backend: 7 new regression tests (1 elbow_flare, 1
bar-path key, 4 threshold-structure, 1 migration-static + 5 migration-equivalent
unit tests). ruff + pyright clean. Migration `2371965f8072` applied. Frontend
untouched (zero references to renamed metric).

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-AUDIT-CLEANUP-01 | Remove dead `elbow_flare_deg` branch from `scoring.py::TechniqueScore._score_bench`; delete MC/DC test class for it; add regression test asserting the metric is silently ignored if it appears. | done | S | — | FR-SCOR-02 | `135a21a` | `backend/app/cv/scoring.py`, `backend/tests/unit/test_scoring.py`, `backend/tests/mcdc/test_mcdc_scoring_technique.py`, `docs/mcdc/traceability.md` |
| L2-AUDIT-CLEANUP-02 | Rename `lateral_deviation_px` → `ap_deviation_px` codebase-wide (production code + tests + JSONB migration). Sagittal x-axis IS the A-P axis from a side-view camera. | done | M | — | FR-SCOR-03 | `499a31e`, `9ee4577` | `backend/app/cv/{barbell_detection,scoring}.py`, `backend/app/services/pdf.py`, `backend/tests/unit/test_{barbell_detection,pipeline,pdf,scoring}.py`, `backend/alembic/versions/2371965f8072_rename_lateral_deviation_px_jsonb_key_.py`, `backend/tests/unit/test_migration_rename_ap_deviation.py` |
| L2-AUDIT-CLEANUP-03 | Move dead threshold entries (knee_valgus_*, lumbar_flexion_*, grip_width_*, wrist_alignment_*, toe_out_*, elbow_flare_*) to a new `deferred_multi_camera` subsection in `thresholds_v1.json` preserving citations; delete the same keys from the `thresholds_v0.json` frozen snapshot. | done | S | — | FR-SCOR-11 | `eb0f4dc` | `config/thresholds_v0.json`, `config/thresholds_v1.json`, `backend/tests/unit/test_threshold_config.py`, `backend/tests/unit/test_expert_thresholds_api.py` |
| L2-AUDIT-CLEANUP-04 | Rewrite SRS §3.7 dimension lists, §3.8 FR-REPM-10/11/12, §3.9 FR-SCOR-00/01/02/03, §6 training-mode table, Appendix D.5 example I/O — each unmeasurable-metric claim is either deleted or annotated as deferred to multi-camera phase. | done | M | — | FR-SCOR-01, FR-SCOR-02, FR-SCOR-03, FR-REPM-10, FR-REPM-11, FR-REPM-12 | `0efd602` | `docs/SRS.md` |
| L2-AUDIT-CLEANUP-05 | Update `backend/CLAUDE.md` SafetyScore/TechniqueScore/PathBalanceScore feature lists to reflect sagittal-observable inputs and mark frontal-plane phenomena as deferred. | done | S | — | — | `336ec07` | `backend/CLAUDE.md` |
| L2-AUDIT-CLEANUP-06 | Add canonical ADR-AUDIT-2026-05-22 to `decisions.md` (sagittal scope + deferred multi-camera roadmap + forward-references to per-session ADRs). | done | S | — | — | `a467745` | `decisions.md` |

## Completed — L2 Sprint Day 18 — Phase 3 transition gate cleared via 3 PRs closing 2026-04-27 audit (2026-04-27, session 62)

The 2026-04-27 spelix-auditor sweep against the 8 Phase 3 Must FRs returned 0 CRITICAL / 3 HIGH / 5 MEDIUM. Three PRs (#126, #127, #128) closed all 8 findings 5 days before the 2026-05-03 hard gate. Backend tests: +7 across 3 PRs. Frontend tests: +1 net (M-04 vitest case landed then reverted; +1 from H-02 rendering). All ruff + pyright + tsc + eslint clean. CI 5/5 green on all three PRs. Deploy to Production succeeded for all three.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-AUDIT-2026-04-27-H01 | **Tombstone contradicted Coach Brain entries on UPDATE path** (auditor H-01 + M-01). When `contradiction_flag=True` on UPDATE, set `existing.status='deprecated'` and merge `extra_metadata.rejected_reason='contradicted_by_<candidate_id>'` instead of bumping `confirmation_count`. Reuses the FR-BRAIN-16 workaround pattern from `coach_brain.py:soft_delete_empty_unconfirmed` (no migration needed — `coach_brain_entries.status` CHECK only allows seed/active/deprecated). 2 new pytest cases + 1 regression guard. | done | M | — | FR-BRAIN-17 | `1ea9f13` (PR #126) | `backend/app/distillation/store.py`, `backend/tests/unit/test_distillation_store.py` |
| L2-AUDIT-2026-04-27-H02 | **Surface nearest-entry `confirmation_count` on Coach Brain candidate review card** (auditor H-02). Backend: new `list_pending_with_nearest_confirmation_count` repo method using LEFT OUTER JOIN to `coach_brain_entries`; new optional field `nearest_entry_confirmation_count: int \| None` on `CandidateListItem`; admin endpoint switched. Frontend: extended `CoachBrainCandidate` TS interface; new `<ConfirmationCountBadge>` helper rendered in card header (3 branches: `Confirms #N` / `New (no count)` / `New (no near match)`). Delivered via `/team` cross-stack coordination (sonnet-be + sonnet-fe). Prod E2E PASS — `Confirms #4` badge visible on first card of 80 pending. | done | L | L2-AUDIT-2026-04-27-H01 | FR-ADMN-12 | `4b9ae0a` + `68b407b` (PR #127) | `backend/app/repositories/coach_brain_candidate.py`, `backend/app/schemas/candidate_review.py`, `backend/app/api/v1/admin.py`, `backend/tests/unit/test_coach_brain_candidate_repo.py`, `backend/tests/unit/test_admin_candidates_api.py`, `frontend/src/api/admin.ts`, `frontend/src/pages/AdminCoachBrainCandidatesPage.tsx`, `frontend/src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx`, `frontend/src/api/__tests__/admin-candidates.test.ts` |
| L2-AUDIT-2026-04-27-H03 | **SRS FR-BRAIN-06 corrected to 7 nodes** (auditor H-03) — `lifecycle_decision` (FR-BRAIN-17) and `cove_verify` (FR-BRAIN-14 Should) sit between `validate_quality` and `format_entry` in the runtime graph. SRS prose updated; ADR-BRAIN-10 captures the supersession with the correct Must/Should labels. Two fixup commits: heading format alignment with neighbouring BRAIN ADRs, and FR-BRAIN-14 Must→Should label correction. | done | S | — | FR-BRAIN-06 | `cba1de2` + `be001b6` (PR #128) | `docs/SRS.md`, `decisions.md` |
| L2-AUDIT-2026-04-27-M02 | **Regression tests for `validate_quality` decision branches** (auditor M-02). 5 new pytest cases covering pass / review-band / reject-band / Phase 2 fallback. Pre-existing `test_validate_quality_gate_matrix` parametrize partially overlaps; net-new is the explicit `pass` path which the auditor specifically wanted documented. | done | S | — | FR-BRAIN-06 | `8d1bf47` (PR #128) | `backend/tests/unit/test_distillation_validate.py` |
| L2-AUDIT-2026-04-27-M03 | **Extract body-stats field tuple to module constant** (auditor M-03). `analysis_worker.py` had two copies of the same hardcoded 6-element tuple; extracted to `_USER_PROFILE_BODY_STATS_FIELDS: frozenset[str]` and replaced both call sites with dict comprehensions. New structural test asserts the constant matches the expected set. | done | S | — | — | `54b4dc4` (PR #128) | `backend/app/workers/analysis_worker.py`, `backend/tests/unit/test_analysis_worker.py` |
| L2-AUDIT-2026-04-27-M04 | **Closed M-04 as auditor-premise-incorrect** — investigation showed `handleApprove` already has its own try/catch that surfaces errors via `setActionError`. Initial `.catch` wrapper attempt landed (`0a271ff`), code review flagged it as dead code, reverted with rationale comment (`f87d3a3`). No behavior change; documents the decision in-source for future readers. | done | S | — | — | `0a271ff` + `f87d3a3` (PR #128) | `frontend/src/pages/AdminCoachBrainCandidatesPage.tsx`, `frontend/src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx` |
| L2-AUDIT-2026-04-27-M05 | **Assert `updated_at` advances on UPDATE-no-contradiction path** (auditor M-05). New pytest case sleeps 0.05s, runs `store_entry`, asserts `seed.updated_at >= original_updated_at` AND `seed.confirmation_count == 3`. Defends against TimestampMixin removal or partial-flush regression. | done | S | — | — | `6eb9089` (PR #128) | `backend/tests/unit/test_distillation_store.py` |

**Subagent-driven execution retro.** All three PRs delivered via subagent dispatch with two-stage review (spec compliance → code quality). Three review-driven fixup loops surfaced and resolved before merge: (1) ADR heading format misaligned with neighbouring BRAIN ADRs; (2) FR-BRAIN-14 mis-labeled as Must when it's Should; (3) M-04 outer `.catch` was dead code because `handleApprove` already has internal error handling. Per-task review caught all three before they shipped to prod. PR B used `/team` for cross-stack coordination (backend published API contract via SendMessage, frontend unblocked); PR A and PR C used single-implementer dispatches.

**Phase 3 transition gate: CLEARED.** All 8 Phase 3 Must FRs implemented, all auditor findings closed, full test suite green, migration 022 applied. 5 days before 2026-05-03 hard date.

**Related:** ADR-BRAIN-10 in `decisions.md`. Plans: `docs/superpowers/plans/2026-04-27-fr-brain-17-tombstone-contradicted.md`, `docs/superpowers/plans/2026-04-27-fr-admn-12-confirmation-count-on-card.md`, `docs/superpowers/plans/2026-04-27-pr-c-h03-mediums-bundle.md`.

## Completed — Expert Portal UX improvements (session 67–68)

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-EXPERT-19 | **Add annotated video to expert analysis detail page** — added `annotated_video_url` to `ExpertAnalysisDetail` schema + service, signed URL in endpoint via `StorageService`, `<video>` player in `ExpertAnalysisDetailPage.tsx`. Expert can now verify AI coaching against skeleton overlay. | done | M | — | FR-EXPV-03 | `225c0d1` | `backend/app/schemas/expert_review.py`, `backend/app/services/expert.py`, `backend/app/api/v1/expert.py`, `frontend/src/api/expert.ts`, `frontend/src/pages/ExpertAnalysisDetailPage.tsx` |
| L2-EXPERT-20 | **Render eval scores as structured UI** — replaced `JSON.stringify` dump with `EvalScoresCard` component showing faithfulness percentage (green/red badge), CoVe verified status, unsupported claims list. Non-technical expert can now interpret eval quality. | done | M | — | FR-EXPV-03 | `225c0d1` | `frontend/src/pages/ExpertAnalysisDetailPage.tsx` |
| L2-EXPERT-21 | **Update Expert Reviewer Guide doc v2.1** — fixed "other reviewers" → single-reviewer language, documented annotated video + structured eval scores, updated FAQ, kept `generate_expert_guide.cjs` for future updates. | done | S | L2-EXPERT-19, L2-EXPERT-20 | — | `225c0d1` | `Spelix_Expert_Reviewer_Guide.docx`, `generate_expert_guide.cjs` |

## Open — Post-Phase-3-gate cleanup (parked from session 62)

| ID | Title | Status | Size | Deps | SRS IDs | Notes |
|----|-------|--------|------|------|---------|-------|
| D-068 | **Remove unused `fireEvent` import from `AdminCoachBrainCandidatesPage.test.tsx`** — left dangling by the M-04 revert in session 62. Currently dead but harmless; eslint not configured so no lint warning fires. Drop the import on the next change to that test file. | pending | XS | — | — | Discovered during PR C T4 fixup. Schedule a 1-week wakeup if no other test edits land. |
| D-069 | **Consolidate `test_distillation_validate.py` test surface** — 2026-04-27 code review noted that the 5 new T2 named tests partially overlap the pre-existing `test_validate_quality_gate_matrix` parametrize. Future maintainers changing a threshold would need to update three test instruments. Pick one form (matrix or named) and migrate. Net-new coverage from T2 (the explicit `pass` path) is preserved either way. | pending | S | — | FR-BRAIN-06 | Schedule for Phase 4 kickoff when the multi-component RAGAS suite ships and `correctness` becomes populated. |

## Completed — L2 Sprint Day 17 — Commercial-gym quality gate fix (2026-04-24, session 61)

Private beta was blocked: the 3 atharva fixture videos (squat 20.6 s, bench 23.4 s, deadlift 26.2 s — all 1080×1920 portrait @ 60 fps, all commercial-gym shoots with 3-6 bystanders visible) were all rejected by the upload quality gate on prod. Investigation showed two compounding issues: `check_single_person` treated MediaPipe tracker re-acquisitions onto bystanders (during occlusion events at deep squat / supine bench / deadlift hinge) as "multiple people", rejecting with impossible user advice ("please film alone"); `check_framing` built the bbox from all 33 raw landmarks, so MediaPipe-hallucinated low-visibility landmarks clustered at the body centre shrank the bbox and pushed portrait framing below the 0.169 floor. The fix shipped in two PRs:

- **PR #121** (`ebfa4dd9`): anchor-based identity-jump detection in `check_single_person` (lifter centroid from first 3 high-visibility samples; reject only on sustained ≥4-consecutive or >30% off-anchor samples at >0.25 frame-width drift; new user_message "Could not consistently track a single lifter — try filming side-on with your full body in frame"); visibility-gated bbox in `check_framing` (skip landmarks with `sigmoid(visibility) < 0.5`; skip samples with <10 visible landmarks); `_FRAMING_MIN_FRACTION` 0.30 → 0.20. 8 new unit tests + 2 rewritten; 98 passed in test_quality_gates.py.
- **PR #122** (`b5b9d80f`): empirical follow-up — after PR #121 the squat still failed `framing` by 0.0009 (0.1115 vs 0.1125 portrait floor). Visibility-gating barely moved the squat metric (commercial-gym lifters at 3-4 m have high visibility on most landmarks). Lowered `_FRAMING_MIN_FRACTION` 0.20 → 0.18 (portrait floor 0.10125) per the spec's authorised follow-up path. 2 tests renamed + constants updated.

**Prod E2E verification:** Playwright MCP re-upload of all 3 fixtures as `atharva6905@gmail.com` on https://spelix.app post-deploy. Final gate metrics captured from prod DB:

| Fixture | Analysis ID | Duration | body_vis | framing (thr 0.10125) | single_person (thr 4) | Terminal status |
|---------|-------------|----------|----------|------------------------|------------------------|-----------------|
| Bench   | `e765a1ff` | 22.69 s | 0.6525 ✓ | **0.2479 ✓** | **0.0 ✓** | completed |
| Squat   | `71737b72` | 19.88 s | 0.6506 ✓ | **0.1116 ✓** (0.001 margin) | **0.0 ✓** | completed |
| Deadlift| `435065d5` | 25.40 s | 0.6559 ✓ | **0.1673 ✓** | **0.0 ✓** | processing (gate passed; scoring/coaching phase) |

All 3 fixtures now pass every gate check as filmed, unblocking private-beta launch on 2026-05-03. Screenshots: `e2e/screenshots/quality-gate-fix-prod-{squat,bench}.png` (local `.playwright-mcp/` captures).

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-QGATE-COMMERCIAL-GYM-01 | **Anchor-based `check_single_person` + visibility-gated `check_framing`.** Replaces per-pair hip-jump rejection rule with lifter-anchor centroid + sustained off-anchor detection. Bbox in framing check now filtered to `sigmoid(visibility) >= 0.5` landmarks. `_FRAMING_MIN_FRACTION` 0.30 → 0.20. User message rewritten: "Multiple people detected — please film alone" → "Could not consistently track a single lifter — try filming side-on with your full body in frame." 8 new unit tests + 2 rewritten. Security review PASS_WITH_FINDINGS (1 HIGH: stale "30%" copy — fixed in `10dc274` pre-merge). | done | L | — | FR-CVPL-04, FR-CVPL-06 | `ebfa4dd9` (PR #121) | `backend/app/cv/quality_gates.py`, `backend/tests/unit/test_quality_gates.py`, `backend/tests/integration/test_quality_gates_atharva_fixtures.py`, `backend/CLAUDE.md` (2 new gotcha blocks), `decisions.md` (ADR-QGATE-COMMERCIAL-GYM), `docs/superpowers/specs/2026-04-24-commercial-gym-quality-gate-design.md`, `docs/superpowers/plans/2026-04-24-commercial-gym-quality-gate-fix.md` |
| L2-QGATE-COMMERCIAL-GYM-02 | **Follow-up calibration — `_FRAMING_MIN_FRACTION` 0.20 → 0.18.** Empirical discovery from prod E2E: visibility-gating barely shifted the squat fixture's framing metric (lifter-occlusion frames aren't dominant in 90th-percentile bbox for this clip). Lowered the floor by the spec-authorised path to admit the 0.1115 squat case. 2 tests renamed + constants updated. No user-facing strings, no auth — spelix-security-reviewer not invoked. | done | S | PR #121 | FR-CVPL-04 | `b5b9d80f` (PR #122) | `backend/app/cv/quality_gates.py`, `backend/tests/unit/test_quality_gates.py` |
| L2-QGATE-COMMERCIAL-GYM-03 | **Prod E2E verification — all 3 atharva fixtures pass the gate.** Playwright MCP re-upload sequence: squat rejected on PR #121 (framing off by 0.0009) → PR #122 shipped → squat (71737b72) completed with framing=0.1116; bench (e765a1ff) completed with framing=0.2479; deadlift (435065d5) passed gate + in processing with framing=0.1673. All 3 with `single_person` metric=0.0 (anchor algorithm verified — was 3/4/5 hip jumps on the old rule). Console clean, no 4xx/5xx on the happy path. | done | M | L2-QGATE-COMMERCIAL-GYM-01, L2-QGATE-COMMERCIAL-GYM-02 | FR-CVPL-04, FR-CVPL-06 | `b5b9d80f` (post-merge Playwright on spelix.app) | `.playwright-mcp/` locally |

**Retro:** The spec correctly predicted the framing-threshold sensitivity and authorised the follow-up reduction in advance ("If the visibility-gated metric still falls under 0.1125, the floor is reduced further as a follow-up commit"). No code had to be re-thought post-E2E; the follow-up was a pure constant change + test rename. Bug discovery timeline — root cause mapped in under 30 min via prod DB query + visual frame inspection + code reading. Fix execution went through the spelix-cv-engineer agent in a worktree; main agent handled PR + CI + deploy + E2E + docs.

**Related:** ADR-QGATE-COMMERCIAL-GYM in `decisions.md`. Design spec: `docs/superpowers/specs/2026-04-24-commercial-gym-quality-gate-design.md`. Plan: `docs/superpowers/plans/2026-04-24-commercial-gym-quality-gate-fix.md`. Post-beta follow-up: YOLOv8 multi-person → primary-lifter crop (architectural correctness, deferred out of L2 sprint scope).

## Completed — L2 Sprint Day 17 — `process_analysis` streaq timeout fix (2026-04-25, session 61 follow-up)

While verifying the commercial-gym quality-gate fix end-to-end, the deadlift fixture's first prod run (analysis `435065d5`, streaq task `e6d23bc3`) revealed an unrelated pre-existing issue: `process_analysis` hit the 900 s per-task timeout exactly during post-gate LLM coaching + CoVe verification — `task process_analysis … timed out` in worker logs at `02:56:55 UTC` after starting `02:41:55 UTC`. DB stuck at `status='processing'`, quality gate had passed cleanly. Root cause: ADR-060's 670 s telemetry budget on a 22.8 s reference clip didn't account for CoVe iteration cost on longer outputs (each rep adds claim-extraction + verification LLM calls). Restored the ADR-058 safety net (1800 s) + added a string-check regression test guarding against future reductions.

**Prod E2E verification:** Re-uploaded `atharva-deadlift.mov` post-deploy via Playwright MCP. Analysis `0ac10ed6` reached `status=completed` in **~18 min** total (3 min queue+gate, 3 min processing-start, 10 min coaching+CoVe), well under the new 1800 s budget. Screenshot: `quality-gate-fix-prod-deadlift.png` showing "Analysis complete / Deadlift — conventional".

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-STREAQ-TIMEOUT-01 | **Raise `process_analysis` streaq timeout 900 → 1800 s.** Single-line decorator bump in `backend/app/workers/streaq_worker.py:150` plus 12-line comment update with the empirical history. New regression test `test_process_analysis_timeout_at_least_1800_seconds` reads `streaq_worker.py` source and regex-asserts `timeout >= 1800` on the `process_analysis` decorator — guards against future accidental reductions below the documented minimum. Red-green verified locally before push. No user-facing strings, no auth surface — `spelix-security-reviewer` not invoked. | done | S | L2-QGATE-COMMERCIAL-GYM-03 (surfaced the bug) | NFR-RELI-01 | `2d62f108` (PR #124) | `backend/app/workers/streaq_worker.py`, `backend/tests/unit/test_streaq_worker.py` |
| L2-STREAQ-TIMEOUT-02 | **Prod E2E verification — deadlift fixture `0ac10ed6` reaches `status=completed`.** Re-upload via Playwright MCP after PR #124 deploy. Total runtime ~18 min (well under new 1800 s budget). Same fixture timed out at exactly 900 s on prior run. Confirms timeout fix end-to-end. | done | S | L2-STREAQ-TIMEOUT-01 | — | `2d62f108` (Playwright on prod) | `quality-gate-fix-prod-deadlift.png` (local capture) |

**Retro:** Cost of the original ADR-060 reduction surfaced 2 weeks later under the L2-sprint deadlift fixture — the kind of latent breakage that only shows up on edge cases (longest video + most reps + multi-paragraph CoVe). Mitigation forward: when raising/lowering a per-task timeout, also write the regression test that codifies the new floor — `test_process_analysis_timeout_at_least_1800_seconds` would have flagged the ADR-060 reduction as a regression. Pattern adopted for future per-task budget changes.

**Related:** ADR-STREAQ-TIMEOUT-01 in `decisions.md` (supersedes ADR-060 timeout value). Post-beta follow-up: split `process_analysis` into separate streaq tasks for pose+gate+score (CV-bound) and coach+CoVe (LLM-bound) so each phase has its own budget + retry semantics — tracked as P3-FOLLOWUP-streaq-split.

## Completed — L2 Sprint — FR-EXPV-08 E2E walkthrough + reusable per-role test-account script (2026-04-22, session 60)

Post-merge 3-role Playwright MCP verification on https://spelix.app against merge commit `4455ca1`. Walked logged-out → regular user → expert_reviewer → admin → back-to-expert. Full flag lifecycle verified: expert submits flag → auto-switch to My Flags tab → admin GETs list + PATCH-resolves → expert sees `status=resolved` on re-fetch. 0 console errors, 0 4xx/5xx network calls on the happy path.

Also codified the per-role E2E test-account provisioning pattern (ADR-E2E-01): new one-off script `backend/scripts/oneoff/e2e_fr_expv_08_test_accounts.py` creates `e2e-regular@spelix.internal`, `e2e-expert@spelix.internal`, `e2e-admin2@spelix.internal` with the right `app_metadata` in one `POST /auth/v1/admin/users` call each. Creds pulled ephemerally from `/home/deploy/spelix/.env.prod` via SSH; temp file deleted after use. Closes session-59 handoff §7 follow-up ("use separate test accounts for E2E") as infrastructure.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-E2E-FR-EXPV-08 | **3-role interactive Playwright MCP walkthrough of FR-EXPV-08 on prod.** Verified: (a) role gate — regular user → `/expert/thresholds` redirects back to `/upload`; (b) expert flow — `/expert/thresholds` renders 4 sections (squat 13 rows, bench 10, deadlift 15, control 3) with correct values + provenance citations, modal pre-populates Section/Key/Current/Citation, submit disabled until rationale ≥20 + citation ≥5, `POST /flags` returns 201, auto-switch to My Flags tab shows `current=5 proposed=8 status=open`; (c) admin API flow — `GET /admin/threshold-flags?status=open` returns 200 with the expert's flag, `PATCH /admin/threshold-flags/{id}` with `status=resolved` returns 200 with `resolved_by + resolved_at`, follow-up `?status=resolved` confirms DB flip; (d) reverse-check — expert signs back in, My Flags tab now shows `status=Resolved`. Screenshots at `e2e/screenshots/fr-expv-08-*.png`. Console clean, no 4xx/5xx on the happy path. | done | M | FR-EXPV-08 (PR #118) | FR-EXPV-08 | `4455ca1` (walkthrough ran against this merge SHA) | `e2e/screenshots/fr-expv-08-expert-my-flags.png`, `e2e/screenshots/fr-expv-08-expert-flag-resolved.png` |
| L2-E2E-TESTACCOUNTS | **Reusable per-role E2E test-account provisioning script** via Supabase service-role admin API. Creates 3 accounts (regular / expert_reviewer / admin+biomechanics_qualified) with email_confirm=true and inline `app_metadata` in a single POST per account. Uses stdlib `urllib` only; reads creds from a CREDS_FILE-pointed `.env`-style file. Passwords generated per-invocation (20-char alphanumeric) and printed once to stdout — not persisted. | done | S | — | — | (branch `docs/session-60-close`) | `backend/scripts/oneoff/e2e_fr_expv_08_test_accounts.py`, `decisions.md` (ADR-E2E-01) |

## Completed — L2 Sprint — FR-EXPV-08 Threshold Validation UI (2026-04-22, session 60)

PR #118 merged to `main` as `4455ca1` via `mcp__github__merge_pull_request` with `merge_method="merge"` (13 commits preserved on the branch). Closes FR-EXPV-08 (Phase 3, Should). Backend: **1794 passed, 21 skipped** (full unit suite, fresh local verification) including 21 new FR-EXPV-08 tests. Frontend FR-EXPV-08-scoped: **10/10 passed** across 3 new test files. Ruff + pyright + tsc clean. CI 7/7 green pre-merge (backend tests 1m53s, frontend tests 1m36s, backend lint 36s, frontend lint 31s, secret scan 15s, Vercel preview, Vercel comments).

**What shipped:** Expert Reviewer in-portal threshold validation workflow. Reviewer views `config/thresholds_v1.json` angle thresholds (squat/bench/deadlift/control filtered from full config) at `/expert/thresholds`, flags any that conflict with literature via a modal form (≥20-char rationale + ≥5-char citation + numeric proposed value enforced client-side + Pydantic + DB CHECK). Admin resolves flags via `/admin/threshold-flags` (list with status filter + PATCH to resolve/reject). Flags are audit-only — UI never writes to `config/thresholds_v1.json` (FR-SCOR-11 preserved: PR review IS the approval path).

**Scope boundaries enforced:** no in-UI value editing, no auto GitHub issue creation, non-angle sections (`scoring_weights`, `phase_multipliers`, `experience_tolerance`, `score_descriptors`, `confidence_landmark_weights`) filtered out of the listing.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| FR-EXPV-08 | **Expert Reviewer threshold validation UI.** Full-stack feature: migration 022 with RLS (reviewer sees own + admin sees all; INSERT bound to `reviewer_id = auth.uid()`; UPDATE admin-only with `WITH CHECK`), `ThresholdFlag` model + `ThresholdFlagRepository` (create with refresh, update_status with RETURNING), 5 Pydantic schemas (`ThresholdRow`, `ThresholdListing`, `ThresholdFlagCreate`, `ThresholdFlagResponse`, `ThresholdFlagResolveAction`), `ThresholdFlagService` with current-value + citation snapshot at submission (immutable via repo), 5 endpoints (3 expert + 2 admin), `ExpertThresholdsPage` tabbed UI (Current thresholds / My flags) with auto-tab-switch after submission, `ThresholdFlagModal` form with client-side validation + reset-on-row-change. | done | L | — | FR-EXPV-08 | `4455ca1` (PR #118) | backend/alembic/versions/022_add_threshold_flags.py, backend/app/models/threshold_flag.py, backend/app/repositories/threshold_flag.py, backend/app/schemas/threshold_flag.py, backend/app/services/threshold_flag.py, backend/app/api/v1/expert.py, backend/app/api/v1/admin.py, backend/tests/unit/{test_threshold_flag_repo.py, test_threshold_flag_schemas.py, test_threshold_flag_service.py, test_expert_thresholds_api.py, test_admin_threshold_flags_api.py}, frontend/src/pages/ExpertThresholdsPage.tsx, frontend/src/pages/ExpertPortalPage.tsx, frontend/src/components/ThresholdFlagModal.tsx, frontend/src/api/expert.ts, frontend/src/routes.tsx, frontend/src/{pages,components,api}/__tests__/{ExpertThresholdsPage,ThresholdFlagModal,expert-thresholds}.test.{ts,tsx}, decisions.md (ADR-EXPV-08), docs/superpowers/plans/2026-04-21-fr-expv-08-threshold-validation-ui.md |

**Audit/review summary:** Final end-to-end code review (superpowers:code-reviewer) PASS — 0 Critical, 2 Important (fragile useEffect cross-dependency + missing tab-switch on submit) both fixed pre-PR in commit `f023232`. RLS security review PASS — snapshot columns (`reviewer_id`, `section`, `key`, `current_value`, `current_citation`, `proposed_value`, `proposed_citation`, `rationale`) are structurally unreachable from any UPDATE path; `ThresholdFlagResolveAction.status` Literal excludes "open" so terminal transitions are one-way via API. SaMD language review clean — no "injury risk" / "safety score" in any user-facing string.

**Subagent-driven execution summary:** 11-task plan authored + executed via fresh-subagent-per-task + two-stage review (spec compliance via spelix-auditor, code quality via superpowers:code-reviewer) per superpowers:subagent-driven-development. Task 1 (migration) needed 1 fix cycle (RLS SELECT over-permissive + constraint naming). Task 2 (model) needed 1 fix cycle (flaky ordering test + missing `refresh`). Task 5 pattern correction in the plan template: `monkeypatch.setattr` doesn't work with FastAPI `Depends()` — corrected to `app.dependency_overrides[dep]` on a fresh `FastAPI()` with mounted router (applied forward to Task 6).

**Related:** Plan `docs/superpowers/plans/2026-04-21-fr-expv-08-threshold-validation-ui.md`. ADR-EXPV-08 in `decisions.md`. SRS FR-EXPV-08 (§3.15, Phase 3 Should), FR-SCOR-11 (§3.9 PR-review invariant).

## Completed — L2 Sprint Day 15 — Phase 3 E2E audit full closure (2026-04-21, session 59)

Full E2E production verification ran against spelix.app from all 3 user perspectives (regular user, admin, expert reviewer) covering 20 verification tasks. Found 1 blocker (chat 500) + 4 non-blockers; all 5 resolved this session across 4 PRs. Backend tests 1769 → 1773 (+4). Frontend tests 347 → 352+ (+5 net). Beta invites unblocked.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-E2E-01 | **Chat endpoint 500 — MissingGreenlet fix.** `ChatService.send_message` called `get_by_id` (no eager load) then accessed `analysis.coaching_result.structured_output_json` — SQLAlchemy 2.0 async lazy-load outside greenlet context raised `MissingGreenlet`, HTTP 500 for every follow-up chat. Swap to existing `get_by_id_with_relations` (selectinloads `coaching_result`). Plus 7 mock updates in `test_chat_service.py` and a new integration test (`test_chat_greenlet.py`) using 2 independent engines to prove old path crashes, new path works. Verified on prod: POST `/chat` returned 201, contextual AI response rendered. | done | S | — | FR-AICP-17 | `82cfa80` | `backend/app/services/chat.py`, `backend/tests/unit/test_chat_service.py`, `backend/tests/integration/test_chat_greenlet.py` |
| L2-E2E-02 | **Citation inline `[N]` markers.** Coaching prose (summary, strengths, correction_plan, issues) had no inline `[N]` markers — frontend `CitationTooltip.parseWithCitations` worked correctly but had nothing to parse. Two-point fix: (1) rewrote `_build_system_prompt` citation instruction to mandate inline `[N]` placement in named prose fields, anchored on "When a Retrieved Evidence section is provided below"; (2) appended `[N]` instruction to 4 Pydantic field descriptions in `CoachingOutput`/`Issue` (instructor passes these to Claude via JSON Schema). Plus ValidateOutputTool `strengths[]` scan addition (L2-E2E-02a) and CoVe Step 4 preservation clause (L2-E2E-02b). Verified on prod: multiple `[1]`/`[2]`/`[5]` superscript tooltips render in coaching text; hover shows paper title + "Retrieved Source N (year)". | done | M | L2-E2E-02a, L2-E2E-02b | FR-AICP-06, FR-AICP-11, FR-RESL-06 | `4571102` | `backend/app/schemas/coaching.py`, `backend/app/services/coaching.py`, `backend/app/services/validate_output.py`, `backend/app/services/cove.py`, `backend/tests/unit/test_validate_output.py`, `backend/tests/unit/test_coaching.py`, `backend/tests/unit/test_coaching_schema_descriptions.py`, `backend/tests/unit/test_cove.py` |
| L2-E2E-02a | **ValidateOutputTool scans `strengths[]` for `[N]` markers.** Previously scanned summary/correction_plan/recommended_cues/issues but missed strengths — after L2-E2E-02 asked Claude to embed markers there, invalid indices would pass validation unchecked. One-line scan addition + dedicated test fixture with out-of-range `[5]` only in strengths. | done | S | — | FR-AICP-11 | `bd5da78` | `backend/app/services/validate_output.py`, `backend/tests/unit/test_validate_output.py` |
| L2-E2E-02b | **CoVe revision prompt preserves `[N]` markers.** Step 4 (Sonnet revision) rewrites CoachingOutput to remove unverified claims — without explicit preservation instruction, Sonnet could strip inline `[N]` markers on claims that survive verification, defeating L2-E2E-02. Added preservation paragraph naming all 4 prose fields; test asserts prompt contains `[N]`, preservation keyword, and `==4` field names. | done | S | L2-E2E-02 | FR-BRAIN-14 | `b4728ee` | `backend/app/services/cove.py`, `backend/tests/unit/test_cove.py` |
| L2-E2E-03 | **Error rendering against `[object Object]`.** Two-layer fix. First pass (PR #115, `7d6bcf8`): defensive `typeof error === "string"` guard in ResultsPage + 3-arm ternary in `useAnalysisDetail` catch branch + regression test. On prod the bug persisted — second pass (PR #116, `fea02e1`) identified the real root cause in `api/analyses.ts`: when backend returns 404 with nested `{"detail": {"error": {...}}}`, the nullish-coalescing chain extracted the detail OBJECT, then `new Error(obj)` coerced via `String(obj)` producing the literal string `"[object Object]"` as `err.message`. Type-guard the raw message in all 3 4xx paths (detail, status, list). Plus 3 regression tests (object-nested 404, top-level error.message, string detail). Verified on prod: alert now shows "Failed to fetch analysis". | done | S | — | — | `fea02e1` | `frontend/src/pages/ResultsPage.tsx`, `frontend/src/hooks/useAnalysisDetail.ts`, `frontend/src/api/analyses.ts`, `frontend/src/api/__tests__/analyses.test.ts`, `frontend/src/pages/__tests__/ResultsPage.test.tsx`, `frontend/src/hooks/__tests__/useAnalysisDetail.test.ts` |
| L2-E2E-04 | **Worker `(unhealthy)` fix.** Two-layer fix. First pass (PR #115): added `r.ping()` before `r.exists()` to force auth round-trip + `socket_connect_timeout=3` + bumped `start_period` 15s→40s to cover first heartbeat write. On prod still unhealthy — second pass (PR #116): ran the healthcheck command manually via `docker exec`, got `ModuleNotFoundError: No module named 'redis'`. The worker's `python` is system Python, not the uv venv; `redis` package lives in `/app/.venv`. Switched healthcheck from `python` → `/app/.venv/bin/python`. Verified on prod: `docker ps` shows `spelix-worker-1 (healthy)`. | done | S | — | NFR-OPER-02 | `fea02e1` | `docker-compose.prod.yml` |
| L2-E2E-05 | **LangSmith tracing enabled on prod.** Added 3 env vars to `/home/deploy/spelix/.env.prod` via SSH heredoc: `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY=<secret>`, `LANGCHAIN_PROJECT=spelix-prod`. Recreated containers via `docker compose up -d --no-build` (restart does NOT re-read env). Confirmed env vars loaded in worker container. Triggered test analysis `a2a78e1f`; completed successfully without LangSmith-related errors. Manual dashboard verification on smith.langchain.com pending user action. | done | S | — | FR-AICP-20 | ops only (no repo change) | `.env.prod` on droplet |
| L2-E2E-06 | **Documentation — api/analyses.ts string-safety convention.** Inline JSDoc at top of file documenting that any `throw "..."` from fetch functions surfaces directly to users via `useAnalysisDetail`, so strings MUST be user-safe — never raw backend detail. Follow-up to code-review feedback on L2-E2E-03's behavioral change to pass thrown strings through. | done | S | L2-E2E-03 | — | `4571102` (bundled) | `frontend/src/api/analyses.ts` |

**5 PRs merged this session:** #113 (chat 500), #114 (citations), #115 (polish bundle v1), #116 (polish bundle v2 — root-cause follow-up), plus `.env.prod` ops for LangSmith.

**Retro:** Two bugs in this session (L2-E2E-03 and L2-E2E-04) required second-pass PRs because the first pass used defensive-coding instead of root-cause fixes. Lesson: when an investigator explicitly identifies a specific coercion/execution site, fix THAT site first; multi-layer defensive guards are weaker than one correct source fix. Related ADR-ROOTCAUSE-01. Worker healthcheck retro: always manually `docker exec <container> <healthcheck-command>` before committing a healthcheck change — "the image has Python" is not equivalent to "our deps are on the system path".

## Completed — L2 Sprint Day 9 — D-040 / D-041 hybrid rep detection + degenerate scoring (2026-04-18, session 45)

PR #84 merged to `main` as `bc17250` and auto-deployed via CI. Closes D-040 + D-041 (FR-CVPL-15, FR-REPM-01, FR-REPM-05, FR-SCOR-02, FR-SCOR-04, FR-SCOR-07). Backend: 1690 → 1693 tests (+1 D-040 hybrid + 6 D-041 net − churn). Frontend unchanged. Ruff + pyright + tsc clean. E2E on prod verified: re-upload of `atharva-bench-nw-10s-720p.mp4` returned **1 rep** (was **0** on session 44), Confidence "Low", form scores all populated (Overall 7.8, Movement Quality 8.0, Technique 8.5, Path & Balance 5.2, Control 10.0). No "Very Low + 10.0" contradiction. Screenshot `e2e/screenshots/d040-d041-post-merge-prod-verified.png`.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-D040-01 | Initial pure peak/valley rewrite of `detect_reps` via `scipy.signal.find_peaks` (superseded by L2-D040-06 after calibration) | done | M | — | FR-CVPL-15 | `f237ccf` | `backend/app/cv/rep_detection.py` |
| L2-D040-02 | Update `test_rep_detection.py` for peak/valley semantics (delete 8 obsolete, update 3, add 4 new) | done | S | L2-D040-01 | — | `109abfc` | `backend/tests/unit/test_rep_detection.py` |
| L2-D040-03 | Clarify `_BENCH_*_L` landmark-naming comment in `signal_processing.py` — subject-right, not body-left | done | S | — | — | `b15f770` | `backend/app/cv/signal_processing.py` |
| L2-D041-01 | Degenerate-scoring short-circuit in `pipeline.py` Step 9b — `_is_degenerate_scoring_input(rep_metrics, session_confidence)` helper + if/else branch writing None to all 5 `form_score_*` on empty reps OR `session_confidence < 0.50` | done | S | — | FR-SCOR-02, FR-SCOR-04, FR-SCOR-07 | `a7477f0` | `backend/app/services/pipeline.py`, `backend/tests/unit/test_pipeline.py` |
| L2-D040-05 | D-040 smoke script `scripts/oneoff/smoke_rep_detection_d040.py` for partial-lockout regression fixture | done | S | L2-D040-01 | — | `41100b8` | `backend/scripts/oneoff/smoke_rep_detection_d040.py` |
| L2-D040-06 | **Pivot** to hybrid detector (state-machine primary + peak/valley fallback) after fixture calibration showed pure peak/valley over-counts on noisy real-video signals (`atharva-bench.mov` 5→21, `atharva-squat.mov` 5→14). Strict Pareto improvement: 3 partial-lockout fixtures unlocked, 0 regressions. Adds `TestHybridStateMachineWins` distinguishing test | done | M | L2-D040-01, L2-D040-02 | FR-CVPL-15 | `dffa59e` | `backend/app/cv/rep_detection.py`, `backend/tests/unit/test_rep_detection.py` |
| L2-D040-07 | spelix-auditor fixes on PR #84 — H-2 asymmetric-hysteresis explanatory comment, M-3 smoke-script docstring, M-4 `probe_duration_seconds` patch in D-041 integration tests, M-5 corrected pre-existing MediaPipe landmark-indexing comment in `signal_processing.py` | done | S | L2-D040-06, L2-D041-01 | — | `e35b86d` | `backend/app/cv/rep_detection.py`, `backend/app/cv/signal_processing.py`, `backend/tests/unit/test_pipeline.py`, `backend/scripts/oneoff/smoke_rep_detection_d040.py` |
| L2-D040-08 | PR #84 → CI 6/6 green (Backend Tests 2m03s, Backend Lint 34s, Frontend Lint 27s, Frontend Tests 1m29s, Secret Scanning 15s, Vercel green) → merge (`merge_method="merge"`) → Deploy to Production auto-run → droplet `bc17250` + containers healthy → Playwright E2E on prod confirms 1 rep detected, form scores populated, no console errors / 4xx-5xx on the flow | done | M | L2-D040-07 | — | `bc17250` | PR #84 |

Auditor verdict: PASS_WITH_FINDINGS (0 CRITICAL; 2 HIGH → H-2 fixed in `e35b86d`, H-1 deferred to D-042; 5 MEDIUM → M-3/M-4/M-5 fixed in `e35b86d`, M-1 declined as docstring-sufficient, M-2 deferred to D-043). Security verdict: PASS (0 findings across 7 checks — SaMD language, auth scope, RLS, secrets, error leakage, injection, FR-SCOR-10 confidence label).

---

## Completed — L2 Sprint Day 7 — P3-006 Coach Brain Expert Review Queue (2026-04-17, session 43)

PR #82 merged to `main` as `3bffdd9` and deployed via CI. Closes P3-006 (FR-ADMN-12, FR-BRAIN-07, FR-BRAIN-18). Backend: 1681 → 1687 tests (+38 net including audit-fix additions), ruff + pyright clean. Frontend: 272 → 290 tests (+18), tsc clean. E2E smoke on prod: route live, non-admin → 403, graceful "Failed to load" state — both endpoints reachable at `api.spelix.app`. 11 real `coach_brain_candidates` from session 42 ready for admin review.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-PHASE3-B3-01 | Repo helpers — `list_pending_ordered` (overall → faithfulness → created_at DESC), `count_pending`, `get_by_id_for_update` (SELECT FOR UPDATE) | done | S | — | FR-ADMN-12 | `475e687` | `backend/app/repositories/coach_brain_candidate.py`, `backend/tests/unit/test_coach_brain_candidate_repo.py` |
| L2-PHASE3-B3-02 | Pydantic v2 schemas — `CandidateListItem`, `ApproveRequest` (min_length=5 max_length=500), `RejectRequest` (strip + min_length=1), `ApproveResponse`, `RejectResponse`, `PendingQueueStats` | done | S | L2-PHASE3-B3-01 | FR-ADMN-12, FR-BRAIN-07 | `246e742` | `backend/app/schemas/candidate_review.py`, `backend/tests/unit/test_candidate_review_schemas.py` |
| L2-PHASE3-B3-03 | `CandidateReviewService.approve` — INSERT entry (status=active, confirmation_count=1 per FR-BRAIN-18) → embed + Qdrant upsert → UPDATE candidate (review_status=approved, promoted_entry_id) → commit; rollback on Qdrant failure (`QdrantUpsertFailed`); concurrent-approve race guard via `CandidateAlreadyReviewed` | done | M | L2-PHASE3-B3-02 | FR-BRAIN-07, FR-BRAIN-18 | `eac2546` | `backend/app/services/candidate_review.py`, `backend/tests/unit/test_candidate_review_service.py` |
| L2-PHASE3-B3-04 | `CandidateReviewService.reject` regression locks — status flip + rejected_reason + idempotency on non-pending | done | S | L2-PHASE3-B3-03 | FR-BRAIN-07 | `2bf7b92` | `backend/tests/unit/test_candidate_review_service.py` |
| L2-PHASE3-B3-05 | Admin router — `GET /admin/coach-brain/candidates` + `/stats` + `POST /{id}/approve` + `POST /{id}/reject` with 404/409/502 error envelopes and admin-only `get_admin_user` guard | done | M | L2-PHASE3-B3-03 | FR-ADMN-12, FR-BRAIN-07 | `6649012` | `backend/app/api/v1/admin.py`, `backend/tests/unit/test_admin_candidates_api.py` |
| L2-PHASE3-B3-06 | Frontend API client — `listCoachBrainCandidates`, `getCoachBrainCandidateStats`, `approveCoachBrainCandidate`, `rejectCoachBrainCandidate` + TS types | done | S | L2-PHASE3-B3-05 | FR-ADMN-12 | `f3c2ccc` | `frontend/src/api/admin.ts`, `frontend/src/api/__tests__/admin-candidates.test.ts` |
| L2-PHASE3-B3-07 | `AdminCoachBrainCandidatesPage` — single-card review UI with 3-mode interaction (view/edit/reject), 4-dim eval scorecard, CoVe banner, compensation banner, nearest-entry badge, source-analysis links, `a/r/e/s` keyboard shortcuts; route registered + admin dashboard link | done | L | L2-PHASE3-B3-06 | FR-ADMN-12, FR-BRAIN-07, NFR-USAB-05 | `6d9b618` | `frontend/src/pages/AdminCoachBrainCandidatesPage.tsx`, `frontend/src/pages/__tests__/AdminCoachBrainCandidatesPage.test.tsx`, `frontend/src/routes.tsx`, `frontend/src/pages/AdminPage.tsx` |
| L2-PHASE3-B3-08 | ADR-BRAIN-REVIEW-01 (near-atomic approve; FR-BRAIN-18 interpretation; L2 deviations deferred to D-037/038/039) + backlog close | done | S | — | — | `606306f` | `decisions.md`, `backlog.md` |
| L2-PHASE3-B3-09 | Audit fixes from spelix-auditor + spelix-security-reviewer — null-out error detail (no vendor-exc leak), prompt-injection denylist (HTTP 422), 4-dim eval scorecard (FR-ADMN-12 H-01), vector-client dep wrap (HTTP 503) | done | M | L2-PHASE3-B3-07, L2-PHASE3-B3-08 | FR-ADMN-12 | `88682cd` | `backend/app/api/v1/admin.py`, `backend/app/services/candidate_review.py`, `backend/tests/unit/test_candidate_review_service.py`, `backend/tests/unit/test_admin_candidates_api.py`, `frontend/src/pages/AdminCoachBrainCandidatesPage.tsx`, `decisions.md` |
| L2-PHASE3-B3-10 | PR #82 → CI green (backend tests 1m58s, frontend 1m26s, ruff 36s, pyright, Vercel) → merge (`merge_method="merge"`) → Deploy to Production via SSH → droplet HEAD `3bffdd9`, containers healthy → Playwright smoke confirms route live + 403 auth guard | done | M | L2-PHASE3-B3-09 | — | `3bffdd9` | PR #82 |

## Completed — Coach Brain + Papers Retrieval Unblock (2026-04-17, session 42)

Five bugs silently inert-ed the entire retrieval-eval-distillation chain since Phase 2 shipped. Discovered during Priority 1 flag-flip verification when a real bench upload completed with `eval_scores=NULL`. Five PRs (#78–#81) merged, all 5 fixed, end-to-end verification produced 11 real `coach_brain_candidates` rows for analysis `73f9a137-c528-4f11-b833-48c638b5d5fc`.

| ID | Title | Status | PR | Commits |
|---|---|---|---|---|
| FIX-RETRIEVAL-01 | `papers_rag` Qdrant missing `exercise` payload index. `ensure_collections` refactored — `add_brain_indexes: bool` → `payload_index_fields: tuple[str, ...]`, papers_rag gets `('exercise',)`, coach_brain gets `('exercise','status')`. One-shot script backfilled the prod collection's index over the 39 pre-existing points. FR-AICP-15, ADR-RAG-03, ADR-BRAIN-03. | done | #78 | `691c28d` (test) + `29fe2de` (fix) + `e36737e` (review polish) + `328d4f1` (one-shot) |
| FIX-RETRIEVAL-02 | `retrieve_coach_brain` (agent path) AND `DualCollectionOrchestrator.retrieve` (imperative path) both hardcoded `status='active'` filter, excluding all 24 seed entries. Both changed to `MatchAny(['active','seed'])` per FR-BRAIN-05 cold-start intent. FR-BRAIN-04, FR-BRAIN-05, ADR-BRAIN-08. | done | #78 | `3985134` (test) + `f52aab2` (agent fix) + `d9c1240` (imperative fix + test update) |
| FIX-RETRIEVAL-03 | Two bench seed entries contained prohibited SaMD language ("rotator cuff impingement risk", "risking sternum or rib injury"). Surfaced by FIX-RETRIEVAL-02 (seeds now reach LLM). Sanitized in `scripts/seed_coach_brain.py` for future ingests; `scripts/oneoff/sanitize_seed_samd_content.py` repairs already-polluted prod Postgres + Qdrant payloads (run successfully on 2026-04-17). | done | #78 | `d9c1240` |
| FIX-RETRIEVAL-04 | `retrieval.py:237` (`dense_search` chunk parser) hardcoded `payload['text']` but coach_brain payloads use `content`. Cohere Rerank returned 400 "documents must not contain only empty strings" on every brain call. Fix: `text=payload.get("text") or payload.get("content","")` + regression test for the coach_brain payload shape. | done | #79 | `d971034` |
| FIX-RETRIEVAL-05 | `_maybe_enqueue_distillation` checked `eval_scores.overall` (Phase 4 RAGAS aggregate, not yet shipped per ADR-RAG-04). Phase 2 only populates `faithfulness`. Gate silently rejected every analysis. Fix: read `overall` first, fall back to `faithfulness` with the same 0.6 floor. ADR-PHASE2-EVAL-FALLBACK. | done | #80 | `95e060a` |
| FIX-RETRIEVAL-06 | `validate_quality` node at `validate.py:29` had the same `overall`-only check. With FIX-RETRIEVAL-05 the gate fired, but the distillation graph then returned `validation_decision=reject`. Same fallback applied; node now returns `review` (not `pass` — `correctness` is still missing) so candidates flow through to lifecycle/CoVe/store. ADR-PHASE2-EVAL-FALLBACK. | done | #81 | `dc35d8c` |

**Final E2E proof:** Analysis `73f9a137-c528-4f11-b833-48c638b5d5fc` (T_SUBMIT 10:02:32Z, completed t+217s): `eval_scores.faithfulness=0.82` → gate fired → `validate_quality=review` → distillation graph wrote **11 candidate rows** with `lifecycle_decision=ADD`, `review_status=pending`. Sample contents: real bench coaching cues ("Tuck your elbows and bend the bar outward...", "Set elbows at 45–75°..."). Phase 3 Batch 3 (P3-006 review queue) is unblocked.

Backend test count: 1641 → 1649 passing (+8 regression guards across 4 PRs), 25 skipped, 0 failing. Ruff clean, pyright `app/` 0 errors. See ADR-BRAIN-08 (seed retrievability) + ADR-PHASE2-EVAL-FALLBACK (faithfulness fallback) + backend/CLAUDE.md "Coach Brain retrieval — seed is retrievable" section.

### Discovered backlog items (post-L2 follow-ups)

| ID | Title | Status | Size | SRS / ADR |
|---|---|---|---|---|
| M-04 | Re-embed 24 seed Coach Brain points with FR-BRAIN-03 contextualized prefix (`exercise:{exercise} phase:{phase} type:{entry_type}\n{content}`). Current seeds were embedded with raw content only — explains why `retrieval_source=papers_only_fallback` even with seeds eligible. One-shot script + Cohere re-embed. | done — `a0a86fc` (PR #85). Re-embed ran successfully on prod (24/24 seeds re-embedded with prefix). Prod E2E post-re-embed STILL shows `retrieval_source=papers_only_fallback` on a bench upload — proves the papers_only_fallback symptom has a different root cause than missing prefix. Re-embed left in place (cannot be worse than prior state). Investigation tracked as D-045. | M | FR-BRAIN-03, ADR-BRAIN-02 |
| M-05 | Bump `BrainCoveService` Haiku 4.5 `max_tokens` from 1024 to ≥2048 OR shorten verification prompt. All 11 candidates from session 42 carry `cove_verified=false` because the verification call hits max_tokens × 3 retries. Not blocking distillation, but Batch 3 reviewers will see "evaluation_failed" CoVe banners on every candidate until fixed. | done — `a0a86fc` (PR #85). Question 256→512, answer 512→2048. TDD-verified (new `test_verify_claim_uses_adequate_max_tokens` asserts both ceilings via `await_args_list` kwarg introspection). Not exercised on prod this session — faithfulness gate rejected the verification E2E analysis, so distillation did not fire. Will be exercised on first subsequent distillation-eligible run. | S | FR-BRAIN-14, ADR-DISTILL-03, ADR-DISTILL-06 |
| M-06 | When Phase 4 RAGAS aggregate ships `eval_scores.overall` + `eval_scores.correctness`, the Phase 2 faithfulness fallbacks in `_maybe_enqueue_distillation` and `validate_quality` become inert (correct precedence). Add a check at Phase 4 kickoff that overall takes precedence and document the deprecation path for the fallbacks. | pending | S | FR-AICP-08, ADR-PHASE2-EVAL-FALLBACK |

## Completed (Phase 0 Core Build)

B-001–B-011, B-015–B-019, B-023–B-025, B-027–B-032, B-035–B-038, B-042 — all verified clean by audit.

Items B-012, B-013, B-020, B-022, B-026, B-033, B-034, B-039, B-040, B-041 had audit findings — reclassified as fix tasks below.

---

## Completed — Audit Fixes (2026-04-09)

All 12 CRITICAL and 16 HIGH findings resolved. 28 tasks (B-043–B-070) done.
Backend: 601 tests, 95% coverage. Frontend: 131 tests, tsc clean. ruff/pyright clean.

B-043–B-054 (CRITICAL): confidence thresholds unified, TUS upload implemented, status transition fixed, env vars aligned, three-tier disclaimer added, rep count + timestamp in summary, status labels corrected, duration validation added, FFprobe check added, barbell detection wired, pipeline tests written (90% cov), synthetic video fixtures created.

B-055–B-070 (HIGH): ErrorBoundary wired, button disabled fixed, sortable table added, confidence guidance text per level, video download link, admin Redis injected, single-person gate, resolution gate, occlusion warning, .dockerignore created, non-root Docker user, .gitignore updated, JWKS ES256 tests, PDF isolation tests, worker coverage 92%, OpenAPI types regenerated (1318 lines).

### MEDIUM — Fix During Phase 1

| ID | Title | Status | Size | Deps | SRS IDs | Audit Ref | Files |
|----|-------|--------|------|------|---------|-----------|-------|
| B-071 | Refactor InsightsService + AdminService to use repositories | done | M | — | — | M-1 | `services/insights.py`, `services/admin.py` |
| B-072 | Use Literal types in AnalysisCreate schema | done | S | — | — | M-2 | `schemas/analysis.py` |
| B-073 | Add `weight_kg` to AnalysisCreate schema | done | S | — | FR-REPM-06 | M-4 | `schemas/analysis.py` |
| B-074 | Pin mediapipe to exact version | done | S | — | — | M-6 | `pyproject.toml` |
| B-075 | Add JWT issuer validation | done | S | — | — | M-7 | `api/deps.py` |
| B-076 | Add `.nvmrc` + `engines` field | done | S | — | — | M-9 | `frontend/.nvmrc`, `frontend/package.json` |
| B-077 | CI: use `uv sync --frozen` | done | S | — | — | M-10 | `.github/workflows/ci.yml` |
| B-078 | Pin `uv` Docker image tag | done | S | — | — | M-11 | `backend/Dockerfile` |
| B-079 | Multi-stage Dockerfile | done | M | B-064, B-065 | — | M-12 | `backend/Dockerfile` |
| B-080 | Add `.env.*` wildcard to `.gitignore` | done | S | — | — | M-13 | `.gitignore` |
| B-081 | Fix TrendChart tooltip — show label not decimal | done | S | — | FR-RESL-08 | M-14 | `TrendChart.tsx` |
| B-082 | Fix AdminPage raw status strings + invalid status | done | S | — | Appendix B | M-15 | `AdminPage.tsx` |
| B-083 | Extract shared API_BASE constant | done | S | — | — | M-16 | `src/api/*.ts`, `ResultsPage.tsx` |
| B-084 | Test coaching retry paths (529, timeout, 400) | done | S | — | — | M-17 | `tests/unit/test_coaching.py` |
| B-085 | Test deps.py edge branches (empty sub/email, UUID) | done | S | — | — | M-18 | `tests/unit/test_auth.py` |
| B-086 | Test rep detection zero-rep + partial rep | done | S | — | — | M-19 | `tests/unit/test_rep_detection.py` |
| B-087 | Test GET /analyses/{id} and /status endpoints | done | S | — | — | M-20 | `tests/unit/test_analysis_api.py` |
| B-088 | Test rate limit 10th-request boundary | done | S | — | — | M-21 | `tests/unit/test_rate_limit.py` |
| B-089 | Test account deletion cascade (rep_metrics, coaching) | done | S | — | — | M-22 | `tests/unit/test_account_deletion.py` |
| B-090 | Frontend tests: HomePage, AppLayout, hooks | done | M | — | — | M-23 | `frontend/src/` |
| B-091 | Fix weak test assertions (heartbeat TTL, QG message) | done | S | — | — | M-24, M-25 | `test_analysis_worker.py`, `test_quality_gates.py` |
| B-092 | Fix `datetime.utcnow()` deprecation | done | S | — | — | M-26 | `test_repositories.py:109` |
| B-093 | Implement lighting + stability warning gates | done | M | — | FR-CVPL-08/09 | M-3 | `cv/quality_gates.py` |

---

## Completed — Phase 1 Build (2026-04-10)

All Phase 1 MUST requirements implemented. Backend 895 tests / 91% coverage.
Frontend 177 tests. Migration 003 applied. 21 commits across Sessions 5–10.

### Batch 0 — ThresholdConfig v1

| ID | Title | Status | Size | SRS IDs | Commit | Files |
|----|-------|--------|------|---------|--------|-------|
| B-094 | ThresholdConfig v1 scaffold with provenance citations | done | M | FR-SCOR-11 | `fab235b` | `config/thresholds_v1.json`, `app/config.py` |

### Batch 1 — 5-Tier Confidence + 4-Dimension Scoring

| ID | Title | Status | Size | SRS IDs | Commit | Files |
|----|-------|--------|------|---------|--------|-------|
| B-095 | Tier 1 per-landmark confidence (sigmoid × presence) | done | S | FR-CVPL-20 | `f8932e7` | `cv/confidence.py` |
| B-096 | Tier 2 per-angle confidence (min of 3 landmarks) | done | S | FR-CVPL-21 | `f8932e7` | `cv/confidence.py` |
| B-097 | Tier 3 per-frame weighted confidence | done | S | FR-CVPL-22 | `f8932e7` | `cv/confidence.py` |
| B-098 | Tier 4 phase-adjusted frame confidence | done | M | FR-CVPL-23 | `f8932e7` | `cv/confidence.py` |
| B-099 | Tier 5 per-rep 10th percentile | done | M | FR-CVPL-24 | `f8932e7` | `cv/confidence.py` |
| B-100 | UI confidence labels + Very Low suppression | done | S | FR-CVPL-25 | `f8932e7` | `cv/confidence.py` |
| B-101 | SafetyScore (Movement Quality) ScoreComponent | done | M | FR-SCOR-01 | `f8932e7` | `cv/scoring.py` |
| B-102 | TechniqueScore ScoreComponent | done | M | FR-SCOR-02 | `f8932e7` | `cv/scoring.py` |
| B-103 | PathBalanceScore ScoreComponent | done | M | FR-SCOR-03 | `f8932e7` | `cv/scoring.py` |
| B-104 | ControlScore ScoreComponent | done | M | FR-SCOR-04 | `f8932e7` | `cv/scoring.py` |
| B-105 | OverallFormScore weighted composite | done | S | FR-SCOR-05 | `f8932e7` | `cv/scoring.py` |
| B-106 | ScoreComponent extensibility protocol | done | S | FR-SCOR-06 | `f8932e7` | `cv/scoring.py` |
| B-107 | Score descriptors (Elite→Needs Attention) | done | S | FR-SCOR-07 | `f8932e7` | `cv/scoring.py` |
| B-108 | Per-issue badges (dimension + severity) | done | S | FR-SCOR-08 | `f8932e7` | `cv/scoring.py` |
| B-109 | Wire Tier 1-5 confidence + scoring into pipeline | done | M | — | `75ab3eb` | `services/pipeline.py`, `workers/analysis_worker.py` |
| B-110 | Remove redundant compute_rep_confidence from rep_detection | done | S | — | `936703c` | `cv/rep_detection.py` |

### Batch 2 — Coaching: Keyframes + GPT-4o + SSE

| ID | Title | Status | Size | SRS IDs | Commit | Files |
|----|-------|--------|------|---------|--------|-------|
| B-111 | Keyframe extraction at rep boundaries + depth | done | M | FR-AICP-01 | `97a3ee5` | `cv/keyframe_extraction.py` |
| B-112 | Extend CoachingOutput schema for Phase 1 fields | done | M | FR-AICP-03/04/05/06 | `455f439` | `schemas/coaching.py`, `services/coaching.py` |
| B-113 | GPT-4o keyframe vision analysis service | done | L | FR-AICP-02 | `c3ac6a2` | `services/keyframe_analysis.py` |
| B-114 | SSE streaming coaching + prompt caching + Redis pub/sub | done | L | FR-AICP-07, FR-AICP-21 | `af0407f` | `services/coaching.py`, `api/v1/coaching_sse.py`, `workers/analysis_worker.py` |
| B-115 | Fix confidence tier test parameters (Tier 4 + presence column) | done | S | — | `d3d6125` | `tests/unit/test_confidence.py`, `tests/unit/test_pipeline.py` |

### Batch 3 — Exercise Auto-Detect + PDF + Body Stats

| ID | Title | Status | Size | SRS IDs | Commit | Files |
|----|-------|--------|------|---------|--------|-------|
| B-116 | Heuristic exercise auto-detection (initial wiring) | done | M | FR-XDET-03 | `561b1fd` | `cv/exercise_detection.py`, `services/pipeline.py` |
| B-117 | Migration 003 — detection_result JSONB column | done | S | — | `561b1fd` | `alembic/versions/003_add_detection_result.py` |
| B-118 | PDF Phase 1 — score pills + safety warnings + cues + citations | done | L | FR-XPRT-02 | `1c66408` | `services/pdf.py`, `reports/templates/analysis_report.html` |
| B-119 | Body stats personalization — arm_span + femur_length fetch | done | S | FR-PROF-06 | `d8be6ff` | `workers/analysis_worker.py` |
| B-120 | Add OPENAI_API_KEY to .env.example | done | S | — | `5299944` | `.env.example` |

### Batch 4 — Gap Closure + Transition Gate

| ID | Title | Status | Size | SRS IDs | Commit | Files |
|----|-------|--------|------|---------|--------|-------|
| B-121 | GPT-4o vision fallback wiring in pipeline Step 2b | done | M | FR-XDET-04 | `3831950` | `services/pipeline.py`, `workers/analysis_worker.py` |
| B-122 | SSE coaching endpoint integration tests (httpx AsyncClient) | done | M | FR-AICP-07 | `9a712ff` | `tests/unit/test_coaching_sse_endpoint.py` |
| B-123 | PDF bar path chart (matplotlib centroid scatter) | done | M | FR-XPRT-02 | `b221b9b` | `services/pdf.py`, `workers/analysis_worker.py` |
| B-124 | PDF keyframe captures (base64 JPEG embeds) | done | S | FR-XPRT-02 | `b221b9b` | `services/pdf.py`, `reports/templates/analysis_report.html` |
| B-125 | PDF user_info header (experience · height · weight) | done | S | FR-XPRT-02 | `b221b9b` | `services/pdf.py`, `workers/analysis_worker.py` |
| B-126 | Detection result on AnalysisStatusResponse + AnalysisDetail | done | M | FR-XDET-07 | `52a2b0b` | `schemas/analysis.py`, `api/v1/analyses.py` |
| B-127 | Frontend DetectionResult type + useAnalysisStatus hook | done | S | FR-XDET-07 | `52a2b0b` | `frontend/src/api/analyses.ts`, `frontend/src/hooks/useAnalysisStatus.ts` |
| B-128 | AnalysisStatusPage detected exercise card | done | S | FR-XDET-07 | `52a2b0b` | `frontend/src/pages/AnalysisStatusPage.tsx` |
| B-129 | Apply migration 003 to Supabase (`alembic upgrade head`) | done | S | — | — | — |
| B-130 | Eccentric phase duration (alias of descent_duration_s) | done | S | FR-REPM-07 | `b268b70` | `cv/metric_extraction.py` |
| B-131 | Lockout quality assessment (squat/bench/deadlift) | done | M | FR-REPM-08 | `b268b70` | `cv/metric_extraction.py` |
| B-132 | Phase of maximum deviation classifier | done | M | FR-REPM-09 | `b268b70` | `cv/metric_extraction.py` |
| B-133 | Rep-to-rep consistency metrics in summary_json | done | M | FR-REPM-12 | `b268b70` | `services/summary.py` |
| B-134 | FormScoreCards component on ResultsPage (4 dims + overall) | done | L | FR-RESL-01 | `5697138` | `frontend/src/pages/ResultsPage.tsx` |
| B-135 | Movement Quality < 3.0 alert banner | done | S | FR-RESL-01 | `5697138` | `frontend/src/pages/ResultsPage.tsx` |
| B-136 | Extended CoachingOutput rendering (safety warnings, cues, citations) | done | M | FR-AICP-03 | `5697138` | `frontend/src/pages/ResultsPage.tsx`, `frontend/src/api/analyses.ts` |
| B-137 | Phase 1 transition gate — CLAUDE.md updated, handoff finalized | done | S | — | `e63a395` | `CLAUDE.md`, `.claude/handoff.md` |

---

## Completed — Production Hardening (Session 13, 2026-04-11)

Phase 1 was code-complete on 2026-04-10 but **production-broken** due to twelve layers of dormant Phase 0 bugs
that no test had ever caught (every test mocked the third-party module entirely — see ADR-032). Session 13
debugged the full upload → worker pipeline → quality gates path live against `spelix.app`, peeling one layer
at a time. Each PR was diagnosed via Playwright MCP browser automation + direct droplet SSH + the enriched
global exception envelope from PR #4. End-to-end pipeline verified: orphan analysis row `214bf593-bd41-45a4-81a1-98064a1fd199`
ran `quality_gate_pending → processing → quality_gate_rejected` in 100.48 s with all 5 quality gates producing
real metrics from real MediaPipe pose extraction.

| ID | Title | Layer | Status | PR | Commit | Files |
|----|-------|-------|--------|----|--------|-------|
| B-138 | `_make_storage_service` returned `client=None` (Phase 0 dormant `pass` branch) + initial global exception handler | 1 | done | #3 | `94dd0fa` | `api/v1/analyses.py`, `app/main.py`, `tests/unit/test_storage_service.py`, `tests/unit/test_global_exception_handler.py` |
| B-139 | Sync `create_client` vs awaited storage methods → switch to `acreate_client`, module-level cache, enrich exception envelope with `detail.type` + `detail.message` | 2 | done | #4 | `754393c` | `api/v1/analyses.py`, `workers/analysis_worker.py`, `app/main.py`, related tests |
| B-140 | `/insights/global` + cleanup cron tz-aware datetime against naive `created_at` column → strip `tzinfo` at boundary | 3 | done | #5 | `02fcc88` | `services/insights.py`, `workers/cleanup.py`, `tests/unit/test_insights.py` |
| B-141 | Droplet env: `SUPABASE_SERVICE_ROLE_KEY` decoded as JWT belonged to a different Supabase project than `SUPABASE_URL` (verified via JWT `ref` claim decode) — fixed by editing `/home/deploy/spelix/.env.prod` and `--force-recreate` | 4 | done | n/a (env) | n/a | `.env.prod` (droplet only) |
| B-142 | Supabase Dashboard: created `videos` storage bucket in canonical project (was missing entirely after the project migration that left B-141 stale) | 5 | done | n/a (dashboard) | n/a | Supabase Storage |
| B-143 | Frontend `tus-js-client` against Supabase REST signed upload URL — wrong protocol entirely. Switched to `XMLHttpRequest` PUT, dropped pause/resume (REST can't resume mid-byte), 22 frontend tests rewritten | 6 | done | #6 | `12cd90b` | `frontend/src/pages/UploadPage.tsx`, `frontend/src/pages/__tests__/UploadPage.test.tsx` |
| B-144 | `get_db()` never committed — SQLAlchemy `autocommit=False` rolled back EVERY write since Phase 0 B-005. Same bug in `process_analysis` and `cleanup_expired_artifacts`. The history page showing "No analyses yet" was direct evidence of months of data loss. | 7 | done | #7 | `4415ad0` | `app/db.py`, `workers/analysis_worker.py`, `workers/cleanup.py`, `tests/unit/test_db_session.py` |
| B-145 | `_get_service` constructed `AnalysisService(arq_pool=None)` — `start_analysis` silently no-op'd the worker enqueue while still flipping the row to `quality_gate_pending`. Worker had never run a real job. Added cached `_get_arq_pool()` factory mirroring the storage cache pattern. | 8 | done | #8 | `eb1a8c9` | `api/v1/analyses.py`, `tests/unit/test_arq_pool_factory.py` |
| B-146a | `ThresholdConfig()` path resolution computed `/config/thresholds_v1.json` (filesystem root) inside Docker via `Path(__file__).parent.parent.parent` walking to `/`. Plus the Dockerfile didn't copy `config/` into the image at all. Robust `_resolve_threshold_path` priority list + bind-mount `./config:/app/config:ro` in compose. | 9a | done | #9 | `b427f17` | `app/config.py`, `docker-compose.prod.yml`, `tests/unit/test_config_path_resolution.py` |
| B-146b | Status guard rejected `queued → failed` and `quality_gate_pending → failed` — early-pipeline crashes orphaned rows forever because the error handler itself crashed trying to mark them failed. Added the operational `→ failed` edges. | 9b | done | #9 | `b427f17` | `app/services/status.py`, `tests/unit/test_status_transitions.py` |
| B-147 | `start_analysis` AND `run_cv_pipeline` both did `queued → quality_gate_pending` — whichever ran second hit a self-transition the guard correctly rejected. Removed the duplicate from the pipeline (`start_analysis` is the canonical owner). | 10 | done | #10 | `92ecc85` | `app/services/pipeline.py`, `tests/unit/test_pipeline.py` |
| B-148a | `analysis.video_path` was set BEFORE flush, so `analysis.id` was None — DB stored literal string `'videos/None/squat-high-bar.mp4'` while signed upload URL used the post-flush real UUID. Fix: pre-generate UUID via `id=gen_uuid()` at construction. | 11a | done | #11 | `7076c4b` | `app/services/analysis.py`, `tests/unit/test_analysis_service.py` |
| B-148b | Worker error handler crashed with `failed → failed` self-transition when re-running an already-failed row. Skip the transition when status is already `failed`. | 11b | done | #11 | `7076c4b` | `app/workers/analysis_worker.py`, `tests/unit/test_analysis_worker.py` |
| B-149a | Linux `mediapipe` wheels (verified 0.10.9–0.10.33) have NEVER shipped the legacy `solutions` API. Migrated `pose_extraction.py` to `mediapipe.tasks.python.vision.PoseLandmarker`. Bake `pose_landmarker_heavy.task` into the Docker image at build via `curl`. 14 pose tests rewritten + 2 new for `_resolve_model_path`. | 12 | done | #12 | `fb1b12d` | `app/cv/pose_extraction.py`, `backend/Dockerfile`, `tests/unit/test_pose_extraction.py` |
| B-149b | MediaPipe Tasks API `libmediapipe.so` links against `libGLESv2.so.2` and `libEGL.so.1` (verified via `ldd`). Dockerfile only had `libgl1`. Added `libgles2` + `libegl1`. | 12-cont | done | #13 | `491da90` | `backend/Dockerfile` |
| B-149c | `quality_gates.video_file_check` shells out to `ffprobe`, catches `FileNotFoundError`, returns "Video file appears corrupt". Dockerfile didn't install `ffmpeg`. Added it. | 12-cont | done | #14 | `7bf8361` | `backend/Dockerfile` |

**Architectural decisions documented**: ADR-027 (AsyncSession commit-on-success), ADR-028 (pre-generate UUIDs at construction), ADR-029 (MediaPipe Tasks API + model bake), ADR-030 (frontend REST PUT not TUS), ADR-031 (operational `→ failed` status edges), ADR-032 (tests must exercise real factories with source-patched third-party modules).

---

## Phase 1 — Tech Debt (rolled into Phase 2 Batch 0)

Session-14 rewrite: IDs re-numbered to match the Phase 2 kickoff brief. Old `P2-023/024/025`
rows (same content as `D-001/002/003`) are deleted to avoid collision with new
Phase 2 Coach Brain tasks that now occupy `P2-023..P2-034`.

| ID | Title | Status | Size | Commits | Notes |
|----|-------|--------|------|---------|-------|
| D-001 | Replace stream-then-reparse with instructor native streaming structured extraction | done | M | — | `42f54cd` (PR #16). Replaced with `create_partial` — single LLM call, JSON-diff deltas for Redis pub/sub. ADR-021 tech debt resolved. |
| D-002 | Remove dead `compute_rep_confidence` from `cv/confidence.py` | done | S | `9d8137f` (guard test, TDD red) + `404b982` (function deletion, TDD green) | Superseded by `compute_confidence_result` Tier 1–5 pipeline (FR-CVPL-20..24, ADR-015). Deleted function body + orphaned `_SQUAT_DEADLIFT_LANDMARKS`/`_BENCH_LANDMARKS`/`_EXERCISE_LANDMARK_MAP` helpers. Guard test `TestComputeRepConfidenceIsRemoved` prevents reintroduction. |
| D-003 | ADR: Phase 1 coaching stream-then-reparse as tech debt | done | S | — | **Already covered by ADR-021 (`decisions.md`). Closed with no new ADR — ADR-021 documents the deviation from SRS FR-AICP-07 phrasing and the migration plan that D-001 executes.** |

## Phase 1 — Session 13 Production Hardening Follow-ups (renumbered D-004..D-010)

Previously occupied `P2-026..P2-032`. Renumbered to `D-*` tech-debt series so they don't
collide with the new Phase 2 Coach Brain / DPIA / eval tasks below.

| ID | Title | Size | Deps | Notes |
|----|-------|------|------|-------|
| D-004 | Drop the doubled `videos/videos/` storage path prefix | S | — | `get_storage_path` returns `f"videos/{id}/{filename}"` and the bucket is also called `videos`, so signed URLs end up at `.../object/upload/sign/videos/videos/{id}/...`. Internally consistent, NOT a functional bug — ugly leftover from before the bucket name was decided. Fix is one line in `storage.py` + a one-shot DB UPDATE / Storage MOVE. Defer until prod has data that would be painful to migrate wrong. |
| D-005 | Replace `e2e/fixtures/squat-high-bar.mp4` with a real 720p side-view clip | S | — | Current fixture is 360p, body fills 8% of frame. Quality gate correctly rejects on `resolution` and `framing`. Need real 720p+ side-view squat clip with ≥30% body coverage so success path (processing → coaching → completed → results → PDF) can be E2E-verified. |
| D-006 | Backend gotcha doc: "tests-mock-everything" anti-pattern | S | — | Dedicated section in `backend/CLAUDE.md` documenting the 8 regression test patterns added in session 13 (`TestMakeStorageServiceFactory`, `TestGetDbCommit`, `TestMakeArqPoolFactory`, `TestGetServicePassesArqPool`, `TestThresholdConfigPathResolution`, `TestModelPathResolution`, `test_video_path_contains_real_uuid_not_string_none`, `test_error_handler_skips_transition_when_already_failed`) as canonical "exercise real factory with third-party patched at source" examples. Reference ADR-032. |
| D-007 | CI factory-coverage smoke test | M | D-006 | CI step asserting every factory function in `api/v1/*.py`, `services/*.py`, `workers/*.py` has ≥1 test exercising the real factory path (not just the consumer). Grep-based heuristic; goal is to make it impossible to add a new singleton/factory/cached-client without a regression test. |
| D-008 | Verify untested production subsystems via E2E after happy-path fixture lands | S | D-005 | Once D-005 lands a fixture that passes the quality gate, run the full E2E and surface dormant config bugs in Anthropic coaching, OpenAI keyframe analysis, WeasyPrint PDF, Realtime status subscriptions, artifact Storage upload. |
| D-009 | Post-deploy smoke check in CI deploy workflow | S | — | Bake into `Deploy to Production` job: after `docker compose up -d --build` and health check, run a one-shot Python script inside the backend container that constructs the storage factory, arq pool, and threshold config — exercising real production env vars. Fail the deploy on any failure. Would have caught B-138/139/141/142/146a at deploy time. |
| D-010 | Tighten `AnalysisService.__init__` arq_pool typing | S | D-009 | Currently `arq_pool: Any \| None = None` — defaulting to None was the dead-code parameter that hid B-145 for months. Tighten to `arq_pool: ArqRedis` (no default) once every call site passes a real pool. Prevents the silent no-op forever. |
| D-014 | Droplet OOM mitigation — add 2GB swap, deploy PR #27, verify E2E | done | M | — | **Resolved session 24.** Power-cycled via DO MCP, added 2GB persistent swap via root SSH (ADR-038). Root access established via Docker privilege escalation. 5 sessions blocked (20–24). `5af89a0` |
| D-015 | Fix consent page mixed content + 422 errors (ADR-037) | done | M | P2-029 | Uvicorn --proxy-headers, FastAPI redirect_slashes=False, consent routes "/" → "", ConsentCreate.granted default True, timezone-naive datetimes. PR #31. `5af89a0` |
| D-016 | Fix VITE_API_URL env var name mismatch on Vercel | done | S | — | Vercel had VITE_API_BASE_URL, code reads VITE_API_URL. Renamed on Vercel dashboard. PR #29. `74429e8` |

---

## Completed — Session 20 Production Bugfixes (2026-04-12)

Three bugs discovered during E2E verification of Batch 5+6 features. All fixed, CI green, deployed.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| D-011 | Fix status page stuck on "Loading…" — add initial fetch on mount | done | S | — | FR-RESL-13 | `d768d95` (PR #24) | `frontend/src/hooks/useAnalysisStatus.ts`, `frontend/src/pages/__tests__/AnalysisStatusPage.test.tsx` |
| D-012 | Include quality_gate_result in status endpoint response | done | S | — | FR-RESL-13 | `93620fa` (PR #25) | `backend/app/schemas/analysis.py`, `backend/tests/unit/test_analysis_api.py` |
| D-013 | Fix framing gate rejecting well-framed portrait (9:16) videos | done | S | — | FR-CVPL-04 | `a11ff80` (PR #26) | `backend/app/cv/quality_gates.py`, `backend/tests/unit/test_quality_gates.py` |

---

## Phase 2 — Active (kickoff 2026-04-11, session 14)

Authoritative task list: Phase 2 kickoff brief.
Active agents: `spelix-tdd`, `spelix-auditor`, `spelix-security-reviewer`, `spelix-migration`,
`spelix-rag-engineer`, `spelix-corpus-curator` (6 total — at the agent roster cap).

**Hard privacy gates** (block any production Coach Brain write until BOTH are met):
1. `P2-031` (DPIA document) merged to main.
2. `P2-029` (three-tier consent UI) passes `spelix-security-reviewer` sign-off.

**Budget cap**: $0.10/analysis (NFR-PERF-05). Do not add LLM calls that push above.
**Latency cap**: ≤90s end-to-end, ≤5s first coaching token, CoVe budget 6–13s/iter max_iterations=2.
**Data provenance**: only `reviewed_approved` documents enter Qdrant `papers_rag`.
Seed Coach Brain corpus only: `source=seed_manual_validated`. Distillation pipeline is Phase 3.

### Batch 1 — Infrastructure (run /parallel — fully independent)

| ID | Title | Size | Deps | SRS IDs | Status | Commits |
|----|-------|------|------|---------|--------|---------|
| P2-001 | Migration 004 — rag_documents + expert_annotations + coach_brain_entries + consent_records tables + retrieval_context + eval_scores JSONB columns on analyses + RLS on consent_records | M | — | FR-AICP-11, FR-BRAIN-01, FR-BRAIN-11, FR-BRAIN-16, NFR-PRIV-01 | done | `608e007` (initial migration + tests) + `d2eb0a0` (drop phantom `set_updated_at()` triggers + fix `pg_class.rowsecurity` helper). Applied to live Supabase. 17/17 integration tests pass. Column names landed as `retrieval_context` + `eval_scores` (not `retrieved_sources_json` + `eval_scores_json`) — Batches 2–8 must use these names. `expert_annotations` designed as chunk-level Qdrant mirror (document_id, chunk_index, chunk_text, embedding_model, qdrant_point_id, citation_metadata), not reviewer/action/notes. `coach_brain_entries.content` not `coaching_action`. `coach_brain_entries.status` enum: `seed \| active \| deprecated`. `consent_records.consent_type` enum: `coach_brain_contribution \| health_data_processing \| analytics`. |
| P2-002 | Qdrant Cloud cluster provisioning + dual-collection schema (`papers_rag` + `coach_brain`, both 1024 dim cosine + BM25 sparse, payload indexes on coach_brain.exercise + status) + nightly keepalive ARQ cron `ping_qdrant_health` | M | — | FR-AICP-09, FR-BRAIN-01, FR-BRAIN-13, ADR-BRAIN-01, ADR-BRAIN-03, ADR-RAG-03, ADR-032, ADR-P2-001 | done | `d54f543` — QdrantClientWrapper + module-level factory cache + deferred source-patch import + ensure_collections() idempotent + ping() never-raises + thin upsert/query passthroughs. Shared Phase 2 RAG schemas (ChunkPayload, RetrievedContext, RetrievalResult, CitationBlock) in `schemas/rag.py`. Nightly `ping_qdrant_health` cron at 02:00 UTC (offset from 03:00 cleanup). `scripts/provision_qdrant.py` one-shot. 38 new tests (18 qdrant_client + 20 rag_schemas). `CoachBrainEntry` deferred to P2-023. **Live provisioning against Qdrant Cloud not yet run — next turn task.** |
| P2-003 | Cohere API client wrapper — `embed-v4.0` + `rerank-v4.0-pro`, 96-batch limit, rate limit respect, explicit `output_dimension=1024`, `cohere.AsyncClientV2` (SDK v6+), mocked in all CI tests | S | — | FR-AICP-09, ADR-RAG-01, ADR-RAG-03, ADR-032 | done | `12b1e46` (test) + `eeec555` (impl) + `67c7df6` (config + `.env.example`). Cherry-picked from worktree `agent-adc83ac4`, dropped stale backlog-hygiene commit `3666581`. cohere SDK 6.1.0 is async-native (no `asyncio.to_thread`). `output_dimension=1024` passed on every call, asserted by regression test. `rerank-v4.0-pro` model pinned + test-asserted. 6 new tests. `COHERE_API_KEY` in `config.py` as `SecretStr`. |

### Batch 2 — Ingestion Pipeline (gate: P2-002, P2-003 merged; /team phase2-rag)

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| P2-004 | Document ingestion pipeline: Docling parse → chunk → embed → Qdrant upsert. Idempotent via `sha256(paper_id:chunk_index)` as point ID. Only `reviewed_approved` documents enter Qdrant. | done | L | P2-002, P2-003 | FR-AICP-09, FR-RAGK-01, ADR-RAG-02 | `42f54cd` (PR #16). IngestionService with 500-token section-aware chunking, SHA-256 deterministic point IDs, status guard. |
| P2-005 | Recursive 500-token chunking, 50-token overlap, section-aware preprocessing (abstract / methods / results extracted separately) | done | M | P2-004 | FR-AICP-09 | Delivered as part of P2-004 `IngestionService._chunk_text` + `_section_chunks`. `42f54cd` (PR #16). |
| P2-006 | Metadata-as-payload pattern: title/authors/year/doi/quality_tier/section stored on every Qdrant point for filter-at-query-time | done | S | P2-004 | FR-AICP-09, FR-RAGK-06 | Delivered as part of P2-004 via `ChunkPayload` fields on every Qdrant point. `42f54cd` (PR #16). |
| P2-007 | Corpus curation — seed research papers. ≥10 per exercise. Sources: PubMed E-utilities, OpenAlex, Semantic Scholar. 4-layer quality tier weights (L1 SR/MA 2.0, L2 PEDro≥5 1.5, L3 PEDro 3-4 1.0, L4 guidelines 0.5). Recency boost ×1.2 for post-2020. | M | P2-004 | FR-RAGK-02, FR-RAGK-03 | done | Session 25. 34 papers (12 squat, 11 bench, 11 deadlift) seeded to DB + Qdrant papers_rag. 36 chunks. `scripts/seed_research_papers.py`. 13 validation tests. |

### Batch 3 — Hybrid Retrieval (gate: P2-004 merged; /team phase2-rag)

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| P2-008 | Cohere dense embedding retrieval from papers_rag (`input_type="search_query"`) | M | P2-004 | FR-AICP-09 | done | `720c97d` (PR #17). `RetrievalService.dense_search()` in `app/services/retrieval.py`. 69 retrieval tests pass. |
| P2-009 | BM25 sparse retrieval via Qdrant server-side sparse vectors (not client-side) | M | P2-004 | FR-AICP-09 | done | `720c97d` (PR #17). `SparseRetrievalService.sparse_search()` in `app/services/sparse_retrieval.py`. mmh3 tokenization + Qdrant `Modifier.IDF`. |
| P2-010 | Cohere **Rerank 4.0** integration as cross-collection score normaliser. Reranks merged papers_rag + coach_brain results in one call. | M | P2-008, P2-009 | FR-AICP-09, ADR-RAG-01 | done | `c176951` (PR #18). `RetrievalService.hybrid_search()` with `rrf_fuse()` + Cohere rerank + 3s timeout fallback. |
| P2-011 | Exercise-type filter at query time via Qdrant payload filter before reranking | S | P2-010 | FR-AICP-12 | done | `698714d` (PR #19). `exercise_filter` param on `dense_search`, `sparse_search`, `hybrid_search`. |
| P2-012 | Min 3 docs per issue guard before generation — emit `coaching_unavailable` sentinel on failure | S | P2-010 | FR-AICP-09 | done | `698714d` (PR #19). `RetrievalGuard.check()` in `app/services/retrieval_guard.py`. MIN_DOCS=3. |

### Batch 4 — Four-Stage Prompt Architecture (gate: P2-010 merged)

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| P2-013 | Stage 1 — Cite-then-generate. Retrieved context injected as CitationBlock list; prompt instructs model to cite by index. | L | P2-010 | FR-AICP-08 | done — PR #19 `698714d` |
| P2-014 | Stage 2 — Structured generation with temperature split. Factual corrections temp=0.1, motivational cues temp=0.7. instructor + Pydantic v2. | M | P2-013 | FR-AICP-08 | done — PR #20 `6970f53` |
| P2-015 | Stage 3 — CoVe verification loop (extract_claims → generate_questions → answer_independently → check_consistency → revise). max_iterations=2, 6–13s budget/iter. Non-convergence is NOT failure — stream with `cove_verified=false`. | XL | P2-014 | FR-AICP-08 | done — PR #20 `6970f53` |
| P2-016 | Stage 4 — RAGAS `FaithfulnesswithHHEM` (Vectara HHEM-2.1-Open T5) gate. Score ≥0.8 stream; <0.8 route to flag_review queue but still stream (FR-AICP-15). | L | P2-015 | FR-AICP-08 | done — PR #20 `6970f53` |

### Batch 5 — Citation & Safety

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| P2-017 | `ValidateOutputTool` — block uncited factual claims. Any claim without matching citation index fails validation, triggers CoVe re-generation. | M | P2-013 | FR-AICP-10 | done | PR #21 `b48c5c1` |
| P2-018 | Mandatory safety hedging for MEDICAL_CLEARANCE category issues. Inject standard disclaimer before any coaching text. "injury risk" / "injury prevention" PROHIBITED (Spelix language rule). | S | P2-014 | FR-AICP-14 | done | PR #21 `b48c5c1` |
| P2-019 | Error handling — Qdrant unavailable fallback to ungrounded coaching with disclaimer. Never raise 500 on retrieval failure. | S | P2-004 | FR-AICP-15 | done | PR #21 `b48c5c1` |
| P2-020 | Rerank timeout handling — if Cohere Rerank 4.0 exceeds 3s, skip rerank and use RRF-merged scores directly. Log to Langfuse. | S | P2-010 | FR-AICP-09 | done | PR #21 `b48c5c1` |

### Batch 6 — Frontend (gate: P2-013 merged; /parallel)

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| P2-021 | Citation rendering on results page. Inline superscript footnotes. Click → expand paper metadata card with "Source: [title], [authors], [year]" format. | M | P2-013 | FR-RESL-06 | done — PR #22 `5cce808` |
| P2-022 | Follow-up chat UI. Post-analysis chat panel using same RAG pipeline. Context window includes `coaching_result + retrieved_sources` from completed analysis. | L | P2-013 | FR-RESL-09, FR-AICP-17 | done — PR #23 `0173006` |

### Batch 7 — Coach Brain Foundation (gate: P2-002 merged; /team phase2-brain)

P2-023 produces the canonical `CoachBrainEntry` schema — blocks P2-024..P2-028.
`spelix-security-reviewer` sign-off is mandatory for P2-025 coaching strings,
P2-029 consent UI, P2-030 withdrawal cascade, and P2-031 DPIA.

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| P2-023 | Coach Brain Qdrant collection schema + canonical `CoachBrainEntry` Pydantic schema in `app/schemas/coach_brain.py`. 1024 dim, BM25 sparse, payload indexes on exercise + status. **Blocks P2-024..P2-028.** | done | M | P2-002 | FR-BRAIN-01, ADR-BRAIN-01 | `42f54cd` (PR #16). 4 schemas: Entry/Create/Update/Payload. Aligned with migration 004 (trigger_tags=list[str], entry_type=cue/correction/principle/drill). |
| P2-024 | Contextual embedding pipeline (FR-BRAIN-03). Prepend `"exercise:{ex} phase:{ph} type:{entry_type}\n{text}"` before embedding. Store enriched text separately from raw `coaching_action`. `input_type="search_document"`. | M | P2-023 | FR-BRAIN-03, ADR-BRAIN-02 | done | `720c97d` (PR #17). `BrainEmbeddingService` in `app/services/brain_embedding.py`. Contextual text format per ADR-BRAIN-02. |
| P2-025 | Seed corpus ingestion — ≥20 entries covering squat (depth, knee cave, back rounding), bench (bar path, elbow flare, leg drive), deadlift (lumbar flexion, hip hinge, lockout). `status=seed`, `source=seed_manual_validated`, `confirmation_count=1`. | L | P2-023, P2-024 | FR-BRAIN-09, FR-BRAIN-18 | done | Session 25. 24 entries (8/exercise) seeded to DB + Qdrant coach_brain collection. `scripts/seed_coach_brain.py`. 20 validation tests. |
| P2-026 | Coach Brain hybrid retrieval in RetrieveTool. Queries BOTH collections concurrently (`asyncio.gather`), reranks merged results via Rerank 4.0. Routing: ≥0.82 `coach_brain_primary`; 0.65–0.82 `hybrid_brain_supplementary`; <0.65 `papers_only_fallback`. | M | P2-023, P2-010 | FR-BRAIN-04, ADR-BRAIN-03 | done | Session 22. `DualCollectionOrchestrator` in `app/services/dual_collection.py`. Worker wired via `orchestrator.retrieve()`. 8 new tests + 2 RetrievalService extension tests. `[RESEARCH]`/`[COACHING]` labels in coaching prompt. |
| P2-027 | Cold-start fallback logic (FR-BRAIN-05). When `retrieval_source=papers_only_fallback`, omit "Based on Coach Brain data..." prefix. Log fallback to Langfuse. | S | P2-026 | FR-BRAIN-05 | done | Session 22. Handled automatically by routing thresholds — empty coach_brain → top_score=0.0 → `papers_only_fallback`. No `[COACHING]` labels in prompt. Tested in Gate 5 of test_dual_collection.py. |
| P2-028 | Privacy-preserving trigger conditions (FR-BRAIN-10). Body proportion attributes in `trigger_tags` use categorical bins (3-5 categories), never raw measurements. Min group size n≥20 enforced before any pattern surfaces. | M | P2-023 | FR-BRAIN-10 | done | `c176951` (PR #18). Categorical bins enforced in `CoachBrainPayload` schema + trigger_tags validation. |
| P2-029 | Three-tier consent UI (FR-BRAIN-11). Tier 1 service consent (Article 6(1)(b)). Tier 2 explicit health-data consent (Article 9(2)(a), distinct interaction). Tier 3 optional aggregate consent (service must work without). Store to `consent_records` with timestamp + ip_hash + tier. | L | P2-001 | FR-BRAIN-11, ADR-BRAIN-05, NFR-PRIV-01 | done | PR #28 (session 23). Backend: ConsentRecord model, ConsentRepository, consent router (POST/GET/withdraw), 17 tests. Frontend: ConsentPage (3 tiers), useConsent hook, consent API module, /consent route, 12 tests. |
| P2-030 | Consent withdrawal cascade (FR-BRAIN-16). ARQ job (NOT synchronous) that removes user analysis_ids from `source_analysis_ids` across ALL `coach_brain_entries`. If empty AND `confirmation_count<3`: soft-delete (`status=deprecated`, `rejected_reason` in metadata JSONB — DB CHECK constraint only allows seed/active/deprecated). | M | P2-001, P2-029 | FR-BRAIN-16 | done | PR #32 (session 24). CoachBrainEntry model, CoachBrainRepository, consent_cascade ARQ job, withdrawal endpoint enqueues job. 9 tests. |
| P2-031 | DPIA documentation (FR-BRAIN-15). Produce `docs/dpia.md` covering GDPR Article 35(7): systematic description, necessity/proportionality, risk assessment, mitigation measures. **Hard gate — no production Coach Brain writes without it.** | M | — | FR-BRAIN-15 | done | PR #28 (session 23). `docs/dpia.md` — 6-section DPIA covering processing operations, necessity/proportionality, risk assessment (9 risks), mitigation measures, data subject rights, review schedule. |

### Batch 8 — Eval Logging (gate: P2-016 merged; /parallel)

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| P2-032 | Retrieval metrics logging to Langfuse (FR-BRAIN-13). Per-query log of `retrieval_source` enum, similarity scores, hit counts, Coach Brain contribution %. Target: Coach Brain contributes to >40% of queries within 3 months. | M | P2-034 | FR-BRAIN-13 | done | PR #32 (session 24). Langfuse client injected into DualCollectionOrchestrator, best-effort trace after retrieval routing. 3 tests. |
| P2-033 | Per-analysis RAGAS + HHEM eval scores stored in `analyses.eval_scores`. Format: `{"faithfulness": float, "hhem": float, "cove_verified": bool, "cove_iterations": int}`. | M | P2-016 ✅, P2-001 ✅ | FR-AICP-16 | done | PR #28 (session 23). Extended faithfulness gate block to include CoVe fields + Langfuse score logging. Key renamed: `faithfulness_score` → `faithfulness` (ADR-036). |
| P2-034 | Langfuse Cloud integration. `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` in env. `LangfuseClient` singleton injected into coaching service. Trace: `analysis_id` as `session_id`. Mock in all CI tests. | M | — | FR-BRAIN-13 | done | PR #28 (session 23). `app/services/langfuse_client.py` two-flag singleton (ADR-036). Config keys in `config.py`. Constructor injection into CoachingService. 4 TODO(P2-034) replaced. 7 tests. |

### Batch 9 — Admin UI (gate: Batch 2 merged)

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| P2-035 | Admin RAG corpus management page — list documents with title, year, exercise type, quality tier, chunk count, review status. CRUD actions (upload, delete, re-embed). | L | P2-004 | FR-ADMN-06, FR-RAGK-08, FR-RAGK-09 | done | Session 26. Migration 006, `RagDocument` model, `RagDocumentRepository`, admin routes (GET/DELETE/POST re-embed), `RagCorpusPanel` on AdminPage. 37 backend tests. |
| P2-036 | Admin expert reviewer queue page — list analyses flagged for review, their status, and submitted annotations | M | P2-035 | FR-ADMN-07 | done | Session 26. `list_flagged_analyses`, `get_expert_queue_stats` on AdminService, `ExpertQueuePanel` on AdminPage with stats summary. |
| P2-037 | Admin Coach Brain management page — view entries with entry_type, exercise, phase, status, confidence_score, confirmation_count. Filter by status/exercise. Approve/reject/edit actions. | L | P2-035 | FR-ADMN-10 | done | Session 26. Extended `CoachBrainRepository` with CRUD. Admin routes (GET/POST/PATCH/DELETE). `CoachBrainPanel` with filters + approve/deprecate/delete actions. |

### Batch 10 — Expert Reviewer Portal (gate: Batch 9 merged)

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| P2-038 | Expert Reviewer portal route with role-based access check | M | — | FR-EXPV-01 | done | Session 26. `get_expert_reviewer_user` dep in deps.py (ADR-041). `ExpertPortalPage.tsx` with role check. `/expert` route in routes.tsx. |
| P2-039 | Expert review queue — flagged analyses, low coaching quality, first-run variants | M | P2-038 | FR-EXPV-02 | done | Session 26. `GET /expert/queue` with queue_type filter (flagged/low_quality/first_run/all). `ExpertService.get_review_queue`. ExpertPortalPage with tab UI. |
| P2-040 | Expert review detail view — anonymized metrics, coaching output, citations, agent trace | M | P2-039 | FR-EXPV-03 | done | Session 26. `GET /expert/analyses/{id}` returns anonymized detail (no user_id). `ExpertAnalysisDetailPage.tsx`. |
| P2-041 | Expert annotation submission form — issues_identified, coaching_quality_score, accuracy booleans, suggested_corrections, cited_sources | M | P2-040 | FR-EXPV-04 | done | Session 26. `POST /expert/analyses/{id}/annotations`. `AnalysisExpertReview` model + migration 006. Annotation form on ExpertAnalysisDetailPage. |
| P2-042 | Expert paper upload from portal with pre-filled metadata form | M | P2-038 | FR-EXPV-05 | done | Session 26. `POST /expert/papers` with metadata. `ExpertPaperUploadPage.tsx`. |
| P2-043 | Expert paper review workflow — approve/reject/needs-revision status transitions | M | P2-042 | FR-EXPV-06 | done | Session 26. `PATCH /expert/papers/{id}/review` with decision enum. `RagDocumentRepository.update_review_status`. |
| P2-044 | Golden dataset workflow — label analyses as golden entries with ground-truth issues and expected coaching output | L | P2-041 | FR-EXPV-07 | done | Session 26. `PATCH /expert/analyses/{id}/golden`. `is_golden_label` on annotation form. `ExpertService.set_golden_label` propagates to `analyses.is_golden_dataset`. |

### E2E Smoke Test Bug Fixes (Session 26)

| ID | Title | Size | Deps | SRS IDs | Status | Commit |
|----|-------|------|------|---------|--------|--------|
| D-018 | Supabase Storage bucket MIME types — add image/png, image/jpeg, application/pdf, text/csv to `videos` bucket allowed types | S | — | FR-RESL-02, FR-RESL-05 | done | Supabase SQL (no code commit) |
| D-019 | Generate signed read URLs for artifact paths in analysis detail API response | M | — | FR-RESL-02, FR-RESL-05, FR-XPRT-02 | done | `7e0b893` (PR #35) |
| D-020 | Lower squat rep detection thresholds — depth 90°→110°, standing 160°→150° to catch parallel-depth reps | M | — | FR-CVPL-07 | done | `7e0b893` (PR #35) |
| D-021 | Re-encode annotated video to H.264 via ffmpeg for browser playback — OpenCV mp4v codec not browser-compatible | M | — | FR-RESL-02 | done | `38e4510` (PR #36) |
| D-022 | PDF template missing in Docker image — `reports/templates/analysis_report.html` not copied into container. Pipeline gracefully continues but pdf_path=null. Fixed in two parts: PR #37 added bind mount; PR #38 added CWD-based path resolution (ADR-045). | M | — | FR-XPRT-02 | done | `b86d07e` (PR #37) + `2fbec9f` (PR #38) |

### Batch 11 — Data Quality (deferred, no code deps)

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| D-017 | Replace AI-generated paper summaries with real full-text content from actual PDFs via Docling ingestion. Current seed papers (P2-007) have real metadata (titles, authors, DOIs, years) but AI-synthesized text, not verbatim paper content. Real PDFs would improve RAG retrieval quality. | L | P2-007 | FR-RAGK-02 | superseded | L2-EXPERT-UPLOAD unblocks real-PDF ingestion via the expert portal (end-to-end upload live on prod). Docling parsing itself remains open as P2-005 — `ingest_paper` is a stub until it ships. Re-scope once the first kin-expert PDF goes through the real pipeline. |

---

## Completed — Session 27 Production Hardening (2026-04-13)

Phase 2 transition gate passed. All 33 Must requirements implemented, E2E smoke test confirmed PDF generation works on production (analysis `5f04cca1`). Three production bugs found during E2E verification and fixed in-session.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| D-023 | PDF template path resolution — `__file__`-relative path walks to `/` in Docker | done | S | D-022 | FR-XPRT-02 | `2fbec9f` (PR #38) | `backend/app/services/pdf.py` |
| D-024 | Qdrant `coach_brain` missing `exercise` + `status` payload indexes — 400 on filtered queries | done | M | — | FR-BRAIN-01 | `6fde5e1` (PR #39) | `backend/app/services/qdrant.py` |
| D-025 | Supabase Realtime on `analyses` table — publication membership + REPLICA IDENTITY FULL | done | M | — | FR-RESL-13 | `b7b6b1f` (PR #39) | `backend/alembic/versions/007_enable_realtime_analyses.py` |

### Known Issues Opened

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| D-026 | Droplet OOM during concurrent analyses — 2GB RAM + 2GB swap insufficient; worker unresponsive to SSH during session 27 test. Previously patched in session 24 (D-014) with swap; may need 4GB droplet upgrade for L2 beta. | M | — | NFR-OPER-02 | done | Resized to `s-2vcpu-4gb` ($24/mo) via DO MCP, Datadog agent purged (saved 181MB). Memory PSI full=0, CPU PSI=0, swap <1MB during analysis. E2E verified. See ADR-048. |
| D-027 | Apply migration 007 to Supabase via `alembic upgrade head` — one-off SQL was used during debugging; alembic head still at 006 in the migrations table. | S | — | — | done | Verified 2026-04-15 session 30: prod `alembic_version` already at `008_beta_requests (head)`; `upgrade head` is a no-op. Applied as side-effect of PR #45 landing V1 deploy. |
| D-028 | Frontend `useAnalysisStatus` hook shows "Connection lost — reconnecting…" banner after a terminal-state UPDATE when it intentionally calls `channel.unsubscribe()`. Cosmetic issue — analysis results still render correctly. Fix: don't set `isReconnecting=true` when channel status is "CLOSED" after we intentionally unsubscribed. | S | — | FR-RESL-13 | done | `intentionalUnsubscribeRef` tracks unsubscribes on terminal status; subscribe callback short-circuits on CLOSED when the flag is set; flag resets on `analysisId` change. 11/11 hook tests green, 272/272 frontend suite clean. |
| D-029 | SaMD/FTC: rename `injury_advice_accurate` to `movement_advice_accurate` across DB column, SQLAlchemy model, Pydantic schema, frontend TypeScript interfaces (`AnnotationCreate`/`AnnotationResponse` in `frontend/src/api/expert.ts`), and DOM `name` attribute in `ExpertAnalysisDetailPage.tsx:460`. Surfaced by expert PDF upload security review (C-2) as pre-existing violation — the user-visible label ("Movement Quality Advice Accurate?") is already correct, only the wire/DOM name leaks the prohibited term. Needs a migration to rename the column. | M | — | — | done | Migration 013 (`96aaabb`), backend rename (`e975c94`), frontend rename (`8f1cfc8`). PR #TBD. |
| D-030 | Orphan `rag_documents` rows with `review_status='uploading'` accumulate if the expert abandons a PDF upload (browser crash, nav-away, failed PUT). No TTL, no scheduled cleanup. Add a nightly streaq cron (similar to `cleanup_expired_artifacts`) that deletes rows + storage objects older than 2 hours (1-hour signed URL TTL + grace). Surfaced by expert PDF upload security review (M-4). | S | — | FR-EXPV-02 | done — `abdd6a2` (PR #TBD, session 56). Nightly streaq cron at 04:00 UTC deletes orphan uploading rows + Storage objects older than 2 hours. Per-row error isolation. 6 new tests. |
| D-031 | Admin `GET /rag/documents` accepts a free-text `review_status` query parameter — replace with `Literal` constraint or filter out `uploading` rows by default. Surfaced by expert PDF upload security review (M-2). | S | — | FR-RAGK-08 | done | `1ff5ecf`. PR #TBD. |
| D-032 | Framing + single-person quality gates reject correctly-framed barbell videos. **THREE co-occurring issues surfaced by session 33 MediaPipe diagnostics on `atharva-{squat,bench,deadlift}.mov`:** (1) **Temporal bias**: `check_framing` uses `landmarks_per_frame[:5]` (for deadlift = bent-over setup); `check_single_person` uses `[:10]` (same problem). Replace with peak (or 90th-percentile) bbox across 20–30 evenly-spaced frames for framing; use a **sustained-tracking** signal over a longer window for single-person (not consecutive-frame jumps). (2) **NO_POSE warmup / plate occlusion**: MediaPipe returns no pose for frames 0-3 when a loaded barbell obscures upper body at the rack (`atharva-squat.mov` first 4 frames = NO_POSE → mean drops to 0.014). Skip NO_POSE frames before averaging. (3) **Visible-landmark-bbox undershoot**: `bbox_width * bbox_height` over landmarks with `sigmoid(vis) > 0.5` understates body-in-frame ratio when landmarks are plate-occluded (squat max=0.092) or self-occluded lying sideways (bench max=0.097) — same-camera `atharva-bench-no-weight.mov` with no plates clears at 0.337. Evaluate three mitigations in an exploratory branch: (a) all-33-landmark bbox ignoring visibility; (b) `presence` score instead of `visibility`; (c) per-exercise thresholds. Do NOT lower `_FRAMING_MIN_FRACTION` globally. See ADR-053 (temporal bias) + ADR-054 (occlusion/orientation). Regression tests must cover: narrow-early / wide-late bbox fixture, rack squat with plates, bench lying sideways, and a genuinely out-of-frame lifter. | L | — | FR-CVPL-04, FR-CVPL-06 | done | `b401615` (PR #58) — chose all-33-landmark bbox + 90th percentile over full clip + NO_POSE skip. E2E verified on prod with 720p bench clip 2026-04-16. |
| D-033 | **streaq task timeout regression — `process_analysis` times out on 1080p 59fps full-length clips on 2-vCPU droplet.** `backend/app/workers/streaq_worker.py:144` sets `@worker.task(timeout=300)` for `process_analysis`. The comment claims "drop-in parity with ARQ's WorkerSettings.job_timeout" but ADR-BRAIN-04's Phase-2 update explicitly raised ARQ `job_timeout` from 300 → 900 ("bumped from 300 for ingestion"). Regression surfaced 2026-04-16 session 33 prod-watch: `atharva-bench.mov` (38 MB, 1080×1920 @ 59fps, 23s, 1382 frames) timed out at 5:00 exactly, analysis row `2158536a-8df6-4fa0-8d68-b01129c0aadb` left stranded in `quality_gate_pending`. MediaPipe BlazePose Heavy on 2 vCPUs consistently runs ~4–6 min for a full 1080p clip; `atharva-squat.mov` (33 MB, 20.6s) barely made it at 4:21. Fix: raise `process_analysis` task timeout to 900s (leave `cascade_consent_withdrawal` + `ingest_paper` at 300s — those are short-lived). Also: the stranded `quality_gate_pending` row confirms there is no cleanup path for timed-out analyses — worth a follow-up (don't block this PR on it). See ADR-055. | S | — | NFR-OPER-02 | done | `1a2fb01` (PR #55) |
| D-034 | **Analysis pipeline OOMs post-MediaPipe on 4GB droplet for full-length 1080p clips.** Surfaced immediately after D-033 fix: `atharva-bench-no-weight.mov` (37 MB, 1080×1920 @ 59fps, 22.8s, 1352 frames) passes quality gate (predicted), then memory climbs to **3.2 GB / 3.8 GB available RAM**, swap thrashes to 1.3 GB, and the worker process exits with **exit code 0** (not cgroup-OOM-killed — `docker inspect` shows `oomKilled=false`). Deterministic: both attempts on analysis `4e19c62b-91c2-4f01-b269-3ac51e05db3f` died at ~7:50 elapsed during the post-quality-gate phase (annotation video encoding + rep detection + Anthropic coaching + artifact upload). Streaq retried per its default `max_tries=3`. Likely mechanism: Python process gets SIGKILL from kernel OOM or hits a caught `MemoryError` that does `sys.exit(0)`; the container's main process dying triggers a restart. Fix paths to investigate: (a) downscale annotation video to 720p before encoding; (b) stream-encode annotation frame-by-frame instead of buffering; (c) release MediaPipe landmarks after rep detection but before annotation; (d) skip annotation for clips >N seconds; (e) resize droplet to 8 GB. Affects any real-user clip filmed at modern phone resolution (≥1080p). Prior D-026 (4 GB resize) covered concurrent-analyses OOM — this is single-analysis OOM, different axis. See ADR-056. | L | — | NFR-OPER-02 | done | `916bd11` (PR #57 — `del frames` + 720p annotation cap) + `6d9f084` (PR #59 — streaming `track_barbell_from_video`). E2E verified 2026-04-16: full 22.8s 1080p bench clip runs to completion with worker RSS rock-steady at 639 MB across 15 min (vs 3.2 GB OOM before). No SIGKILL. Task timed out at 900s — that's a **new** CPU-bound bottleneck (D-035), not memory. |
| D-035 | **Pipeline timeout on 1080p@59fps clips — root cause was `cv2.HoughCircles` at source resolution inside `track_barbell_from_video`, not pose extraction.** Originally framed as a pose-extraction issue after D-034; telemetry from ADR-058 (session 38 analysis `fc318bc3-3cf9-4f0e-85ee-0f5d61cb77b1`) showed pose is 287 s (5 min) of a 22.8 s clip's budget but **`barbell_tracking` alone was 24.4 min — 83 % of total wall time**. Session 39 worker benchmark measured 1037 ms/frame on the bench clip (HoughCircles with radius range 10-100 on 1080p = 1 s/frame). **Fix (ADR-060)**: `_downscale_for_detection` resizes every frame to 480 px longest dim before HoughCircles, scales centroid back on return. Post-fix bench: **99.6 ms/frame = 10.4× speedup**; stage wall time 1388 s → 133 s; detection rate 100 % preserved. Session 35.5's 720p pose cap (PR #61) stays in place but is not the load-bearing fix. | M | — | NFR-OPER-02, FR-BDET-01, FR-BDET-02 | done | `91b1903` (PR #71) + `3febef7` (PR #73, streaq timeout restored 1800s → 900s). Prod E2E on analysis `01fd3c57-af0d-4c7d-b846-b298260bd7ca` confirmed end-to-end: barbell 118.8s, total pipeline 670s, status=completed, 15/15 stages persisted. Pre/post bench evidence in `backend/bench_barbell.py`; see ADR-060. Unblocks D-036 trigger re-evaluation. |
| D-036 | **GPU offload for pose extraction (post-private-beta).** BlazePose Heavy on the 2-vCPU droplet costs ~120-150 ms/frame regardless of input resolution (session 35 bench). The fundamental constraint per ADR-058 is that the CPU pipeline cannot scale to clips much beyond ~30 s @ 60 fps without GPU acceleration. Defer evaluation + implementation to **after** L2 private beta launches. **Trigger condition** to lift: (a) demand exceeds the CPU pipeline's capacity (queue depth grows faster than worker can drain), OR (b) clip duration limits become the top user complaint (>3 distinct beta users explicitly request longer clips). **Scope when triggered**: vendor evaluation (Modal vs Replicate vs self-hosted), prototype with `atharva-bench-no-weight.mov`, threshold validation against current MediaPipe Heavy outputs, swap behind a feature flag, ramp 10% → 100%. **Estimated cost**: $0.001-$0.005 per analysis; estimated 50-100x inference speedup. | L | post-beta | NFR-OPER-02 | deferred |

---

## Phase 3 — LangGraph Agent Orchestration (seeded 2026-04-13, session 27)

**Phase 3 is deferred until post-Saturniq (mid-August 2026).** Per STRATEGY.md, feature work freezes after L2 beta launch (May 9, 2026). Phase 3 tasks are seeded here for reference but NOT active.

Active agents when Phase 3 begins: add `spelix-langgraph-engineer`.

8 Must requirements from SRS.

### Batch 1 — LangGraph Agent Core

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| L2-PHASE3-BATCH1 | Phase 3 Batch 1 — LangGraph agent core (FR-AICP-18/19/20) | XL | — | FR-AICP-18, FR-AICP-19, FR-AICP-20 | done (PR #52 → `5df0921`) |
| P3-001 | LangGraph StateGraph definition — AgentState with tools: get_rep_metrics, retrieve_papers, retrieve_coach_brain, flag_form_deviation, compare_to_user_history, generate_correction_plan. Conditional edges for deterministic flow initially. | XL | — | FR-AICP-18 | done — covered by L2-PHASE3-BATCH1 |
| P3-002 | Adaptive agent reasoning — agent reasons based on observations, not fixed script. Tool selection via LLM with descriptive docstrings. | L | P3-001 | FR-AICP-19 | done — covered by L2-PHASE3-BATCH1 |
| P3-003 | LangSmith tracing integration — full agent reasoning trace logged per analysis | M | P3-001 | FR-AICP-20 | done — covered by L2-PHASE3-BATCH1 |

### Batch 2 — Distillation Pipeline

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| L2-PHASE3-BATCH2 | Phase 3 Batch 2 — distillation pipeline (FR-BRAIN-06/14/16/17/18) | XL | L2-PHASE3-BATCH1 | FR-BRAIN-06, FR-BRAIN-14, FR-BRAIN-16, FR-BRAIN-17, FR-BRAIN-18 | done (PR #77 → `8e587c3`) |
| P3-004 | LangGraph distillation StateGraph — extract_insights → validate_quality → [gate] → lifecycle_decision → cove_verify → format_entry → store_entry. Quality gate: eval_scores overall ≥0.85 AND correctness ≥0.8 for approval. Runs async after analysis completion via streaq task, never blocks coaching response. FR-BRAIN-14 CoVe slim service + FR-BRAIN-16 consent cascade extension to candidates table also land in this batch. | XL | P3-001 | FR-BRAIN-06, FR-BRAIN-14, FR-BRAIN-16 | done — covered by L2-PHASE3-BATCH2 |
| P3-005 | Knowledge lifecycle operations — cosine similarity dedup before creating entries. >0.92: NOOP, 0.75–0.92: UPDATE (increment confirmation_count + append source_analysis_id same-txn, FR-BRAIN-18), <0.75: ADD new candidate. Contradiction flag set when UPDATE + CoVe unverified. | L | P3-004 | FR-BRAIN-17, FR-BRAIN-18 | done — covered by L2-PHASE3-BATCH2 |
| P3-008 | FR-BRAIN-08 auto-triage — confidence-based auto-approve/auto-reject thresholds for distilled candidates. Blocks on ≥50 human-reviewed candidates for threshold calibration (per SRS "start conservative"). | M | P3-004, P3-005 | FR-BRAIN-08 | deferred post-L2 |

### Batch 3 — Admin & Frontend

| ID | Title | Size | Deps | SRS IDs | Status |
|----|-------|------|------|---------|--------|
| P3-006 | Coach Brain expert review queue for distillation candidates — single-screen review cards with eval scorecard, CoVe result, approve/reject/edit actions. Compensation entries flagged for biomechanics-qualified review. | L | P3-004 | FR-ADMN-12, FR-BRAIN-07 | done — `3bffdd9` (PR #82, session 43) |
| P3-007 | "How AI Reasoned" sidebar on results page — readable LangGraph agent trace rendered from LangSmith data | M | P3-003 | FR-RESL-07 | done — `70d736c` (PR #83, session 44) |
| D-037 | Surface top 2 similar existing approved entries on review card (FR-ADMN-12 completeness — current impl shows 1 via nearest_entry_id from candidate schema) | S | P3-006 | FR-ADMN-12 | done — `ed5527d` (new GET /coach-brain/candidates/{id}/similar endpoint + SimilarEntriesList component; session 54) |
| D-038 | Add `compensation` to coach_brain_candidates.entry_type CHECK constraint + biomechanics reviewer routing (UI banner already renders forward-compatibly) | S | — | FR-ADMN-12 | done — `e87f2c3` (migration 012 + EntryTypeLiteral widening + distillation prompt + frontend cast cleanup; session 54) |
| D-039 | Re-run CoVe after admin content edit on approve (current impl carries original cove_verified to entry.extra_metadata; needs throttling to avoid Haiku max_tokens blowup) | M | M-05 | FR-BRAIN-14 | done — `24aec8d` (PR #TBD, session 56). CoVe re-runs via BrainCoveService.verify_claim on fresh papers_rag contexts when admin edits content during approval. Falls back to original values on any failure. ADR-COVE-RERUN-01. |
| D-040 | Replace fixed-threshold rep detection state machine with `scipy.signal.find_peaks` peak/valley extraction in `backend/app/cv/rep_detection.py::detect_reps`. Final design ended up **hybrid** (state machine primary + peak/valley fallback) after session 45 fixture calibration showed pure peak/valley over-counts by 3-4x on noisy real-video signals (`atharva-bench.mov` 5→21, `atharva-squat.mov` 5→14). Hybrid is strict Pareto improvement: 3 partial-lockout fixtures unlocked, 0 regressions. See ADR-REPDET-01 + PR #84. | M | — | FR-CVPL-15, FR-REPM-01, FR-REPM-05 | done — `bc17250` (PR #84, session 45) |
| D-041 | Degenerate scoring short-circuit in `backend/app/services/pipeline.py` Step 9b: when `rep_metrics` is empty OR `session_confidence < 0.50` (the "Very Low" boundary), write `None` to all `form_score_*` columns and skip `OverallFormScore.compute`. Frontend FormScoreCards already renders `None` as "Not available" cards + hides overall rating — no frontend edit. Eliminates the session 44 trust-violating contradiction (Very Low banner + 10.0 Technique). Shipped with D-040 in PR #84. | S | — | FR-SCOR-02, FR-SCOR-04, FR-SCOR-07 | done — `bc17250` (PR #84, session 45) |
| D-042 | Wire `_PROMINENCE_DEG` + `_STANDING_THRESHOLD` + `_DEPTH_THRESHOLD` + `_MIN_REP_DURATION_S` in `backend/app/cv/rep_detection.py` through `ThresholdConfig` (FR-SCOR-11) so Expert Reviewers can tune rep-detection knobs via PR. Follow-up to D-040. Session 53, ADR-REPDET-04. Closes spelix-auditor H-1 on PR #84. | S | — | FR-SCOR-11 | done |
| D-043 | Additive test: partial descent signal with <20° prominence amplitude in `test_rep_detection.py` — must return 0 reps from both state-machine and peak/valley paths. Follow-up from spelix-auditor M-2 on PR #84. Session 53. | S | — | — | done |
| D-044 | Investigate `atharva-bench.mov` signal-quality over-count (state machine returns 13 reps vs hand count 5 — same on main since before PR #84). Suspected MediaPipe landmark flicker or Savgol `window=7, polyorder=3` over-smoothing creating mid-range valleys. Not urgent — loaded bench is the rarer case on prod today, but worth understanding before beta launch. | M | — | FR-CVPL-15 | **deferred-post-L2** — session 51 investigation (see ADR-REPDET-03) rejected parameter tuning (0/640 combos land 5/1/5/5), Savgol widening (w=11 → 13→12 only), and Tier-1 visibility gating (0.30–0.35 thresholds leave bench at 13; 0.40 breaks squat). Revised root cause: the 13 detected motions correspond to 5 working reps + ~8 setup/re-grip/rack motions; detector is not hallucinating. Superseded by D-056. Investigation scripts preserved in `backend/scripts/oneoff/{diagnose,sweep,prototype_visibility_gate}_rep_detection_d044.py`. |
| D-056 | **Post-L2 successor to D-044.** Distinguish "working reps" from "non-working bar motions" (setup, re-grip, rack, tentative dips) in the rep detector. Likely feature set: bar-path velocity profile, dwell-time at BOTTOM state, ROM consistency vs trailing-rep mean, descent-to-ascent symmetry. May need a secondary classifier (lightweight model or rule cascade). Design work needed; not a parameter tweak. Re-opens when sprint schedule allows and a broader fixture library is available (single lifter's bench is insufficient for calibration). | L | — | FR-CVPL-15, FR-REPM-01 | open-post-L2 |
| D-045 | Investigate why `retrieval_source=papers_only_fallback` persists on prod even after M-04 re-embedded all 24 seeds with the FR-BRAIN-03 contextualized prefix (session 46 E2E, bench fixture `atharva-bench-nw-10s-720p.mp4`, analysis `6aa7b42b`). | M | — | FR-BRAIN-03, FR-BRAIN-05, ADR-BRAIN-02, ADR-BRAIN-08 | done — `811a6c3` (PR #87, session 47). All four backlog hypotheses (a/b/c/d) **falsified** by `backend/scripts/oneoff/diagnose_coach_brain_retrieval.py` run on prod: bench Q1 agent query "bench flat coaching cue correction" scored 0.32 on Cohere Rerank 4.0 against the bench seed corpus (well below 0.65 hybrid threshold), while squat Q1 scored 0.84 and deadlift Q1 scored 0.92 — both crossing 0.82 primary. Q4 self-query ceiling = 0.99 across all three exercises (seeds embed fine; corpus fine; prefix fine). Root cause: bench seed content uses "bench press"/"elbows"/"scapula" vocabulary not "bench" alone, so a 5-token agent query lacks lexical overlap. Fix: per-exercise vocabulary tail (drawn from seed `trigger_tags` + content nouns) appended to query in `app/agents/tools.py::retrieve_coach_brain`. Verified end-to-end on prod: same fixture, fresh upload `de316a7a-b4fd-4fb4-afc4-a1d6be596fa2` flipped to `retrieval_source=coach_brain_primary` (vs prior `papers_only_fallback`). Screenshot `e2e/screenshots/d045-post-fix-bench-coach-brain-primary-de316a7a.png`. |
| D-046 | Hoist `_HAIKU_MODEL = "claude-haiku-4-5-20251001"` into a shared constant in `app/constants.py` (or `app/config.py`). Currently duplicated in `app/distillation/cove_brain.py:25` and `app/distillation/extract.py:_HAIKU_MODEL`; `app/services/cove.py` has its own model constant. Drift risk is low but real. Follow-up from spelix-auditor M-03 on PR #85. | S | — | — | done — `72aac69` (PR #100, session 52) |
| D-047 | Additive coverage test for the pre-fix M-05 failure mode in `test_distillation_cove_brain.py`: stub `instructor_client.chat.completions.create` with `side_effect=ValidationError(...)` and assert `BrainCoveResult.explanation == "evaluation_failed: ValidationError"`. Prevents silent regression if a future refactor drops max_tokens below the 2048 ceiling. Follow-up from code-reviewer suggestion on PR #85. | S | — | FR-BRAIN-14 | done — `72aac69` (PR #100, session 52) |
| D-048 | Apply the M-05-style max_tokens bump to the coaching-path `app/services/cove.py::CoveVerificationService`. Prod E2E on session 46 observed output_tokens=1024→2048→3072 exponential retry, all truncated, on bench analysis `6aa7b42b`. Coaching succeeds because CoVe failure falls back gracefully, but `eval_scores.cove_verified=false` is persisted spuriously. Needs the same 2048+ headroom and the same TDD gate as M-05. | S | M-05 | FR-AICP-08 | done — `4ef4091` |
| D-049 | Patch `Citation` Pydantic serializer warnings observed during coaching runs on prod. Worker log shows `PydanticSerializationUnexpectedValue(Expected 'Citation' — serialized value may not be as expected ...)` on every coaching call with citations. Root cause likely a dict-vs-model mismatch in how `CoachingOutput.citations` is populated somewhere upstream (instructor deserialization?). Non-functional — coaching still completes — but the log spam makes production-log triage harder. | S | — | FR-AICP-01, FR-AICP-07 | done — `72aac69` (PR #100, session 52). Root cause: instructor `create_partial` yields progressive snapshots where `citations` is `list[dict]` vs schema `list[Citation]`; Pydantic v2 fires the warning per partial. Fix is `warnings=False` kwarg on the SSE-only per-partial `model_dump_json` call. Final validated `CoachingOutput` returned unchanged; DB-persistence path (`analysis_worker.py:591,784` via `.model_dump()`) untouched. |
| D-050 | Refine `CoveVerificationService` claim-extraction prompt to focus on PRINCIPLE-level claims rather than lifter-specific MEASUREMENT claims. | S | D-048 | FR-AICP-08, ADR-COVE-02 | done — `6c41953` (PR #90, session 49). Core goal achieved: session 49 prod E2E on analysis `c46023c9` produced 17/17 principle-shaped claims (zero measurements). Faithfulness 0.92→0.82 (above 0.8 gate). `cove_verified` still false for a NEW reason (extractor hallucinates inversions + invents out-of-coaching principles) — filed as D-052. |
| D-051 | Auditor M-02 follow-up from PR #88: add a regression test for the `else` branch of Step 4 revision in `_run_cove_loop` (`iteration == max_iterations`). The new D-048 `test_cove_max_tokens_meets_headroom_revision_path` exercises only the `if iteration < max_iterations` branch; the `else` "final iteration exhausted" revision at `backend/app/services/cove.py:389` is structurally identical but untested by max_tokens assertion. Add a test with `max_iterations=1` and a "No" answer to exercise the else path. | S | D-048 | FR-AICP-08 | done — `72aac69` (PR #100, session 52) |
| D-052 | Tighten the D-050 claim-extraction prompt with an explicit inversion-guard + add a negative worked example for inverted-principle hallucination. Session 49 E2E on analysis `c46023c9` showed iteration 2 reached 7/8 Yes but the one No blocked convergence: the extractor emitted "excessively slow eccentric makes bar path control harder" — the source actually says a rushed/fast descent is the problem. Iteration 1 additionally invented "minimum of 60°" (coaching never stated a minimum), "60–100° reference range", and "stretch-shortening cycle disruption" claims that weren't in the coaching output at all. The current prompt's "do not invent a principle that was not written" rule is too soft — needs an explicit "do not invert, re-direction, or extrapolate beyond what the coaching says" clause + a before/after worked example showing an inverted-principle rejection. | S | D-050 | FR-AICP-08, ADR-COVE-02, ADR-COVE-03 | done — `8740388` (PR #92, session 50). Core goal achieved: session 50 prod E2E on analysis `43f25db8` produced `cove_verified=true` (was false) with iter 2 converging 7/7 Yes on principle-shaped claims. Faithfulness improved 0.82→0.88. Iter 1 still surfaced one extrapolation ("60–100°"), but CoVe's verification + Step 4 revision correctly narrowed it to the sourced "45–75°" range; convergence reached in iter 2. |
| D-053 | Investigate + fix `lifecycle_decision: qdrant search failed ('AsyncQdrantClient' object has no attribute 'search') — treating as ADD` warnings observed in session 49 worker logs during distillation runs. Known gotcha per `backend/CLAUDE.md` "qdrant_client passed to lifecycle_decision must support .search(...) directly. QdrantClientWrapper only exposes .query_points, so deps.py passes the raw _client (AsyncQdrantClient). Watch for breakage if the wrapper API changes." The wrapper API has apparently changed — `AsyncQdrantClient.search` is deprecated/removed in newer qdrant-client. Currently silent-fallback to `ADD` which over-admits duplicate candidates to the review queue. Migrate `lifecycle_decision` to `query_points` or the new API. | M | — | FR-BRAIN-06, FR-BRAIN-17, ADR-DISTILL-01, ADR-DISTILL-07 | done — `88fb0ae` (PR #94, session 50). Migrated to `QdrantClientWrapper.query_points` via deps.py wrapper pass-through. Prod E2E on analysis `0e5d755b` produced 5 candidates with real non-zero `nearest_cosine_sim` (0.72, 0.74, 0.72, 0.84 UPDATE, 0.88 UPDATE) — was uniformly `0.0` ADD pre-fix. Zero `.search` warnings in worker logs post-deploy. |
| D-054 | Narrow the `except Exception` catch in `backend/app/distillation/lifecycle.py::lifecycle_decision` to distinguish Qdrant auth failures (401/403) from transient network errors. Currently all failures are logged at WARNING level and routed to `ADD` — which masks sustained auth drift (e.g. API key rotation or revocation) at a WARNING-only severity. Filed from `spelix-security-reviewer` on PR #94 as a non-blocking observation: "A sustained 401/403 would be operationally invisible at WARNING level. ... Future improvement would be to inspect `exc` type or HTTP status and emit `logger.error` for 4xx specifically." Keep the broad fallback intact (distillation must not crash the graph on transient errors) but promote 4xx to ERROR so operators paging on ERROR logs are notified. | S | — | FR-BRAIN-17, ADR-DISTILL-07 | done — `72aac69` (PR #100, session 52). New `_is_qdrant_4xx` helper (duck-types on `status_code` attribute) routes 401/403/404/429 → `logger.error`; everything else stays at `logger.warning`. Broad ADD-fallback preserved. Security-reviewer HIGH on PR #100 also addressed: 4xx log string no longer interpolates raw `exc` (which embeds response `content` body that could echo API-key fragments from Qdrant Cloud); only `status_code` + `type(exc).__name__` are logged. |
| D-055 | Add `testpaths = ["tests"]` under `[tool.pytest.ini_options]` in `backend/pyproject.toml` to make the pytest collection boundary explicit. Currently smoke scripts under `backend/scripts/oneoff/` are protected from accidental collection only by the absence of `def test_*` / `Test*` symbols — a future script that inadvertently defines a helper named `test_*` would be silently collected and fail in CI due to missing env vars (ANTHROPIC_API_KEY, etc.). Pre-existing hygiene gap; filed from `spelix-auditor` M-01 on PR #92 as non-blocking. | S | — | — | done — `72aac69` (PR #100, session 52) |

---

## Completed — L2 Sprint Day 13 — Priority 2 maintenance bundle (2026-04-19, session 52)

PR #100 merged to `main` as `72aac69` via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash). 10 commits preserved on the branch: `d5aa1e4` testpaths (D-055) → `b763ff7` hoist HAIKU_MODEL (D-046) → `81507b9` ValidationError test (D-047) → `7a2645f` failing serializer-warning test (D-049) → `533b78c` warnings=False fix (D-049) → `99daca1` else-branch revision test (D-051) → `e9ca620` failing 4xx ERROR test (D-054) → `0750ab3` _is_qdrant_4xx + logger.error (D-054) → `0197f6c` docstring symbolic refs (auditor M-01 follow-up) → `b3b514b` redact exc in 4xx log (security HIGH follow-up). CI 6/6 green pre-merge and post-merge; Deploy to Production green on `72aac69`; droplet containers `spelix-backend-1` / `spelix-worker-1` restarted 2min post-deploy and healthy. Backend: **1705 → 1710 tests** (+5 new: D-047 H-2 invariant guard, D-049 serializer-warning guard, D-051 else-branch max_tokens guard, D-054 4xx-ERROR + transient-WARNING guards). Ruff + pyright clean. No frontend changes. No new ADR — all six items execute existing decisions (ADR-DISTILL-03, ADR-COVE-02, ADR-DISTILL-07) or are pure CI hygiene.

**Audits (pre-merge):**
- `spelix-auditor` → PASS (0 CRITICAL / 0 HIGH). 1 valid MEDIUM (M-01 `cove.py` docstring still hardcoded the literal — addressed in-branch as `0197f6c`). 2 false positives (M-02/M-03 — auditor read truncated views of the test files; verified by grep that the claimed missing content exists).
- `spelix-security-reviewer` → PASS_WITH_FINDINGS (0 CRITICAL). 1 HIGH (`logger.error("... (%s)", exc)` could log `UnexpectedResponse.__str__` content which on 401 may echo API-key fragments from Qdrant Cloud — addressed in-branch as `b3b514b`, drops `exc` interpolation in favour of `status_code` + `type(exc).__name__`).

**Smoke (post-deploy, 2026-04-19):**
- Frontend `https://spelix.app/` → 307 (auth redirect, normal)
- Backend containers: `spelix-backend-1` / `spelix-worker-1` both up ~2min post-deploy, healthy status
- `docker logs spelix-worker-1 --since 10m 2>&1 | grep -c PydanticSerializationUnexpectedValue` → 0 (but worker restarted 2min ago; long-run post-traffic validation deferred to natural traffic or a subsequent admin session)
- No spurious `ERROR.*lifecycle_decision` in post-deploy window

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| D-046 | Hoist HAIKU_MODEL to app/constants.py | done | S | — | — | `72aac69` | `backend/app/constants.py`, `backend/app/distillation/cove_brain.py`, `backend/app/distillation/extract.py`, `backend/app/services/cove.py` |
| D-047 | Regression test for BrainCoveService ValidationError path | done | S | — | FR-BRAIN-14 | `72aac69` | `backend/tests/unit/test_distillation_cove_brain.py` |
| D-049 | Suppress PydanticSerializationUnexpectedValueWarning on streaming partials | done | S | — | FR-AICP-01, FR-AICP-07 | `72aac69` | `backend/app/services/coaching.py`, `backend/tests/unit/test_coaching_streaming.py` |
| D-051 | Regression test for `_run_cove_loop` else-branch revision | done | S | D-048 | FR-AICP-08 | `72aac69` | `backend/tests/unit/test_cove.py` |
| D-054 | Promote Qdrant 4xx failures in lifecycle_decision to logger.error | done | S | — | FR-BRAIN-17, ADR-DISTILL-07 | `72aac69` | `backend/app/distillation/lifecycle.py`, `backend/tests/unit/test_distillation_lifecycle.py` |
| D-055 | Add testpaths = ["tests"] to backend/pyproject.toml | done | S | — | — | `72aac69` | `backend/pyproject.toml` |

---

## Completed — L2 Sprint Day 12 — D-053 lifecycle_decision Qdrant API migration (2026-04-18, session 50)

PR #94 merged to `main` as `88fb0ae` via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash). 5 commits preserved: `f4d1040` failing tests (migrated mocks + regression guard) → `2c5850a` lifecycle.py migration → `1f112c5` deps.py simplification → `df3cdc1` CLAUDE.md gotcha → `5badb4f` test-assertion review fix-up. CI 6/6 green pre-merge; Deploy to Production green on merge commit; droplet HEAD matches + all containers healthy. Backend: 1702 → 1703 tests (+1 D-053 regression guard; 5 existing lifecycle tests migrated in place). Ruff + pyright clean. No frontend changes.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-D053-01 | TDD failing tests: migrate 5 existing `test_distillation_lifecycle.py` tests to mock `query_points` returning QueryResponse envelope; add new `test_lifecycle_decision_never_calls_legacy_search` regression guard via `MagicMock(spec=QdrantClientWrapper)` (plan's explicit fallback — the original `__getattr__` override failed against MagicMock's `_unsupported_magics`). | done | S | — | FR-BRAIN-17 | `f4d1040` | `backend/tests/unit/test_distillation_lifecycle.py` |
| L2-D053-02 | Impl: migrate `lifecycle_decision` from `qdrant_client.search(...)` to `qdrant_client.query_points(...)`. Unpack `response.points`. Updated docstring (D-053 / ADR-DISTILL-07) + warning-log message. Preserved try/except safety net. FR-BRAIN-17 thresholds unchanged. | done | S | L2-D053-01 | FR-BRAIN-17, ADR-DISTILL-07 | `2c5850a` | `backend/app/distillation/lifecycle.py` |
| L2-D053-03 | Simplify `build_distillation_ctx`: pass `qdrant_wrapper` directly (removed `qdrant_raw = wrapper._client` escape hatch + justifying module-docstring paragraph). | done | S | L2-D053-02 | — | `1f112c5` | `backend/app/workers/deps.py` |
| L2-D053-04 | Update `backend/CLAUDE.md` gotcha — replaced stale "must support .search" bullet with post-D-053 note referencing `QdrantClientWrapper.query_points`, ADR-DISTILL-07, the regression-guard test name, and the try/except safety-net rationale. | done | S | L2-D053-02 | — | `df3cdc1` | `backend/CLAUDE.md` |
| L2-D053-05 | Code-review fix-up: `test_distillation_worker_body.py:276` asserted `ctx["qdrant_client"] is fake_qdrant_wrapper._client` — stale post-D-053 when deps.py returns the wrapper directly. Plan's Task 4 Step 3 flagged this as a potential update site; the pre-D-053 test passed silently via MagicMock attribute-child caching even though the identity check should have failed. One-line fix: `is fake_qdrant_wrapper._client` → `is fake_qdrant_wrapper`. | done | S | L2-D053-03 | — | `5badb4f` | `backend/tests/unit/test_distillation_worker_body.py` |
| L2-D053-06 | PR #94 → CI 6/6 green → `spelix-auditor` PASS (0 CRITICAL / 0 HIGH / 0 MEDIUM, all 10 checklist items verified) → `spelix-security-reviewer` PASS (0 CRITICAL / 0 HIGH; noted non-blocking monitoring gap: 4xx auth failures to Qdrant would currently be swallowed at WARNING level, future improvement suggestion) → merge (`merge_method="merge"`) → Deploy to Production auto-run → droplet HEAD `88fb0ae` + containers healthy → prod distillation run on fresh bench upload. | done | M | L2-D053-02, L2-D053-03, L2-D053-04, L2-D053-05 | — | `88fb0ae` | PR #94 |

**Prod verification** (session 50, fresh bench upload analysis `0e5d755b-6506-4f2b-80ca-638eca1f7ccc`):

- **Worker-log check** (`ssh spelix-droplet "docker logs spelix-worker-1 --since 10m | grep -iE 'search|query_points failed'"`): **zero matches**. Pre-D-053 every distillation run logged the `.search` `AttributeError` warning; post-D-053 the lifecycle call succeeds silently.
- **`coach_brain_candidates` sanity check** (Supabase SQL on `ORDER BY created_at DESC LIMIT 5`): all 5 candidate rows from `0e5d755b` carry **non-zero** `nearest_cosine_sim` values. Distribution:

| Row | Decision | nearest_cosine_sim | review_status |
|---|---|---|---|
| 1 | ADD | 0.7258 | pending |
| 2 | ADD | 0.7420 | pending |
| 3 | **UPDATE** | **0.8387** | superseded (confirmation row per FR-BRAIN-18) |
| 4 | **UPDATE** | **0.8757** | superseded (confirmation row per FR-BRAIN-18) |
| 5 | ADD | 0.7205 | pending |

Pre-D-053 every row would have been `nearest_cosine_sim=0.0, lifecycle_decision=ADD`. Post-D-053 the FR-BRAIN-17 routing works as spec'd: the UPDATE band (0.75–0.92) correctly matches, triggers FR-BRAIN-18's `confirmation_count` bump, and writes an audit-only `superseded` row; the ADD band (<0.75) routes novel candidates to the review queue. Distillation task completed with `status: 'ok'` — no swallowed exceptions.

- **Distillation task log** (`spelix-worker-1`): `task distill_analysis ■ 0d480aaec3… ← {'status': 'ok', ...}` — graph converged without any `except Exception` branch firing.

**Audits (pre-merge):**
- `spelix-auditor` → PASS. 0 CRITICAL / 0 HIGH / 0 MEDIUM. All 10 checklist items verified: FR-BRAIN-17 thresholds unchanged, call signature matches wrapper API, `response.points` unpacking correct, try/except preserved with updated log message, zero `wrapper._client` grep hits, CLAUDE.md gotcha updated, regression-guard test structurally sound, no backfill (out of scope), retrieval paths untouched, git discipline clean.
- `spelix-security-reviewer` → PASS. 0 CRITICAL / 0 HIGH. All 10 checks clean. Noted non-blocking observation: sustained 401/403 auth failures to Qdrant Cloud would currently be swallowed at WARNING level (the broad `except Exception` catch is intentional per ADR-DISTILL-07 to prevent distillation crashes). Future improvement suggestion: narrow the catch or emit `logger.error` for 4xx specifically. Not a merge blocker.

**Reviews (per subagent-driven-development):**
- Spec compliance reviewer → PASS WITH NOTED DEVIATION (plan-authorized fallback: `spec=QdrantClientWrapper` instead of `__getattr__` override; plan's Abort/rollback explicitly prefers the `spec=` approach). One Important issue surfaced on file outside scope (`test_distillation_worker_body.py:276` stale assertion) — fixed as L2-D053-05.
- (No separate code-quality reviewer dispatch; the spec reviewer's finding + one-line fix-up was sufficient for this infrastructure-only diff.)

**Class-of-bug lesson captured in ADR-DISTILL-07**: MagicMock without `spec=` silently satisfies any attribute access, so unit tests don't catch SDK API drift. Use `MagicMock(spec=SomeClass)` when mocking external clients whose API surface may drift between pinned versions.

---

## Completed — L2 Sprint Day 12 — D-052 CoVe inversion + extrapolation guards (2026-04-18, session 50)

PR #92 merged to `main` as `8740388` via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash). 4 commits preserved: `8ce576a` failing tests → `2d28fa5` prompt tightening → `6b27045` adversarial smoke script → `323fe9b` code-review fix-up (drop trailing-space negative-example marker that false-positive-matched the D-050 "DO NOT extract MEASUREMENT-LEVEL" paragraph). CI 6/6 green on pre-merge HEAD `323fe9b`; Deploy to Production green on merge commit `8740388`; droplet HEAD matches + all containers healthy. Backend: 1701 → 1704 tests (+3 D-052 structural-assertion tests). Frontend unchanged. Ruff + pyright clean.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-D052-01 | TDD failing tests: `test_claim_extraction_prompt_prohibits_inversion`, `test_claim_extraction_prompt_prohibits_extrapolation`, `test_claim_extraction_prompt_has_negative_worked_examples` | done | S | — | FR-AICP-08 | `8ce576a` | `backend/tests/unit/test_cove.py` (+121 lines) |
| L2-D052-02 | Impl: extend `_build_claim_extraction_prompt` with inversion-guard paragraph (invert / reverse / negate / direction) + extrapolation-guard paragraph (minimum / maximum / reference range) + 2 new `Do NOT extract:` worked-example blocks. All D-050 content preserved verbatim. | done | S | L2-D052-01 | FR-AICP-08, ADR-COVE-03 | `2d28fa5` | `backend/app/services/cove.py` |
| L2-D052-03 | Adversarial live-API smoke script: `smoke_cove_claim_extraction_d052.py` — fast-descent issue (inversion trigger) + bare optimal-range 45–75° issue (extrapolation trigger). Sibling of D-050 smoke. Not CI. | done | S | L2-D052-02 | — | `6b27045` | `backend/scripts/oneoff/smoke_cove_claim_extraction_d052.py` (new) |
| L2-D052-04 | Code-review fix-up: tighten `negative_example_markers` tuple from `("do not extract:", "do not extract ")` to `("do not extract:",)` — the trailing-space form false-positive-matched the D-050 paragraph `"DO NOT extract MEASUREMENT-LEVEL"`, creating a regression-survival hole. | done | S | L2-D052-01 | — | `323fe9b` | `backend/tests/unit/test_cove.py` |
| L2-D052-05 | PR #92 → CI 6/6 green → `spelix-auditor` PASS_WITH_FINDINGS (0 CRITICAL / 0 HIGH / 2 MEDIUM pre-existing hygiene: missing pytest `testpaths`, minor smoke-script style inconsistency vs D-050 precedent) → `spelix-security-reviewer` PASS (0 findings) → merge (`merge_method="merge"`) → Deploy to Production auto-run → droplet HEAD `8740388` + containers healthy → Playwright E2E on prod bench fixture. | done | M | L2-D052-02, L2-D052-03, L2-D052-04 | — | `8740388` | PR #92 |

**Prod E2E verification** (session 50, analysis `43f25db8-c922-4211-bb98-5266c8ff6f74`, bench fixture `atharva-bench-nw-10s-720p.mp4`, fresh upload under admin test account):

| Metric | Session 49 (`c46023c9`, post-D-050) | Session 50 (`43f25db8`, post-D-052) |
|---|---|---|
| analysis status | completed | completed |
| `retrieval_source` | `coach_brain_primary` ✅ | `coach_brain_primary` ✅ |
| `degraded_mode` | false | false |
| `eval_scores.faithfulness` | 0.82 | **`0.88`** ✅ (above 0.80 gate; `faithfulness_passed=true`) |
| `eval_scores.cove_verified` | `false` (hallucinated-inversion No) | **`true`** ✅ (iter 2 converged 7/7 Yes) |
| `cove_iterations` count | 2 | 2 |
| iter1 / iter2 claim count | 9 / 8 | 7 / 7 |
| iter 2 Yes / No / Uncertain | 7 / 1 / 0 | **7 / 0 / 0** ✅ |
| converged (iter 2) | false | **true** ✅ |
| console errors / 4xx-5xx | 0 | 0 |

**Gate verdicts** (per D-052 plan Task 7):
- **Gate A (`cove_verified=true`)**: ✅ **PASS** — flipped from false → **true**. Iteration 2 reached full convergence (7/7 Yes, all principle-shaped, all source-cited).
- **Gate B (`faithfulness ≥ 0.70`)**: ✅ **PASS** — 0.88 (not the predicted regression to 0.70–0.82 band; D-052 was net-positive on faithfulness).
- **Gate C (no iter-2 inversions / extrapolations)**: ✅ **PASS** — all 7 iter-2 claims correctly principle-shaped, zero inversions, zero invented min/max/alternate-range.

**Residual observation** (non-blocker): iteration 1 still surfaced ONE extrapolation — claim 1: "Optimal elbow angle at the bottom of the bench press is 60–100° from the torso" (coaching-output 45–75° range extrapolated to 60–100°). Verification correctly answered No (sources 1+4 specify 45–75°), Step 4 revision narrowed the iter-1 claim set to the correct "45–75°" for iter 2, and iter 2 converged cleanly. CoVe's revision loop is working as designed — the guard is not a total barrier against extrapolation in iter 1, but the revision step closes the gap and iter 2 is pristine. No follow-up D-### filed; if future prod E2Es show iter-2 convergence failing for inversion/extrapolation reasons, we file a new D-### then. Screenshot: `e2e/screenshots/d052-post-fix-results-43f25db8.png`.

**Audits (pre-merge):**
- `spelix-auditor` → PASS_WITH_FINDINGS. 0 CRITICAL / 0 HIGH. 2 MEDIUM non-blocking: M-01 missing `testpaths = ["tests"]` under `[tool.pytest.ini_options]` (pre-existing hygiene gap not introduced by this PR); M-02 minor smoke-script client-instantiation style drift vs D-050 precedent (cosmetic, not a security issue).
- `spelix-security-reviewer` → PASS. 0 CRITICAL / 0 HIGH. All checks clean.

**Reviews (per subagent-driven-development):**
- Spec compliance reviewer → PASS (4/4 checks: tests verbatim per plan, prompt body verbatim per plan Task 3 Step 2, smoke script verbatim per plan Task 4 Step 1, no unrelated drift).
- Code quality reviewer → APPROVED WITH MINOR ISSUES (1 Important fix applied as L2-D052-04; 2 Minor noted non-blocking).

---

## Completed — L2 Sprint Day 11 — D-050 CoVe claim extraction principle-level (2026-04-18, session 49)

PR #90 merged to `main` as `6c41953` via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash). 4 commits preserved: `e2d74e6` failing tests → `647450a` prompt rewrite → `7cab235` smoke script → `9d6a447` code-review fix-up (tighten `Extract:` label assertion from substring check to count-based check). CI 6/6 green on pre-merge HEAD `9d6a447`; Deploy to Production green 37s on merge commit `6c41953`; droplet + containers confirmed healthy. Backend: 1698 → 1701 tests (+3 D-050 structural-assertion tests). Frontend unchanged. Ruff + pyright clean.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-D050-01 | TDD failing tests: `test_claim_extraction_prompt_emphasises_principle_level`, `test_claim_extraction_prompt_includes_worked_examples`, `test_claim_extraction_prompt_still_references_falsifiability` | done | S | — | FR-AICP-08 | `e2d74e6` | `backend/tests/unit/test_cove.py` (+105 lines) |
| L2-D050-02 | Impl: rewrite `_build_claim_extraction_prompt` body — explicit principle vs measurement distinction, SKIP directive, translate-not-invent rule, 2+2 worked examples | done | S | L2-D050-01 | FR-AICP-08, ADR-COVE-02 | `647450a` | `backend/app/services/cove.py` (+50/-7) |
| L2-D050-03 | Live-API smoke script for operator qualitative review (not CI) | done | S | L2-D050-02 | — | `7cab235` | `backend/scripts/oneoff/smoke_cove_claim_extraction_d050.py` (new, +153) |
| L2-D050-04 | Code-review fix-up: tighten `Extract:` label assertion from `"extract" in lowered` (too weak — satisfied by opening-sentence `extracting` token) to `lowered.count("extract:") >= 2` (requires worked-example labels) | done | S | L2-D050-01 | — | `9d6a447` | `backend/tests/unit/test_cove.py` |
| L2-D050-05 | PR #90 → CI 6/6 green (Backend Tests 2m14s, Backend Lint 35s, Frontend Lint 24s, Frontend Tests 1m23s, Secret Scanning 10s, Vercel pass) → `spelix-auditor` PASS_WITH_FINDINGS (0 CRITICAL / 0 HIGH / 3 MEDIUM all non-blocking: M-01 ADR deferred, M-02 backlog deferred, M-03 SaMD-exclusion test suggestion) → `spelix-security-reviewer` PASS (0 findings, 8/8 checks) → merge (`merge_method="merge"`) → Deploy to Production auto-run 37s → droplet HEAD `6c41953` + containers healthy → Playwright E2E on prod bench fixture | done | M | L2-D050-02, L2-D050-03, L2-D050-04 | — | `6c41953` | PR #90 |

**Prod E2E verification** (session 49, analysis `c46023c9-b098-4083-9c19-dad174b14a04`, bench fixture `atharva-bench-nw-10s-720p.mp4`, fresh upload under admin test account):

| Metric | Session 48 (`bfbed270`, post-D-048) | Session 49 (`c46023c9`, post-D-050) |
|---|---|---|
| analysis status | completed | completed |
| `retrieval_source` | `coach_brain_primary` ✅ | `coach_brain_primary` ✅ |
| `degraded_mode` | false | false |
| `eval_scores.faithfulness` | **`0.92`** | **`0.82`** (above 0.8 gate; `faithfulness_passed=true`) |
| `eval_scores.cove_verified` | `false` (measurement Uncertains) | `false` (hallucinated-inversion No) |
| `cove_iterations` count | 2 | **2** |
| iter1 claims / iter2 claims | 11 / 15 | **9 / 8** (tighter extraction) |
| Claim-shape (iter 2) | 9/15 measurement-Uncertain | **0/8 measurements, 7/8 principle-Yes** ✅ |
| converged | false | false |
| console errors / 4xx-5xx | 0 | 0 |

**Key finding:** D-050 core goal ACHIEVED. All 17 claims across 2 iterations are principle-level ("Optimal elbow angle at the bottom of the bench press is 45–75° from the torso", "The recommended eccentric phase duration for bench press is approximately 2 seconds", "At lockout, the bar should be directly over the shoulder joint..."). Zero lifter-specific measurement claims. Compare to session 48 `bfbed270` which had claims like "Did the eccentric phase duration measure 5.16 seconds?" — these are gone.

`cove_verified` remained false for a DIFFERENT reason (not a D-050 regression — a newly-surfaced hallucination pattern). Iteration 2 reached 7/8 Yes but the one No blocked convergence: extractor emitted "excessively slow eccentric makes bar path control harder" (source 2 says fast descent is the problem — extractor inverted the direction). Iteration 1 additionally invented "minimum of 60°", "60–100° reference range", "stretch-shortening cycle disruption from extreme eccentric" — principles not in the coaching output. The "translate-not-invent" rule in the refined prompt needs strengthening against inversions and extrapolations. Filed as D-052. Screenshot: `e2e/screenshots/d050-post-fix-results-c46023c9.png`.

**Audits (pre-merge):**
- `spelix-auditor` → PASS_WITH_FINDINGS. 0 CRITICAL / 0 HIGH. 3 MEDIUM: M-01 ADR-COVE-02 not yet in `decisions.md` (per-plan, landed in this docs close-out commit); M-02 D-050 backlog row still open (per-plan, landed in this docs close-out commit); M-03 optional SaMD-vocabulary test hardening suggestion (non-blocking, deferred).
- `spelix-security-reviewer` → PASS. 0 CRITICAL / 0 HIGH. All 8 checks clean.

**Reviews (per subagent-driven-development):**
- Spec compliance reviewer → PASS (6/6 checks, no scope creep).
- Code quality reviewer → APPROVED after 1 Important fix-up (the L2-D050-04 assertion tightening).

---

## Completed — L2 Sprint Day 10 — D-048 coaching-path CoVe max_tokens bump (2026-04-18, session 48)

PR #88 merged to `main` as `4ef4091` via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash per `feedback_no_squash_merge.md`). 3 commits preserved: `8113499` failing tests → `4146ac7` 6× max_tokens bump → `d056848` code-review fix-up (restore cost-impact rationale in Steps 1/2 comments + defensive `calls[2]` assertion in revision-path test). CI 6/6 green on pre-merge HEAD `d056848`; Deploy to Production green 37s on merge commit `4ef4091`; droplet + containers confirmed healthy.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| D-048 | Bump `CoveVerificationService` max_tokens across all 4 CoVe steps (claim 1024, question 1024, answer 4096, revision 3072) | done | S | M-05 | FR-AICP-08, ADR-COVE-01 | `4ef4091` | `backend/app/services/cove.py:262,286,315,328,371,389`, `backend/tests/unit/test_cove.py` (+146 lines, 2 new tests) |

**Prod E2E verification** (session 48, analysis `bfbed270-1117-4a8a-8246-6d2dc9391781`, bench fixture `atharva-bench-nw-10s-720p.mp4`):

| Metric | Session 46 (`6aa7b42b`) | Session 47 (`de316a7a`) | Session 48 (`bfbed270`) |
|---|---|---|---|
| analysis status | completed | completed | completed |
| `retrieval_source` | `papers_only_fallback` ❌ | `coach_brain_primary` ✅ | `coach_brain_primary` ✅ |
| `eval_scores.faithfulness` | `0.0` ❌ | `0.0` ❌ | **`0.92`** ✅ |
| `eval_scores.cove_verified` | `false` (silent crash) | `false` (silent crash) | `false` (legit Uncertain on measurement claims) |
| `cove_iterations` count | 0 or empty | 0 or empty | **2** (real, with source-cited reasoning) |
| iter1 claims / iter2 claims | n/a | n/a | **11 / 15** |
| console errors / 4xx-5xx | 0 | 0 | 0 |

**Key finding:** The D-048 fix works as designed. The CoVe loop now runs real verifications with source-cited reasoning instead of crashing on instructor `ValidationError` retries. Faithfulness flipped 0.0 → 0.92. `cove_verified=false` still persists on this run, but for a DIFFERENT and legitimate reason — filed as new follow-up D-050. Screenshot: `e2e/screenshots/d048-post-fix-cove-verified-bfbed270.png`.

**Audits (pre-merge):**
- `spelix-auditor` → PASS_WITH_FINDINGS. 0 CRITICAL / 0 HIGH. 3 MEDIUM (non-blocking): M-01 patch-style inconsistency in pre-existing tests (future standardization), M-02 else-branch regression test gap (filed as D-051), M-03 backlog update deferred to post-merge docs commit (per session-46 precedent — acceptable).
- `spelix-security-reviewer` → PASS. 0 CRITICAL / 0 HIGH. All 8 checks clean: no SaMD/FTC language drift, no widened logging, error-handling invariant preserved, no secret exposure, no JWT/RLS/auth touch, no prompt injection surface, test mocking safe, ADR-DISTILL-05 style preserved.

## Completed — L2 Sprint Day 10 — D-045 Coach Brain query enrichment (2026-04-18, session 47)

PR #87 merged to `main` as `811a6c3` and auto-deployed via CI (Deploy to Production green). Closes D-045 (M priority follow-up from PR #85 / session 46). Investigation per `superpowers:systematic-debugging` Phase 1 → wrote read-only diagnostic `backend/scripts/oneoff/diagnose_coach_brain_retrieval.py` and ran on prod via `docker exec spelix-backend-1 /app/.venv/bin/python /app/scripts/oneoff/diagnose_coach_brain_retrieval.py`. Diagnostic measures Cohere Rerank 4.0 scores along the live agent retrieval path (`hybrid_search(coach_brain, rerank=True)` with status + exercise filters) for 4 query variants per exercise (current agent Q1, vocab-rich Q2, rep-context Q3, self-query ceiling Q4). Output table **falsified all four backlog hypotheses (a/b/c/d)** and isolated the root cause: bench Q1 scored 0.32 because seed content uses "bench press"/"elbows"/"scapula" not "bench" alone — squat/deadlift Q1 already crossed 0.82 because their exercise word appears verbatim in seed text. Q4 ceiling = 0.99 across all three (corpus is fine, prefix is fine).

Fix per `superpowers:test-driven-development`: failing test `test_retrieve_coach_brain_query_includes_seed_corpus_vocabulary` first → confirmed RED (`Actual query: 'bench x coaching cue correction'` missing required tokens) → minimal implementation: per-exercise vocabulary tail constant `_COACH_BRAIN_QUERY_VOCAB` appended to query in `app/agents/tools.py::retrieve_coach_brain` → confirmed GREEN. Backend: 1694 → 1696 tests (+2: vocabulary assertion + unknown-exercise graceful-degradation regression). Ruff + pyright clean. Auditor PASS_WITH_FINDINGS (1 CRITICAL on pre-existing FR-BRAIN-04 SRS doc gap not introduced here; 3 HIGH — H-01 falsified against runtime via prod DB query confirming `ExerciseType = Literal["squat","bench","deadlift"]`, H-02 fixed inline via additive test, H-03 vocab-drift risk documented in ADR-BRAIN-09 as accepted; M-01 fixed inline via `logger.warning` for unknown exercise types). Security PASS clean (0 CRITICAL / 0 HIGH; ADR-DISTILL-05 compliance confirmed on the new diagnostic script).

**E2E verified on prod:** Same fixture as session 46 (`atharva-bench-nw-10s-720p.mp4`), fresh upload `de316a7a-b4fd-4fb4-afc4-a1d6be596fa2` via test admin account. `agent_trace_json.retrieval_source` flipped from `papers_only_fallback` (session 46) → `coach_brain_primary` (this session). 0 console errors. Screenshot `e2e/screenshots/d045-post-fix-bench-coach-brain-primary-de316a7a.png`.

**Carry-over (NOT addressed by this PR):** The same analysis still shows `eval_scores.faithfulness=0.0`, `cove_verified=false`, `overall=null` — exact same coaching-path CoVe truncation observed in session 46. That is D-048 (M-05-style max_tokens bump on `app/services/cove.py::CoveVerificationService`), not a D-045 regression. D-048 remains open.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-D045-01 | Read-only diagnostic `backend/scripts/oneoff/diagnose_coach_brain_retrieval.py` — connects to prod Postgres + Qdrant + Cohere, mirrors live agent path, prints 4-query-per-exercise rerank score table with FR-BRAIN-05 threshold classification. ADR-DISTILL-05-compliant error handling (`type(exc).__name__` only, no `str(exc)`). Pure ORM query — no SQL injection surface. Reusable for future RAG retrieval investigations. | done | M | — | — | `607b193` | `backend/scripts/oneoff/diagnose_coach_brain_retrieval.py` |
| L2-D045-02 | TDD: failing test `test_retrieve_coach_brain_query_includes_seed_corpus_vocabulary` asserts the agent query for each of bench/squat/deadlift contains seed-corpus-overlapping high-signal tokens. Drove the implementation. | done | S | — | FR-BRAIN-05, FR-BRAIN-09, FR-AICP-18 | `607b193` | `backend/tests/unit/test_agents_tools.py` |
| L2-D045-03 | Impl: `_COACH_BRAIN_QUERY_VOCAB: dict[str, str]` constant at module top of `tools.py` (lines 33-58 with full provenance comment referencing the diagnostic + before/after rerank scores); appended via `.get(exercise_type, "").strip()` to existing query. | done | S | L2-D045-02 | FR-AICP-18, ADR-BRAIN-09 | `607b193` | `backend/app/agents/tools.py` |
| L2-D045-04 | Audit-finding fixup #1: H-02 additive test `test_retrieve_coach_brain_unknown_exercise_type_degrades_gracefully` covers the `dict.get(..., "")` fallback path — call completes without raising and emits a well-formed un-enriched query (`"overhead_press standing coaching cue correction"`). M-01: `logger.warning` when vocab tail is empty so the silent degradation is visible in worker logs. | done | S | L2-D045-03 | — | `a084e06` | `backend/app/agents/tools.py`, `backend/tests/unit/test_agents_tools.py` |
| L2-D045-PR | PR #87 → CI 6/6 green on `607b193` and after fixup `a084e06` → spelix-auditor PASS_WITH_FINDINGS (1 CRITICAL = pre-existing SRS doc inconsistency on FR-BRAIN-04, NOT this PR's problem; H-01 falsified against runtime + prod DB; H-02/M-01 fixed inline; H-03 documented as accepted drift risk in ADR-BRAIN-09) → spelix-security-reviewer PASS clean (0 CRITICAL / 0 HIGH; secret exposure / SQL injection / Qdrant payload injection / SaMD language / ADR-DISTILL-05 all confirmed) → merge (`merge_method="merge"`) → Deploy to Production green → droplet HEAD + containers healthy → Playwright E2E on prod (bench fixture) flipped `retrieval_source: papers_only_fallback → coach_brain_primary` + screenshot saved | done | M | L2-D045-04 | — | `811a6c3` | PR #87 |

---

## Completed — L2 Sprint Day 10 — M-04 / M-05 Coach Brain maintenance bundle (2026-04-18, session 46)

PR #85 merged to `main` as `a0a86fc` and auto-deployed via CI (Deploy to Production 39s). Addresses M-04 (re-embed 24 Coach Brain seeds with FR-BRAIN-03 prefix) + M-05 (bump `BrainCoveService` Haiku 4.5 max_tokens so distillation candidates stop persisting `cove_verified=false, explanation="evaluation_failed: ValidationError"`). Backend: 1693 → 1694 tests (+1 `test_verify_claim_uses_adequate_max_tokens` via `await_args_list` kwarg introspection). Ruff + pyright + tsc clean. E2E on prod: re-embed script ran cleanly inside `spelix-backend-1` container (24/24 points upserted, 26→26 total point count unchanged — confirming UUID-match upsert replaces in place, no duplicates). Admin-account upload of `atharva-bench-nw-10s-720p.mp4` completed with Overall 7.8 + all form scores populated + 0 console errors + 0 network 4xx/5xx (screenshot `e2e/screenshots/m04-m05-post-reembed-prod-verified-6aa7b42b.png`).

**M-04 finding:** `retrieval_source=papers_only_fallback` persists on prod post-re-embed — proves the observed symptom has a different root cause than missing prefix. Filed as D-045 (see above). Re-embed left in place (cannot be worse than prior state).

**M-05 finding:** TDD-verified correct, but not exercised on prod this session — coaching faithfulness gate rejected the verification analysis so distillation did not fire. Will be exercised on first subsequent distillation-eligible run.

**Bonus finding:** Coaching-path `CoveVerificationService` (separate from distillation's `BrainCoveService`) has the same max_tokens-exhaustion bug — filed as D-048.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-M04-01 | New oneoff `backend/scripts/oneoff/reembed_coach_brain_seeds.py` — loads `coach_brain_entries` rows with `status='seed'`, re-embeds via `BrainEmbeddingService.embed_and_upsert_batch` (applies FR-BRAIN-03 prefix via `build_contextual_text`), upserts to Qdrant with matching UUIDs. Idempotent. No Postgres writes. | done | M | — | FR-BRAIN-03, FR-BRAIN-09, ADR-BRAIN-02 | `28404a7` | `backend/scripts/oneoff/reembed_coach_brain_seeds.py` |
| L2-M04-02 | Code-review fixup: single outer `try/finally` around schema_entries build + embed/upsert (`engine.dispose` always runs); `assert len(point_ids) == len(schema_entries)` invariant; strip raw `str(exc)` from stderr prints per ADR-DISTILL-05 intent. | done | S | L2-M04-01 | — | `b8b88b5` + `a1f0f78` | `backend/scripts/oneoff/reembed_coach_brain_seeds.py` |
| L2-M05-01 | TDD: failing test `test_verify_claim_uses_adequate_max_tokens` asserts `await_args_list[0].kwargs["max_tokens"] >= 512` (question) + `[1].kwargs["max_tokens"] >= 2048` (answer) + both `model == _HAIKU_MODEL`. | done | S | — | FR-BRAIN-14 | `7d2b3c1` + `a1f0f78` | `backend/tests/unit/test_distillation_cove_brain.py` |
| L2-M05-02 | Impl: `cove_brain.py:87` question `max_tokens=256→512` + 3-line comment; `cove_brain.py:95` answer `max_tokens=512→2048` + 6-line comment. | done | S | L2-M05-01 | FR-BRAIN-14, ADR-DISTILL-03, ADR-DISTILL-06 | `66e255d` | `backend/app/distillation/cove_brain.py` |
| L2-M04-M05-PR | PR #85 → CI 6/6 green on `66e255d` and after fixup `a1f0f78` → spelix-auditor PASS_WITH_FINDINGS (0 CRITICAL; 2 HIGH → H-01 fixed inline in `a1f0f78`, H-02 deferred as D-045 pre-existing FR-BRAIN-03 payload gap; 4 MEDIUM → M-01/M-04 fixed in `a1f0f78`, M-02 no-action, M-03 deferred as D-046) → spelix-security-reviewer PASS_WITH_FINDINGS (2 LOW ADR-DISTILL-05 style issues both fixed in `a1f0f78`) → merge (`merge_method="merge"`) → Deploy to Production 39s → droplet HEAD + containers healthy → prod re-embed script ran 24/24 → Playwright E2E on prod (bench fixture) complete + screenshot saved | done | M | L2-M05-02 | — | `a0a86fc` | PR #85 |

---

## Completed — L2 Sprint Day 8 — Phase 3 Batch 3 P3-007 "How AI Reasoned" Sidebar (2026-04-17, session 44)

Phase 3 Batch 3 P3-007 surfaces the `coaching_results.agent_trace_json` JSONB column — persisted since Phase 3 Batch 1 landed on prod (session 32) — through `GET /api/v1/analyses/{id}` and renders it as a right-side drawer on ResultsPage. FR-RESL-07 (Phase 3, Must) + NFR-USAB-05 (Must). The drawer uses `@xyflow/react@12.10.2` (React 19 compatible, MIT, attribution removable on free tier) to render `nodes_executed[]` as a clickable vertical chain with plain-English labels (no raw snake_case reaches users — enforced by three mapping functions + humanizer fallbacks: `labelForNode`, `labelForOutputKey`, `labelForRetrievalSource`). Clicking a node opens a detail pane with duration / produced AgentState keys (as plain-English chips) / error (if any). Summary header shows the retrieval source (plain English), CoVe verification status, faithfulness %, step count, and a degraded-mode banner when coaching ran without research backing. A11y: `<div role="dialog" aria-modal="true" aria-labelledby=…>`, keyboard focus moves to Close button on open, Escape + scrim click close (full focus trap deferred).

Single PR #83, merged via `mcp__github__merge_pull_request` with `merge_method="merge"` (NOT squash) as `70d736c`. Post-merge Deploy to Production green in 37s (not manual SSH). Droplet HEAD verified = merge commit; containers healthy. E2E verification via Playwright MCP: admin account upload of the 10s bench fixture → pipeline-completed analysis → sidebar rendered from real agent_trace_json. A design-time ADR-REASONING-SIDEBAR-01 captures the 8 locked decisions (xyflow over hand-rolled SVG; execution-order edges; index-based node IDs; all-optional payload fields; degraded-mode shown with banner; custom drawer not shadcn; a11y posture; plain-English defence-in-depth).

### Pre-merge audit findings (both fixed inline)

| ID | Reviewer | Severity | Finding | Fix commit |
|---|---|---|---|---|
| H-1 | spelix-auditor | HIGH | `labelForRetrievalSource` fell back to raw `src` (snake_case) on unknown values — NFR-USAB-05 violation | `4987307` (humanizer added) |
| H-2 | spelix-auditor | HIGH | `output_keys` chips in detail pane rendered raw snake_case (`rep_metrics`, `papers_contexts`, …) — NFR-USAB-05 violation | `4987307` (`labelForOutputKey` map + fallback) |
| MED | spelix-security-reviewer | MEDIUM | `NodeEvent.error` Python exception strings could leak `/tmp/...` paths | Deferred to D-### (owner-only visibility, low exploit) |

### Batch commits

| Ref | What | Commit |
|----|----|----|
| L2-PHASE3-B3-P3007-01 | Backend: expose `agent_trace_json` on `CoachingResultSchema` + MagicMock factory drift fix in `test_analysis_crud.py` | `c3b7a12` |
| L2-PHASE3-B3-P3007-02 | Frontend: `AgentNodeEvent` / `AgentEvalScores` / `AgentRetrievalSource` / `AgentTracePayload` types (all fields optional to accommodate Phase 2 imperative-path partial writes) + `CoachingResultDetail` extension + ResultsPage fixture update + types round-trip test | `71759e1` |
| L2-PHASE3-B3-P3007-03 | Install `@xyflow/react@12.10.2` | `c44356b` |
| L2-PHASE3-B3-P3007-04 | `lib/agentTraceLabels.ts` — 10 deterministic nodes + reasoner + humanizer fallback + retrieval-source map + formatDuration; 8 tests | `bfe81a3` |
| L2-PHASE3-B3-P3007-05 | `lib/agentTraceGraph.ts` — `buildTraceGraph()` sequential chain layout, index-based IDs; 9 tests | `89883da` |
| L2-PHASE3-B3-P3007-06 | `components/AgentReasoningSidebar.tsx` — drawer with summary + xyflow graph + detail pane; 17 tests including 2 a11y (focus-on-mount + role/aria) | `dd083fb` |
| L2-PHASE3-B3-P3007-07 | ResultsPage button + sidebar wire-up (conditional on `nodes_executed.length > 0`) + xyflow vi.mock at top of tests; 4 integration tests | `9aa749b` |
| L2-PHASE3-B3-P3007-08 | Audit fix: `labelForRetrievalSource` humanizer fallback + `labelForOutputKey` map + sidebar chip wire-up + 4 new tests | `4987307` |
| L2-PHASE3-B3-P3007-09 | PR #83 → CI 5/5 green → merge-not-squash → Deploy to Production (37s) → droplet HEAD match → E2E verified | `70d736c` (merge) |

### Test counts (baseline → post-P3-007)

- **Backend:** 1687 → 1690 passed (+3: one new detail-exposure test + two previously-failing tests unblocked by the `_make_mock_coaching_result` factory fix). 25 skipped (was 27 — two un-skipped by the factory fix). 0 failing. ruff clean. pyright 0 errors on `app/`.
- **Frontend:** 290 → 333 passed (+43: 12 labels + 9 graph + 17 sidebar + 4 ResultsPage integration + 1 types round-trip). 0 failing. tsc clean.
- **CI on PR #83:** 5/5 gate checks green (Backend Lint 35s, Backend Tests 2m0s, Frontend Lint 28s, Frontend Tests 1m25s, Secret Scanning 17s). Vercel preview + Deploy to Production both pass.

### Deferred post-P3-007 follow-ups (new D-### items)

| ID | Title | Size | Notes |
|---|---|---|---|
| D-### | Full focus trap inside AgentReasoningSidebar | S | Close-button autofocus + Escape + scrim close ship today; Tab-cycling focus trap needs ~15 LOC beyond MVP |
| D-### | Adaptive-mode reasoner-loop UI polish | M | Iteration counters, tool-call nesting. Prod runs deterministic only (`SPELIX_AGENT_MODE=deterministic`) |
| D-### | CoVe iteration drill-down pane | M | Surface question / answer / judgment per iteration. Summary currently shows `converged: bool` + count only |
| D-### | LangSmith run link-out from summary header | S | Admin-only, reveals full LangGraph run in LangSmith UI |
| D-### | Sanitize `NodeEvent.error` in `serialize_trace_for_storage` | S | spelix-security-reviewer MED. Strip `/tmp/...` and similar infra paths before JSONB write |

---

## Completed — L2 Sprint Day 6-7 — Phase 3 Batch 2 Distillation Pipeline (2026-04-17, session 41)

Phase 3 Batch 2 delivered async distillation on top of Batch 1's LangGraph agent. Five SRS requirements landed in one PR: FR-BRAIN-06 (standalone distillation `StateGraph` with six nodes gated on `eval_scores.overall ≥ 0.85 AND correctness ≥ 0.8`), FR-BRAIN-14 Should (CoVe verification against `papers_rag` via a new slim `BrainCoveService` for single-claim inputs, separate from the coaching-path `CoveVerificationService` per ADR-DISTILL-03), FR-BRAIN-17 (ADD/UPDATE/NOOP cosine lifecycle — `> 0.92` NOOP / `0.75–0.92` UPDATE / `< 0.75` ADD, with an auditor-caught boundary fix at exactly 0.92), FR-BRAIN-18 (confirmation_count +1 in the same transaction as the candidate INSERT), and the applied extension of FR-BRAIN-16 to the new candidates table. Migration 011 added `coach_brain_candidates` with admin-only RLS (`FORCE ROW LEVEL SECURITY`), separate from `coach_brain_entries` per ADR-DISTILL-01 so retrieval's `status='active'` filter stays load-bearing. Pipeline invocation is a new streaq task `distill_analysis` enqueued from the tail of `process_analysis` when `SPELIX_DISTILLATION_ENABLED=1` AND `eval_scores.overall ≥ 0.6`, gated by `_maybe_enqueue_distillation` which swallows enqueue errors as warnings (ADR-DISTILL-02). ADR-DISTILL-04 added a lightweight `Chunk` model alongside `ChunkPayload` in `app/schemas/rag.py` so distillation test stubs didn't need the full `ChunkPayload` payload; `coaching.py` narrows with `isinstance` before reading `.authors`/`.doi`. 18 commits merged via PR #77 (`8e587c3`) — 16 planned tasks + 2 fixup rounds (audit findings C-01/H-1/H-2 + CI coverage/pyright). `spelix-auditor` + `spelix-security-reviewer` both PASS_WITH_FINDINGS, all CRITICAL + HIGH findings fixed pre-merge. Backend 1637 tests passing (baseline 1586 + 51 new), coverage 90.31%, ruff + pyright clean. Feature flag left at `0` post-merge — prod verification deferred to next session so the first real candidate row can be inspected on a fresh analysis. FR-BRAIN-08 auto-triage explicitly deferred to `P3-008` post-L2 per SRS "start conservative" guidance (blocks on ≥50 human-reviewed candidates for threshold calibration).

| ID | Title | Size | Deps | Refs | Status | Commit |
|----|-------|------|------|------|--------|--------|
| L2-PHASE3-B2-01 | Alembic migration 011 + `CoachBrainCandidate` SQLAlchemy model (admin-only RLS, 3 indexes, no DDL FK) | S | — | FR-BRAIN-06, FR-BRAIN-14, FR-BRAIN-17, FR-BRAIN-18 | done | `ac1ec15` |
| L2-PHASE3-B2-02 | `CoachBrainCandidateCreate` / `CoachBrainCandidate` Pydantic v2 schemas + `CoachBrainCandidateRepository` (create, list_pending, get_by_id) | S | L2-PHASE3-B2-01 | FR-BRAIN-06 | done | `c44b578` |
| L2-PHASE3-B2-03 | `DistillationState` TypedDict + `CandidateInsight` / `LifecycleDecision` / `BrainCoveResult` Pydantic models + `make_initial_distillation_state` | S | L2-PHASE3-B2-02 | FR-BRAIN-06 | done | `cbdb494` |
| L2-PHASE3-B2-04 | `extract_insights` node — Haiku 4.5 + instructor; never raises | S | L2-PHASE3-B2-03 | FR-BRAIN-06 | done | `f6995af` |
| L2-PHASE3-B2-05 | `validate_quality` pure gate node (pass/review/reject on eval_scores) | S | L2-PHASE3-B2-03 | FR-BRAIN-06 | done | `705906f` |
| L2-PHASE3-B2-06 | `lifecycle_decision` node — Cohere embed + Qdrant cosine routing (ADD/UPDATE/NOOP) | M | L2-PHASE3-B2-03 | FR-BRAIN-17 | done | `97e6299` |
| L2-PHASE3-B2-07 | `BrainCoveService.verify_claim` + `cove_verify` node — single-claim CoVe, Haiku 4.5, skips NOOP candidates | M | L2-PHASE3-B2-03 | FR-BRAIN-14 | done | `e42d33a`, `5cfae29` (Chunk addition) |
| L2-PHASE3-B2-08 | `format_entry` pure node — zips candidates+decisions+cove_results into CoachBrainCandidateCreate rows; contradiction_flag on UPDATE+cove_unverified | S | L2-PHASE3-B2-06, L2-PHASE3-B2-07 | FR-BRAIN-06 | done | `bbfbec0` |
| L2-PHASE3-B2-09 | `store_entry` node — INSERT candidate + (UPDATE path) bump `coach_brain_entries.confirmation_count` + append `source_analysis_id` in same txn | M | L2-PHASE3-B2-08 | FR-BRAIN-18 | done | `c73c434` |
| L2-PHASE3-B2-10 | Compiled distillation `StateGraph` — 6 nodes + conditional edge on validate_quality + `_wrap_trace` helper + `run_distillation_graph` entry point | M | L2-PHASE3-B2-04..09 | FR-BRAIN-06 | done | `5f8988b` |
| L2-PHASE3-B2-11 | `distill_analysis` streaq task + `build_distillation_ctx` deps + `_maybe_enqueue_distillation` tail in `analysis_worker.py` (gated on `SPELIX_DISTILLATION_ENABLED=1 AND eval_scores.overall >= 0.6`, swallows enqueue errors) | L | L2-PHASE3-B2-10 | FR-BRAIN-06 | done | `e1d864d` |
| L2-PHASE3-B2-11b | Consent cascade extension — `cascade_consent_withdrawal` strips withdrawing user's analysis IDs from `coach_brain_candidates`, soft-deletes empties with `review_status='rejected'` + `rejected_reason='source_consent_withdrawn'` | S | L2-PHASE3-B2-01, L2-PHASE3-B2-11 | FR-BRAIN-16 | done | `8a1c568` |
| L2-PHASE3-B2-12 | `backend/CLAUDE.md` Phase 3 Distillation Architecture section (feature flags, rollout, graph flow, storage model, gotchas) | S | L2-PHASE3-B2-11 | — | done | `f367967` |
| L2-PHASE3-B2-13 | ADR-DISTILL-01 (candidate table split) + ADR-DISTILL-02 (streaq task) + ADR-DISTILL-03 (slim CoVe) + ADR-DISTILL-04 (Chunk union widening); backlog P3-004/005/008 rows | S | L2-PHASE3-B2-12 | — | done | `5a7f98a` |
| L2-PHASE3-B2-14 | Address audit findings — auditor C-01 (`>=` → `>` at NOOP boundary + regression test at cosine=0.92); security H-1 (cascade return dict carries `candidates_updated`); security H-2 (cove_explanation no longer embeds raw exception messages — sanitised to type name only) | S | L2-PHASE3-B2-13 | — | done | `698acab` |
| L2-PHASE3-B2-15 | CI fixes — pyright narrow on `ChunkPayload \| Chunk` union in `coaching.py`; coverage tests for `deps.py` + `distillation_worker.py` (0% → 100%/~96%); 89.44% → 90.31% | S | L2-PHASE3-B2-14 | — | done | `6ca3f1c` |
| L2-PHASE3-B2-16 | Open PR #77, 2 CI rounds green, merge via `mcp__github__merge_pull_request` `merge_method="merge"`, verify droplet HEAD + healthy containers | S | all above | — | done | PR #77 `8e587c3` |

---

## Completed — L2 Sprint Day 5 — Phase 3 Batch 1 LangGraph Agent (2026-04-15, session 32)

Phase 3 Batch 1 pulled forward from the scheduled Day 10-13 window into the Day 5-9 buffer freed by the streaq migration shipping on Day 4 (per ADR-TIMELINE-01). Three SRS Must requirements landed in a single PR: FR-AICP-18 (deterministic `StateGraph` with 6 composable tools + conditional edges), FR-AICP-19 (adaptive tool-calling graph via `ChatAnthropic.bind_tools` + docstring-driven selection), FR-AICP-20 (LangSmith tracing + enriched `agent_trace_json` JSONB payload). The entire agent path lives in `backend/app/agents/` as a new package; existing imperative coaching orchestration in `analysis_worker.py` was extracted into `_run_coaching_imperative` and kept as a fallback behind `SPELIX_PHASE3_AGENT_ENABLED=0` default, so the merge itself changed no prod behavior. Post-merge infra op flipped the flag to `1` + restarted worker; Playwright MCP E2E against live `spelix.app` confirmed analysis `d42f33ea-b464-4c9b-bd3d-c775547d52c2` ran all 10 graph nodes with `mode=deterministic`, `retrieval_source=papers_only_fallback`, 0 console errors. Backend 1520 tests passing (baseline 1477 + 43 new agent tests), coverage 90%, ruff + pyright clean. 21 commits merged via PR #52 (`5df0921`) — 17 planned tasks + 4 CI-feedback fixups (e2e patch paths post-extraction, pyright TypedDict `total=True` per ADR-AGENTSTATE-01, `ChatAnthropic` signature alignment, coverage uplift). Final code review by superpowers:code-reviewer surfaced 2 Important issues pre-merge (both fixed in `85f27fc`): `_wrap_trace` exception path now propagates the failed-node trace entry; `retrieve_coach_brain` classifies `retrieval_source` per FR-BRAIN-05 thresholds (0.82 primary, 0.65 hybrid floor, else papers-only fallback).

| ID | Title | Size | Deps | Refs | Status | Commit |
|----|-------|------|------|------|--------|--------|
| L2-PHASE3-01 | deps: langgraph, langchain-anthropic, langchain-core, langsmith | S | — | — | done | `eeb8732` |
| L2-PHASE3-02 | ADR-LANGGRAPH-01 + ADR-TIMELINE-01 | S | — | — | done | `18b78fa` |
| L2-PHASE3-03 | `AgentState` TypedDict + `NodeEvent` + `make_initial_state` | S | L2-PHASE3-01 | FR-AICP-18 | done | `d5d168f` |
| L2-PHASE3-04 | Six composable tools — `get_rep_metrics`, `retrieve_papers`, `retrieve_coach_brain`, `flag_form_deviation`, `compare_to_user_history`, `generate_correction_plan` (+ `AnalysisRepository.list_recent_by_user`) | L | L2-PHASE3-03 | FR-AICP-18 | done | `9bc5866`, `7e74973`, `0eb486f`, `1b9c284`, `0a1df6d`, `1002c55` |
| L2-PHASE3-05 | Post-generation nodes — `validate_output`, `cove_verify`, `safety_filter`, `faithfulness_gate` (wrap existing Phase 2 services) | M | L2-PHASE3-03 | FR-AICP-10, FR-AICP-14, FR-AICP-08, FR-BRAIN-14 | done | `0cef358` |
| L2-PHASE3-06 | Deterministic `StateGraph` — 10 nodes, conditional edges, `_wrap_trace` helper appending `NodeEvent` per node | M | L2-PHASE3-04, L2-PHASE3-05 | FR-AICP-18 | done | `4d91e5a` |
| L2-PHASE3-07 | LangSmith tracing helpers — `langsmith_enabled`, `run_config_for_analysis`, `serialize_trace_for_storage` (8KB JSONB cap) | S | L2-PHASE3-06 | FR-AICP-20 | done | `08be771` |
| L2-PHASE3-08 | Adaptive tool-calling graph — `ChatAnthropic.bind_tools` + `StructuredTool.from_function` + `state_box` mutable-handle pattern | L | L2-PHASE3-06 | FR-AICP-19 | done | `0f702bb` |
| L2-PHASE3-09 | `run_coaching_graph` entry point + enriched `agent_trace_json` payload shape (`mode`, `nodes_executed[]`, `eval_scores`, `cove_iterations`, `converged`, `retrieval_source`, `degraded_mode`) | S | L2-PHASE3-06..08 | FR-AICP-18, FR-AICP-19, FR-AICP-20 | done | `2313148` |
| L2-PHASE3-10 | Worker dispatcher — extract `_run_coaching_imperative` from `_run_pipeline`; add `_run_coaching_graph`; route via `SPELIX_PHASE3_AGENT_ENABLED` env flag; return tuple propagated to PDF pipeline | L | L2-PHASE3-09 | FR-AICP-18 | done | `7917761` |
| L2-PHASE3-11 | Full deterministic E2E integration test — real graph, mocked LLM; asserts tool ordering + `trace_payload` shape + eval_scores | S | L2-PHASE3-10 | — | done | `95ace59` |
| L2-PHASE3-12 | `backend/CLAUDE.md` "Phase 3 Agent Architecture" section + env-flag table + rollout procedure + backlog row seed | S | all above | — | done | `18e2c50` |
| L2-PHASE3-13 | Code-review fixes — `_wrap_trace` propagates failed-node trace via `state["trace"]` mutation before re-raise; `retrieve_coach_brain` classifies `retrieval_source` per FR-BRAIN-05 thresholds (0.82 primary, 0.65 hybrid floor, else `papers_only_fallback`) | S | L2-PHASE3-12 | FR-AICP-20, FR-BRAIN-05 | done | `85f27fc` |
| L2-PHASE3-14 | CI fixes — e2e `test_full_flow.py` patch paths redirected to source modules post-extraction; `AgentState` `total=True` (ADR-AGENTSTATE-01); `ChatAnthropic` signature alignment (`model_name`, `max_tokens_to_sample`, `timeout`, `stop`); typed `BaseMessage` list + `StructuredTool.ainvoke({})` for adaptive graph | M | L2-PHASE3-13 | ADR-AGENTSTATE-01 | done | `f7d5094`, `d36e581` |
| L2-PHASE3-15 | Coverage uplift — 6 integration tests for `_run_coaching_graph` branches (happy path, flagged-review, Qdrant available, Qdrant degraded, keyframe, no-profile, coaching_output=None RuntimeError). Restored 88.51% → 90% | S | L2-PHASE3-10 | — | done | `13287de` |
| L2-PHASE3-16 | Open PR #52, green CI round 4, merge via `mcp__github__merge_pull_request` `merge_method="merge"` (never squash per memory) | S | all above | — | done | PR #52 `5df0921` |
| L2-PHASE3-17 | Post-merge infra op — `.env.prod` → `SPELIX_PHASE3_AGENT_ENABLED=1` + `SPELIX_AGENT_MODE=deterministic`; worker recreated via `docker compose up -d worker`. Playwright MCP E2E against analysis `d42f33ea-b464-4c9b-bd3d-c775547d52c2` on `spelix.app`: all 10 graph nodes executed, `mode=deterministic`, `retrieval_source=papers_only_fallback`, all 7 trace keys persisted to `agent_trace_json`, 0 console errors | S | L2-PHASE3-16 | FR-AICP-18, FR-AICP-19, FR-AICP-20 | done | (infra op, no code commit) |

**ADRs added this session:**
- **ADR-LANGGRAPH-01** — LangGraph as agent orchestration framework (Phase 3)
- **ADR-TIMELINE-01** — Phase 3 pulled forward into the May 3 L2 sprint
- **ADR-AGENTSTATE-01** — `AgentState` TypedDict uses `total=True` for pyright-safe reads

**Files touched:**
- `backend/app/agents/{__init__,state,tools,nodes,graph,tracing}.py` (new package)
- `backend/app/workers/analysis_worker.py` — imperative extraction + graph dispatcher
- `backend/app/repositories/analysis.py` — `list_recent_by_user` method
- `backend/tests/unit/test_agents_{state,tools,nodes,graph_deterministic,graph_adaptive,tracing}.py` (new)
- `backend/tests/integration/{test_agents_coaching_e2e,test_agents_coaching_graph_path}.py` (new)
- `backend/tests/unit/test_analysis_repository.py` (new)
- `backend/pyproject.toml`, `backend/uv.lock` — +4 deps
- `backend/CLAUDE.md` — Phase 3 Agent Architecture section
- `decisions.md` — 3 ADRs (LANGGRAPH-01, TIMELINE-01, AGENTSTATE-01)

---

## Completed — L2 Sprint Day 4 — ARQ → streaq Migration (2026-04-15, session 31)

Drop-in replacement of the Redis-backed job queue per ADR-BRAIN-04-reversal. All 5 job types (`process_analysis`, `cascade_consent_withdrawal`, `ingest_paper`, `cleanup_expired_artifacts`, `ping_qdrant_health`) moved to streaq 6.4.0. Existing task bodies untouched — a `_adapt_ctx()` shim in `streaq_worker.py` converts streaq's `WorkerDepends()`-injected `WorkerContext` back to the ARQ-style `ctx: dict` each body still expects. NFR-OPER-02 heartbeat preserved (`spelix:worker:heartbeat`, TTL 90s, 30s cadence). Concurrency=1 preserved (MediaPipe 350MB on 2GB droplet). Coaching SSE pub/sub untouched (independent `redis.asyncio` client). Queue-depth admin probe fixed to `xlen("streaq:spelix:queues:")` (streaq uses Redis streams, not lists). Backend 1475 tests passing (net +8 new, -11 deleted), ruff + pyright clean. 19 commits merged via PR #48 (`2870c6a`). Post-merge hotfix PR #49 (`e35826b`) added the missing `run` subcommand to the streaq CLI invocation in docker-compose.prod.yml — streaq 6.4.0's CLI uses `streaq run <worker_path>`, not bare `streaq <worker_path>`. Worker healthy on droplet with heartbeat TTL 61s confirmed post-hotfix.

| ID | Title | Size | Deps | Refs | Status | Commit |
|----|-------|------|------|------|--------|--------|
| L2-STREAQ-01 | ADR-BRAIN-04-reversal in `decisions.md` — reverses Phase 3 deferral clause, documents drop-in scope + preserved behaviors + stop-loss trigger | S | — | ADR-BRAIN-04-reversal | done | `9145b6a`, `9f9caeb` |
| L2-STREAQ-02 | Add `streaq>=6.4.0,<7.0` to `backend/pyproject.toml`; regenerate `uv.lock` (ARQ still present during migration to allow revert) | S | — | — | done | `9fae77e` |
| L2-STREAQ-03 | Failing test for `streaq_worker` module shape (5 tests: importability, Worker instance, WorkerContext fields, task + cron registration) — TDD red step | S | — | — | done | `8b279e3`, `ccff88d` |
| L2-STREAQ-04 | `backend/app/workers/streaq_worker.py` — Worker instance, `WorkerContext` dataclass, zero-arg `lifespan()` with heartbeat loop, `_adapt_ctx()` shim, 3 task wrappers + 2 cron wrappers delegating to existing ARQ-style bodies | L | L2-STREAQ-02, L2-STREAQ-03 | ADR-BRAIN-04-reversal | done | `71f082d`, `97d4c4a` |
| L2-STREAQ-05 | Integration test — `async with worker:` opens the streaq Redis connection, PINGs, closes cleanly against local Redis | S | L2-STREAQ-04 | — | done | `9a6248d` |
| L2-STREAQ-06 | `app/api/v1/analyses.py` — `_get_arq_pool` → `_get_streaq_worker` (two-state cache, lazy import). `AnalysisService.arq_pool` → `streaq_worker`. Enqueue via `process_analysis.enqueue(analysis_id)`. Replaced `test_arq_pool_factory.py` with `test_streaq_enqueuer.py` (4 tests inc. import-failure regression + strong cache-count assertion + strong patch.object target). | L | L2-STREAQ-04 | — | done | `125900a`, `d801591` |
| L2-STREAQ-07 | `app/api/v1/consent.py` — same `_get_streaq_worker` pattern. `cascade_consent_withdrawal.enqueue(str(user_id))` replaces `pool.enqueue_job("cascade_consent_withdrawal", ...)`. Import-failure regression test added. | M | L2-STREAQ-04 | — | done | `1c85c21`, `5d60208` |
| L2-STREAQ-08 | `app/api/v1/expert.py` — PUBLIC `get_arq_pool` → `get_streaq_worker` (no underscore per unit-test patch requirement). `ingest_paper.enqueue(str(paper_id))` replaces `pool.enqueue_job("ingest_paper", ...)`. Import-failure regression test added preemptively. `test_expert_paper_complete.py` also updated. | M | L2-STREAQ-04 | — | done | `5da091f` |
| L2-STREAQ-09 | Retarget remaining ARQ-shaped tests (`test_paper_ingestion_task.py` → `worker.registry["ingest_paper"] is ingest_paper`; `test_admin.py` → `xlen("streaq:spelix:queues:")`). Deleted `test_worker_settings.py` + extra `llen` mock sites in `test_admin.py`. **Bonus bug fix**: `app/services/admin.py` was calling `llen("arq:queue")` → changed to `xlen("streaq:spelix:queues:")` (streaq stores a stream, not a list; bare `"spelix"` key is nonexistent). | M | L2-STREAQ-04..08 | — | done | `5118eb4`, `43c9176` |
| L2-STREAQ-10 | `docker-compose.prod.yml` worker `command` swap to streaq CLI | S | L2-STREAQ-04 | — | done | `4831528` |
| L2-STREAQ-11 | Drop `arq` from `backend/pyproject.toml` + regenerate `uv.lock`; delete `backend/app/workers/settings.py`; rewrite ARQ sections in `backend/CLAUDE.md` (stack line, Worker section, gotchas, SSE subsection, dependencies list, inline mentions) | M | L2-STREAQ-10 | — | done | `67e1a51` |
| L2-STREAQ-12 | Open PR #48, CI green, merge via `mcp__github__merge_pull_request` with `merge_method: "merge"` (`2870c6a`), wait for CI "Deploy to Production" | S | all above | — | done | PR #48 `2870c6a` |
| L2-STREAQ-13 | **Hotfix PR #49** — `docker-compose.prod.yml` worker command must be `streaq run <path>`, not bare `streaq <path>`. streaq 6.4.0 CLI uses subcommands (`run`, `web`). Merged (`e35826b`); worker container came up healthy post-deploy, heartbeat TTL 61s observed, `starting worker 886e2c68 for queue spelix` in logs. | S | L2-STREAQ-12 | — | done | PR #49 `e35826b` |

---

## Completed — L2 Sprint Day 3 — Expert PDF Upload Wiring (2026-04-15, session 30)

Two-phase signed-URL PDF upload end-to-end on the expert reviewer portal (ADR-EXPERT-01). Phase 1: `POST /api/v1/expert/papers` issues a signed Supabase Storage upload URL after filename sanitisation + 50 MB size guard + `uploading` row creation. Phase 2: browser `PUT`s the PDF directly to the `papers` bucket (FastAPI never touches bytes). Phase 3: `POST /api/v1/expert/papers/{id}/complete` does a magic-byte check via service-role download, flips `review_status` from `'uploading'` to `'pending'` and enqueues `ingest_paper`. Docling parsing itself is a stub (P2-005 open). Backend 1479 tests passing (+36 new), frontend 266 tests passing (+10 new). Security review (C-1, H-1..H-4) addressed; C-2 opened as D-029.

| ID | Title | Size | Deps | Refs | Status | Commit |
|----|-------|------|------|------|--------|--------|
| L2-EXPERT-01 | Migration 009 — `papers` Supabase Storage bucket (50 MB, PDF-only), `storage.objects` RLS (INSERT for expert_reviewer+admin, SELECT/DELETE for service_role), `rag_documents.review_status` CHECK widened with `'uploading'` | S | — | migration 009 | done | `732f157` |
| L2-EXPERT-02 | `app/utils/pdf_upload.py` — `sanitize_pdf_filename` (path-traversal, null-byte, control-char rejection; 255-char truncation), `MAX_PDF_BYTES=52_428_800`, `PDF_MAGIC_BYTES=b"%PDF-"` + 16 tests | S | — | ADR-EXPERT-01 | done | `54c7ddd`, `18acd67` |
| L2-EXPERT-03 | `PaperStorageService` — bucket-scoped signed-URL issuer, `download_head_bytes` (magic-byte helper), `delete_object` cleanup + 5 tests | S | — | ADR-EXPERT-01 | done | `0e5ded1` |
| L2-EXPERT-04 | `RagDocumentUploadRequest` / `RagDocumentUploadResponse` / `RagDocumentCompleteResponse` Pydantic schemas + 9 tests | S | — | FR-EXPV-02 | done | `973b180` |
| L2-EXPERT-05 | `POST /api/v1/expert/papers` phase 1 — signed URL; creates `rag_documents` row with `review_status='uploading'`. `app/services/supabase_client.py::get_service_role_client()` async singleton. + 5 tests | M | L2-EXPERT-01..04 | ADR-EXPERT-01 | done | `0d5e705`, `18acd67` |
| L2-EXPERT-06 | `POST /api/v1/expert/papers/:id/complete` phase 3 — magic-byte check + cleanup on failure + `ingest_paper` enqueue on success + QUEUE_UNAVAILABLE 503 when pool missing + 5 tests. `RagDocumentRepository.get_by_id`, `update_review_status`, `delete` helpers added. | M | L2-EXPERT-05 | ADR-EXPERT-01 | done | `ae1a71b`, `18acd67` |
| L2-EXPERT-07 | `ingest_paper` ARQ task stub (downloads head bytes to prove read path, logs `docling_pending`) — registered in `WorkerSettings.functions`. Full Docling parsing deferred to P2-005. + 3 tests | S | L2-EXPERT-06 | FR-EXPV-02 | done | `6b2d514` |
| L2-EXPERT-08 | Integration test — full phase 1 → 3 walk through FastAPI TestClient with dict-backed in-memory repo. Happy path + invalid-PDF cleanup. + cleanup: `update_review_status.reviewer_id` now optional so system transitions don't fabricate a UUID. | S | L2-EXPERT-05, L2-EXPERT-06 | — | done | `0ae6a8c` |
| L2-EXPERT-09 | Frontend API client — `requestPaperUploadUrl`, `uploadPaperFile` (XHR PUT + progress), `completePaperUpload`. Deprecated `uploadPaper` + `PaperUploadData` deleted. + 5 vitest cases | S | — | ADR-EXPERT-01 | done | `af8bbee`, `86a1670` |
| L2-EXPERT-10 | `ExpertPaperUploadPage.tsx` — file input + client-side PDF/size guards + 3-phase orchestration + progress bar + success/error banners. + 5 vitest cases | M | L2-EXPERT-09 | ADR-EXPERT-01 | done | `86a1670` |
| L2-EXPERT-11 | `spelix-security-reviewer` pre-merge pass → fixed C-1 (QUEUE_UNAVAILABLE guard before status flip), H-1 (empty-stem truncation reject), H-2 (control-char reject), H-3 (`datetime.now(timezone.utc)`), H-4 (`get_service_role_client` awaits `acreate_client`). C-2 (pre-existing `injury_advice_accurate` SaMD violation) opened as D-029 out of scope. | S | all above | ADR-EXPERT-01 | done | `18acd67` |

---

## Completed — L2 Sprint Day 2 — Landing V1 (2026-04-15, session 29)

Landing V1 live on prod via PR #45 (merged as `ae3b4fb`). STRATEGY.md v3 Day 1-2 hard gate met. No SRS FR IDs — growth/ops surface (see migration 008 docstring + ADR-049). Backend 1436 tests passing (15 new), frontend 256 tests passing (30 new), 91% coverage preserved. E2E verified on live `spelix.app/` — POST `/api/v1/beta/requests` returned 201 for anonymous submission. See ADR-049..ADR-052.

| ID | Title | Size | Deps | Refs | Status | Commit |
|----|-------|------|------|------|--------|--------|
| L2-LANDING-01 | Migration 008 — `beta_requests` table + RLS anon INSERT policy | S | — | migration 008 | done | `c005665` (PR #44) |
| L2-LANDING-02 | Backend beta-request API — `BetaRequest` model + Pydantic schemas + repository + service + `POST /api/v1/beta/requests` router (5/hr rate-limited, 15 tests) | M | L2-LANDING-01 | ADR-052 | done | `f3b8ac9`, `225f528`, `bffbd90`, `fb71fbe`, `4a5966c`, `1dce55b`, `3c19031`, `4cc34c0` |
| L2-LANDING-03 | Frontend landing components — SectionWrapper/Label/Heading primitives, ScrollReveal, AccordionItem, EmailCaptureForm, BetaDisclaimer + 8 section components (NavBar, Hero, Problem, HowItWorks, Differentiators, Privacy, FinalCta, Footer) | L | L2-LANDING-04 | ADR-049 | done | `c04ef1e`, `a548f08`, `a810350`, `5ee7945`, `1238cc4`, `39f0802`, `25118d9`, `eda5d8d`, `6ca9c85`, `149eb2f`, `631bb1d`, `c0a990b`, `edd56f0`, `e10a307` |
| L2-LANDING-04 | Tailwind v4 `@theme` brand tokens (chartreuse, DM Sans + Host Grotesk, container 1128px) + Google Fonts preconnect + `<title>` update | S | — | ADR-049 | done | `e5e10f8`, `7b2790b`, `ddf9f5e` |
| L2-LANDING-05 | PostHog cookieless instrumentation (`persistence: "memory"`, `ip: false`, `autocapture: false`) + `landing_view` + `landing_email_submit_{attempt,success,error}` with `cta_location` + `email_domain` | S | L2-LANDING-03 | ADR-051 | done | `8d25e32` |
| L2-LANDING-06 | Landing static assets — 3 SVG step icons, ResultsPage screenshot captured via Playwright MCP on prod, CSS radial-gradient hero bg (real photo deferred to V2) | S | — | ADR-049 | done | `1abe968` |
| L2-LANDING-07 | Route swap — `/` → `LandingPage`, `HomePage.tsx` deleted, `/beta-terms` added → `BetaTermsPage` rendering `public/beta-terms.md` via `react-markdown` | S | L2-LANDING-03 | — | done | `e900697`, `119cb68`, `adccb64`, `c963a13` |
| L2-LANDING-08 | `spelix-security-reviewer` pre-merge pass → C-1 fix: remove `email` from `BetaRequestResponse` 201 body (observability PII leak) | S | L2-LANDING-02 | ADR-052 | done | `3ee6f37` |
| L2-LANDING-09 | CI fix: declare `uq_beta_requests_email` UNIQUE index on `BetaRequest.__table_args__` so CI's `create_all` picks it up + regression-guard unit test | S | L2-LANDING-02 | ADR-052 | done | `6197b14` |
| L2-LANDING-10 | E2E on live `spelix.app/` via browse skill — anon load, 5 H2s present, no console errors, POST `/api/v1/beta/requests` 201 Created, "Thanks" success state rendered. Screenshots: `e2e/screenshots/landing-v1-prod/` | S | L2-LANDING-02, L2-LANDING-03 | — | done | (verification, no code commit) |

### L2 Sprint items opened but NOT in V1 — deferred to Sprint BETA (May 4-14)

| ID | Title | Size | Deps | Refs | Status |
|----|-------|------|------|------|--------|
| L2-LANDING-V2-01 | Section 5 "Four Dimensions" — 2×2 card grid (Movement Quality / Technique / Path & Balance / Control) with §6.5 verbatim copy | S | — | landing-page-plan §5 | pending |
| L2-LANDING-V2-02 | Section 6 "Roadmap" — 3 cards (Progress tracking / Adaptive coaching / Per-athlete memory) with §6.6 verbatim copy | S | — | landing-page-plan §5 | pending |
| L2-LANDING-V2-03 | Hero bg real photo — sagittal barbell-lift stock image, ≤250 KB WebP (currently a chartreuse-radial-gradient placeholder) | S | — | landing-page-plan §16.4 | pending |
| L2-LANDING-V2-04 | Admin beta-request approval UI — BetaRequestsPanel in AdminPage with table, status filter, approve/reject buttons, pagination, stats bar. Transactional-email invite flow deferred. | M | L2-LANDING-02 | ADR-050 | done — `e8e82a5` (PR #142, session 64) |
| L2-LANDING-V2-05 | Beta-terms markdown file — `public/beta-terms.md` polish and legal review (current draft is landing-page-plan §10 verbatim, two paragraphs, GDPR-aligned but not counsel-reviewed) | S | — | — | done — `9b78e39` (PR #143, session 65) |


## Completed — Pre-Beta Audit Full Closeout (2026-04-20/21, session 58)

Closed 20 audit findings across 4 PRs, then ran Phase 3 audit and fixed 2 HIGH findings in a 5th PR. 38 of 42 total audit findings resolved — remaining 4 are intentional deferrals (H-11 Phase 4, M-07 infra sprint, M-10 refactor, L-03 server config; L-06 was already resolved pre-session).

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| AUDIT-M-01 | Remove exception details from 500 responses (no `type(exc).__name__` / `str(exc)` leak) | done | S | — | NFR-SECU-08 | `c620dcb` | `backend/app/main.py`, `backend/tests/unit/test_global_exception_handler.py` |
| AUDIT-M-02 | IP-based rate limiting (remove unverified JWT sub extraction) | done | S | — | NFR-SECU-10 | `4cd0412` | `backend/app/rate_limit.py`, `backend/tests/unit/test_rate_limit_key.py` |
| AUDIT-M-03 | Chat endpoint prompt injection defense (`_sanitize_user_message`) | done | S | — | FR-AICP-17 | `ca98a8a` | `backend/app/services/chat.py`, `backend/tests/unit/test_chat_prompt_injection.py` |
| AUDIT-H-03 | RLS on `rag_documents`, `expert_annotations`, `coach_brain_entries` | done | S | — | NFR-SECU-07 | `c97680d` | `backend/alembic/versions/015_rls_admin_tables.py` |
| AUDIT-H-08 | FR-SCOR-09 app-purpose statement on ResultsPage | done | S | — | FR-SCOR-09 | `5f733ea` | `frontend/src/pages/ResultsPage.tsx` |
| AUDIT-H-09 | `requires_technical_review` column + distillation wiring | done | M | — | FR-ADMN-12 | `86f3d80` | `backend/alembic/versions/016_add_requires_technical_review.py`, `backend/app/models/coach_brain_candidate.py`, `backend/app/distillation/store.py` |
| AUDIT-M-08 | ChatService unit tests (32% → ~70% coverage) | done | S | — | — | `06d8daf` | `backend/tests/unit/test_chat_service.py` |
| AUDIT-M-09 | ExpertService unit tests (31% → ~65% coverage) | done | S | — | — | `1526318` | `backend/tests/unit/test_expert_service.py` |
| AUDIT-H-07 | Pin Docker base images to SHA256 digests | done | S | — | — | `bb5712f` | `backend/Dockerfile`, `docker-compose.prod.yml`, `docker-compose.dev.yml`, `.github/workflows/ci.yml` |
| AUDIT-H-10 | ExpertPortalPage + ExpertAnalysisDetailPage test coverage | done | M | — | NFR-MAIN-05 | `6328098` | `frontend/src/pages/__tests__/ExpertPortalPage.test.tsx`, `frontend/src/pages/__tests__/ExpertAnalysisDetailPage.test.tsx` |
| AUDIT-H-13 | Log 6 silently-swallowed exceptions in `analysis_worker.py` | done | S | — | NFR-OPER-01 | `347162b` | `backend/app/workers/analysis_worker.py` |
| AUDIT-H-14 | Standalone index on `analyses.status` | done | S | — | NFR-PERF-01 | `17cd9bb` | `backend/alembic/versions/017_add_missing_indexes.py` |
| AUDIT-H-15 | Standalone index on `consent_records.consent_type` | done | S | — | NFR-PERF-01 | `17cd9bb` | `backend/alembic/versions/017_add_missing_indexes.py` |
| AUDIT-M-04 | SHA256 checksum verification on BlazePose model download | done | S | — | — | `fccdebd` | `backend/Dockerfile` |
| AUDIT-M-05 | Pin TruffleHog action to v3.94.3 commit SHA (no more `@main`) | done | S | — | — | `fccdebd` | `.github/workflows/ci.yml` |
| AUDIT-M-06 | Worker Docker healthcheck (Redis heartbeat probe) | done | S | — | NFR-RELI-02 | `fccdebd` | `docker-compose.prod.yml` |
| AUDIT-M-11 | Extract magic numbers to `app/config_constants.py` | done | M | — | — | `0a2fe8c` | `backend/app/config_constants.py`, `backend/app/agents/graph.py`, `backend/app/api/deps.py`, `backend/app/distillation/graph.py` |
| AUDIT-M-12 | Widen `coach_brain_candidates.review_status` VARCHAR(20) → (30) | done | S | — | — | `cce6a47` | `backend/alembic/versions/f2c0572a0bde_widen_review_status_varchar30.py`, `backend/app/models/coach_brain_candidate.py` |
| AUDIT-M-13 | Standalone index on `analyses.user_id` | done | S | — | NFR-PERF-01 | `66b43c2` | `backend/alembic/versions/019_add_analyses_user_id_index.py` |
| AUDIT-M-14 | Distillation graph passes `RunnableConfig` with `run_name` + `tags` for LangSmith tracing | done | S | AUDIT-M-11 | FR-BRAIN-06 | `93c4ce0` | `backend/app/distillation/graph.py`, `backend/tests/unit/test_distillation_graph.py` |
| AUDIT-M-15 | Wrap delete button query in `waitFor` to fix flaky AdminPage test | done | S | — | — | `e068a69` | `frontend/src/pages/__tests__/AdminPage.test.tsx` |
| AUDIT-L-01 | CI deploy script rollback on post-deploy health check failure | done | S | — | NFR-RELI-02 | `48d9071` | `.github/workflows/ci.yml` |
| AUDIT-L-02 | Upper-bound 26 backend dependencies in `pyproject.toml` | done | M | — | — | `f2a0cd9` | `backend/pyproject.toml`, `backend/uv.lock` |
| AUDIT-L-04 | Dedupe `_HEARTBEAT_TTL` constant across worker files | done | S | — | — | `5a5d3e1` | `backend/app/workers/analysis_worker.py`, `backend/app/workers/streaq_worker.py` |
| AUDIT-L-05 | Centralize 5 LLM `MAX_TOKENS` constants to `config_constants.py` | done | S | AUDIT-M-11 | — | `2bed7d1` | `backend/app/config_constants.py`, `backend/app/services/chat.py`, `backend/app/services/faithfulness_gate.py`, `backend/app/services/ingestion.py`, `backend/app/services/keyframe_analysis.py`, `backend/app/services/coaching.py` |
| AUDIT-L-07 | Dedupe `MAX_FILE_SIZE_BYTES` between schemas and services | done | S | — | — | `ddcb227` | `backend/app/services/analysis.py` |
| AUDIT-L-08 | Remove "diagnose" language from landing PrivacySection (SaMD policy) | done | S | — | — | `067872d` | `frontend/src/components/landing/PrivacySection.tsx` |
| AUDIT-L-09 | Read JWT role from `app_metadata` not `user_metadata` (privilege escalation fix) | done | M | — | NFR-SECU-09 | `0b5363c` | `backend/app/api/deps.py`, `backend/tests/unit/test_auth.py`, `backend/scripts/oneoff/migrate_roles_to_app_metadata.py` |
| AUDIT-L-10 | Composite index on `consent_records(user_id, consent_type)` | done | S | — | NFR-PERF-01 | `30fafd1` | `backend/alembic/versions/020_add_consent_records_composite_index.py` |
| AUDIT-L-11 | Standalone index on `coach_brain_entries.status` | done | S | — | NFR-PERF-01 | `3e2197a` | `backend/alembic/versions/021_add_coach_brain_entries_status_index.py` |
| AUDIT-P3-H01 | Expose `requires_technical_review` in `CandidateListItem` API response + frontend banner condition | done | S | — | FR-ADMN-12 | `341779f` | `backend/app/schemas/candidate_review.py`, `frontend/src/api/admin.ts`, `frontend/src/pages/AdminCoachBrainCandidatesPage.tsx` |
| AUDIT-P3-H02 | Gate compensation approve on `biomechanics_qualified` claim; HTTP 403 otherwise | done | M | AUDIT-L-09 | FR-ADMN-12 | `0e45401` | `backend/app/api/deps.py`, `backend/app/services/candidate_review.py`, `backend/app/api/v1/admin.py`, `backend/tests/unit/test_auth.py` |

**Ops completed this session:**
- `migrate_roles_to_app_metadata.py` ran against prod Supabase: 0 users needed migration
- `app_metadata.biomechanics_qualified=true` set on `atharva6905+admin-p3006@gmail.com`
- Migrations 015→021 applied via CI deploy pipeline

**Deferred items (still open):**

| ID | Title | Status | Reason |
|---|---|---|---|
| D-AUDIT-H-11 | deepeval CI suite against golden dataset | deferred | Phase 4 work; `spelix-eval-engineer` agent not yet active |
| D-AUDIT-M-07 | Pin system apt packages in Dockerfile | deferred | Requires per-mirror version resolution; infra sprint |
| D-AUDIT-M-10 | Refactor files > 300 lines | deferred | Tech debt / refactoring scope — no feature context |
| D-AUDIT-L-03 | Enable ufw on droplet | deferred | Pure server config, not code fix — do manually |

---

## Completed — Expert Onboarding Prep (2026-05-12, session 63)

Three PRs preparing the expert portal for the first kinesiology reviewer. PR #135: nav link + unmeasurable dimension cleanup + structured annotation form. PR #136: "My Papers" tab replacing "Papers Pending" stub. PR #137: full paper ingestion pipeline (Docling PDF extraction → IngestionService → Qdrant).

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-EXPERT-12 | Expert Portal nav link in AppLayout (isExpert state for expert_reviewer + admin) | done | S | — | FR-EXPV-01 | `fc71a82` (PR #135) | `frontend/src/components/AppLayout.tsx` |
| L2-EXPERT-13 | Remove unmeasurable dimension references from coaching prompts, Coach Brain vocab, distillation examples, scoring badge text, backend CLAUDE.md | done | M | — | — | `fc71a82` (PR #135) | `backend/app/services/coaching.py`, `backend/app/agents/tools.py`, `backend/app/distillation/extract.py`, `backend/app/cv/scoring.py`, `backend/CLAUDE.md` |
| L2-EXPERT-14 | Replace JSON annotation textareas with exercise-specific checkboxes + structured citation rows | done | M | — | FR-EXPV-04 | `fc71a82` (PR #135) | `frontend/src/pages/ExpertAnalysisDetailPage.tsx`, `frontend/src/pages/__tests__/ExpertAnalysisDetailPageBranches.test.tsx` |
| L2-EXPERT-15 | Repurpose "Papers Pending" → "My Papers" tab: GET /api/v1/expert/papers endpoint + PapersTable frontend component | done | M | — | FR-EXPV-02 | `9ac7147` (PR #136) | `backend/app/api/v1/expert.py`, `frontend/src/api/expert.ts`, `frontend/src/pages/ExpertPortalPage.tsx` |
| L2-EXPERT-16 | Wire ingest_paper worker: Docling PDF extraction + IngestionService + chunk_count write-back. Triggered on paper approval. | done | L | L2-EXPERT-07 | FR-EXPV-02 | `05c37ee` (PR #137) | `backend/app/workers/paper_ingestion.py`, `backend/app/services/pdf_extraction.py`, `backend/app/services/paper_storage.py`, `backend/app/repositories/rag_document.py`, `backend/app/workers/streaq_worker.py` |
| L2-EXPERT-17 | Gitignore cleanup: model binaries, e2e video fixtures, Playwright YML snapshots, superpowers plans, Word lock files | done | S | — | — | `9ac7147` (PR #136) | `.gitignore` |
| L2-EXPERT-18 | Add "Approve & Ingest" self-approval button to My Papers tab for pending papers | done | S | L2-EXPERT-15, L2-EXPERT-16 | FR-EXPV-02 | `e0a6182` (PR #138) | `frontend/src/pages/ExpertPortalPage.tsx` |

## Completed — Pre-Beta Fixes (2026-05-12, session 64)

Prod audit found 4 issues blocking private beta invites. All 4 fixed via independent PRs (#139–#142), merged, deployed, E2E verified.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-BETA-01 | Add nightly cron to auto-fail analyses stuck in non-terminal states >2h | done | S | — | — | `8c3ccd8` (PR #139) | `backend/app/workers/cleanup_stuck_analyses.py`, `backend/app/workers/streaq_worker.py`, `backend/tests/unit/test_cleanup_stuck_analyses.py` |
| L2-BETA-02 | Replace hardcoded waitlist count with live GET /api/v1/beta/count endpoint | done | S | — | — | `a35937b` (PR #140) | `backend/app/api/v1/beta.py`, `backend/app/repositories/beta_request.py`, `frontend/src/api/beta.ts`, `frontend/src/components/landing/LandingHero.tsx` |
| L2-BETA-03 | Add mandatory consent gate — RequireConsent redirect + backend 403 defense-in-depth | done | M | — | NFR-PRIV-01 | `698e447` (PR #141) | `frontend/src/components/RequireConsent.tsx`, `frontend/src/routes.tsx`, `frontend/src/pages/ConsentPage.tsx`, `backend/app/api/v1/analyses.py`, `backend/tests/unit/test_analysis_api.py` |
| L2-BETA-04 | Add admin BetaRequestsPanel — list/approve/reject beta requests from /admin | done | M | — | — | `e8e82a5` (PR #142) | `backend/app/api/v1/admin.py`, `backend/app/repositories/beta_request.py`, `frontend/src/api/admin.ts`, `frontend/src/pages/AdminPage.tsx`, `backend/tests/unit/test_admin_beta_api.py` |
| L2-BETA-05 | Omit pdf_extraction.py from coverage (IO-heavy, integration-tested) | done | S | — | — | `e8e82a5` (PR #142) | `backend/pyproject.toml` |

## Completed — cv-audit Session 3: Infrastructure Scaffold (2026-05-22, session 65)

Session 3 of the cv-audit effort. Built the rails Sessions 4-7 ride on: 16-entry sagittal metrics registry on the backend, expert-portal UnvalidatedMetricsPanel on the frontend, threshold_flags.section CHECK constraint extension. No extraction logic yet -- all 16 entries show "Not yet computed".

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-SAGITTAL-INFRA-01 | Sagittal metrics registry frozenset + Pydantic schemas | done | M | — | — | `3204436` (PR #153) | `backend/app/cv/sagittal_metrics_registry.py`, `backend/app/schemas/expert_review.py`, `backend/tests/unit/test_sagittal_metrics_registry.py` |
| L2-SAGITTAL-INFRA-02 | GET /api/v1/expert/sagittal-metrics-registry endpoint (expert+admin auth) | done | S | L2-SAGITTAL-INFRA-01 | FR-EXPV-01 | `b4dfedf` (PR #153) | `backend/app/api/v1/expert.py`, `backend/tests/unit/test_expert_sagittal_metrics_endpoint.py` |
| L2-SAGITTAL-INFRA-03 | Alembic CHECK constraint on threshold_flags.section + ThresholdFlagCreate Literal widening + service bypass for unvalidated_metrics | done | M | — | FR-EXPV-08 | `060bdb9`/`37a903d` (PR #153) | `backend/alembic/versions/7c4af3e51f08_threshold_flags_section_check.py`, `backend/app/schemas/threshold_flag.py`, `backend/app/services/threshold_flag.py`, `backend/tests/unit/test_threshold_flag_service.py` |
| L2-SAGITTAL-INFRA-04 | UnvalidatedMetricsPanel + ThresholdSection union widening + ExpertAnalysisDetailPage mount + ThresholdFlagModal section addendum | done | M | L2-SAGITTAL-INFRA-02 | FR-EXPV-03, FR-EXPV-08 | `b62b059` (PR #153) | `frontend/src/components/UnvalidatedMetricsPanel.tsx`, `frontend/src/components/__tests__/UnvalidatedMetricsPanel.test.tsx`, `frontend/src/api/expert.ts`, `frontend/src/pages/ExpertAnalysisDetailPage.tsx`, `frontend/src/pages/ExpertThresholdsPage.tsx`, `frontend/src/components/__tests__/ThresholdFlagModal.test.tsx`, `frontend/src/pages/__tests__/ExpertAnalysisDetailPage.test.tsx`, `frontend/src/pages/__tests__/ExpertAnalysisDetailPageBranches.test.tsx` |

## Completed — cv-audit Session 4: Trivial Metrics + Auto-Flow Scoring (2026-05-22, session 66)

Session 4 of the cv-audit effort. Four sagittal-view extractors derived from already-computed pipeline data; two of them (`depth_classification` for squat, `ecc_con_ratio` for all exercises) auto-flow into existing form scoring. First user-visible scoring impact of the cv-audit work. No migrations — all keys ride through the existing `rep_metrics.metrics_json` JSONB column. See ADR-AUTO-FLOW-REFINEMENTS.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-SAGITTAL-TRIVIAL-01 | depth_classification extractor + TechniqueScore branch + thresholds_v1.json entry + registry flip (computed_yet+in_scoring) + ResultsPage chip | done | M | L2-SAGITTAL-INFRA-01..04 | FR-SCOR-02 | _pending merge_ | `backend/app/cv/metric_extraction.py`, `backend/app/cv/scoring.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/app/services/pipeline.py`, `config/thresholds_v1.json`, `backend/tests/unit/test_metric_extraction_sagittal.py`, `backend/tests/unit/test_scoring.py`, `frontend/src/pages/ResultsPage.tsx`, `frontend/src/pages/__tests__/ResultsPage.autoFlowMetrics.test.tsx` |
| L2-SAGITTAL-TRIVIAL-02 | ecc_con_ratio extractor + ControlScore branch (rushed/excessive) + thresholds_v1.json target window + registry flip + ResultsPage chip | done | M | L2-SAGITTAL-INFRA-01..04 | FR-SCOR-04 | _pending merge_ | `backend/app/cv/metric_extraction.py`, `backend/app/cv/scoring.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/app/services/pipeline.py`, `config/thresholds_v1.json`, `backend/tests/unit/test_metric_extraction_sagittal.py`, `backend/tests/unit/test_scoring.py`, `frontend/src/pages/ResultsPage.tsx`, `frontend/src/pages/__tests__/ResultsPage.autoFlowMetrics.test.tsx` |
| L2-SAGITTAL-TRIVIAL-03 | pause_duration_s extractor (compute-only, squat + bench + DL) + registry flip (computed_yet only) | done | S | L2-SAGITTAL-INFRA-01..04 | FR-EXPV-03 | _pending merge_ | `backend/app/cv/metric_extraction.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/tests/unit/test_metric_extraction_sagittal.py` |
| L2-SAGITTAL-TRIVIAL-04 | lockout_torso_lean_deg extractor (compute-only, squat + DL) + registry flip (computed_yet only) + side-agnosticism mirror test | done | S | L2-SAGITTAL-INFRA-01..04 | FR-EXPV-03 | _pending merge_ | `backend/app/cv/metric_extraction.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/tests/unit/test_metric_extraction_sagittal.py` |

**Integration test**: `backend/tests/integration/test_pipeline_session4_metrics.py` runs the full pipeline on `e2e/fixtures/atharva-squat.mov`: 6 reps detected, all four keys populated for every rep, aggregate ecc/con=2.16 inside target window (no auto-flow badge fired on this clean rep set), OverallFormScore.overall=6.90 executed without exception. Per-rep depth_classification all `below_parallel`; ecc_con_ratio ranges 0.07..5.73 across reps (rep-level granularity preserved in JSONB even though session-aggregate is used for scoring). Backend total: 2096 + 24 (sagittal extractors) + 11 (scoring) + 4 (registry session4) + 2 (integration) = **2137 tests pass**. Frontend total: **758 tests pass** (+3 over Session-3 baseline of 755). Coverage threshold not lowered.

## Completed — cv-audit Session 5: Standard Single-Frame Landmark Math (2026-05-22, session 67)

Session 5 of the cv-audit effort. 7 sagittal-view metrics (8 JSONB keys) computed from small landmark sets at specific phase frames. All compute-only — no scoring branches; `in_scoring=False` on every registry entry. Expert `<UnvalidatedMetricsPanel />` auto-renders the new values via the existing registry-driven path (Session 3 infra). Introduces `_facing_sign(side: Literal["left","right"]) -> float` as the convention for x-direction signed metrics so left-side-filmed analyses produce the same signed output as right-side-filmed (mirror tests). No threshold config entries (post-onboarding expert validation via FR-EXPV-08). No migrations (additive JSONB keys per design Section 2). Plan expansion: PR #160 merged `3560cec`. Implementation: PR #161 merged `b9ab8fa`.

| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| L2-SAGITTAL-STANDARD-01 | #1 ankle_dorsiflexion_deg + heel_rise_flag extractors (squat, compute-only) + registry flip + side-agnosticism mirror test | done | M | L2-SAGITTAL-INFRA-01..04 | FR-EXPV-03 | `b9ab8fa` | `backend/app/cv/metric_extraction.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/tests/unit/test_metric_extraction_sagittal.py` |
| L2-SAGITTAL-STANDARD-02 | #3 wrist_alignment_deg extractor (bench, compute-only) + `_facing_sign` helper + registry flip + side-agnosticism mirror test | done | S | L2-SAGITTAL-INFRA-01..04 | FR-EXPV-03 | `b9ab8fa` | `backend/app/cv/metric_extraction.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/tests/unit/test_metric_extraction_sagittal.py` |
| L2-SAGITTAL-STANDARD-03 | #5 bar_touch_height_pct extractor (bench, compute-only, y-only) + registry flip + side-agnosticism mirror test | done | S | L2-SAGITTAL-INFRA-01..04 | FR-EXPV-03 | `b9ab8fa` | `backend/app/cv/metric_extraction.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/tests/unit/test_metric_extraction_sagittal.py` |
| L2-SAGITTAL-STANDARD-04 | #10 setup_shoulder_x_offset extractor (deadlift, compute-only) + facing-sign + registry flip + side-agnosticism mirror test | done | S | L2-SAGITTAL-INFRA-01..04 | FR-EXPV-03 | `b9ab8fa` | `backend/app/cv/metric_extraction.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/tests/unit/test_metric_extraction_sagittal.py` |
| L2-SAGITTAL-STANDARD-05 | #11 shin_angle_deg extractor (squat, compute-only) + facing-sign + registry flip + side-agnosticism mirror test | done | S | L2-SAGITTAL-INFRA-01..04 | FR-EXPV-03 | `b9ab8fa` | `backend/app/cv/metric_extraction.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/tests/unit/test_metric_extraction_sagittal.py` |
| L2-SAGITTAL-STANDARD-06 | #13 setup_knee_angle_deg extractor (deadlift, compute-only, joint angle) + registry flip + side-agnosticism mirror test | done | S | L2-SAGITTAL-INFRA-01..04 | FR-EXPV-03 | `b9ab8fa` | `backend/app/cv/metric_extraction.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/tests/unit/test_metric_extraction_sagittal.py` |
| L2-SAGITTAL-STANDARD-07 | #15 arch_deg extractor (bench, compute-only, non-rep frames mean) + facing-sign + registry flip + side-agnosticism mirror test | done | M | L2-SAGITTAL-INFRA-01..04 | FR-EXPV-03 | `b9ab8fa` | `backend/app/cv/metric_extraction.py`, `backend/app/cv/sagittal_metrics_registry.py`, `backend/tests/unit/test_metric_extraction_sagittal.py` |

**Integration test**: `backend/tests/integration/test_pipeline_sagittal_metrics.py` runs the full pipeline on all 3 atharva fixtures and asserts each Session-5 key applicable to that exercise is populated within its natural-domain sanity range. Squat: 6 reps detected, ankle/heel/shin keys populated. Bench: 13 reps detected, wrist/touch/arch keys populated (wide atan2/ratio domains — expert validates meaningful sub-ranges post-onboarding via FR-EXPV-08; FR-EXPV-03 captures the compute-only stance). Deadlift: 5 reps detected, setup_shoulder/setup_knee keys populated. Backend total: **2210 unit tests pass** (+73 over Session 4 baseline of 2137). Frontend total: **758 tests pass** (unchanged). Coverage on `app.cv.metric_extraction`: 94% (all Session-5-new lines covered; pre-existing uncovered lines pre-date this session). Coverage threshold not lowered.
