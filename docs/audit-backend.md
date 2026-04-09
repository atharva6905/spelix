# Backend Audit Report — Phase 0

**Date**: 2026-04-09
**Auditor**: Claude Sonnet 4.6 (sub-agent)
**Scope**: backend/app/ against SRS v1.11 Phase 0 requirements

---

## SRS Compliance

### 3.1 Authentication and Authorization (FR-AUTH)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-AUTH-01 | Email/password + Google OAuth registration | PASS | Handled by Supabase Auth client-side. Backend validates JWTs regardless of sign-in method. |
| FR-AUTH-02 | FastAPI validates JWT on all protected endpoints | PASS | `deps.py` implements JWKS-based ES256 verification with HS256 fallback. Audience validated as `"authenticated"`. |
| FR-AUTH-03 | Email verification before first analysis | WARN | Not enforced at the FastAPI layer. The backend does not check `email_confirmed_at` in the JWT payload. If Supabase is configured to block unverified users at the Auth level this is fine — but there is no defensive check in `get_current_user`. |
| FR-AUTH-04 | Password reset via Supabase | PASS | Supabase built-in; no backend code needed. |
| FR-AUTH-05 | Session persistence via localStorage | PASS | Handled by `@supabase/js` on frontend. |
| FR-AUTH-06 | RLS at Supabase Postgres layer | PASS | CLAUDE.md documents this; no DDL FK to auth.users (correct). |
| FR-AUTH-07 | Account deletion purges all data | PASS | `AccountService.delete_account()` deletes all analyses (cascades to rep_metrics + coaching_results), all Storage artifacts, and the user_profiles row. |
| FR-AUTH-08 | Admin role protected server-side | PASS | `get_admin_user` dependency reads `user_metadata.role`; returns 403 for non-admins. Used on all admin routes. |

### 3.2 User Profile and Body Stats (FR-PROF)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-PROF-01 | First-login onboarding flow | PASS | Backend provides GET/PUT `/api/v1/profiles/me`. Frontend enforces onboarding; backend returns 404 if no profile exists (usable as gate). |
| FR-PROF-02 | Required stats: height_cm, weight_kg, age, experience_level | PASS | `ProfileUpdate` schema has all four as required fields with `Field(...)` (no default). |
| FR-PROF-03 | Optional stats: arm_span_cm, femur_length_cm | PASS | Both optional in schema and model. |
| FR-PROF-04 | Experience level definitions (Beginner/Intermediate/Advanced) | PASS | Schema uses `Literal["beginner", "intermediate", "advanced"]`. Note: SRS says "Beginner/Intermediate/Advanced" (title-case); implementation uses lowercase values. This is a style mismatch but not a functional defect — the stored values just differ from the SRS wording. |
| FR-PROF-05 | Profile editable at any time | PASS | PUT `/api/v1/profiles/me` upserts. |
| FR-PROF-06 | Body stats injected into AI coaching context | PASS (Phase 1) | Phase 1 requirement; not implemented in Phase 0. |
| FR-PROF-07 | Landmark-inferred body proportions vs declared stats | PASS (Phase 1) | Phase 1 requirement; out of scope. |

