# Phase 0 Implementation Plan — Spelix

## Overview

Phase 0 ships: auth → profile → upload → CV pipeline → rep detection → metrics → coaching → results page → history → admin skeleton → PDF export.

**Duration estimate**: 4–5 weeks at focused effort.
**Dependency order**: infra → models → auth → profile → upload API → CV pipeline → coaching → results UI → history → admin → PDF → polish.
**Convention**: All backend commands use `uv run <cmd>` (auto-activates `backend/.venv/`). The local `.venv` is required — Claude Code hooks (ruff, pyright) and pytest run locally, not in Docker.

---

## Week 1: Foundation (B-001 through B-007)

### B-001 — Project scaffold and Docker Compose
**What**: Create all directories, `pyproject.toml`, `docker-compose.dev.yml` (Redis only), `.env.example`, `backend/app/main.py` (minimal FastAPI app with CORS + health endpoint), `frontend/` Vite scaffold.
**SRS**: NFR-OPER-01, NFR-SECU-11, NFR-SECU-12
**Files**: `docker-compose.dev.yml`, `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/config.py`, `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `.env.example`, `.nvmrc`, `.python-version`
**Parallel**: No — everything depends on this.
**TDD gate**: `GET /health` returns `{"status":"ok"}`. `docker compose up -d` starts Redis. `npm run dev` renders React stub. `pytest backend/tests/unit/test_health.py` passes.

### B-002 — SQLAlchemy models and Alembic migration 001
**What**: Define `analyses`, `user_profiles`, `rep_metrics`, `coaching_results` models. Status CHECK constraint. All JSONB columns. Required indexes. Alembic env.py configured for async. Run migration against Supabase.
**SRS**: Section 7.2, 7.3 — all column types and indexes as specified. Status values: queued/quality_gate_pending/quality_gate_rejected/processing/coaching/completed/failed.
**Files**: `backend/app/models/analysis.py`, `backend/app/models/user_profile.py`, `backend/app/models/rep_metric.py`, `backend/app/models/coaching_result.py`, `backend/app/models/__init__.py`, `backend/app/db.py`, `backend/alembic/env.py`, `backend/alembic.ini`, `backend/alembic/versions/001_initial_schema.py`
**Parallel**: No — all service code depends on models.
**TDD gate**: `alembic upgrade head` succeeds against Supabase. `alembic downgrade -1` succeeds. Unit test validates all model fields and CHECK constraint.

### B-003 — Status transition guard
**What**: Implement `transition(current: str, target: str) -> str` function per SRS 5.2a table. Raises `InvalidTransition` on illegal moves.
**SRS**: Section 5.2a transition table (authoritative).
**Files**: `backend/app/services/status.py`, `backend/tests/unit/test_status_transitions.py`
**Parallel**: Yes — can run alongside B-004.
**TDD gate**: Test every valid transition succeeds. Test every invalid transition raises. Test terminal states (completed, quality_gate_rejected, failed@retry=3) reject all transitions.

### B-004 — Repository layer
**What**: `AnalysisRepository`, `UserProfileRepository`, `RepMetricRepository`, `CoachingResultRepository`. All take `AsyncSession` in constructor. CRUD operations. No business logic.
**SRS**: Section 5.1 Repository pattern, NFR-MAIN-08.
**Files**: `backend/app/repositories/analysis.py`, `backend/app/repositories/user_profile.py`, `backend/app/repositories/rep_metric.py`, `backend/app/repositories/coaching_result.py`, `backend/app/repositories/__init__.py`
**Parallel**: Yes — can run alongside B-003.
**TDD gate**: Integration tests against test DB for create/read/update on each repo. Status transition integration test (create analysis, update status through valid chain).

### B-005 — Supabase JWT auth dependency
**What**: FastAPI dependency `get_current_user` that validates Supabase JWT via `SUPABASE_JWT_SECRET`. Extract user_id from token. 401 on invalid/expired. Admin role check helper.
**SRS**: FR-AUTH-02, FR-AUTH-08, NFR-SECU-05.
**Files**: `backend/app/api/deps.py`, `backend/tests/unit/test_auth.py`
**Parallel**: Yes — can run alongside B-003/B-004.
**TDD gate**: Unit test with valid mock JWT → returns user_id. Invalid JWT → 401. Expired JWT → 401. Admin check with role metadata.

### B-006 — Supabase RLS policies
**What**: SQL RLS policies on analyses, user_profiles, rep_metrics, coaching_results. Users access only own rows. Service role bypasses.
**SRS**: FR-AUTH-06, NFR-SECU-01, NFR-SECU-06.
**Files**: `backend/alembic/versions/002_rls_policies.py` (raw SQL via `op.execute`)
**Parallel**: Yes — after B-002.
**TDD gate**: Integration test: user A cannot read user B's analysis. Service role can read all.

### B-007 — Frontend auth (Supabase client + routes)
**What**: Supabase client init (`@supabase/supabase-js`), login/signup pages, `RequireAuth` wrapper, React Router setup, session persistence.
**SRS**: FR-AUTH-01, FR-AUTH-04, FR-AUTH-05, FR-AUTH-07.
**Files**: `frontend/src/lib/supabase.ts`, `frontend/src/components/RequireAuth.tsx`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/SignupPage.tsx`, `frontend/src/routes.tsx`, `frontend/src/App.tsx`
**Parallel**: Yes — can run alongside B-003 through B-006.
**TDD gate**: Vitest: RequireAuth redirects unauthenticated users. Login form renders. Signup form renders. Supabase client mock returns session.

