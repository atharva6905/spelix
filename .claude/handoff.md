# cv-audit handoff — Session 6 → Session 7

## Status
- **Session 6:** complete — merge SHA `cc308299b755f78a3cefa384f6595dba99c31d4a`, PR #164 (https://github.com/atharva6905/spelix/pull/164)
- **Plan expansion (sub-PR):** PR #163 merged `c6d6cde` before the implementation /goal proceeded (mirrors Sessions 2/3/4/5)
- **Next session:** Session 7 — Complex multi-frame analysis (#2 `lumbar_flexion_proxy_delta_deg`, #6 `bar_path_classification`, #16 `technique_consistency_std`). **Highest calibration risk.**
- **Launch command:** see `docs/superpowers/goals/2026-05-22-cv-audit-master.md` §Session-7 "Launch command" block. **Note:** the Session 7 plan at `docs/superpowers/plans/2026-05-22-session-7-complex-multi-frame.md` is a SKELETON. Session 7 ALSO requires a **mandatory `/plan` spike** with `spelix-cv-engineer` BEFORE skeleton expansion (baseline-frame identification, J-curve heuristic boundaries, consistency-metric choice). Both the `/plan` spike output AND the expanded skeleton must be committed before launching the implementation `/goal`.

## Completed this session
- `c6d6cde` docs(session-6-plan): expand Session 6 skeleton into full TDD plan (PR #163)
- `874141f` feat(cv): Session 6 bar-coordinate helpers + extractors (identify_liftoff_frame, identify_knee_pass_frame, _bar_to_hip_distance_dict #4, _shoulder_protraction_proxy_px #14, _wrist_midpoint_trajectory; RepMetrics.metrics type widened)
- `8b097bc` test(cv): allow dict value for bar_to_hip_distance in metric invariants
- `959c0b2` feat(cv): flip computed_yet=True for Session 6 registry entries
- `8b68de5` test(cv): Session 6 fixture integration tests + smoke script
- `cc30829` Merge pull request #164 (impl)
- `20ebf54` docs: close Session 6 in backlog + master manifest (direct-to-main, post-merge hygiene)

## Surfaced evidence (for verifier transparency)
- **PR #164:** https://github.com/atharva6905/spelix/pull/164 — merged 2026-05-23 with `merge_method=merge`, merged=true, SHA `cc30829`
- **PR-level CI on PR #164:** all 6 checks pass (Backend Lint & Type Check, Backend Tests, Frontend Lint & Type Check, Frontend Tests, Secret Scanning, Vercel). Deploy to Production = skipping (PR-level; fires post-merge).
- **Post-merge "Deploy to Production"** (main run `26325438213`): `conclusion=success`, completed 2026-05-23T06:13:54Z.
- **Droplet HEAD** matches merge SHA: `cc30829 feat(cv): Session 6 bar-coordinate metrics (#164)` (path `/home/deploy/spelix`).
- **Containers**: `spelix-backend-1 (healthy)`, `spelix-worker-1 (healthy)`, `spelix-redis-1 (healthy)` — backend + worker freshly restarted post-deploy.
- **Unit tests:** 27 new Session-6 tests in `test_metric_extraction_sagittal.py` all pass; combined `test_metric_extraction.py` + `test_sagittal_metrics_registry.py` + `test_expert_sagittal_metrics_endpoint.py` + `test_metric_extraction_sagittal.py` = **191 passed** locally. ruff clean, pyright 0 errors on `metric_extraction.py` + `sagittal_metrics_registry.py`.
- **Integration tests** (`test_pipeline_sagittal_metrics.py::test_session6_*`): 2 passed in 1243s.
  - Deadlift (5 reps, side=right): rep 0 resolved all 4 phase frames — setup=0.808, liftoff=0.791, knee_pass=0.695, lockout=0.164. Reps 1-4 resolved setup+lockout (liftoff/knee_pass None — bar already above the 2% liftoff threshold at rep start on touch-and-go reps; ≥2/4 gate satisfied).
  - Bench (13 reps, side=right): `shoulder_protraction_proxy_px` per rep in range -0.191..+0.061 (rep2 = -0.191, rep9 = +0.061, several reps ~0.0).
- **E2E on prod:** see "E2E results" below.

## E2E results — FULLY VERIFIED on prod
- **Deploy:** Deploy to Production = success on main run `26325438213`; droplet `/home/deploy/spelix` HEAD = `cc30829`; backend + worker containers `(healthy)`.
- **Auth:** the prod `e2e-expert@spelix.internal` password was unknown (created by a prior Claude session). Per user authorization, reset it via `auth.users.encrypted_password = crypt(..., gen_salt('bf'))` scoped by id `3806c3ca-...` (NOT `expert@spelix.app` — reserved for the real expert). Logged in, granted Tier-2 consent.
- **#14 shoulder_protraction_proxy_px (bench):** re-uploaded `atharva-bench.mov` → analysis `e931b5f4-0844-4dcc-96ce-a50d74cab40e`. Prod `rep_metrics` has the key on all 12 reps (range -0.032..+0.069). Expert `<UnvalidatedMetricsPanel />` renders the "Shoulder Protraction Proxy" row populated across all 12 reps. Screenshot `e2e/screenshots/session6-bench-expert-panel.png`. 0 console errors.
- **#4 bar_to_hip_distance (deadlift):** re-uploaded `atharva-deadlift.mov` → analysis `0afe3bb1-e634-44a7-b106-dc2c9ad0e8c1`. Prod `rep_metrics` has the key on all 6 reps as a 4-phase dict (rep0 all four resolved: setup=0.747/liftoff=0.720/knee_pass=0.696/lockout=0.140; reps with touch-and-go starts resolve setup+lockout, liftoff/knee_pass null — bar already above the 2% liftoff threshold at rep start, ≥2/4 gate met). Expert panel renders the "Bar-to-Hip Distance" row with the full dict per rep. Screenshot `e2e/screenshots/session6-deadlift-expert-panel.png`. 0 console errors. Session 7 metrics correctly show "Not yet computed".
- **Prod values match local integration tests** (deadlift rep0 local 0.808/0.791/0.695/0.164 vs prod 0.747/0.720/0.696/0.140 — same shape; minor differences are MediaPipe non-determinism + the prod re-upload being a fresh capture).

## Observed (out-of-Session-6-scope) — worker retry idempotency gap
The FIRST deadlift upload this session (`17095c73-...`) was interrupted mid-`processing` by the "Deploy to Production" triggered by close-out PR #165 merging. streaq re-delivered the in-flight task, but `_run_pipeline` re-ran `transition(status, "processing")` while status was already `processing`, raising `InvalidTransition` → analysis marked `failed`. This is a pre-existing worker idempotency gap (not a Session 6 defect): a deploy (or any container recreate) during an in-flight analysis leaves a poison task that fails its retry. Re-uploading worked cleanly (no pending deploys). **Backlog candidate:** make `process_analysis` idempotent on retry — treat `processing→processing` as a no-op resume, or reset status to a re-runnable state before re-entering the pipeline. Also a benign pre-existing `NFR-RELI-09` log (`PostgresSaver init failed — no pq wrapper`) appears at the coaching step and is gracefully handled (coaching continues without the LangGraph checkpointer); unrelated to Session 6.

## Blockers
- None.

## Deferred items
- **Threshold validation for #4 + #14** — expert flags via FR-EXPV-08; per-metric remediation PRs post-onboarding.
- **Scoring wiring** — both stay `in_scoring=False` per design Section-4 until expert validates thresholds.
- **HoughCircles bar-x for #4** — Session 6 uses the wrist-midpoint proxy (matches `compute_bar_path_from_landmarks` fallback). If post-onboarding calibration shows the wrist-midpoint diverges materially from HoughCircles bar position on deadlift, a follow-up can plumb the actual bar-x trajectory into `extract_rep_metrics` (would require a pipeline reorder: barbell detection currently runs Step 9, after metric extraction Step 6).
- **PDF report inclusion** — explicitly deferred per design Section-1 Non-Goal #5.

## Resume guidance for Session 7
1. Read `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md` §Session-7 (3 metrics; multi-frame analysis, baseline reference, shape classification — highest calibration risk).
2. Read this handoff + master manifest §Session-7.
3. **Run the mandatory `/plan` spike FIRST** with `spelix-cv-engineer` (design spec Session-7 "Pre-implementation"). Save spike output to `docs/superpowers/plans/2026-XX-XX-session-7-complex-metrics-plan.md`. Then expand the Session 7 skeleton via `superpowers:writing-plans` and commit BOTH via a doc PR before launching `/goal`.
4. `/goal` with the Session 7 launch command from the master manifest.
5. Specialist agent: `spelix-cv-engineer` solo (backend-only, registry-driven frontend auto-picks up). Session 7 also requires ADR-LUMBAR-FLEXION-PROXY-NAMING in `decisions.md` and an Expert Reviewer Guide update.
6. Session 7 has an explicit post-merge **calibration mini-session**: run pipeline on all 3 fixtures, eyeball new metric values against video frames, document expected-vs-measured in the handoff.