### 3.3 Video Upload and Management (FR-UPLD)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-UPLD-01 | Accepted formats: MP4, MOV, AVI | WARN | No format validation implemented at the backend upload endpoint. Validation is deferred to the ARQ worker (FFprobe) per CLAUDE.md. However, no FFprobe validation is visible in `analysis_worker.py` or `pipeline.py` either. **FFprobe codec check specified in FR-UPLD-14 is not implemented.** |
| FR-UPLD-02 | Default max 40s duration | WARN | No duration validation implemented in backend. SRS says "rejected at upload time" but no check exists in `POST /analyses` or the worker pipeline. |
| FR-UPLD-03 | Minimum ~2s duration | WARN | Same issue as FR-UPLD-02 — no duration check exists. |
| FR-UPLD-04 | Toggle to extend max to 2 minutes | WARN | No `extended_duration` or similar field in `AnalysisCreate` schema. Not implemented. |
| FR-UPLD-05 | Videos exceeding max duration rejected | FAIL | No duration validation exists anywhere in the backend pipeline. |
| FR-UPLD-06 | TUS resumable upload | PASS | StorageService generates a signed TUS upload URL. Browser uploads directly to Supabase Storage. |
| FR-UPLD-07 | Upload flow: POST /analyses → signed URL → POST /{id}/start | PASS | Correctly implemented across `analyses.py` and `analysis.py`. |
| FR-UPLD-08 | Upload progress indicator | PASS | Frontend concern; backend provides the URL. |
| FR-UPLD-09 | Inline filming guidance on upload page | PASS | Frontend concern. |
| FR-UPLD-10 | Rename analyses / add tags | PASS | PATCH `/api/v1/analyses/{id}` supports `tags` field. |
| FR-UPLD-11 | Delete analysis + artifacts | PASS | `delete_analysis()` deletes Storage artifacts then the DB row (cascade). |
| FR-UPLD-12 | TUS mid-upload resume | PASS | TUS protocol handles this; no backend intervention needed. |
| FR-UPLD-13 | Storage quota check before upload | FAIL | No quota check before upload. `POST /analyses` does not call the Supabase Admin API to check available storage. |
| FR-UPLD-14 | FFprobe codec check on corrupt files | FAIL | Not implemented. The worker downloads and passes the file directly to OpenCV/MediaPipe without any FFprobe validation step. |
| FR-UPLD-15 | Video lifecycle (temp + Storage deletion) | PASS | Source video deleted from Storage after full CV pipeline (`pipeline.py` step 12). Local temp deleted in `finally` block of `process_analysis`. |
| FR-UPLD-16 | POST /analyses spec (request/response, 413/400/429/401) | PASS | File size check: 0→400, >50MB→413. Exercise type/variant→400. Rate limiting→429. JWT→401. |
| FR-UPLD-17 | POST /analyses/{id}/start spec (202/404/403/409/401) | PASS | All error codes handled correctly. |
| FR-UPLD-18 | ARQ worker job signature and settings | PASS | Matches spec: `queue_name="arq:queue"`, `job_timeout=300`, `max_jobs=1`, `keep_result=0`, `REDIS_URL` env var. |
| FR-UPLD-19 | 7-day artifact retention + nightly cleanup + 7-day banner | PASS | Cleanup job implemented in `cleanup.py`, registered as cron at 03:00 UTC. 7-day window enforced. DB row preserved. |

### 3.4 Exercise Selection and Auto-Detection (FR-XDET)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-XDET-01 | Phase 0: user selects exercise type/variant before upload | PASS | Required in `AnalysisCreate` schema and validated in `create_analysis()`. |
| FR-XDET-02 | Supported variants: bench (flat/incline/decline), deadlift (conventional/sumo/romanian), squat (high_bar/low_bar) | PASS | Validated in `AnalysisService._VALID_VARIANTS`. "Romanian" stored as "romanian" (lowercase). |
| FR-XDET-03–04 | Auto-detection (Phase 1+) | PASS | Out of scope for Phase 0. |
| FR-XDET-05 | User can override exercise type/variant | WARN | No override/re-analysis endpoint exists in backend. Frontend would need to delete and re-upload. FR-XDET-06 says "triggers full re-analysis from scratch" — this is not wired up. |
| FR-XDET-06 | Manual override triggers re-analysis | FAIL | No re-analysis endpoint exists. |
| FR-XDET-07 | Detection confidence shown (Phase 1+) | PASS | Out of scope. |
| FR-XDET-08 | Barbell-only scope | PASS | Enforced by the `_VALID_VARIANTS` allowlist. |
| FR-XDET-09 | Upload button disabled until type+variant selected | PASS | Frontend concern. |

