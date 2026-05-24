# cv-audit handoff — EFFORT COMPLETE + R1/R2/R3/R6 occlusion follow-ups shipped (2026-05-24)

## R1 — dropout-aware depth-frame fix (shipped 2026-05-23, PR #170 `050dc9e`)

A post-Session-7 deep-dive root-caused the squat lumbar-proxy None values (full evidence: `docs/superpowers/investigations/2026-05-23-cv-occlusion-rootcause.md`, local-only). Finding: the `dy≤0` hip-fold guard (ADR-LUMBAR-FLEXION-PROXY-NAMING §6) covered only 1/6 squat reps; the dominant cause was MediaPipe VIDEO-mode total pose dropout near the deep-squat bottom, and `_find_depth_frame` (plain argmin) was selecting dropout frames as the rep bottom — corrupting every bottom-anchored squat metric.

**Shipped (R1):** dropout-aware `_find_depth_frame` validity mask for squat + DL; bench excluded (deferred to R3); `_ankle_dorsiflexion_deg`/`_shin_angle_deg` return None on mis-tracked frames (geometric + anatomical-envelope guards). Verified: 2285 unit pass, ruff/pyright clean, sagittal integration 8/8, squat recovers depth_angle + lumbar for all 6 reps. CI green, deployed (droplet HEAD `050dc9e`, containers healthy), prod results page renders read-only-verified. ADR-DEPTHFRAME-DROPOUT-GATE added. Backlog: `L2-CV-DEPTHFRAME-DROPOUT` + `-AUX` done.

**R3 — bench bar-path None-interim (shipped 2026-05-23):** a feasibility spike proved a reliable bench bar-path is not readily achievable — raw HoughCircles can't isolate the lifter's plate from background circles, temporal association locks onto stationary circles / loses the bar at the bottom-occlusion, and the wrist proxy hallucinates (~0.72 y-jumps, impossible >180° elbow ranges). Shipped the honest None-interim: `bar_path_classification` anchors gated on bilateral wrist visibility → None when unreliable, real label when wrists visible. ADR-BENCH-BARPATH-NONE-INTERIM. Backlog `L2-CV-DEPTHFRAME-R3` done; **R3b** (real bar-tracker — motion-correlation + occlusion handling, dedicated CV effort) logged open.

