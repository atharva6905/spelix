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

## Phase 1 — Known Deferred Items (non-blocking)

These are tracked as Phase 2 tech-debt items, not blockers.

| ID | Title | Rationale |
|----|-------|-----------|
| D-001 | Double LLM call in `generate_coaching_streaming` — stream then re-validate with second instructor call. Doubles per-analysis token cost. Phase 2 will replace with instructor native streaming structured extraction. | Found by transition-gate auditor; Phase 1 correctness OK, cost optimization only. |
| D-002 | Dead code — legacy `compute_rep_confidence` in `backend/app/cv/confidence.py` (no callers). Safe to remove in Phase 2 cleanup pass. | Superseded by `compute_confidence_result` Tier 1-5 pipeline. |
| D-003 | ADR needed: document "stream-then-reparse" coaching pattern as Phase 1 tech debt and Phase 2 migration plan. | No ADR exists yet documenting the deviation from SRS "streams initial LLM response directly" phrasing. |

---

## Phase 2 — Planning (Not Started)

Generated directly from SRS Phase 2 MUST filter. Activate `spelix-rag-engineer` and
`spelix-corpus-curator` at Phase 2 kickoff.

### Infrastructure & Migrations

| ID | Title | Size | Deps | SRS IDs |
|----|-------|------|------|---------|
| P2-001 | Migration 004 — rag_documents + expert_annotations tables | M | — | FR-AICP-11 |
| P2-002 | Qdrant Cloud cluster provisioning + collection schema | M | — | FR-AICP-09 |
| P2-003 | Cohere API key env setup + embed-v4 client wrapper | S | — | FR-AICP-09 |

### RAG Corpus Ingestion

| ID | Title | Size | Deps | SRS IDs |
|----|-------|------|------|---------|
| P2-004 | Document ingestion pipeline (chunk → embed → Qdrant upsert) | L | P2-002, P2-003 | FR-AICP-09 |
| P2-005 | Recursive chunking at 500 tokens with 50-token overlap | M | P2-004 | FR-AICP-09 |
| P2-006 | Metadata-as-payload pattern (title, authors, year, DOI, quality_tier) | S | P2-004 | FR-AICP-09 |
| P2-007 | Corpus curation — seed research papers (Phase 2 initial set) | M | P2-004 | FR-AICP-09 |

### Hybrid Retrieval

| ID | Title | Size | Deps | SRS IDs |
|----|-------|------|------|---------|
| P2-008 | Cohere dense embedding retrieval | M | P2-004 | FR-AICP-09 |
| P2-009 | BM25 sparse retrieval over Qdrant payload | M | P2-004 | FR-AICP-09 |
| P2-010 | Cohere Rerank 3.5 integration | M | P2-008, P2-009 | FR-AICP-09 |
| P2-011 | Exercise-type filter at query time | S | P2-010 | FR-AICP-12 |
| P2-012 | Min 3 docs per issue before generation guard | S | P2-010 | FR-AICP-09 |

### Four-Stage Prompt Architecture

| ID | Title | Size | Deps | SRS IDs |
|----|-------|------|------|---------|
| P2-013 | Stage 1 — Cite-then-generate (retrieval before generation) | L | P2-010 | FR-AICP-08 |
| P2-014 | Stage 2 — Structured generation (temperature split factual/motivational) | M | P2-013 | FR-AICP-08 |
| P2-015 | Stage 3 — CoVe verification loop (claims → questions → revise) | XL | P2-014 | FR-AICP-08 |
| P2-016 | Stage 4 — RAGAS faithfulness + TruLens groundedness gate | L | P2-015 | FR-AICP-08 |

### Citation & Safety

| ID | Title | Size | Deps | SRS IDs |
|----|-------|------|------|---------|
| P2-017 | ValidateOutputTool — block uncited claims | M | P2-013 | FR-AICP-10 |
| P2-018 | Mandatory safety hedging for medical clearance category | S | P2-014 | FR-AICP-14 |
| P2-019 | Error handling — Qdrant unavailable fallback to ungrounded | M | P2-004 | FR-AICP-15 |
| P2-020 | Error handling — Cohere rate limit + OpenAI embed fallback | M | P2-003 | FR-AICP-16 |

### Frontend — Citations + Follow-Up Chat