---

## Week 2: Upload + Quality Gates (B-008 through B-014)

### B-008 — User profile API + onboarding page
**What**: `POST /api/v1/profiles`, `GET /api/v1/profiles/me`, `PUT /api/v1/profiles/me`. Onboarding page with required fields (height, weight, age, experience) and optional (arm span, femur length).
**SRS**: FR-PROF-01 through FR-PROF-05.
**Files**: `backend/app/api/v1/profiles.py`, `backend/app/schemas/profile.py`, `backend/app/services/profile.py`, `frontend/src/pages/ProfilePage.tsx`, `frontend/src/api/profiles.ts`
**Parallel**: No — depends on B-005 (auth), B-004 (repos).
**TDD gate**: Backend: create profile → read back. Reject missing required fields. Frontend: form renders all fields, submit calls API.

### B-009 — Upload API endpoint (POST /analyses + POST /analyses/{id}/start)
**What**: Create analysis record (status=queued), generate Supabase Storage signed TUS URL (1h TTL), return 201 with analysis_id + upload_url. Start endpoint: validate ownership, enqueue ARQ job, return 202.
**SRS**: FR-UPLD-07, FR-UPLD-16, FR-UPLD-17, NFR-SECU-10.
**Files**: `backend/app/api/v1/analyses.py`, `backend/app/schemas/analysis.py`, `backend/app/services/analysis.py`, `backend/app/services/storage.py`
**Parallel**: No — depends on B-004, B-005.
**TDD gate**: Unit: valid request → 201 with UUID + URL. 400 on invalid exercise. 413 on >50MB. 429 on >10/day. Start: 202 on valid. 409 on already-started. 403 on wrong user.

### B-010 — Rate limiting middleware
**What**: slowapi + Redis. 10 uploads/user/day on `POST /analyses`.
**SRS**: NFR-SECU-10.
**Files**: `backend/app/middleware/rate_limit.py`, modify `backend/app/main.py`
**Parallel**: Yes — can run alongside B-009.
**TDD gate**: 11th request in same day → 429.

### B-011 — ARQ worker skeleton
**What**: `process_analysis` async function. WorkerSettings per SRS. Heartbeat key. Status transition sequence. Error handling with retry_count. Idempotent check at start.
**SRS**: FR-UPLD-18, NFR-RELI-01 through NFR-RELI-04, NFR-OPER-02.
**Files**: `backend/app/workers/analysis_worker.py`, `backend/app/workers/settings.py`, `backend/tests/unit/test_worker_skeleton.py`
**Parallel**: No — depends on B-003, B-004.
**TDD gate**: Unit test: idempotent skip on completed. Error increments retry_count. Status transitions in correct order. Heartbeat key written.