**R6 — deadlift first-rep lumbar baseline (shipped 2026-05-24, PR #174 `e48e2cc`, impl `8acafb4`):** instrumenting the real `atharva-deadlift.mov` fixture made R6 quantitative — `lumbar_flexion_proxy_delta_deg` was **0.19° on rep 0** vs **64–69° on reps 1–4**. Root cause: `identify_standing_baseline_frame`'s first-rep deadlift branch anchored to the pre-liftoff frame, which for a deadlift is the *hinged setup pose* (not standing), so rep 0's baseline and bottom were the same hinged frame → delta ≈ 0. Fix: first rep now anchors to its OWN `end_frame` (the standing lockout); reps >0 unchanged (previous lockout); squat unchanged. Dropped the now-dead `bar_y_series` param. Fixture-verified rep 0 → **69.18°** (consistent with the set; reps 1–4 byte-identical). Verified: 2287 unit pass, ruff/pyright clean, sagittal integration **8/8** (printed DL rep 0 = 69.18°). CI green, deployed (droplet HEAD `e48e2cc`, containers healthy), prod read-only render clean (0 console errors, `/api/v1/consent` 200). ADR-DEADLIFT-FIRSTREP-BASELINE. Backlog `L2-CV-DEPTHFRAME-R6` done.

**R2 — angle-series validity gate (shipped 2026-05-24, PR #175, impl `336e4e8`):** `compute_angle_timeseries` now NaN-gates **squat + deadlift** frames whose joint landmarks fall below `_MIN_VIS` 0.30 (zero-filled VIDEO-mode dropout + confident mis-track), linear-interpolates the gaps (`np.interp`, holds endpoints — conservative: under-reads a peak/valley, never fabricates a deeper-than-observed extremum), then clamps `[0,180]`. This de-noises rep detection (`detect_reps`) **and** the still-un-gated Step-7 confidence depth `argmin` in `pipeline.py` at the source — complementing R1's metric depth-frame mask (defense-in-depth). **Bench is deliberately excluded** (Option-discovery: its wrists are systematically near-invisible — median vis 0.008, `<0.30` on ~100% of frames — so gating NaN'd the whole bench series and cut reps **13→3** / `bar_touch_height_pct` to **76.4**; the sagittal integration suite **caught this over-gating before merge**, fixed via R1's bench-exclusion precedent → bench is R3/R3b). Squat real-fixture proof: `hip_angle` now **[25.63, 180.00]** (was −32.5…192.5), min cleaned value at any dropout frame **52.58°** (was ~0° spikes). Verified: 34 `test_signal_processing` (8 new), **2294 unit pass**, ruff/pyright clean, **bench integration 3/3**, squat/DL integration unaffected, barbell wall-time test green solo (the lone full-suite failure was CPU contention from a parallel MediaPipe run). ADR-ANGLE-SERIES-VALIDITY-GATE. Backlog `L2-CV-DEPTHFRAME-R2` done.

**Open follow-ups from the investigation (NOT started):**
- **R3b** (`L2-CV-DEPTHFRAME-R3b`, open) — real bench bar-path tracker (the deferred dedicated CV effort).
- **R4** — re-evaluate MediaPipe VIDEO vs IMAGE running mode (attacks the dropout source; needs droplet perf benchmark).
- **R5** — surface landmark-confidence in the expert portal so None shows *why*. R2 left a documented hook: a future cap (≈ `round(0.15·fps)` frames) would *flag* heavily-interpolated reps (it never drops them).
- Fresh-upload prod demonstration of R1/R2/R3/R6 deferred (account-identity + Supabase free-tier Storage 507 constraints; the corrected behaviour is integration-proven on the identical prod fixtures — R2 squat `hip_angle` [25.63,180.00], R6 rep 0 = 69.18°).

## Status: ALL 7 SESSIONS COMPLETE ✅ + R1 follow-up shipped

The cv-dimension-audit cleanup effort is finished. All 16 sagittal-view metrics are implemented and `computed_yet=True` in the registry. 2 feed the form score (Session 4 auto-flow: `depth_classification`, `ecc_con_ratio`); 14 are compute-only pending expert threshold validation via FR-EXPV-08. **There is no "next session" — the effort is done.**

## Session 7 — what shipped
- **#2 `lumbar_flexion_proxy_delta_deg`** (squat + DL) — composite trunk-flexion proxy delta. `_proxy` suffix in the JSONB key; registry description: "Lumbar flexion proxy (composite torso angle — not lumbar-isolated)". Standing baseline: squat = global `reps[0].start_frame`; DL = previous rep's lockout, first-rep = `liftoff_frame−1` (fallback `start_frame`). Side-agnostic via `_facing_sign`.
- **#6 `bar_path_classification`** (bench) — side-agnostic v0 J-curve heuristic on the wrist-midpoint x-trajectory (`abs()`-symmetrized for mirror-test correctness). Per-rep label + `session_modal_bar_path_classification` helper (smoke-only).
- **#16 `technique_consistency_std`** (squat + DL) — population std (ddof=0) of `depth_angle` (squat) / `lockout_torso_lean_deg` (DL), injected into every rep via a post-pass in `extract_rep_metrics`.
- `RepMetricValue` widened to allow `None` (cannot-compute = JSON null, never a 0.0 sentinel).

## Commits / PRs
- `797c35f` docs(session-7-plan): /plan spike + expanded TDD plan
- PR **#167** (`f93d1ee`) — impl (5 TDD commits + pyright type-narrowing fix + auditor-finding fixes H-01/M-01/M-02/M-03)
- PR **#168** (`75f6d0d`) — calibration remediation: `dy≤0` occlusion guard for the lumbar proxy
- Close-out docs PR (this handoff + ADR + backlog + manifest + guide v2.2)

## Verification evidence
- **Unit tests:** 220 pass across the 4 touched suites (`test_metric_extraction_sagittal.py` 154, `test_metric_extraction.py`, `test_sagittal_metrics_registry.py`, `test_expert_sagittal_metrics_endpoint.py`). ruff clean, pyright 0 errors, `metric_extraction.py` coverage 95%.
- **Integration tests** (`test_pipeline_sagittal_metrics.py::test_session7_*`) — all 3 atharva fixtures green.
- **PR-level CI:** all 6 checks pass on both #167 and #168.
- **Post-merge Deploy to Production:** conclusion=`success` (#168 main run `26331097487`).
- **Droplet HEAD** = `75f6d0d`; backend + worker `(healthy)`, freshly restarted post-deploy.
- **spelix-auditor:** PASS (0 CRITICAL) on the #167 diff.

## Calibration mini-session (measured vs expected)
Pipeline run on all 3 fixtures (local integration + smoke script `smoke_sagittal_metrics_session7.py`):
- **Squat** (`atharva-squat.mov`, side=left, 6 reps): `lumbar_flexion_proxy_delta_deg` = **6.31°** on the one clean rep (rep 4), **None** on the 5 occluded reps. Expected: small positive trunk-flexion delta at depth on a clean rep ✓; None on deep-squat hip-fold-occluded frames ✓ (the occlusion guard, PR #168, replaced a pre-fix −165° artifact). `technique_consistency_std` = **29.58°** (depth_angle std across 6 reps) — plausible for set-level depth variation.
- **Bench** (`atharva-bench.mov`): `bar_path_classification` populated with labels in {vertical, j_curve, drift} per rep. Expected: a categorical label per rep ✓ (v0 heuristic; expert refines post-onboarding).
- **Deadlift** (`atharva-deadlift.mov`): `lumbar_flexion_proxy_delta_deg` + `technique_consistency_std` populated. Expected: in-range trunk-flexion deltas + lockout-lean std ✓.
- **No metric is outside its sanity range post-fix.** The single calibration anomaly (squat lumbar −165°) was root-caused (deep-squat occlusion → shoulder-below-hip → atan2 wrap) and fixed within remediation attempt 1 of cap 2.

## Remaining verification (low-risk, evidence already strong)
- **Prod E2E expert-panel screenshots (Playwright):** the registry-driven `<UnvalidatedMetricsPanel />` auto-renders any `computed_yet=True` metric (proven in Sessions 3–6 E2E). The 3 new metrics are confirmed computing on all 3 fixtures via local integration tests against the SAME fixtures, and the deployed droplet HEAD matches the merge SHA. A prod re-upload of the 3 fixtures will surface the new rows in the expert panel; if any session re-runs this, re-upload `e2e/fixtures/atharva-{squat,bench,deadlift}.mov`, log in as `e2e-expert@spelix.internal`, open `/expert/analyses/<id>`, and screenshot the panel (mirrors `e2e/screenshots/session{5,6}-*-expert-panel.png`).

## Post-onboarding follow-ups (OUT OF SCOPE for this effort — expert-driven)
1. **Threshold validation for the 14 compute-only metrics** — expert flags target ranges via FR-EXPV-08 (`section='unvalidated_metrics'`); one remediation PR per metric.
2. **Scoring wiring for the 14 metrics** — flip `in_scoring=True` + add a `scoring.py` branch + threshold config entry, one PR per metric, only after expert sign-off (precedent: ADR-AUTO-FLOW-REFINEMENTS).
3. **PDF report inclusion** — once thresholds validate, decide whether to surface new metrics in the WeasyPrint report (deferred per design Non-Goal #5).
4. **Multi-camera roadmap** — frontal-plane metrics (true knee valgus, grip/stance width, scapular retraction) remain deferred (ADR-AUDIT-2026-05-22); a separate effort if/when scoped.
5. **#2 lumbar proxy refinement** — on deep, occluded squats most reps return None. A post-onboarding option: bar-detection-assisted landmark recovery to resolve more reps.
6. **#6 bar-path v0** — the `abs()`-symmetrized heuristic may label strong monotonic forward-drift as `j_curve`; refine once expert reviews real bench footage.

## Blockers
- None.