| ID | Title | Size | Deps | SRS IDs |
|----|-------|------|------|---------|
| P2-021 | Citation tooltips on coaching claims (hover → source) | M | P2-013 | FR-RESL-06 |
| P2-022 | Follow-up chat panel below coaching | L | P2-013 | FR-RESL-09, FR-AICP-17 |

### Phase 2 Cleanup (from Phase 1 deferred)

| ID | Title | Size | Deps |
|----|-------|------|------|
| P2-023 | Replace stream-then-reparse with instructor native streaming | M | — |
| P2-024 | Remove dead compute_rep_confidence function | S | — |
| P2-025 | Write ADR for Phase 1 coaching pattern deviation | S | — |

### Phase 2 Cleanup (from Session 13 production hardening)

| ID | Title | Size | Deps | Notes |
|----|-------|------|------|-------|
| P2-026 | Drop the doubled `videos/videos/` storage path prefix | S | — | `get_storage_path` returns `f"videos/{id}/{filename}"` and the bucket is also called `videos`, so signed URLs end up at `.../object/upload/sign/videos/videos/{id}/...`. Internally consistent (read + write use the same path), so NOT a functional bug — just an ugly leftover from before the bucket name was decided. Fix is one line in `storage.py` + a one-shot DB UPDATE / Storage MOVE to migrate any existing rows. Defer until prod has data we'd lose if migrated wrong. |
| P2-027 | Replace `e2e/fixtures/squat-high-bar.mp4` with a real 720p side-view clip | S | — | Current fixture is 360p with body filling 8% of frame. The quality gate correctly rejects on `resolution` (need 720p) and `framing` (need ≥30%). Need a real 720p+ side-view squat clip where body fills ≥30% of frame so the **success path** (`processing → coaching → completed → results page → PDF`) can be verified end-to-end. Phone-recorded 10s clip is fine. |
| P2-028 | Backend gotcha doc: "tests-mock-everything" anti-pattern with concrete examples | S | — | Add a dedicated section to `backend/CLAUDE.md` documenting the eight regression test patterns added in session 13 (`TestMakeStorageServiceFactory`, `TestGetDbCommit`, `TestMakeArqPoolFactory`, `TestGetServicePassesArqPool`, `TestThresholdConfigPathResolution`, `TestModelPathResolution`, `test_video_path_contains_real_uuid_not_string_none`, `test_error_handler_skips_transition_when_already_failed`) as canonical examples of "exercise the real factory with the third-party patched at its source". Reference ADR-032. |
| P2-029 | CI factory-coverage smoke test | M | P2-028 | Add a CI step (or pytest marker) that asserts every factory function in `app/api/v1/*.py`, `app/services/*.py`, `app/workers/*.py` has at least ONE test that exercises the real factory path (not just the consumer). Linter or grep-based heuristic; doesn't need to be exhaustive. The goal is to make it impossible to add a new singleton/factory/cached-client without a regression test. |
| P2-030 | Verify untested production subsystems via E2E once happy-path lands | S | P2-027 | After P2-027 lands a fixture that passes the quality gate, run the full E2E and surface any further dormant config bugs in: Anthropic coaching call (`ANTHROPIC_API_KEY`), OpenAI keyframe analysis (`OPENAI_API_KEY`, best-effort), WeasyPrint PDF generation (system fonts), Realtime status subscriptions, artifact upload to Storage. Each will surface as `error_message` on the row OR via the global exception handler from PR #4 if it fails. Probably zero changes needed but never been verified live. |
| P2-031 | Add post-deploy smoke check to CI deploy workflow | S | — | Bake into the `Deploy to Production` job in `.github/workflows/ci.yml`: after `docker compose up -d --build` and the health check, run a one-shot Python script inside the backend container that constructs the storage factory, the arq pool, and the threshold config — exercising the real production env vars. Fail the deploy if any of them fail. Would have caught B-138/139/141/142/146a at deploy time instead of letting the user discover them via Playwright E2E. |
| P2-032 | Tighten `AnalysisService.__init__` arq_pool typing | S | P2-031 | Currently `arq_pool: Any \| None = None` — defaulting to None was the dead-code parameter that hid Phase 0 B-145 for months. Tighten to `arq_pool: ArqRedis` (no default) once we're confident every call site passes a real pool. Existing test fixtures will need to construct a fake pool, but that's a one-time update and prevents the silent no-op forever. |

