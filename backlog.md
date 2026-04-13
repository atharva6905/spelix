# backlog.md — Phase 0, Phase 1 Build, Phase 2 Prep

Phase 0 core build complete (B-001 through B-042). Audit on 2026-04-09 found 67 issues.
Full audit: `docs/phase0-audit.md`. Detailed reports: `docs/audit-{backend,frontend,tests,infra}.md`.

**Phase 1 code-complete 2026-04-10** — all MUST requirements implemented; tests green; transition gate passed.
**Phase 1 production-functional 2026-04-11** — twelve dormant Phase 0 bugs surfaced and fixed across PRs #3–#14 in session 13.
The full upload → worker pipeline → quality gates path now runs end-to-end on `spelix.app`. See B-138–B-149 below
and ADR-027 through ADR-032 in `decisions.md` for the full breakdown.

Backend: **960** tests passing (was 895 at code-complete), 91% coverage. Frontend: **178** tests passing (was 177).
Migration 003 applied to Supabase. Ready for Phase 2 (RAG).

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