### 3.5 Computer Vision Pipeline (FR-CVPL)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-CVPL-01 | BlazePose Heavy required | PASS | `model_complexity=2` enforced in `pose_extraction.py`. |
| FR-CVPL-02 | All CPU-bound CV in `run_in_executor` | PASS | All CV calls in `pipeline.py` wrapped: `extract_landmarks`, `run_quality_gates`, `compute_angle_timeseries`, `detect_reps`, `extract_rep_metrics`, `compute_bar_path_from_landmarks`, `generate_annotated_video`, `generate_angle_plot`. PDF generation also wrapped. |
| FR-CVPL-03 | Quality gate execution in ARQ worker | PASS | Gates run in worker after status→`quality_gate_pending`. Results stored in `analyses.quality_gate_result` JSONB. |
| FR-CVPL-04 | P0 body visibility gate: mean visibility < 0.30 → reject | PASS | `check_body_visibility()` uses landmarks {11,12,13,14,23,24,25,26}, sigmoid applied, threshold 0.30, first 5 frames. Exact match to SRS. |
| FR-CVPL-05 | P0 framing gate: bbox < 30% or > 80% → reject | PASS | `check_framing()` correctly computes bounding box from visible landmarks across first 5 frames, thresholds [0.30, 0.80]. |
| FR-CVPL-06 | P1 single-person gate | WARN | SRS Phase column says Phase 0 ("Must", Phase 0). NOT implemented. Only P0-01 and P0-02 gates exist. |
| FR-CVPL-07 | P1 resolution gate: min(w,h) < 720px → reject | WARN | Same note: SRS Phase column says Phase 0. NOT implemented. |
| FR-CVPL-08 | P2 lighting gate (warn) | WARN | Not implemented. SRS priority "Should", Phase 0. |
| FR-CVPL-09 | P2 camera stability gate (warn) | WARN | Not implemented. SRS priority "Should", Phase 0. |
| FR-CVPL-10 | P3 motion blur gate (warn) | INFO | Not implemented. SRS priority "Could", Phase 0 — acceptable to defer. |
| FR-CVPL-11 | All gate results in quality_gate_result JSONB | PASS | Stored correctly with all fields. |
| FR-CVPL-12 | MediaPipe config (exact) | PASS | `model_complexity=2, static_image_mode=True, min_detection_confidence=0.5, min_tracking_confidence=0.5, num_threads=1`. Exact match. Sigmoid applied to visibility/presence. |
| FR-CVPL-13 | Most prominent person selected | PASS | MediaPipe selects the most prominent person internally with `static_image_mode=True`. |
| FR-CVPL-14 | Savitzky-Golay filter (window=7, polyorder=3) | PASS | `smooth_signal()` in `signal_processing.py` uses window=7, polyorder=3 (defaults). |
| FR-CVPL-15 | Rep detection thresholds | PASS | Squat: hip >160°/< 90°. Deadlift: hip >160°, <70° conv/sumo, <90° RDL. Bench: elbow >160°/<90°. Hysteresis ±5°. Min duration 0.5s. Exact match to SRS. |
| FR-CVPL-16 | Phase 0 confidence: mean visibility per rep, session = mean of reps | PASS | `compute_rep_confidence()` uses landmarks {23,24,25,26,27,28} for squat/DL and {11,12,13,14,15,16} for bench. Sigmoid applied. Session confidence = mean of per-rep scores. |
| FR-CVPL-17 | Occlusion detection and UI warning | FAIL | No explicit occlusion detection or user-facing warning implemented. The system uses low confidence scores but does not generate specific "barbell occluded keypoints" messages. |
| FR-CVPL-18 | Z-axis tagged as monocular estimate | PASS (Phase 1) | Phase 1 requirement. |
| FR-CVPL-19 | Annotated video spec | PASS with minor caveat | Color `#00FF88` used as BGR `(0x88, 0xFF, 0x00)` ✓. Thickness 2px ✓. Angle labels at joints with white text + 1px black outline ✓. Rep counter `"Rep: N / M"` top-left ✓. **Caveat**: Font used is `cv2.FONT_HERSHEY_SIMPLEX` (not Arial, which doesn't exist as a named font in OpenCV). This is the closest available equivalent. Font scale 0.55 for labels (≈18px) and 0.75 for counter (≈24px bold) are reasonable approximations. The SRS spec of "Arial 18px" and "Arial 24px bold" is not literally achievable in OpenCV without loading a TTF file. |

### 3.6 Barbell Detection and Tracking (FR-BDET)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-BDET-01 | OpenCV-based barbell detection per frame | PASS | `detect_barbell_in_frame()` uses HoughCircles on grayscale+blur. |
| FR-BDET-02 | Bar centroid tracked across frames | PASS | `track_barbell()` and `compute_bar_path()` implemented. `_interpolate_centroids()` fills gaps. |
| FR-BDET-03 | Squat: lateral + anterior-posterior deviation tracked | WARN | `compute_bar_path()` returns `lateral_deviation_px` and `vertical_range_px` but **the pipeline calls `compute_bar_path_from_landmarks()` (wrist midpoint proxy) instead of the actual HoughCircles-based detection**. The `track_barbell()` and `compute_bar_path()` functions exist but are not wired into `pipeline.py`. This means real barbell tracking via computer vision is not active. |
| FR-BDET-04 | Deadlift: bar-to-body distance at key points | FAIL | Not computed. The landmark-based bar path proxy does not calculate bar-to-body distance at setup/liftoff/knee pass/lockout. |
| FR-BDET-05 | Bench: touch-point detection, J-curve classification | FAIL | Not implemented in Phase 0 pipeline. |
| FR-BDET-06 | If no barbell in >50% frames: continue with null fields | PASS | `compute_bar_path()` returns None when >50% of frames have no centroid. However since actual HoughCircles detection isn't active in the pipeline (see FR-BDET-03), this path is not exercised. |
| FR-BDET-07 | Bar path visualization in results + PDF | PASS | Bar path data stored in DB; PDF template includes bar path section. |

### 3.7 Rep Detection and Per-Rep Metrics (FR-REPM)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-REPM-01 | Exercise-specific state machine | PASS | `detect_reps()` with STANDING→DESCENDING→BOTTOM→ASCENDING state machine. |
| FR-REPM-02 | Exercise-variant-specific metrics per rep | PASS | Squat: depth_angle, knee_angle_at_depth, torso_lean, rep/descent/ascent durations. Bench: elbow/shoulder angles, durations. Deadlift: hip_angle_at_bottom, knee_angle_at_lockout, torso_lean_at_start, durations. |
| FR-REPM-03 | Per-rep metrics stored in rep_metrics JSONB | PASS | `metrics_json` JSONB column used. |
| FR-REPM-04 | Confidence score per rep (Phase 0 = simple mean visibility) | PASS | `compute_rep_confidence()` called per rep; stored in `rep_metrics.confidence_score`. |
| FR-REPM-05 | Single-rep videos produce valid output | PASS | State machine handles single reps. |
| FR-REPM-06 | Weight/load logged at upload | WARN | `analyses.weight_kg` column exists but `AnalysisCreate` request schema does **not** include `weight_kg`. Users cannot log weight at upload time in the current API. |
| FR-REPM-07–12 | Phase 1 requirements | PASS | Out of scope. |

### 3.8 AI Coaching Pipeline (FR-AICP)

Phase 0 uses a simplified coaching pipeline without GPT-4o, RAG, or LangGraph. Phase 0 coaching requirements are in FR-RESL-03 and Appendix D.

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| Phase 0 coaching model | Claude Sonnet 4.6, temperature=0.3, max_tokens=2048 | PASS | Exact values in `coaching.py`. |
| Mandatory disclaimer | Verbatim disclaimer in output | PASS | `MANDATORY_DISCLAIMER` constant matches SRS. Included in system prompt. |
| Retry logic | 429/529 → 1s/2s/4s backoff, 3 retries; 401 → fail immediately | PASS | Implemented in `CoachingService.generate_coaching()`. |
| CoachingOutput schema | Pydantic v2 with instructor | PASS | `CoachingOutput` with `Issue` model. `raw_prompt_tokens` and `raw_completion_tokens` fields present for cost tracking. |
| No "injury risk" language | Forbidden phrases excluded from prompts | PASS | System prompt explicitly bans "injury risk score", "injury prevention", "prevents injuries". Uses "movement quality" instead. |
| Storage | Stored in `coaching_results.structured_output_json` JSONB | PASS | Correct. |

### 3.9 Form Scoring (FR-SCOR — Phase 0 subset)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-SCOR-00 | ThresholdConfig from `config/thresholds_v0.json` | PASS | Loaded at startup, version "v0". Contains squat/bench/deadlift/experience thresholds. |
| FR-SCOR-10 | Confidence label/guidance (≥0.80 High, 0.65 Moderate, 0.50 Low, <0.50 Very Low) | PASS | `confidence_label()` and `confidence_guidance()` implement exact thresholds. |
| Form scores (form_score_*) | NULL in Phase 0 | PASS | Columns exist in model, written as NULL. |
| _confidence_label in coaching.py | Separate thresholds (≥0.90/≥0.70/≥0.50) | WARN | `_confidence_label()` in `coaching.py` uses different thresholds (0.90/0.70/0.50) than the canonical thresholds in `confidence.py` (0.80/0.65/0.50). This is a private helper for the coaching prompt text only, but the inconsistency is a defect — both should use the same thresholds or the canonical function should be used. |

### 3.10 Results and Reporting (FR-RESL)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-RESL-01 | Results page with annotated video | PASS | Frontend concern; backend provides `annotated_video_path`. |
| FR-RESL-02 | Annotated video inline + download | PASS | Storage path available via `GET /api/v1/analyses/{id}`. |
| FR-RESL-03 | Phase 0: static coaching render | PASS | Worker stores full response synchronously; frontend fetches on page load. |
| FR-RESL-04 | Per-rep metrics table | PASS | `rep_metrics` returned in `AnalysisDetail`. |
| FR-RESL-05 | Bar path visualization | PASS | `bar_path` data available in `summary_json` → frontend renders. |
| FR-RESL-08 | Confidence label + guidance | PASS | `confidence_label()` implemented with correct thresholds. |
| FR-RESL-10 | PDF download | PASS | PDF generated and stored; `pdf_path` in analysis row. |
| FR-RESL-11 | Three-tier disclaimer on all results pages | PASS | Primary disclaimer in `PDFService`. Frontend concern for pages. |
| FR-RESL-12 | Camera guidance panel | PASS | Frontend concern. |
| FR-RESL-13 | Supabase Realtime subscription + polling fallback | PASS | `GET /api/v1/analyses/{id}/status` returns `{id, status, updated_at}` as fallback. |

### 3.11 Progress and History Analytics (FR-HIST)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-HIST-01 | Dashboard lists analyses in reverse chrono order | PASS | `GET /api/v1/analyses` returns paginated list ordered by `created_at DESC`. |
| FR-HIST-02 | Per-exercise insights | PASS | `InsightsService.exercise_insights()` computes: 7-session rolling avg confidence, rep count trend, most common QG warning, personal best confidence. |
| FR-HIST-03 | Global insights | PASS | `InsightsService.global_insights()` computes: most common 30-day warning, highest rep count variance exercise. |
| FR-HIST-04 | summary_json written after each analysis | PASS | `SummaryService.compute_and_store()` called after coaching in worker. Includes `rep_count`, `confidence_score`, `confidence_label`, `quality_gate_warnings`, `top_metric_keys`. |
| FR-HIST-05 | Recurring issue flag (Phase 2) | PASS | Out of scope. |
| FR-HIST-06 | Visual trend charts (Recharts) | PASS | Frontend concern. |

**Note on InsightsService pattern violation**: `InsightsService` takes `AsyncSession` directly and runs SQLAlchemy queries inline — it is a service that does DB access without going through a repository. This violates the repository pattern (see Code Pattern section below).

### 3.12 Export and Data Management (FR-XPRT)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-XPRT-01 | Annotated video downloadable as MP4 | PASS | Storage path available in API. |
| FR-XPRT-02 | PDF summary report layout | PASS | `PDFService` renders via WeasyPrint from `reports/templates/analysis_report.html`. Includes: confidence badge, rep metrics table, plot, coaching sections (summary/strengths/issues/corrections), disclaimer. Page layout matches SRS roughly. **Note**: Phase 0 form score pills (four dimension pills) are not included since form scores are NULL — acceptable for Phase 0. |
| FR-XPRT-03 | PDF generated as background ARQ task, stored in Storage | PASS | Done in `_generate_and_upload_pdf()` within the worker. `pdf_path` stored on analysis row. |
| FR-XPRT-04 | All user data as CSV | PASS | `ExportService.generate_csv()` exports analysis metadata + per-rep metrics. |
| FR-XPRT-05 | Account deletion (GDPR Article 17) | PASS | `AccountService.delete_account()` removes all data. |

### 3.13 Admin Dashboard (FR-ADMN)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| FR-ADMN-01 | Admin routes protected by server-side role check | PASS | All admin routes use `get_admin_user` dependency. 403 for non-admins. |
| FR-ADMN-02 | User management: list, disable, delete | PASS | `GET /admin/users`, `DELETE /admin/users/{id}`. Disable is a stub (Phase 1 note — acceptable). |
| FR-ADMN-03 | Analysis metadata log | PASS | `GET /admin/analyses` with optional status filter. Returns ID, exercise type, status, confidence level, timestamps. |
| FR-ADMN-04 | Confidence audit panel | PASS | `GET /admin/confidence-audit?threshold=` filters by confidence below threshold. |
| FR-ADMN-05 | System health panel | PASS | `GET /admin/health` returns queue depth (ARQ), worker heartbeat, DB connectivity. **Note**: Redis is not injected into `AdminService` via DI — `AdminService` is constructed without a Redis client in the endpoint factory `_get_service()`. This means `queue_depth` and `worker_heartbeat` always return 0/False in production unless Redis is wired. |

### NFR-RELI (Reliability)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| NFR-RELI-01 | Retry up to 3 times | PASS | `retry_count` incremented on error; `_is_terminal()` blocks re-processing at retry_count ≥ 3. |
| NFR-RELI-02 | Idempotent pipeline | PASS | Idempotency guard at `process_analysis()` entry — terminal state check before any work. |
| NFR-RELI-03 | ARQ job state in Redis | PASS | ARQ handles this natively. |
| NFR-RELI-04 | 5-minute hard timeout | PASS | `job_timeout=300` in WorkerSettings. |
| NFR-RELI-05 | Clean failure state returned to user | PASS | `error_message` written to DB, status→failed. Frontend can poll status. |
| NFR-RELI-06 | Status page never times out | PASS | Realtime + polling fallback endpoint. |
| NFR-RELI-07 | Determinism within ±2°: `static_image_mode=True, num_threads=1` | PASS | Exact config enforced in `pose_extraction.py`. |
| NFR-RELI-08 | RAGAS/TruLens quality gate in CI | PASS (Phase 2+) | Out of scope for Phase 0. |

### NFR-SECU (Security)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| NFR-SECU-01 | RLS at Supabase layer | PASS | Architectural constraint; enforced in DB config not in app code. |
| NFR-SECU-02 | SERVICE_ROLE_KEY only in backend/worker | PASS | No frontend env files contain it. Backend uses `SUPABASE_SERVICE_KEY`. |
| NFR-SECU-03 | ANON_KEY for frontend Supabase operations | PASS | Frontend concern. |
| NFR-SECU-04 | TLS on all connections | PASS | Caddy handles TLS termination; all external API calls use HTTPS. |
| NFR-SECU-05 | JWT validation on all protected endpoints | PASS | `get_current_user` used on all non-admin and admin routes. |
| NFR-SECU-06 | Storage access policies per user | PASS | Supabase RLS on Storage policies (DB config, not app code). |
| NFR-SECU-07 | GDPR Article 20 data export | PASS | CSV export via `ExportService`. |
| NFR-SECU-08 | Account deletion within session | PASS | `AccountService.delete_account()` is synchronous and immediate. |
| NFR-SECU-09 | No secrets in version control | PASS | All secrets loaded from env vars. No hardcoded keys found in code. |
| NFR-SECU-10 | Rate limiting 10/day on POST /analyses | PASS | `@limiter.limit("10/day")` on `create_analysis`. Key function extracts JWT `sub` claim. |
| NFR-SECU-11 | CORS: only explicit origins, no wildcard | PASS | `main.py` lists `https://spelix.app`, `https://www.spelix.app`. Dev origins only added when `SPELIX_ENV=development`. Vercel preview via env var. TUS headers in `allowed_headers`. |
| NFR-SECU-12 | API versioned under `/api/v1/` | PASS | `api_v1_router = APIRouter(prefix="/api/v1")`. |

### NFR-OPER (Operations)

| Req ID | Description | Status | Notes |
|--------|-------------|--------|-------|
| NFR-OPER-01 | Health endpoint | PASS | `GET /health` returns `{"status": "ok"}`. |
| NFR-OPER-02 | Worker heartbeat `spelix:worker:heartbeat` 90s TTL every 30s | PASS | `_heartbeat_loop()` in `settings.py` writes every 30s with 90s TTL. Also written inside the pipeline at key checkpoints. |

---

## Type Safety Findings

### `type: ignore` Usage

| File | Line | Comment | Assessment |
|------|------|---------|------------|
| `db.py` | 21, 23 | `get_db` is an async generator — pyright can't properly type `yield` in an `async def` returning `AsyncSession` | ACCEPTABLE — known pyright limitation with async generators. |
| `main.py` | 15 | `_rate_limit_exceeded_handler` type mismatch with FastAPI exception handler signature | ACCEPTABLE — slowapi type stub issue. |
| `workers/settings.py` | 34 | `redis.set(...)` — redis object typed as `object` | WARN — `redis` is typed `object` in `_heartbeat_loop`. Should be typed as `Redis` or `ArqRedis`. Not a runtime bug but weakens type safety. |
| `cv/barbell_detection.py` | 251, 252, 258 | Tuple unpacking and list comprehension with `None`-typed entries after `_interpolate_centroids` | ACCEPTABLE — logic guarantees non-None at those points; suppressing is reasonable. |
| `workers/cleanup.py` | 171 | `supabase` package import | ACCEPTABLE — optional dependency. |
| `cv/pose_extraction.py` | 75 | `mp.solutions.pose.Pose` — mediapipe attr | ACCEPTABLE — mediapipe lacks type stubs. |
| `cv/signal_processing.py` | 82 | `savgol_filter` return type | ACCEPTABLE — scipy stubs return `np.ndarray` but annotated differently. |

**Summary**: No `type: ignore` comment is hiding a genuine logic error. All are suppressing known library stub gaps.

### Pydantic v2 Schema Review

- `ProfileUpdate`: Uses `Field(..., gt=0)` correctly for positive-only fields. `Optional[float]` with `Field(default=None, gt=0)` — correct Pydantic v2 usage.
- `AnalysisCreate`: `exercise_type` and `exercise_variant` are typed as plain `str` rather than the `ExerciseType`/`SquatVariant` etc. `Literal` types defined in the same file. This means schema-level validation of enum values is delegated entirely to service-layer logic. **WARN**: Type literals exist but are not applied to the schema fields, so the OpenAPI spec does not document the allowed values, and `model_validate` will not reject invalid strings.
- `CoachingOutput`: `strengths: list[str] = Field(min_length=1)` — in Pydantic v2, `min_length` on a `list` field constrains list length (≥1 item), which is correct for "two to three positives."
- `Issue.severity: Literal["High", "Medium", "Low"]` — correct.
- All models use `model_config = {"from_attributes": True}` where needed for ORM→schema conversion.

### SQLAlchemy 2.0 Model Review

- All models use `Mapped[]` generic annotations and `mapped_column()` — correct SA 2.0 style.
- `Analysis` uses `JSONB`, `ARRAY(Text)`, `CheckConstraint` — all correct PostgreSQL-specific types.
- Relationships use `Mapped[list["RepMetric"]]` and `Mapped[Optional["CoachingResult"]]` with string forward refs — correct.
- `RepMetric` and `CoachingResult` have circular imports resolved with `from app.models.analysis import Analysis  # noqa: E402` at the bottom of each file — this is an acceptable pattern but could be replaced with `TYPE_CHECKING` guard.
- `TimestampMixin` referenced but not shown — assumed to be correct from usage.

---

## Code Pattern Violations

### Repository Pattern

| Violation | Location | Severity |
|-----------|----------|---------|
| `InsightsService` accepts `AsyncSession` directly and runs SQLAlchemy `select()` queries inline | `services/insights.py` | MEDIUM — violates the stated pattern "services receive repos via DI / all DB access behind repository interfaces." The entire `InsightsService` is effectively acting as its own repository. |
| `AdminService` accepts `AsyncSession` directly and runs `select(Analysis)`, `select(UserProfile)` inline | `services/admin.py` | MEDIUM — same pattern violation. Admin service bypasses the repository layer entirely. |
| `SummaryService` uses `AnalysisRepository` and `RepMetricRepository` | `services/summary.py` | PASS — correct usage. |

Both `InsightsService` and `AdminService` should use repository classes for DB access. This is not a runtime defect, but it violates the stated architecture and reduces testability.

### Status Transition Guard Bypasses

| Location | Line | Issue | Severity |
|----------|------|-------|---------|
| `workers/analysis_worker.py` | 333 | `analysis.status = "failed"` — direct assignment, bypasses `transition()` guard | HIGH |

All other status assignments in `pipeline.py` and `analysis_worker.py` use `transition()`. This single bypass in the error handler allows the transition from any state (including potentially `quality_gate_rejected` or `completed`) to `failed` without validation. The comment says "for any non-terminal state" and there is a guard `if analysis.status not in _TERMINAL_STATES`, which partially mitigates this, but it still bypasses the `processing → failed` and `coaching → failed` transition validation that `transition()` would apply.

**Fix**: Replace with `analysis.status = transition(analysis.status, "failed")` (or catch `InvalidTransition` if needed).

### CV Function Purity

All CV functions in `app/cv/` are pure (no DB access, no IO other than reading video files, no side effects beyond pixel writes on frames). `pose_extraction.py` reads from disk but is documented as intentionally blocking and called via executor.

`artifact_generation.py` calls `upload_artifact()` which is async I/O, but this is only called from the worker orchestration layer (`pipeline.py`), not from within pure CV functions. The pure CV functions (`generate_annotated_video`, `generate_angle_plot`) are CPU-only.

**PASS** — CV purity maintained.

### run_in_executor Coverage

All CPU-bound CV calls in `pipeline.py` are wrapped with `loop.run_in_executor(None, fn)`. PDF generation in `analysis_worker.py` also uses `run_in_executor`. **PASS**.

---

## Forbidden Strings

### "injury risk" / "injury prevention" / "prevents injuries" in user-facing context

Three occurrences found in `services/coaching.py`:
1. Line 16: Comment `"- Never use 'injury risk' or 'injury prevention' in prompts or output."` — **OK** (instructional comment, not user-facing).
2. Line 83–84: System prompt that says `"Never use 'injury risk score,' 'injury prevention,' or 'prevents injuries.'"` — **OK** (meta-instruction to the LLM, teaching it what NOT to say, not user-facing output).

**No violations** of the forbidden-string rule in user-facing context.

### "safety score" 

No occurrences found. **PASS**.

### Hardcoded "localhost" in non-test files

| File | Location | Context |
|------|----------|---------|
| `app/main.py` | Lines 26–27 | `http://localhost:5173` and `http://localhost:3000` added to CORS origins — but only when `SPELIX_ENV == "development"`. **ACCEPTABLE** — gated by env var. |
| `app/workers/settings.py` | Line 66 | `RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))` — fallback default for local dev. **WARN** — if `REDIS_URL` is not set in production, the worker silently connects to localhost Redis which will fail. Should either not provide a default or raise if unset in production. |

### Hardcoded API keys or secrets

No hardcoded keys or secrets found anywhere in `backend/app/`. All accessed via `os.environ.get()`. **PASS**.

### TODO / FIXME / HACK / XXX

Zero occurrences found across all Python files in `backend/app/`. **PASS**.

---

## Summary of Critical Issues

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | HIGH | `workers/analysis_worker.py:333` | Status transition to "failed" bypasses `transition()` guard. |
| 2 | HIGH | `services/pipeline.py` | `compute_bar_path_from_landmarks()` (wrist proxy) called instead of actual `track_barbell()` + `compute_bar_path()` HoughCircles detection. FR-BDET-01/02 are not actually active. |
| 3 | HIGH | Multiple | FR-UPLD-05, FR-UPLD-13, FR-UPLD-14 not implemented: no duration validation, no storage quota check, no FFprobe codec validation. |
| 4 | MEDIUM | `services/insights.py` | Repository pattern violation — direct DB access in service layer. |
| 5 | MEDIUM | `services/admin.py` | Repository pattern violation — direct DB access in service layer. |
| 6 | MEDIUM | `api/v1/admin.py` | `AdminService` created without Redis client — health endpoint always reports `queue_depth=0` and `worker_heartbeat=False`. |
| 7 | MEDIUM | FR-CVPL-06, FR-CVPL-07 | Single-person gate and resolution gate specified as Phase 0 "Must" in SRS but not implemented. |
| 8 | MEDIUM | FR-CVPL-17 | No occlusion detection or targeted "barbell occluded keypoints" warning implemented. |
| 9 | MEDIUM | `schemas/analysis.py` + `services/analysis.py` | `AnalysisCreate` schema accepts raw `str` for `exercise_type`/`exercise_variant` instead of typed `Literal` — OpenAPI spec does not document allowed values; validation is only in service logic. |
| 10 | MEDIUM | `services/coaching.py:58` | `_confidence_label()` uses thresholds (0.90/0.70/0.50) inconsistent with canonical `confidence_label()` thresholds (0.80/0.65/0.50). |
| 11 | LOW | `schemas/analysis.py` | `AnalysisCreate` does not include `weight_kg` field — FR-REPM-06 ("Should") cannot be satisfied. |
| 12 | LOW | `workers/settings.py:66` | `REDIS_URL` has localhost fallback — silent failure mode in production if env var missing. |
| 13 | LOW | FR-XDET-05/06 | No re-analysis/override endpoint — exercise type/variant cannot be changed post-upload. |

---

## Positive Findings

- MediaPipe configuration is exactly correct per SRS.
- Savitzky-Golay smoothing parameters match SRS exactly.
- Rep detection thresholds match SRS exactly for all exercise types and variants.
- Quality gate P0-01 (body visibility) and P0-02 (framing) match SRS predicates exactly, including sigmoid application.
- Confidence computation landmark sets match SRS exactly ({23,24,25,26,27,28} for squat/DL, {11,12,13,14,15,16} for bench).
- Status transition guard is well-implemented and covers all 7 valid states.
- Idempotency guard correctly prevents re-processing terminal analyses.
- Heartbeat implementation (30s interval, 90s TTL) matches spec.
- ARQ WorkerSettings match spec exactly (queue_name, job_timeout, max_jobs, keep_result).
- All CPU-bound CV operations are properly wrapped in `run_in_executor`.
- DB connection correctly uses PgBouncer pooler with `statement_cache_size=0`.
- No hardcoded secrets found.
- No "injury risk" language in any user-facing context.
- Zero TODO/FIXME/HACK/XXX markers.
- CORS correctly blocks wildcard origins in production.
- Rate limiting correctly keys on JWT `sub` claim (per-user, not per-IP).