### B-012 — Quality gates (body visibility + framing)
**What**: P0 body visibility gate: `mean(visibility[0:5][landmarks∈{11,12,13,14,23,24,25,26}]) < 0.30` → reject. P0 framing gate: bounding box area <30% or >80% → reject. `GateCheckResult` and `QualityGateResult` types. All warning gates (lighting P2, camera stability P2, motion blur P3).
**SRS**: FR-CVPL-03 through FR-CVPL-11.
**Files**: `backend/app/cv/quality_gates.py`, `backend/app/schemas/quality_gate.py`, `backend/tests/unit/test_quality_gates.py`
**Parallel**: Yes — pure functions, no deps on other services.
**TDD gate**: Unit tests with synthetic numpy arrays: visibility below threshold → reject. Above → pass. Bounding box too small → reject. Too large → reject. Correct → pass. GateCheckResult fields populated correctly.

### B-013 — Upload page (frontend)
**What**: Exercise type + variant dropdowns. Filming guidance per exercise. Upload button disabled until both selected (FR-XDET-09). TUS upload to Supabase Storage signed URL. Progress indicator. Duration toggle (40s/2min). Call POST /analyses then POST /analyses/{id}/start.
**SRS**: FR-XDET-01, FR-XDET-02, FR-XDET-05, FR-XDET-08, FR-XDET-09, FR-UPLD-01 through FR-UPLD-09, FR-UPLD-12, FR-RESL-12, NFR-USAB-01.
**Files**: `frontend/src/pages/UploadPage.tsx`, `frontend/src/components/UploadForm.tsx`, `frontend/src/components/FilmingGuidance.tsx`, `frontend/src/api/analyses.ts`, `frontend/src/hooks/useUpload.ts`
**Parallel**: Yes — can run alongside B-011/B-012.
**TDD gate**: Vitest: upload button disabled when exercise not selected. Enabled when both selected. Filming guidance renders per exercise. Progress bar renders during upload.

### B-014 — Analysis status page (frontend)
**What**: Subscribe to Supabase Realtime `postgres_changes` on `analyses` filtered by id. User-facing status labels from Appendix B. Reconnection indicator + polling fallback (10s). On `quality_gate_rejected`: show corrective guidance from quality_gate_result.
**SRS**: FR-RESL-13, FR-CVPL-03 (rejected UI), NFR-RELI-06, NFR-PERF-03.
**Files**: `frontend/src/pages/AnalysisStatusPage.tsx`, `frontend/src/hooks/useAnalysisStatus.ts`, `frontend/src/components/AnalysisStatus.tsx`
**Parallel**: Yes — can run alongside B-012.
**TDD gate**: Vitest: correct label for each status. Reconnection indicator on disconnect. Quality gate rejection renders user_message.

---

## Week 3: CV Pipeline (B-015 through B-021)

### B-015 — MediaPipe pose extraction
**What**: Extract 33 landmarks per frame. Exact config: `model_complexity=2, static_image_mode=True, min_detection_confidence=0.5, min_tracking_confidence=0.5, num_threads=1`. Apply sigmoid if values outside [0,1]. Run in executor.
**SRS**: FR-CVPL-01, FR-CVPL-02, FR-CVPL-12, FR-CVPL-13.
**Files**: `backend/app/cv/pose_extraction.py`, `backend/tests/unit/test_pose_extraction.py`
**Parallel**: No — B-016+ depend on this.
**TDD gate**: Unit test with synthetic image → returns landmarks with visibility. Config values enforced.

### B-016 — Savitzky-Golay smoothing + angle calculation
**What**: SG filter (window=7, polyorder=3) on angle time series. Exercise-specific angle calculation (hip, knee, elbow).
**SRS**: FR-CVPL-14.
**Files**: `backend/app/cv/signal_processing.py`, `backend/tests/unit/test_signal_processing.py`
**Parallel**: Yes — pure math, can run alongside B-015.
**TDD gate**: Unit test: known angle series → smoothed output within tolerance. Angle calculation from 3 landmarks → correct degrees.

