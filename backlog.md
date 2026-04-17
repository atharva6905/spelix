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
| D-029 | SaMD/FTC: rename `injury_advice_accurate` to `movement_advice_accurate` across DB column, SQLAlchemy model, Pydantic schema, frontend TypeScript interfaces (`AnnotationCreate`/`AnnotationResponse` in `frontend/src/api/expert.ts`), and DOM `name` attribute in `ExpertAnalysisDetailPage.tsx:460`. Surfaced by expert PDF upload security review (C-2) as pre-existing violation — the user-visible label ("Movement Quality Advice Accurate?") is already correct, only the wire/DOM name leaks the prohibited term. Needs a migration to rename the column. | M | — | — | pending |
| D-030 | Orphan `rag_documents` rows with `review_status='uploading'` accumulate if the expert abandons a PDF upload (browser crash, nav-away, failed PUT). No TTL, no scheduled cleanup. Add a nightly ARQ cron (similar to `cleanup_expired_artifacts`) that deletes rows + storage objects older than 2 hours (1-hour signed URL TTL + grace). Surfaced by expert PDF upload security review (M-4). | S | — | FR-EXPV-02 | pending |
| D-031 | Admin `GET /rag/documents` accepts a free-text `review_status` query parameter — replace with `Literal` constraint or filter out `uploading` rows by default. Surfaced by expert PDF upload security review (M-2). | S | — | FR-RAGK-08 | pending |
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
| P3-006 | Coach Brain expert review queue for distillation candidates — single-screen review cards with eval scorecard, CoVe result, approve/reject/edit actions. Compensation entries flagged for biomechanics-qualified review. | L | P3-004 | FR-ADMN-12, FR-BRAIN-07 | pending |
| P3-007 | "How AI Reasoned" sidebar on results page — readable LangGraph agent trace rendered from LangSmith data | M | P3-003 | FR-RESL-07 | pending |

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
| L2-LANDING-V2-04 | Admin beta-request approval UI + transactional-email invite flow — `/admin` card listing pending requests with approve/reject; single-use invite token → `/signup?invite=TOKEN` | M | L2-LANDING-02 | ADR-050 | pending |
| L2-LANDING-V2-05 | Beta-terms markdown file — `public/beta-terms.md` polish and legal review (current draft is landing-page-plan §10 verbatim, two paragraphs, GDPR-aligned but not counsel-reviewed) | S | — | — | pending |