### B-017 — Rep detection state machine
**What**: Per-exercise state machine: STANDING → DESCENDING → BOTTOM → ASCENDING → STANDING. Threshold-crossing on primary angle. Min rep duration 0.5s. Hysteresis ±5°. Partial reps at >50% ROM. Exercise-specific thresholds per FR-CVPL-15.
**SRS**: FR-CVPL-15, FR-REPM-01, FR-REPM-05.
**Files**: `backend/app/cv/rep_detection.py`, `backend/tests/unit/test_rep_detection.py`
**Parallel**: No — depends on B-016.
**TDD gate**: Synthetic angle series with known reps → correct rep count and boundaries. Single-rep video → valid output. Partial rep detection.

### B-018 — Per-rep metric extraction
**What**: Exercise-variant-specific metrics per FR-REPM-02. Squat: knee valgus, lumbar angle, depth classification, torso lean, bar path deviation. Deadlift: lumbar angle, hip hinge, bar-to-body distance. Bench: elbow flare, wrist alignment, bar touch point. Phase 0: extract what's measurable from 2D landmarks. Store as structured JSON in rep_metrics.metrics_json.
**SRS**: FR-REPM-02, FR-REPM-03, Section 3.7 metric definitions.
**Files**: `backend/app/cv/metric_extraction.py`, `backend/app/cv/analyzers/squat.py`, `backend/app/cv/analyzers/deadlift.py`, `backend/app/cv/analyzers/bench.py`, `backend/app/cv/analyzers/__init__.py`, `backend/tests/unit/test_metric_extraction.py`
**Parallel**: No — depends on B-017.
**TDD gate**: Synthetic landmark data → correct metrics per exercise. Depth classification (above/at/below parallel). Squat valgus angle extraction.

### B-019 — Phase 0 confidence scoring
**What**: Per-rep confidence = mean(visibility[exercise_relevant_landmarks]) across frames. Session confidence = mean of per-rep confidences. Landmark sets: squat/DL = {23,24,25,26,27,28}, bench = {11,12,13,14,15,16}. Confidence label mapping: ≥0.80 High, 0.65–0.79 Moderate, 0.50–0.64 Low, <0.50 Very Low.
**SRS**: FR-CVPL-16, FR-RESL-08, FR-REPM-04, FR-SCOR-10.
**Files**: `backend/app/cv/confidence.py`, `backend/tests/unit/test_confidence.py`
**Parallel**: Yes — pure function, can run alongside B-018.
**TDD gate**: Known visibility arrays → correct per-rep and session scores. Label mapping at boundaries.

### B-020 — Barbell detection and tracking
**What**: OpenCV contour/circle detection for barbell per frame. Bar centroid trajectory. Per-rep bar path deviation. Graceful null when barbell not detected in >50% frames.
**SRS**: FR-BDET-01 through FR-BDET-07.
**Files**: `backend/app/cv/barbell_detection.py`, `backend/tests/unit/test_barbell_detection.py`
**Parallel**: Yes — can run alongside B-018.
**TDD gate**: Synthetic frame with circle → detected centroid. No circle → null gracefully. Trajectory from frame sequence.

### B-021 — Annotated video + artifact generation
**What**: Skeleton overlay (#00FF88, 2px), angle labels (Arial 18px), rep counter top-left ("Rep: N / M" Arial 24px bold). Exercise-specific skeleton connections. Angle time-series plot (matplotlib PNG). Upload all to Supabase Storage. Write paths to analyses row. Video lifecycle: delete from Storage after pipeline, delete local temp on exit.
**SRS**: FR-CVPL-19, FR-UPLD-15, FR-XPRT-01.
**Files**: `backend/app/cv/artifact_generation.py`, `backend/app/cv/video_annotator.py`, `backend/tests/unit/test_artifact_generation.py`
**Parallel**: No — depends on B-018, B-020.
**TDD gate**: Synthetic frame → annotated frame has correct overlay color/position. Rep counter shows cumulative completed. Plot PNG generated. Paths written to DB.

---

## Week 4: Coaching + Results (B-022 through B-029)

### B-022 — Wire CV pipeline in ARQ worker
**What**: Connect B-011 skeleton with B-012, B-015–B-021. Full pipeline: download video → quality gates → pose extraction → smoothing → rep detection → metrics → confidence → barbell → artifacts → upload artifacts → delete video from Storage → delete local temp.
**SRS**: FR-UPLD-15, FR-UPLD-18, all FR-CVPL, all FR-REPM, all FR-BDET.
**Files**: `backend/app/workers/analysis_worker.py` (complete), `backend/app/services/pipeline.py`
**Parallel**: No — depends on all Week 3 tasks.
**TDD gate**: Integration test with real fixture video → analysis completes with status=processing. Rep count > 0. Metrics populated. Artifacts uploaded. Video deleted from Storage.

### B-023 — Phase 0 coaching service
**What**: Claude Sonnet 4.6 call via instructor + Pydantic v2. CoachingOutput schema. System prompt + user turn from Appendix D. Error handling: 429→backoff, 401→fail, timeout 60s. Store in coaching_results.structured_output_json.
**SRS**: FR-RESL-03 (Phase 0 sync), Appendix D (prompt template, schema, tone rules).
**Files**: `backend/app/services/coaching.py`, `backend/app/schemas/coaching.py`, `backend/tests/unit/test_coaching.py`
**Parallel**: Yes — can run alongside B-022.
**TDD gate**: Unit test with mocked LLM: valid response parsed into CoachingOutput. 429 triggers retry. 401 fails immediately. Disclaimer present. Token counts logged.

### B-024 — Wire coaching into ARQ worker
**What**: After CV pipeline completes (status=processing → coaching), call coaching service, store result, transition to completed.
**SRS**: Status transition: processing → coaching → completed.
**Files**: Modify `backend/app/workers/analysis_worker.py`
**Parallel**: No — depends on B-022, B-023.
**TDD gate**: Integration test: full pipeline with mocked LLM → status=completed. coaching_results row created.

### B-025 — Hardcoded thresholds config
**What**: `config/thresholds_v0.json` with Phase 0 defaults. Squat knee valgus caution 5°, high-risk 10°. Lumbar flexion caution 28°, high-risk 44°. Bench grip flag >1.5× biacromial. Experience tolerance ±3° beginner, ±5° advanced. Named constants loaded at startup.
**SRS**: FR-SCOR-00.
**Files**: `config/thresholds_v0.json`, `backend/app/config.py` (ThresholdLoader)
**Parallel**: Yes — can run alongside B-022.
**TDD gate**: Unit test: loader reads file, returns typed config. All values match SRS.

### B-026 — Results page (frontend)
**What**: Phase 0 summary card: exercise/variant, rep count, confidence label, timestamp. Space reserved for Phase 1 dimension scores. Annotated video player (Supabase Storage signed URL). Angle plot image. Coaching markdown rendered from structured_output_json. Issues sorted by severity (High first). Confidence label with guidance text. Three-tier disclaimer. CSV download link. 7-day download banner.
**SRS**: FR-RESL-01a, FR-RESL-02, FR-RESL-03, FR-RESL-04, FR-RESL-05, FR-RESL-08, FR-RESL-10, FR-RESL-11, FR-SCOR-09, FR-SCOR-10, NFR-USAB-02, NFR-USAB-03, NFR-USAB-06, NFR-USAB-07, FR-UPLD-19.
**Files**: `frontend/src/pages/ResultsPage.tsx`, `frontend/src/components/SummaryCard.tsx`, `frontend/src/components/CoachingOutput.tsx`, `frontend/src/components/ConfidenceLabel.tsx`, `frontend/src/components/RepMetricsTable.tsx`, `frontend/src/components/BarPathChart.tsx`, `frontend/src/components/DisclaimerBanner.tsx`, `frontend/src/api/analyses.ts` (add getAnalysis, getCoaching)
**Parallel**: Yes — can start with mock data while B-024 completes.
**TDD gate**: Vitest: confidence label renders correct text/color for each level. Disclaimer present. Issues sorted High→Medium→Low. Video player renders. Upload button absent for completed analysis.

### B-027 — Status poll endpoint
**What**: `GET /api/v1/analyses/{id}/status` → `{id, status, updated_at}`. Fallback for Realtime disconnect.
**SRS**: FR-RESL-13.
**Files**: Modify `backend/app/api/v1/analyses.py`
**Parallel**: Yes.
**TDD gate**: Returns current status. 404 on unknown ID. 403 on wrong user.

### B-028 — Analysis CRUD (delete, rename, tags)
**What**: `DELETE /api/v1/analyses/{id}` purges DB + Storage artifacts. `PATCH /api/v1/analyses/{id}` for rename and tags.
**SRS**: FR-UPLD-10, FR-UPLD-11, FR-XPRT-05 (partial).
**Files**: Modify `backend/app/api/v1/analyses.py`, `backend/app/services/analysis.py`
**Parallel**: Yes.
**TDD gate**: Delete removes analysis + rep_metrics + coaching_results + Storage files. Rename updates title. Tags update.

### B-029 — Get single analysis + list analyses endpoints
**What**: `GET /api/v1/analyses/{id}` (full detail with coaching + metrics). `GET /api/v1/analyses` (list for current user, reverse chronological, with status badge fields).
**SRS**: FR-HIST-01.
**Files**: Modify `backend/app/api/v1/analyses.py`, `backend/app/schemas/analysis.py`
**Parallel**: Yes — after B-004.
**TDD gate**: Get returns all fields. List returns reverse chronological. Filtered to current user only.

---

## Week 5: History + Admin + PDF + Polish (B-030 through B-038)

### B-030 — Summary metrics computation
**What**: After analysis completes, compute and write `analyses.summary_json` with trend inputs: confidence, rep count, quality gate warnings, per-exercise/variant grouping.
**SRS**: FR-HIST-04.
**Files**: `backend/app/services/summary.py`, modify `backend/app/workers/analysis_worker.py`
**Parallel**: No — depends on B-024.
**TDD gate**: Unit test: given analysis + rep metrics → correct summary_json structure.

### B-031 — History insights endpoints
**What**: `GET /api/v1/insights/exercise/{type}/{variant}` → 7-session rolling avg confidence, rep count trend, most common quality gate warning, personal best confidence. `GET /api/v1/insights/global` → most common warning (30 days), highest rep count variance exercise.
**SRS**: FR-HIST-02, FR-HIST-03.
**Files**: `backend/app/api/v1/insights.py`, `backend/app/services/insights.py`
**Parallel**: Yes — after B-030.
**TDD gate**: Unit test with synthetic analyses → correct rolling average, correct personal best. Global insights correct.

### B-032 — History page (frontend)
**What**: Reverse-chronological analysis list with status badge, exercise/variant, confidence label, date. Per-exercise insights. Global insights panel. Trend charts (Recharts).
**SRS**: FR-HIST-01, FR-HIST-02, FR-HIST-03, FR-HIST-06.
**Files**: `frontend/src/pages/HistoryPage.tsx`, `frontend/src/components/InsightsPanel.tsx`, `frontend/src/components/TrendChart.tsx`, `frontend/src/api/insights.ts`
**Parallel**: Yes — can mock data.
**TDD gate**: Vitest: list renders. Insights panel renders. Charts render with data.

### B-033 — Admin API endpoints
**What**: User management (list, disable, delete). Analysis metadata log. System health (ARQ queue depth, job success/failure rate). Confidence audit. All behind admin role check.
**SRS**: FR-ADMN-01 through FR-ADMN-05.
**Files**: `backend/app/api/v1/admin.py`, `backend/app/services/admin.py`
**Parallel**: Yes — after B-005.
**TDD gate**: Non-admin → 403. Admin can list users. Admin can view analysis metadata (no coaching content). Health endpoint returns queue depth.

### B-034 — Admin page (frontend)
**What**: User management table. Analysis metadata table. Confidence audit filter. System health panel.
**SRS**: FR-ADMN-01 through FR-ADMN-05.
**Files**: `frontend/src/pages/AdminPage.tsx`, `frontend/src/components/admin/UserTable.tsx`, `frontend/src/components/admin/AnalysisLog.tsx`, `frontend/src/components/admin/HealthPanel.tsx`, `frontend/src/api/admin.ts`
**Parallel**: Yes — after B-033.
**TDD gate**: Vitest: admin page renders. Non-admin redirected. Tables render with mock data.

### B-035 — PDF report generation
**What**: WeasyPrint HTML→PDF. Template at `reports/templates/analysis_report.html`. Layout per FR-XPRT-02. Generated as background ARQ task after coaching completes. Stored in Supabase Storage. Path written to analyses.pdf_path.
**SRS**: FR-XPRT-02, FR-XPRT-03, NFR-PERF-07.
**Files**: `reports/templates/analysis_report.html`, `backend/app/services/pdf.py`, `backend/app/workers/pdf_worker.py`
**Parallel**: Yes — after B-024.
**TDD gate**: Unit test: given analysis + coaching → generates valid PDF. Integration: PDF path written to DB. Download URL serves file.

### B-036 — CSV data export
**What**: `GET /api/v1/export/csv` → ZIP of analyses metadata + rep metrics + coaching summaries for current user.
**SRS**: FR-XPRT-04, NFR-SECU-07.
**Files**: `backend/app/api/v1/export.py`, `backend/app/services/export.py`
**Parallel**: Yes.
**TDD gate**: Returns valid CSV. Contains all user data. Does not contain other users' data.

### B-037 — Account deletion
**What**: `DELETE /api/v1/account` → purges user_profiles, analyses, rep_metrics, coaching_results, all Storage artifacts.
**SRS**: FR-AUTH-07, FR-XPRT-05, NFR-SECU-08.
**Files**: `backend/app/api/v1/profiles.py` (add delete), `backend/app/services/account.py`
**Parallel**: Yes.
**TDD gate**: After deletion: no rows exist for user. Storage artifacts deleted. Supabase auth user deleted.

### B-038 — Artifact cleanup cron job
**What**: Scheduled ARQ cron job. Runs nightly. Deletes annotated_video_path, plot_path, pdf_path from Storage for analyses older than 7 days. Sets columns to NULL. Analyses row retained.
**SRS**: FR-UPLD-15, FR-UPLD-19.
**Files**: `backend/app/workers/cleanup.py`, modify `backend/app/workers/settings.py`
**Parallel**: Yes.
**TDD gate**: Unit test: analyses >7 days → artifacts deleted, columns nulled. Analyses <7 days → untouched. Row still exists.

---

## Final Polish (B-039 through B-042)

### B-039 — Error boundaries (frontend)
**What**: React error boundaries at component level. SSE interruption, malformed data, WebSocket disconnect, failed API calls → localized recovery UI.
**SRS**: NFR-USAB-09.
**Files**: `frontend/src/components/ErrorBoundary.tsx`, wrap all page components.
**Parallel**: Yes.
**TDD gate**: Vitest: error in child component → boundary catches and renders retry button.

### B-040 — OpenAPI type generation
**What**: `npm run gen-types` script using openapi-typescript. Generate from FastAPI /openapi.json. Replace any hand-written API types.
**SRS**: NFR-MAIN-07.
**Files**: `frontend/package.json` (add script), `frontend/src/api/types.ts` (generated)
**Parallel**: Yes — after all API endpoints exist.
**TDD gate**: Types generate without error. Frontend builds with generated types.

### B-041 — E2E integration test
**What**: Full flow: create analysis → upload video (fixture) → start → wait for completion → verify results. Uses httpx AsyncClient.
**SRS**: NFR-MAIN-04.
**Files**: `backend/tests/e2e/test_full_flow.py`
**Parallel**: No — depends on everything.
**TDD gate**: Test passes end-to-end with a real fixture video.

### B-042 — CI pipeline (GitHub Actions)
**What**: On push: ruff, pyright, pytest with coverage (≥90%), vitest with coverage (≥90%), tsc --noEmit. Secret scanning.
**SRS**: NFR-MAIN-01, NFR-MAIN-05, NFR-MAIN-06.
**Files**: `.github/workflows/ci.yml`
**Parallel**: Yes.
**TDD gate**: CI passes on main branch.

---

## Dependency Graph Summary

```
B-001 → B-002 → B-003/B-004/B-005/B-006 (parallel)
B-005 → B-008 → B-009 → B-011 → B-022
B-007 (parallel with backend)
B-012 (parallel, pure functions)
B-013/B-014 (parallel, frontend)
B-015 → B-016 → B-017 → B-018 → B-021
B-019/B-020 (parallel with B-018)
B-022 → B-024 → B-030
B-023 (parallel) → B-024
B-025 (parallel)
B-026/B-027/B-028/B-029 (parallel, after B-024)
B-030 → B-031 → B-032
B-033 → B-034
B-035/B-036/B-037/B-038 (parallel)
B-039/B-040/B-041/B-042 (final)
```
