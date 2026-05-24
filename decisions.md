# decisions.md — Architecture Decision Records

## ADR-001: Greenfield Build
**Context**: Existing WorkoutFormAnalyzer codebase uses RQ, sync Postgres, different schema.
**Decision**: Complete greenfield rebuild. No migration, no backward compat, no copy-paste.
**Consequences**: Alembic starts at 001. Old repo is reference only. Clean architecture from day 1.

## ADR-002: ARQ over RQ
**Context**: RQ is synchronous, has Windows multiprocessing issues. ARQ is async-native.
**Decision**: Use ARQ with `max_jobs=1, job_timeout=300, keep_result=0, queue_name="arq:queue"`.
**Consequences**: All CPU-bound work via `run_in_executor()`. Heartbeat via Redis key with 90s TTL. Simpler worker model.

## ADR-003: Supabase FK — No DDL Constraint
**Context**: Supabase manages `auth.users` in a separate schema. DDL FKs to `auth.users` are rejected or unreliable.
**Decision**: `user_id UUID NOT NULL` with NO FOREIGN KEY constraint. Enforce via RLS policies only.
**Consequences**: Orphan rows possible if Supabase auth user deleted outside our flow. Account deletion endpoint handles cascade explicitly.

## ADR-004: 7-Day Artifact Retention
**Context**: At ~108 analyses/month, 30-day retention = ~1.78 GB active storage (exceeds Supabase free 1 GB). 7-day retention = ~413 MB.
**Decision**: Retain annotated MP4, plot PNG, PDF for 7 days. Nightly ARQ cron deletes expired. Analyses rows kept permanently.
**Consequences**: Users see 7-day download banner. Must download PDF/video before expiry. History and metrics preserved forever.

## ADR-005: Phase 0 Coaching — Sync, Not SSE
**Context**: Phase 1 adds streaming SSE. Phase 0 is simpler — full response stored and fetched.
**Decision**: Worker calls Claude Sonnet synchronously, stores full response in `coaching_results.structured_output_json`. Frontend polls via REST.
**Consequences**: Results page component must support both static (Phase 0) and streaming (Phase 1) without rewrite. No SSE infrastructure needed yet.

## ADR-006: Python 3.12 Mandatory
**Context**: MediaPipe 0.10.x has no Python 3.13 wheels (GitHub #6025, #6081, #6159).
**Decision**: All environments use Python 3.12. Do NOT upgrade until MediaPipe publishes 3.13 wheels.
**Consequences**: Pin in `.python-version`, Dockerfiles, CI. Block any PR that bumps Python.

## ADR-007: Node.js 22 LTS Mandatory
**Context**: Vite 8 requires Node.js 20.19+ or 22.12+.
**Decision**: Use Node.js 22 LTS for maximum support window.
**Consequences**: Pin in `.nvmrc`, Docker frontend image (`node:22-alpine`).

## ADR-008: JSONB Over JSON
**Context**: JSONB supports indexing and efficient querying; JSON does not.
**Decision**: All schema columns that store JSON use JSONB type.
**Consequences**: Slightly more storage, much better query performance.

## ADR-009: "Movement Quality" Not "Safety Score"
**Context**: FDA SaMD classification, FTC substantiation, BIPA exposure triggered by "injury risk" language.
**Decision**: Internal field `form_score_safety`, user-facing label "Movement Quality". Never use "injury risk" or "injury prevention" in any user-facing string.
**Consequences**: All UI, coaching prompts, PDF reports, error messages must use wellness/optimization framing.

## ADR-010: Quality Gates in Worker, Not FastAPI
**Context**: Video frame decoding (OpenCV/FFmpeg) is CPU-intensive. Running in FastAPI request handler would block the 2GB web server.
**Decision**: Upload endpoint returns immediately after enqueueing. Worker transitions to `quality_gate_pending`, runs gates, then `quality_gate_rejected` or `processing`.
**Consequences**: User sees "Preparing to analyse…" status. Rejection is async, not synchronous.

## ADR-011: Status Column — VARCHAR(30) with CHECK
**Context**: Need to enforce valid status values at DB level.
**Decision**: `status VARCHAR(30) CHECK (status IN ('queued','quality_gate_pending','quality_gate_rejected','processing','coaching','completed','failed'))`.
**Consequences**: Invalid status writes fail at DB level. Adding new statuses requires migration.

## ADR-012: Phase 0 Confidence — Simple Mean
**Context**: Five-tier composite confidence is Phase 1. Phase 0 needs something simple.
**Decision**: Per-rep confidence = mean(visibility) of exercise-relevant landmarks. Session = mean of per-rep. Labels: ≥0.80 High, 0.65–0.79 Moderate, 0.50–0.64 Low, <0.50 Very Low.
**Consequences**: Phase 1 replaces this entirely with Tier 5 algorithm. Column semantics change between phases.

## ADR-013: opencv-python-headless in Docker
**Context**: Full `opencv-python` requires GUI libraries (`libgl1`) which bloat Docker images.
**Decision**: Use `opencv-python-headless`. Note: `libgl1` (not `libgl1-mesa-glx`) on Debian trixie+.
**Consequences**: No GUI functions available (not needed for server-side processing).

## ADR-014: GSD Framework Coexistence
**Context**: Local PC has GSD hooks (session state, context monitor, prompt guard, read guard, workflow guard, phase boundary, validate commit) active globally.
**Decision**: Keep both GSD hooks and project-level hooks. They are additive. If GSD guards block a legitimate write, document and override per-case.
**Consequences**: May see extra hook output on writes. Context monitor may suggest compaction. Follow its guidance.

---
<!-- New decisions made during implementation go below this line -->

## ADR-015: Tier 5 Per-Rep Confidence — 10th Percentile, Not Mean
**Context**: Phase 0 used `mean(visibility)` per rep (FR-CVPL-16), but mean is optimistic — a single high-visibility frame hides dozens of low-visibility frames. Phase 1 needs a pessimistic bound that flags reps with any bad frames.
**Decision**: Tier 5 per-rep confidence = `percentile(phase_adjusted_frame_conf, 10)`. Pessimistic lower bound, not arithmetic mean. Tier 1 = sigmoid(visibility) × sigmoid(presence) per landmark. Tier 2 = min of 3 landmark confidences per angle. Tier 3 = exercise-weighted mean per frame. Tier 4 = frame × phase multiplier (1.0 static peaks, 0.85–0.95 transitions, 0.70–0.80 known-occluded phases).
**Consequences**: Reps with even brief occlusion events are flagged Low/Very Low, which matches user intuition. Column semantics change between Phase 0 and Phase 1 — `rep_metrics.confidence_score` means "mean visibility" for Phase 0 analyses and "10th percentile phase-adjusted" for Phase 1 analyses. Migration note: existing Phase 0 data is retained as-is, not recomputed.

## ADR-016: ScoreComponent Protocol for Extensibility
**Context**: FR-SCOR-06 mandates that adding a fifth dimension requires no changes to DB writes, results page, PDF, or eval dashboard. Hardcoded 4-dimension logic would violate this.
**Decision**: All scorers implement `ScoreComponent` Protocol with `name`, `compute(metrics, thresholds) -> ScoreResult`. Overall composite is computed as `sum(weight_i × score_i)` over all registered components. Adding a fifth dimension means implementing one new class and registering it.
**Consequences**: DB columns `form_score_safety/technique/path_balance/control/overall` are hardcoded for Phase 1, but the composite formula is extensible. Phase 5+ dimensions would need a schema change but no logic change.

## ADR-017: GPT-4o Vision Fallback Threshold = 0.7
**Context**: FR-XDET-04 requires GPT-4o vision fallback when heuristic confidence is "low", but the threshold is not spelled out in the SRS.
**Decision**: `_FALLBACK_CONFIDENCE_THRESHOLD = 0.7` in `backend/app/services/pipeline.py`. When heuristic auto-detect confidence < 0.7, pipeline extracts 3 evenly-spaced frames from the video as base64 JPEG and calls `KeyframeAnalysisService.classify_exercise()`. On any GPT-4o failure, gracefully falls back to the heuristic result — never blocks the pipeline.
**Consequences**: The threshold is a named constant, easy to tune if the heuristic improves. Fallback is best-effort — missing OPENAI_API_KEY or rate limits degrade to heuristic without analysis failure.

## ADR-018: ThresholdConfig — Versioned JSON in Repo, PR Review as Approval
**Context**: FR-SCOR-11 requires threshold values to be expert-reviewable and auditable without a custom admin UI. Expert reviewers propose changes via PR.
**Decision**: Threshold configs live at `config/thresholds_v{N}.json` with a top-level `version` field read at application startup via `ThresholdConfig`. Each threshold entry carries `value`, `unit`, `provenance_citation`, `last_modified_by`. PR review IS the approval flow — no admin UI. Analyses freeze `threshold_version` at analysis time so later threshold changes don't retroactively alter scored analyses.
**Consequences**: Zero custom admin tooling for Phase 1. Git history is the change log. Re-scoring old analyses against new thresholds requires a migration script, not a live update. `analyses.threshold_version` column was added in Phase 1 pipeline wiring.

## ADR-019: SSE Coaching — Redis Pub/Sub Between Worker and FastAPI
**Context**: FR-AICP-07 mandates streaming coaching output via SSE. The worker runs coaching generation (Claude Sonnet streaming), but the SSE endpoint is in FastAPI. Worker and web process are separate.
**Decision**: Worker publishes chunk messages to Redis pub/sub channel `coaching:{analysis_id}` as they arrive from Claude. FastAPI SSE endpoint subscribes to that channel and forwards chunks as SSE events. Race prevention: endpoint subscribes BEFORE checking `stream_complete` in DB. If coaching completes between subscribe and check, the endpoint returns the stored output. On "done" sentinel, endpoint fetches the final validated `CoachingOutput` from DB and emits as `event: complete`.
**Consequences**: Decoupled architecture — worker doesn't need to know about HTTP connections. Multiple clients can subscribe to the same analysis. Requires a dedicated Redis client (not the ARQ `ctx["redis"]`) because pub/sub blocks the connection. If worker and web are on separate Redis instances, this breaks — must use a shared Redis.

## ADR-020: Prompt Caching on Stable Sections (FR-AICP-21)
**Context**: Claude Sonnet 4.6 supports prompt caching with a 5-minute TTL. Caching saves tokens and latency on repeated stable content (system prompt, persona, tool schemas). Rep metrics and session data are fresh per-analysis.
**Decision**: System prompt, persona description, coaching priority hierarchy text, and tool schemas are marked with `cache_control: {"type": "ephemeral"}` in the Anthropic API call. Rep metrics, body stats, keyframe analysis text, and user-specific context are NOT cached — passed as fresh content each request.
**Consequences**: Batched analyses within a 5-minute window share the cached prefix; the first analysis pays full token cost, subsequent analyses pay only fresh content cost. RAG docs (Phase 2) are per-analysis and typically uncacheable — do not attempt cross-analysis caching of retrieval results.

## ADR-021: Phase 1 Coaching — Stream-Then-Reparse Pattern (Tech Debt)
**Context**: FR-AICP-07 phrasing "Phase 1 streams initial LLM response directly" suggests a single streaming call that emits structured output. The current implementation (`backend/app/services/coaching.py::generate_coaching_streaming`) streams Claude Sonnet text to Redis pub/sub, then makes a SECOND instructor call with the accumulated text as an assistant message to re-validate into the `CoachingOutput` Pydantic schema.
**Decision**: Ship Phase 1 with the stream-then-reparse pattern. Accept the double token cost and the race between "done" sentinel and re-validation. Phase 2 will replace with `instructor`'s native streaming structured extraction in a dedicated cleanup task (P2-023).
**Consequences**: Per-analysis token cost is ~2× the single-call cost. Latency is higher because re-validation happens after streaming completes. The SSE client sees streamed chunks correctly, then receives a `complete` event with the validated structured payload. This is a known tech-debt item, tracked in `backlog.md` as D-001 / P2-023. Do not optimize other parts of the coaching pipeline until this is addressed in Phase 2.

## ADR-022: Per-Rep Metrics Dict — Widened to `dict[str, float | str]`
**Context**: FR-REPM-09 requires a `phase_of_max_deviation` field that is a categorical label (setup/descent/bottom/ascent/lockout), not a float. The original `RepMetrics.metrics: dict[str, float]` type annotation could not represent this.
**Decision**: Widen `RepMetrics.metrics` to `dict[str, float | str]`. The `test_all_*_metric_values_are_floats` invariant test special-cases `phase_of_max_deviation` as a string; all other metrics remain float. If a future FR adds more non-numeric fields, split into a structured `RepMetricPayload` dataclass with typed subgroups instead of widening further.
**Consequences**: JSON serialization to `rep_metrics.metrics_json` JSONB is unaffected (Postgres accepts mixed types). Frontend types treat metrics as `Record<string, unknown>`. Consistency metric computation in `SummaryService._compute_consistency_metrics` filters to numeric values only via `isinstance(v, (int, float))` guard.

## ADR-023: Detection Result Stored as JSONB on Analyses Row
**Context**: FR-XDET-07 requires displaying the detected exercise type/variant + confidence + method on the status page. Options: (a) JSONB column on `analyses`, (b) dedicated `detections` table.
**Decision**: Add `detection_result JSONB` column on `analyses` (migration 003). Stores `{detected_type, detected_variant, confidence, method, details}`. Does NOT override user-selected `exercise_type` — detection is informational only, user's original choice drives quality gates / rep detection / scoring.
**Consequences**: Simple 1:1 storage, no join required for status display. Cost: historical drift analysis (e.g., Phase 4 eval of detection accuracy over time) requires JSONB path queries rather than a proper indexed table. If Phase 4 needs to track detection accuracy trends, migrate to a `detections` table then.

## ADR-024: Worker OpenAI Client — Single Instance, Graceful Degradation
**Context**: The worker needs OpenAI for two purposes: GPT-4o vision fallback in exercise detection (FR-XDET-04) and GPT-4o keyframe analysis (FR-AICP-02). Creating a new `AsyncOpenAI` client for each is wasteful. Missing `OPENAI_API_KEY` should not crash the worker — tests run without it.
**Decision**: Worker creates a single `openai.AsyncOpenAI()` instance wrapped in a try/except at pipeline start. If instantiation fails (missing env var), `openai_client = None` and all GPT-4o features are skipped with a warning log. The same client instance is passed to `run_cv_pipeline` and reused by `KeyframeAnalysisService`.
**Consequences**: Tests can run without `OPENAI_API_KEY` set — pipeline still executes, GPT-4o features no-op gracefully. Production must set the key or detection/keyframe features silently degrade to heuristic-only mode. Degradation is logged at WARNING level but does not fail analyses.

## ADR-025: PDF Bar Path Chart — Matplotlib Lazy Import
**Context**: FR-XPRT-02 requires a bar path visualization in the PDF report. The bar path data is a list of (x, y) normalized centroids from the CV pipeline. Options: (a) server-side matplotlib PNG, (b) SVG generation, (c) client-side Recharts screenshot.
**Decision**: Generate a static PNG via matplotlib in `backend/app/services/pdf.py::generate_bar_path_plot`. Matplotlib is imported lazily inside the function body so WeasyPrint-only code paths don't pay the import cost. PNG is embedded as base64 `data:` URI in the HTML template — no external file reference needed.
**Consequences**: PDF service now has a soft dependency on matplotlib. Import time is ~200ms which is negligible vs WeasyPrint's render time. If we ever move PDF generation to a lightweight service, matplotlib must be bundled in that service's image. For now, matplotlib is already in requirements for the angle time-series plot generator, so no new dependency was added.

## ADR-026: Worktree is Vite + React SPA, Not Next.js
**Context**: Editor hooks repeatedly suggest `"use client"` directives on React components in `frontend/src/pages/*.tsx` based on pattern matching against Next.js App Router conventions. These suggestions are false positives.
**Decision**: The Spelix frontend is a Vite 8 + React 19 SPA with React Router v6. There is no Next.js, no App Router, no Server Components. The `"use client"` directive is a Next.js-specific concept that has no meaning in Vite. Ignore all hook-injected suggestions recommending `"use client"`.
**Consequences**: Reviewers and AI agents must understand this distinction. Adding `"use client"` to Vite components is harmless (it's just a string literal at the top of the file) but creates confusion. Documented in CLAUDE.md and this ADR so future sessions don't "fix" these phantom warnings.

## ADR-027: AsyncSession `commit-on-success` in `get_db()` Dependency (Session 13)
**Context**: SQLAlchemy `AsyncSession` defaults to `autocommit=False`. The Phase 0 `get_db()` dependency yielded a session inside `async with` and never called `session.commit()` — so every flushed write was rolled back when the session closed at request end. The bug went undetected until session 13 because every test mocked the repository layer entirely. Production data loss in disguise: `POST /analyses` returned 201 with a UUID built from the in-memory ORM object, the row never persisted, then `POST /analyses/{id}/start` returned 404 because request 2 couldn't find what request 1 "created".
**Decision**: `get_db()` MUST wrap the `yield` in `try/except` and call `await session.commit()` on success, `await session.rollback()` on any exception (including `HTTPException`, so partial writes from a failed handler don't leak). The same pattern applies to ARQ worker session blocks (`analysis_worker.process_analysis`, `cleanup.cleanup_expired_artifacts`) — both opened sessions via `async_session()` directly and need explicit commits at every persistence boundary.
**Consequences**: Backend dev gotcha — anyone writing a new dependency or worker entry point that holds an `AsyncSession` MUST commit explicitly. Regression test in `tests/unit/test_db_session.py::TestGetDbCommit` exercises the dependency lifecycle directly via `gen.__anext__()` / `gen.athrow()` and would catch any reintroduction. Worker error paths must commit twice — once for the in-flight write that crashed (rolled back), then a fresh write for the failure-state row + commit. Backend CLAUDE.md gotcha added.

## ADR-028: Pre-Generate UUIDs at Construction Time, Not Via SQLAlchemy `default=` (Session 13)
**Context**: `Analysis.id` was declared as `mapped_column(UUID, primary_key=True, default=gen_uuid)`. SQLAlchemy `default=` runs at INSERT/flush time, NOT at `__init__`. `AnalysisService.create_analysis` set `analysis.video_path = get_storage_path(analysis.id, filename)` BEFORE calling `repo.create()`, so `analysis.id` was `None` and the f-string in `get_storage_path` formatted the literal string `"None"` into the path: `"videos/None/squat-high-bar.mp4"`. The signed upload URL handed back to the browser used the post-flush real UUID (correct), but the database column had the wrong path. The worker download then 404'd because the actual file in Storage was at `videos/<real-uuid>/...`, not `videos/None/...`.
**Decision**: For any code path that needs to read `analysis.id` BEFORE the first flush, pass `id=gen_uuid()` explicitly at construction:
```python
analysis = Analysis(
    id=gen_uuid(),
    user_id=user_id,
    ...
)
analysis.video_path = get_storage_path(analysis.id, filename)  # safe — id is set
analysis = await self._repo.create(analysis)
```
The model's `default=gen_uuid` is kept for any other call site that doesn't override it.
**Consequences**: Pattern applies to any future model where downstream logic derives a path, URL, key, or hash from the row's primary key before it's persisted. Regression test `test_video_path_contains_real_uuid_not_string_none` captures the real `Analysis` instance passed to `repo.create()` and asserts `video_path` parses as a UUID equal to `analysis.id`. Backend CLAUDE.md gotcha added.

## ADR-029: MediaPipe Tasks API, Not Legacy `solutions` (Session 13)
**Context**: Phase 0 `pose_extraction.py` used `mediapipe.solutions.pose.Pose(...)`. This worked locally on Mac/Windows because those wheels still ship `solutions`, but Linux x86_64 wheels for `mediapipe==0.10.x` have NEVER shipped the legacy `solutions` submodule (verified by inspecting wheel contents from PyPI for versions 0.10.9, 0.10.11, 0.10.14, 0.10.18, 0.10.21, 0.10.33 — every Linux wheel contains zero `solutions/` files). CI tests passed because they fully mocked `mediapipe`. Production worker on the DigitalOcean droplet (Debian) crashed with `AttributeError: module 'mediapipe' has no attribute 'solutions'` on the very first real video.
**Decision**: All MediaPipe pose-extraction code MUST use the modern Tasks API (`mediapipe.tasks.python.vision.PoseLandmarker`). The BlazePose Heavy `.task` model file (`pose_landmarker_heavy.task`, ~30 MB) is downloaded into the Docker image at build time via `RUN curl ... -o /app/models/pose_landmarker_heavy.task`. Path resolution prefers the env var `POSE_LANDMARKER_MODEL_PATH`, then `/app/models/pose_landmarker_heavy.task`, then falls back to a local-dev candidate via `Path(__file__).parent.parent.parent.parent`. Config mapping from the legacy API: `model_complexity=2` → BlazePose Heavy `.task` file; `static_image_mode=True` → `running_mode=RunningMode.IMAGE`; `min_detection_confidence=0.5` → `min_pose_detection_confidence=0.5`; `min_tracking_confidence=0.5` → `min_tracking_confidence=0.5`; new `min_pose_presence_confidence=0.5` matched to detection confidence; new `num_poses=1` (Spelix is single-person). The Tasks API `libmediapipe.so` also requires `libgles2` and `libegl1` system packages (verified via `ldd`) — both added to the Dockerfile apt install list.
**Consequences**: All pose-extraction code is now cross-platform consistent — Linux, Mac, and Windows all run the same Tasks API path. The legacy `solutions` API is forbidden. Adding new MediaPipe features (e.g. `HandLandmarker`, `FaceLandmarker`) MUST use the corresponding Tasks API and bake the relevant `.task` file into the image. The Docker image grew by ~30 MB (model file) and ~250 MB (ffmpeg + libgles2 + libegl1) but those costs are unavoidable for a working pipeline. Tests now mock the Tasks API symbols (`PoseLandmarker`, `PoseLandmarkerOptions`, `BaseOptions`, `RunningMode`, `mp.Image`, `mp.ImageFormat`) instead of the legacy `solutions` tree.

## ADR-030: Frontend Upload — REST PUT, Not TUS Resumable (Session 13)
**Context**: Phase 0 frontend used `tus-js-client` to upload videos to the Supabase signed upload URL returned by `POST /api/v1/analyses`. But Supabase's signed upload URL endpoint (`/storage/v1/object/upload/sign/{bucket}/{path}?token=...`) is a REST endpoint that accepts a one-shot HTTP `PUT`, NOT a TUS resumable upload session. The TUS protocol requires an `Authorization: Bearer <user_jwt>` header on a different endpoint (`/storage/v1/upload/resumable`). Sending TUS protocol semantics to the REST signed URL produced `400: headers must have required property 'authorization'` on every upload attempt. The mismatch was a Phase 0 design bug that never fired in production until upstream layers (storage factory, async client, etc.) were fixed.
**Decision**: Frontend uses plain `XMLHttpRequest` (NOT `fetch` — XHR is the only browser API that exposes upload progress events for FR-UPLD-12) to PUT the file body to the signed URL with `Content-Type: <file mime>`. No `Authorization` header (the signed URL's query-string token is the auth). Drop pause/resume — REST upload cannot resume mid-byte. The cancel button calls `xhr.abort()` and resets state. For the 50 MB file size cap, REST PUT is fine — typical upload is <30s on broadband; TUS resumability is overkill at this size.
**Consequences**: `tus-js-client` is no longer used (kept in `package.json` for potential future TUS migration if larger files become a requirement). Future TUS migration path: backend stops returning a signed REST URL, instead returns `{id, status, expires_at}`; frontend uploads via Supabase's `/storage/v1/upload/resumable` with `tus-js-client` AND the user's bearer JWT in the `Authorization` header. That migration also requires Supabase RLS policies allowing authenticated users to INSERT into the `videos` bucket where the path matches their `user_id`. Deferred until actually needed.

## ADR-031: Status Table — Operational `→ failed` Edges (Session 13)
**Context**: The Phase 0 status transition table (`backend/app/services/status.py`) only allowed `→ failed` from `processing` or `coaching`. But operational failures (missing config, OOM, ARQ crash, Anthropic 401, MediaPipe model download failure, Supabase auth) can fire at ANY phase of the worker pipeline — including before the worker has had a chance to transition the row out of `queued` or `quality_gate_pending`. The worker error handler in `analysis_worker.process_analysis` does `transition(analysis.status, "failed")` for any non-terminal status, so an early-pipeline crash hit a guard wall and the error handler ITSELF crashed with `InvalidTransition`, leaving the row orphaned at `quality_gate_pending` forever and masking the original error.
**Decision**: Add `queued → failed` and `quality_gate_pending → failed` to the transition table. Operational failures can fire at any phase. The semantic distinction with `quality_gate_rejected` is preserved: that state remains reserved for analyses where the actual quality-gate predicate refused the user's video content (resolution, framing, body visibility, single-person). `failed` is reserved for infrastructure/operational failures. The worker error handler is also updated to skip the transition entirely when the row is already at `failed` (a different row state from a previous attempt re-running) to avoid the `failed → failed` self-transition wall.
**Consequences**: Any new operational error path can land the row in `failed` from anywhere. The two terminal-soft-fail states (`failed` with `retry_count >= 3`, `quality_gate_rejected`, `completed`) remain unchanged. The retry path `failed → queued` (allowed when `retry_count < 3`) is also unchanged. Regression tests for both new edges + the worker self-transition skip live in `test_status_transitions.py` and `test_analysis_worker.py::test_error_handler_skips_transition_when_already_failed`.

## ADR-032: Tests Must Exercise Real Factories with Source-Patched Third-Party Modules (Session 13)
**Context**: Session 13 uncovered TWELVE distinct dormant Phase 0 bugs in production code that had been live for months behind perfectly green CI:
1. `_make_storage_service` factory `pass`-branch returning `client=None`
2. Sync `create_client` vs awaited storage methods
3. tz-aware datetime against `TIMESTAMP WITHOUT TIME ZONE` column
4. `get_db()` never committed
5. `_get_service` never wired the ARQ pool
6. `ThresholdConfig()` path resolution wrong inside Docker
7. Status guard rejected `quality_gate_pending → failed`
8. Duplicate `→ quality_gate_pending` transition
9. `video_path` set to literal `"None"` because of `gen_uuid` timing
10. Worker error handler `failed → failed` self-transition
11. MediaPipe `solutions` API doesn't exist on Linux
12. Worker error handler caught `InvalidTransition` instead of original error

**Common root cause across all 12**: every test that touched these subsystems mocked the third-party module entirely (`mock_mp = MagicMock()`, `mock_supabase = AsyncMock()`, `mock_repo = AsyncMock(spec=AnalysisRepository)`) so the real factory and singleton paths were never exercised. CI was green because the mocks always behaved correctly; production was broken because the real code paths had bugs the mocks couldn't catch.

**Decision**: Any factory or singleton that constructs a third-party client OR derives behavior from runtime configuration (env vars, file paths, model files) MUST have at least ONE regression test that exercises the REAL factory function with the third-party module patched at its SOURCE, not at the consumer. Pattern:
```python
# WRONG (masks bugs):
def test_my_endpoint():
    mock_service = AsyncMock(spec=MyService)
    app.dependency_overrides[get_my_service] = lambda: mock_service
    ...

# RIGHT (exercises real factory):
def test_my_factory_wires_real_client():
    monkeypatch.setenv("MY_API_KEY", "test-key")
    fake_client = MagicMock()
    with patch("third_party.create_client", return_value=fake_client) as create:
        svc = my_factory()
    assert svc._client is fake_client
    create.assert_called_once_with("test-key")
```
The regression tests added in session 13 (`TestMakeStorageServiceFactory`, `TestGetDbCommit`, `TestMakeArqPoolFactory`, `TestGetServicePassesArqPool`, `TestThresholdConfigPathResolution`, `TestModelPathResolution`, `test_video_path_contains_real_uuid_not_string_none`, `test_error_handler_skips_transition_when_already_failed`) all follow this pattern. Each one would have caught its corresponding production bug at PR review time.

**Consequences**: Phase 2+ code review checklist must include "is there a real-factory test for any new singleton/factory/cached-client introduced by this PR?". Mocks at the consumer level remain fine for endpoint tests and business logic tests — but at least one test per factory must patch at the source. Backend CLAUDE.md gotcha added documenting all eight regression test patterns from session 13 as canonical examples.

---

<!-- Phase 2 kickoff ADRs (session 14, 2026-04-11). Decisions locked in the
     Phase 2 kickoff brief — do not re-litigate. Each ADR below was confirmed
     in that brief as a pre-committed choice, not an open design question. -->

## ADR-P2-001: Qdrant Cloud Free Tier for Phase 2 (Session 14)
**Context**: Phase 2 needs a vector store with two collections (`papers_rag` + `coach_brain`). Options considered: (a) Qdrant Cloud free tier, (b) self-hosted Qdrant on the 2GB DigitalOcean droplet alongside the backend/worker/redis containers, (c) managed Weaviate, (d) Pinecone starter. The kickoff brief initially flagged a concern that the free tier "allows only 1 collection" and asked to fall back to self-hosted if confirmed.
**Decision**: Use Qdrant Cloud free tier. Verified during provisioning: the collection limit is NOT "1 collection" — the free tier has resource limits (1GB RAM, 4GB disk) but no collection count cap. Both `papers_rag` and `coach_brain` fit within those limits for the Phase 2 corpus scale (~30 research papers × ~50 chunks each + ≤100 Coach Brain entries). Do NOT self-host on the droplet — MediaPipe BlazePose Heavy already consumes ~350MB and `max_jobs=1` is the only safe worker config.
**Consequences**: Phase 2 depends on Qdrant Cloud availability. Free tier pauses clusters after 1 week of inactivity — mitigated by a nightly ARQ keepalive cron (`ping_qdrant_health`, `cron="0 3 * * *"`) that hits `/healthz` to reset the idle timer. If the corpus grows past free-tier capacity (late Phase 2 or Phase 3), upgrade to paid tier; do not migrate to self-hosted — the droplet is committed to CV + web workload.

## ADR-RAG-01: Cohere Rerank 4.0 as Cross-Collection Score Normaliser (Session 14)
**Context**: Phase 2 hybrid retrieval merges results from two Qdrant collections (`papers_rag` and `coach_brain`) that use different embedding and sparse retrieval spaces. Raw scores from the two collections are NOT comparable — a 0.84 cosine similarity in `papers_rag` does not mean the same thing as a 0.84 in `coach_brain`. A single ranked list requires a normalisation step. Options: (a) min-max rescale per collection, (b) reciprocal rank fusion only, (c) cross-encoder rerank, (d) Cohere Rerank 3.5, (e) Cohere Rerank 4.0.
**Decision**: Use Cohere **Rerank 4.0** (`rerank-v4.0-pro`) as the cross-collection score normaliser. Reranks the merged top-K results from both collections in a single call and emits comparable, content-aware scores. Do NOT use Rerank 3.5 — Rerank 4.0 is the current generation and the brief explicitly supersedes 3.5. Timeout budget: 3 seconds; on timeout fall back to RRF-merged scores and log the degradation to Langfuse (P2-020).
**Consequences**: Every Phase 2 retrieval query pays one Rerank 4.0 call (~$0.002 per 1000 search units at current pricing, well inside the $0.10/analysis budget). The call is on the critical path for coaching latency; the 3s timeout protects the ≤5s first-token target. All Phase 2 code must pin `rerank-v4.0-pro` as a named constant and reject any PR that introduces `rerank-v3.*` or `rerank-english-v2.*`.

## ADR-RAG-02: Docling for PDF Parsing (Session 14)
**Context**: Document ingestion (P2-004) requires parsing research papers from PDF. Options: (a) `unstructured.io`, (b) `marker-pdf`, (c) IBM Docling, (d) LlamaParse API, (e) `pymupdf` + custom layout logic.
**Decision**: Use IBM Docling as the default PDF parser. MIT licence, runs locally (no API call per document), handles scientific paper layout (columns, figures, tables, equations) better than `unstructured.io` in recent benchmarks. `marker-pdf` remains an optional fallback path if Docling produces degraded output on a specific paper type — wire the interface so the parser is swappable, but ship Phase 2 with Docling only.
**Consequences**: Adds `docling` as a backend dependency. Local parsing keeps per-analysis cost predictable (no per-page API charges). Parse time is measured in seconds per paper, which is fine for ingestion (offline batch) but would be too slow for query-time parsing — all papers must be pre-ingested. If future requirements need on-demand parsing of user-uploaded content, revisit with a streaming parser.

## ADR-RAG-03: Matryoshka 1024 Dimensions for Both Qdrant Collections (Session 14)
**Context**: Cohere `embed-v4.0` is a Matryoshka embedding model — it emits 1536-dimensional vectors by default but supports truncation to 1024, 768, 512, or 256 dimensions via the `output_dimension` parameter. Lower dimensions trade retrieval quality for storage + compute efficiency. The Phase 2 scale (≤100k chunks in papers_rag, ≤1k Coach Brain entries) can fit comfortably at 1024 dimensions on Qdrant Cloud free tier.
**Decision**: Both `papers_rag` and `coach_brain` collections use **exactly 1024 dimensions**. Every call to `CohereEmbedClient.embed_batch` MUST pass `output_dimension=1024` explicitly — omitting it defaults to 1536 and will cause Qdrant dimension mismatch on every upsert. Both collections must have matching dimensions so Cohere Rerank 4.0 can operate on the merged result set without per-collection branches.
**Consequences**: 33% storage savings vs 1536 dims while retaining the bulk of retrieval quality per Cohere's published Matryoshka benchmarks. The `output_dimension=1024` argument is a pre-commit checklist item for any PR touching `CohereEmbedClient` — regression tests must assert it is passed. If Phase 3+ needs higher fidelity, re-index both collections at 1536 in a coordinated migration — never mix dimensions across collections.

## ADR-BRAIN-01: Separate Qdrant Collection for Coach Brain (Session 14)
**Context**: Coach Brain entries (concise corrective cues distilled from successful coaching sessions) and research papers (long-form scientific prose) are fundamentally different data types. Options: (a) merge both into a single `papers_rag` collection with a `source_type` payload filter, (b) dedicated `coach_brain` collection.
**Decision**: Use a separate `coach_brain` Qdrant collection. Both collections share identical vector config (1024 dim cosine + BM25 sparse) but have different payload schemas — `coach_brain` carries `exercise`, `phase`, `entry_type`, `trigger_tags`, `status`, `confirmation_count`; `papers_rag` carries `title`, `authors`, `year`, `doi`, `quality_tier`, `section`. The routing logic in `RetrieveTool.retrieve` queries both concurrently via `asyncio.gather` and Rerank 4.0 merges the results (ADR-RAG-01).
**Consequences**: Two collections is more operational surface area (two indexes to back up, two to restore) but massively simpler querying: payload filters stay semantically clean, the coach-brain-primary vs papers-only-fallback routing logic (FR-BRAIN-04/05) just switches which collection drives the decision. Attempting to encode the same logic via `source_type` filters on a single collection would obscure the routing rules and force every query to carry a filter the retrieval layer has no other use for.

## ADR-BRAIN-02: Contextual Padding Before Embedding Short Cues (Session 14)
**Context**: Coach Brain entries are typically 1-3 sentences — far shorter than research paper chunks (500 tokens). Embedding models tend to under-utilize their latent space on very short inputs, which hurts retrieval precision when matching a user's specific situation (exercise + phase + entry type) to the right cue. Without context padding, "drive your knees out" and "keep your hips back" embed into similar regions because both lack the framing that distinguishes them.
**Decision**: Before embedding any `CoachBrainEntry`, prepend contextual metadata in a fixed format: `"exercise:{exercise} phase:{phase} type:{entry_type}\n{coaching_action}"`. The enriched text is what the embedding model sees; store it separately from the raw `coaching_action` so the raw text is available for rendering in coaching output without the prefix leaking to users. Query-time embeddings use `input_type="search_query"` over the raw user context (exercise + phase keywords + issue description); the retrieval still works because both sides share the exercise/phase/type vocabulary.
**Consequences**: Retrieval precision improves for short cues — the contextual prefix acts as a high-weight disambiguator. Adds a small per-entry compute cost (handled at ingestion, not query time, so no latency impact). Any code that embeds `CoachBrainEntry` instances MUST apply the same prefix template — enforce via a single `contextualize(entry)` helper in `app/services/coach_brain.py` with unit tests that guard the exact format string. If the prefix format ever changes, the entire `coach_brain` collection must be re-indexed — no mixed-format entries allowed.

## ADR-BRAIN-03: Hybrid Dense + Sparse + Server-Side RRF for Coach Brain (Session 14)
**Context**: Coach Brain retrieval needs to match on both semantic similarity ("valgus knee collapse" → entries about knees caving) and lexical exact matches ("elbow flare" → any entry that literally says "elbow flare"). Options: (a) dense only, (b) sparse BM25 only, (c) client-side hybrid with custom fusion, (d) Qdrant server-side sparse vectors with native RRF fusion.
**Decision**: Use Qdrant server-side sparse vectors (BM25) alongside the 1024-dim dense vectors, fused via Qdrant's native reciprocal rank fusion in a single query. Both collections (`papers_rag` and `coach_brain`) get sparse indexes enabled at creation time. No client-side fusion — Qdrant RRF is one query, one network round-trip, one cache hit.
**Consequences**: Ingestion must populate both dense and sparse vectors for every point (handled by `CohereEmbedClient` for dense + Qdrant's built-in BM25 tokenizer for sparse — no extra embedding calls). Query layer calls `client.query_points` with both vectors and lets Qdrant merge; avoids the client-side reranking bug class entirely. If Qdrant ever removes native RRF (very unlikely), fall back to manual RRF — but not sooner.

## ADR-BRAIN-04: Defer ARQ → streaq Migration to Phase 3 (Session 14)
**Context**: Phase 2 adds long-running ingestion jobs (document parsing + embedding + Qdrant upsert) to the worker. `streaq` (a newer async job queue) has better cancellation semantics and native support for long-running tasks than ARQ. Tempting to migrate now.
**Decision**: DO NOT migrate. Phase 2 continues on ARQ with `max_jobs=1` and `job_timeout=900` (bumped from 300 for ingestion). Ingestion jobs are idempotent (sha256 chunk IDs) so retries on timeout are safe. Migration to streaq is scheduled for Phase 3 when LangGraph agent orchestration brings new requirements that justify the rewrite.
**Consequences**: Phase 2 keeps one less moving part. Ingestion job timeout bumps are config-only. Any Phase 2 work that assumes streaq semantics (e.g. cooperative cancellation mid-parse) MUST be rewritten to ARQ semantics (coarse-grained checkpoints + full re-run on retry). Phase 3 kickoff will inherit the streaq migration as a pre-requisite for LangGraph.

## ADR-BRAIN-05: GDPR Article 9 Explicit Consent for All Health Data Processing (Session 14)
**Context**: Spelix processes biometric/movement data, historical session data, and user-provided form responses. Under GDPR, movement form data and coaching history may qualify as "health data" per Article 9 depending on interpretation — the conservative stance treats them as Article 9 special category data requiring explicit consent. The UK ICO guidance specifically cites "fitness and wellness apps processing biometric data" as Article 9 triggers.
**Decision**: Treat ALL Phase 2+ health data processing (movement scores, form analyses, session history, body stats) as Article 9 special category data. Require explicit, tiered consent: Tier 1 general service consent at signup under Article 6(1)(b) (contract performance for the coaching service itself), Tier 2 separate explicit consent under Article 9(2)(a) for health data analysis (MUST be a distinct interaction, NOT bundled with ToS acceptance), Tier 3 optional aggregate consent for anonymized pattern contribution to Coach Brain improvements (service MUST function without Tier 3). Consent records stored in a dedicated `consent_records` table with timestamp, ip_hash, consent_tier, and withdrawal timestamp. DPIA (ADR-BRAIN-05 cross-reference: P2-031 `docs/dpia.md`) is a hard gate before any production Coach Brain write.
**Consequences**: Every user-facing string, UI flow, API endpoint, and data-write path in Phase 2 touching health data must respect the consent tier. Tier 1 missing → block service. Tier 2 missing → block analysis creation. Tier 3 missing → analysis proceeds normally but the resulting entries are excluded from Coach Brain distillation (Phase 3). Withdrawal (P2-030) cascades as an ARQ job that removes user analysis_ids from all `coach_brain_entries.source_analysis_ids` arrays; entries with no remaining sources and `confirmation_count < 3` are soft-deleted. Every PR touching consent flow, data writes, or user-facing health data language requires `spelix-security-reviewer` sign-off.

## ADR-BRAIN-06: Postgres JSONB for Per-Athlete Episodic Memory (Phase 4 Schema Reservation)
**Context**: Phase 4 introduces per-athlete episodic memory — a longitudinal view of each user's coaching trajectory (recurring issues, progression metrics, cue effectiveness history). This is NOT a Coach Brain entry (which is population-level). It is per-user. The storage options for Phase 4 were: (a) dedicated Qdrant collection per user (doesn't scale), (b) single Qdrant collection with user_id filter (ACL risk), (c) Postgres JSONB column on a user-scoped table (simpler, enforced by RLS).
**Decision**: Use Postgres JSONB (Supabase, public schema, RLS-enforced) for episodic memory. Phase 2 RESERVES the schema columns but does NOT populate them. The column is `users_profiles.episodic_memory_json JSONB DEFAULT '{}'::jsonb` (name TBD at Phase 4 migration time — do not lock in now). Phase 2 migration 004 does NOT add this column; it will be added in a Phase 4 migration when the access patterns are known.
**Consequences**: Zero Phase 2 code touches episodic memory. If any Phase 2 PR tries to add an `episodic_memory` column, reviewers reject on the grounds that the schema is reserved and the design is incomplete. This ADR exists to prevent premature schema bikeshedding — the decision is "not yet, and in Postgres JSONB when it happens."

## ADR-BRAIN-07: Distillation Pipeline as Standalone StateGraph in Phase 3 (Session 14)
**Context**: The Phase 3 distillation pipeline (FR-BRAIN-06/07/08) ingests historical successful analyses and produces candidate `CoachBrainEntry` items for human review. It is a multi-stage workflow with LLM calls, clustering, and HITL approval. Tempting to scaffold the LangGraph state machine in Phase 2 "to be ready." Options: (a) scaffold now as a subgraph inside the main coaching StateGraph, (b) build now as a standalone graph, (c) defer entirely to Phase 3.
**Decision**: Defer entirely to Phase 3. Phase 2 ships a functional Coach Brain with hand-seeded entries only (`source=seed_manual_validated`). No distillation code, no candidate entries, no HITL queue beyond what already exists for research-paper review. When Phase 3 activates LangGraph, distillation will be a standalone `StateGraph` (NOT a subgraph of coaching) because it runs offline against the analyses table, not inline per-analysis.
**Consequences**: Phase 2 Coach Brain retrieval quality is upper-bounded by seed corpus quality (P2-025, ≥20 entries). This is acceptable because the seed corpus is hand-curated and validated. Any Phase 2 PR that introduces a `distillation_*` file, function, or ARQ job must be rejected — the design belongs to Phase 3. The `source_analysis_ids UUID[]` column added in migration 004 is populated with `[]` by the seed ingest and waits for Phase 3 to attach real analysis IDs.

## ADR-RAG-04: LLM-as-Judge Faithfulness Instead of HHEM T5 (Session 16)
**Context**: FR-AICP-08 specifies FaithfulnesswithHHEM (Vectara HHEM-2.1-Open, a T5-based classifier) for the faithfulness gate. The T5 model requires ~400–800MB RAM. The 2GB droplet already peaks at ~350MB during MediaPipe pose extraction (`max_jobs=1`). Loading T5 alongside MediaPipe would exceed available memory. No managed HHEM inference API exists.
**Decision**: Phase 2 uses Claude Sonnet 4.6 as an LLM-as-judge for faithfulness scoring in `app/services/faithfulness_gate.py`. Single structured call via instructor with `FaithfulnessScore(score: float, reasoning: str, unsupported_claims: list[str])`. Threshold remains 0.8 per SRS. Sub-threshold results set `analysis.flagged_for_review=True` and write to `analysis.eval_scores` JSONB. The gate never raises — failures return `score=0.0, flagged=True`.
**Consequences**: LLM-as-judge is less calibrated than a purpose-trained classifier — faithfulness scores are directional, not directly comparable to HHEM benchmarks. Phase 3 can swap in HHEM T5 on a dedicated eval instance or via a future Vectara API without changing the `FaithfulnessGateService` interface. Any calibration work (score thresholds, comparison to HHEM) should wait for Phase 4 eval infrastructure.

## ADR-P2-021: CSS-only Citation Tooltips — No shadcn/Radix Dependency (Session 18)
**Context**: FR-RESL-06 requires hover tooltips on `[N]` citation markers showing source metadata. No shadcn/ui components were installed yet (`components/ui/` didn't exist). Options: (a) install `@radix-ui/react-tooltip` (~8KB gzipped) as the first shadcn primitive, (b) CSS-only tooltip via Tailwind `group-hover`/`group-focus-within`, (c) native `title` attribute (can't render links). Option (c) fails the DOI link requirement.
**Decision**: CSS-only tooltip in `frontend/src/components/CitationTooltip.tsx`. Trigger is a `<button>` (keyboard-accessible via `:focus-within`). Tooltip panel uses `invisible group-hover:visible group-focus-within:visible` classes. `parseWithCitations(text, citations)` splits on `\[(\d+)\]` regex, renders valid indices as `CitationTooltip` components, out-of-range as plain text.
**Consequences**: Zero new npm dependencies for P2-021. Tooltip positioning is basic (`bottom-full left-1/2 -translate-x-1/2`) — clips at viewport edges on narrow screens. Phase 3 polish can add smart positioning or install Radix if more tooltip uses emerge. The `:hover` pattern doesn't work on touch devices but `:focus-within` on the button handles tap-to-focus.

## ADR-P2-022a: Non-Streaming Chat for Phase 2 MVP (Session 18)
**Context**: FR-AICP-17 requires follow-up chat. Streaming (SSE) provides better UX for long responses but adds complexity — the existing SSE coaching architecture (ADR-019) uses Redis pub/sub between worker and web process, and has known tech debt (ADR-021: stream-then-reparse doubles tokens). Building a second SSE channel for chat would inherit these issues.
**Decision**: Phase 2 chat uses non-streaming `POST /api/v1/analyses/{id}/chat` → returns complete `ChatMessageResponse` JSON. Claude Sonnet 4.6, `temperature=0.3`, `max_tokens=512`. Endpoint in `backend/app/api/v1/chat.py`, service in `backend/app/services/chat.py`. Rate-limited to 30/day via slowapi.
**Consequences**: Chat responses take 2–5s with no streaming indicator (frontend shows animated dots). Acceptable for Phase 2 MVP. Phase 3 LangGraph agent (FR-AICP-18) will likely replace this endpoint with a streaming agentic chat — the `ChatMessage` model and `useChat` hook interface are stable and compatible with either backend.

## ADR-P2-022b: SafetyFilter.apply_text() for Plain String Filtering (Session 18)
**Context**: `SafetyFilter.apply()` takes a `CoachingOutput` Pydantic model and replaces prohibited phrases in each field. Chat responses are plain strings, not structured coaching output. Calling `_replace_prohibited()` directly would work but bypasses the class's error-handling wrapper and isn't discoverable.
**Decision**: Added `SafetyFilter.apply_text(text: str) -> str` static method in `backend/app/services/safety_filter.py`. Thin wrapper over the module-level `_replace_prohibited()` function. Returns cleaned text only (no `SafetyFilterResult` — not needed for plain strings).
**Consequences**: Any future plain-text output (chat, summaries, notifications) uses `apply_text()` for language compliance. The method is independently testable (3 tests in `test_chat_api.py::TestSafetyFilterApplyText`). If a new prohibited phrase is added to `_PROHIBITED_REPLACEMENTS`, it automatically applies to both coaching and chat outputs.

## ADR-033: Realtime Hooks Must Fetch Initial State on Mount (Session 20)
**Context**: `useAnalysisStatus` subscribed to Supabase Realtime `postgres_changes` UPDATE events but never fetched the current row state. If the page loaded after a status transition (or Realtime was slow to connect), the page showed "Loading…" forever. All three test uploads (squat, bench, deadlift) exhibited this — the status page never displayed results even after the worker finished. Root cause: Realtime only delivers future UPDATEs, not the current state.
**Decision**: After subscribing to the Realtime channel, immediately call `getAnalysisStatus(analysisId)` via REST (`GET /api/v1/analyses/{id}/status`). The initial fetch sets `isLoading=false` and populates the current state. Realtime updates then override as they arrive. In `frontend/src/hooks/useAnalysisStatus.ts`.
**Consequences**: Any new Realtime subscription hook in this project must follow the same pattern: subscribe first, then fetch initial state. The initial fetch is a no-op if Realtime delivers the first update faster (last-write-wins via `applyUpdate`). Tests that focus on Realtime callbacks should mock `getAnalysisStatus` to return a never-resolving promise so the callback is the only state source.

## ADR-034: Aspect-Ratio-Aware Framing Gate Threshold (Session 20)
**Context**: The `check_framing()` quality gate measured `bbox_width × bbox_height` in normalised [0,1] coordinates as the fraction of frame area, rejecting below 30%. Portrait (9:16) videos naturally produce smaller area fractions because the body's landmark width spans a smaller percentage of the tall frame. A well-framed deadlift video (person filling ~70% height, ~30% width) measured 21.2% and was rejected. All three test videos (squat 1080×1920, bench, deadlift) were rejected despite clearly filling the frame.
**Decision**: Scale the minimum framing threshold by aspect ratio for portrait videos: `min_threshold = 0.30 × (width / height)` when `width < height`, else `0.30`. For 9:16 portrait: threshold = 0.30 × 0.5625 = 0.169. In `backend/app/cv/quality_gates.py::check_framing()`.
**Consequences**: Landscape (16:9) threshold unchanged at 0.30 — no regression. Portrait videos with area fraction 0.17–0.30 now pass. A truly distant portrait subject (<17% area) is still rejected. The max threshold (80%) is NOT aspect-adjusted — too-close rejection works the same regardless of orientation. Future square (1:1) videos are unaffected (aspect = 1.0).

## ADR-035: Status Endpoint Includes quality_gate_result for Rejection Guidance (Session 20)
**Context**: The lightweight `GET /analyses/{id}/status` endpoint returned `{id, status, updated_at, detection_result}` but NOT `quality_gate_result`. The full detail endpoint (`GET /analyses/{id}`) had it, but the status page used the lightweight endpoint. When a video was quality-gate rejected, the status page showed "What to check:" with no specific guidance — the framing rejection message ("move closer to camera") was invisible to the user.
**Decision**: Added `quality_gate_result: dict | None = None` to `AnalysisStatusResponse` in `backend/app/schemas/analysis.py`. The status endpoint now includes the full quality gate result when present. No change to the full detail endpoint.
**Consequences**: The status page now renders specific failure messages from `quality_gate_result.checks[].user_message` on rejection. The exact-set key assertion in `test_get_status_response_has_no_extra_fields` was updated — future schema extensions to this response must update that test. The status response is no longer "minimal" — it carries the fields the status page actually needs. If the response grows further, consider splitting into `/status/summary` vs `/status/detail`.

## ADR-036: Langfuse Observability — Two-Flag Singleton, Best-Effort Tracing, eval_scores Key Standardisation (Session 23)
**Context**: P2-034 (FR-BRAIN-13) requires observability for the coaching pipeline — tracing retrieval source routing, coaching generation, and faithfulness evaluation. Four `TODO(P2-034)` markers existed in the worker and services. Separately, P2-033 (FR-AICP-16) requires standardised `eval_scores` keys including CoVe fields. The existing `faithfulness_score` key didn't match the SRS spec format `{"faithfulness": float, ...}`.
**Decision**: Langfuse client uses the async two-flag singleton pattern from `qdrant.py` in `app/services/langfuse_client.py` — `_initialized` bool + `_cache` value, so `None` (missing env vars) is cached and doesn't retry. Injected into `CoachingService.__init__` as `langfuse_client=None` (None = skip). Worker creates one client at start (single-client pattern, ADR-024). All Langfuse calls wrapped in try/except — never fail the pipeline. Renamed `eval_scores["faithfulness_score"]` → `eval_scores["faithfulness"]` to match SRS spec. Added `cove_verified` and `cove_iterations` to the same dict.
**Consequences**: Langfuse is fully optional — missing env vars produce a cached `None` with zero retries, so dev/CI run without it. The `faithfulness_score` → `faithfulness` rename is a breaking change for any code reading eval_scores by key name; grep confirmed no other references exist. Future P2-032 (retrieval metrics logging) can reuse the same Langfuse client singleton. The `eval_scores` dict now has 7 standardised keys — any new eval dimension must be added to both the worker block and the test assertions.

## ADR-037: Uvicorn Proxy Headers + FastAPI redirect_slashes=False (Session 24)
**Context**: Consent page made API requests to `https://api.spelix.app/api/v1/consent` (no trailing slash). FastAPI's `redirect_slashes=True` (default) generated a 307 redirect to `/consent/`, but uvicorn wasn't reading Caddy's `X-Forwarded-Proto: https` header, so the redirect used `http://` — triggering a mixed content error in the browser. Additionally, 307 redirects on POST requests lost the request body, causing 422 errors even after fixing the scheme.
**Decision**: (1) Add `--proxy-headers --forwarded-allow-ips *` to uvicorn CMD in Dockerfile so it trusts Caddy's forwarded headers. (2) Set `redirect_slashes=False` on the FastAPI app to eliminate trailing-slash 307 redirects entirely. (3) Change consent router routes from `"/"` to `""` so they match without trailing slash. Frontend URLs consistently omit trailing slashes.
**Consequences**: All API routes now match without trailing slashes — no 307 redirects. Any future route definition should use `""` not `"/"` for the root of a router with a prefix. The `--forwarded-allow-ips=*` is safe because the backend only listens on `127.0.0.1:8000` (Docker port binding), so only Caddy can reach it.

## ADR-038: Docker Privilege Escalation for Root SSH Access (Session 24)
**Context**: The `deploy` user had no passwordless sudo and root SSH login was disabled (`PermitRootLogin no`). The DO web console required a root password that was never set (droplet created with SSH keys only). Needed root to add swap and fix OOM.
**Decision**: Used Docker's host mount capability to (1) copy deploy's SSH key to root's `authorized_keys` via `docker run --rm -v /root/.ssh:/root_ssh -v /home/deploy/.ssh:/deploy_ssh alpine sh -c 'cp ...'`, and (2) edit `/etc/ssh/sshd_config` to change `PermitRootLogin no` → `PermitRootLogin prohibit-password` via the same Docker mount approach, then restart sshd via `docker run --rm --pid=host --privileged alpine nsenter -t 1 -m -u -i -n -- systemctl restart ssh`.
**Consequences**: Root is now accessible via SSH with key-only auth. The `deploy` user being in the `docker` group is equivalent to root access (Docker daemon runs as root). This is acceptable for a single-developer project; in a multi-tenant environment, Docker group membership should be restricted.

## ADR-039: Seed Corpus Uses AI-Synthesized Paper Text, Not Verbatim PDFs (Session 25)
**Context**: P2-007 (FR-RAGK-02) requires ≥10 research papers per exercise seeded into the `papers_rag` Qdrant collection. Downloading and parsing actual PDFs via Docling adds significant manual effort and legal considerations (copyright). The RAG pipeline needs populated collections to test end-to-end.
**Decision**: Seed papers in `scripts/seed_research_papers.py` use real metadata (titles, authors, DOIs, years, quality tiers from actual published studies) but AI-synthesized summary text representing each paper's key findings and coaching implications. Coach Brain entries in `scripts/seed_coach_brain.py` are original expert-level coaching content authored for Spelix. Both scripts are idempotent with `--dry-run` mode. Deferred task D-017 tracks replacing summaries with real full-text via Docling.
**Consequences**: The RAG pipeline is fully testable end-to-end with realistic metadata and topically accurate content. However, retrieval quality will be lower than with real full-text — summaries are 80-150 tokens vs 2000-8000 for actual papers, producing fewer chunks (36 total vs potentially 200+). Some DOIs may not resolve exactly. D-017 should be prioritized before any retrieval quality evaluation (Phase 4 eval metrics will be meaningless against synthetic text).

## ADR-040: analysis_expert_reviews Table Name (Session 26)
**Context**: Migration 004 created `expert_annotations` for chunk-level RAG provenance (document_id, chunk_index, chunk_text, embedding_model). Phase 2 FR-EXPV-04 requires analysis-level expert review annotations (analysis_id, annotator_id, coaching_quality_score, issues_identified). These are fundamentally different entities.
**Decision**: Create a new table named `analysis_expert_reviews` instead of reusing or renaming `expert_annotations`. The SRS uses the term "expert_annotations" but doesn't mandate the table name.
**Consequences**: Two tables with distinct purposes coexist: `expert_annotations` (chunk provenance) and `analysis_expert_reviews` (expert review workflow). No migration conflict, no schema confusion. Future code can reference each by its purpose.

## ADR-041: Expert Reviewer Role System — Dual Access (Session 26)
**Context**: FR-EXPV-01 requires expert reviewer portal protected by role check. Admins should also be able to use the expert portal for review work without needing a separate login.
**Decision**: `get_expert_reviewer_user` dependency accepts both `role === "expert_reviewer"` and `role === "admin"`. The role is stored in Supabase JWT `user_metadata.role`.
**Consequences**: Admins can do review work directly. The admin expert queue view (FR-ADMN-07) can link into the expert portal detail view. No separate role switching needed.

## ADR-042: Signed Read URLs for Private Storage Artifacts (Session 26)
**Context**: Supabase Storage bucket `videos` is private. The backend stored raw storage paths (`artifacts/{id}/annotated.mp4`) in the DB and returned them in the API response. The frontend used these as `<video src>` and `<img src>`, which resolved to relative URLs on spelix.app — not valid Supabase Storage URLs.
**Decision**: `StorageService.create_signed_read_url(path, expires_in=3600)` generates 1-hour signed read URLs. The `GET /analyses/{id}` endpoint signs `annotated_video_path`, `plot_path`, and `pdf_path` before returning `AnalysisDetail`. Graceful degradation: if signing fails, the raw path is returned (no 500). Frontend needs no changes.
**Consequences**: Artifacts are accessible in the browser via HTTPS signed URLs. URLs expire after 1 hour — the page must be refreshed for long-lived sessions. The frontend CLAUDE.md already documented this pattern: "Use signed read URLs returned by the API. Never construct Storage URLs manually on the client."

## ADR-043: H.264 Re-encoding for Browser Video Playback (Session 26)
**Context**: `cv2.VideoWriter.fourcc(*"mp4v")` writes MPEG-4 Part 2 codec, which browsers do not support for inline `<video>` playback. The annotated video appeared as a black frame in Chrome/Firefox/Safari despite having a valid signed URL and correct file size.
**Decision**: Write annotated frames to a `.raw.mp4` file with `mp4v` codec (universally available in opencv-python-headless), then re-encode to H.264 via `ffmpeg -c:v libx264 -preset fast -crf 23 -movflags +faststart`. ffmpeg is already in the Docker image (installed for ffprobe codec validation). Fallback: if ffmpeg is unavailable, the raw mp4v file is used as-is (downloadable but won't play inline).
**Consequences**: Adds ~30s to pipeline time for the ffmpeg re-encode step. Video files are slightly smaller (H.264 is more efficient than mp4v). `-movflags +faststart` enables progressive download. All modern browsers can now play the annotated video inline.

## ADR-044: Squat Rep Detection Threshold Adjustment (Session 26)
**Context**: Rep detection used a squat depth threshold of 90° (effective 85° after 5° hysteresis) and standing threshold of 160° (effective 155°). Parallel-depth squats (~90–110° hip angle) were silently skipped because the smoothed signal (Savitzky-Golay window=7) never dipped below 85°. Athletes who didn't fully lock out between reps (hip angle ~150°) had reps merged.
**Decision**: Lower squat depth threshold to 110° (effective 105°) and standing threshold to 150° (effective 145°). Added both values to `thresholds_v1.json` for future tunability. Bench and deadlift thresholds unchanged.
**Consequences**: Parallel-depth squats are now detected. Quarter squats (>120° hip) are still correctly rejected. Rep count increased from 2 to the actual count for test videos with moderate depth. The Savitzky-Golay filter was NOT changed — only thresholds.

## ADR-045: Host-Mounted Resource Directories Use CWD-Based Path Resolution (Session 27)
**Context**: `PDFService.__init__` resolved the WeasyPrint template via `os.path.dirname(__file__) + "../../../reports/templates/analysis_report.html"`. Locally this walks to the repo root; inside the production Docker container, `__file__` is `/app/app/services/pdf.py` so `../../..` walks to `/` and produces `/reports/templates/...` — which doesn't exist. PR #37 added the bind mount `./reports/templates:/app/reports/templates:ro` to match the existing `./config:/app/config:ro` pattern, but the code still resolved to the wrong path and emitted `FileNotFoundError: PDF template not found at /reports/templates/analysis_report.html`.
**Decision**: Resolve template paths via a priority list mirroring `ThresholdConfig` (ADR-046a): (1) `__file__`-relative path (works locally), (2) `os.getcwd()`-relative path (works in Docker where CWD is `/app` and the bind mount lands at `/app/reports/templates/`). See `_CANDIDATE_PATHS` in `backend/app/services/pdf.py`.
**Consequences**: Any host directory bind-mounted into `/app/<name>` inside the container — whether templates, fixtures, or future read-only assets — can now be resolved by the CWD-relative candidate. Both dev (uv run from `backend/`) and prod (Docker CWD=`/app`) work with the same code path. New code adding similar host-mounted resources should adopt this two-candidate pattern rather than adding more Docker-specific plumbing.

## ADR-046: Qdrant Payload Indexes Are Idempotent on Existing Collections (Session 27)
**Context**: `QdrantClientWrapper.ensure_collections()` created the `coach_brain` collection with keyword payload indexes on `exercise` and `status` only when the collection did not already exist. When a collection was created by an earlier code version without the indexes (or when an index was manually dropped), subsequent queries filtering by `exercise` raised `400 Bad Request: Index required but not found for "exercise"`. The production `coach_brain` collection was in exactly this state with 24 seed points.
**Decision**: `_ensure_collection` always calls `_create_brain_indexes` when `add_brain_indexes=True`, regardless of whether the collection already existed. `_create_brain_indexes` wraps each `create_payload_index` call in try/except so duplicate-index errors from Qdrant are logged and swallowed. See `backend/app/services/qdrant.py:_ensure_collection` and `:_create_brain_indexes`.
**Consequences**: `ensure_collections()` is now self-healing — re-running it against an existing collection with or without indexes produces the correct final state without raising. Every worker startup becomes an opportunity to correct index drift. The test suite (18 tests in `test_qdrant_client.py`) continues to pass because the added try/except only activates on duplicate-index errors that unit tests never produce.

## ADR-047: Supabase Realtime Requires Both Publication Membership and REPLICA IDENTITY FULL (Session 27)
**Context**: FR-RESL-13 requires the Analysis Status page to receive live UPDATE events via Supabase Realtime. Session 27 E2E testing found the page stuck on "Preparing to analyse…" forever while the DB row progressed through `quality_gate_pending → processing → completed`. Root cause: the `supabase_realtime` publication had zero tables. The Realtime hook subscribed successfully (no `CHANNEL_ERROR`) but received no events. Secondary issue: `REPLICA IDENTITY DEFAULT` sends only PK + modified columns for UPDATEs, but the frontend hook reads `payload.new.detection_result` and `payload.new.quality_gate_result` which aren't always in the modified set.
**Decision**: Migration `007_enable_realtime_analyses.py` applies two DDL statements, both wrapped in idempotent `DO $$ ... $$` blocks: (1) `ALTER PUBLICATION supabase_realtime ADD TABLE public.analyses`, (2) `ALTER TABLE public.analyses REPLICA IDENTITY FULL`. Both were also applied one-off via the Supabase SQL console during debugging; the migration captures that state as code so any fresh Supabase project is reproducible.
**Consequences**: Status page updates live without the 10s REST polling fallback. REPLICA IDENTITY FULL increases WAL volume for `analyses` UPDATEs (full row vs PK+changed), acceptable at our write volume. Any future table that needs Realtime push must add BOTH: publication membership AND REPLICA IDENTITY FULL — this pattern applies to `rep_metrics`, `coaching_results`, `chat_messages` if/when we add live subscriptions for those. Never assume "the table is in Supabase, so Realtime works" — always verify via `SELECT * FROM pg_publication_tables`.

## ADR-048: Droplet Sizing for L2 Private Beta — Basic 2 vCPU / 4 GB (Session 28)
**Context**: Session 27 E2E testing experienced SSH banner timeouts and apparently-stuck analyses on the 1 vCPU / 2 GB droplet (`s-1vcpu-2gb`, $12/mo). Session 28 systematic investigation disproved the initial "CPU starvation" hypothesis using Pressure Stall Info: CPU PSI avg300=0.00 (zero pressure) but **memory PSI avg300=3.57% at idle** (7× over healthy threshold), with 7.01 million swap pages written over 32 hours of uptime (~27 GiB total = 13× swap turnover) and kswapd0 permanently active. The session 24 swap fix (ADR-038) had silently converted hard OOM-kills into chronic thrashing, which then caused SSH's fork to stall on memory allocation during analysis. Datadog agent was discovered consuming 181 MB / 9% of RAM with no active use.
**Decision**: Resize droplet to `s-2vcpu-4gb` ($24/mo, +$12/mo) via `mcp__digitalocean__resize-droplet` with `ResizeDisk=true`. Snapshot taken pre-resize (id 3139971337, name `spelix-pre-resize-session27`) as rollback insurance. Datadog agent + installer purged via root SSH. Post-resize E2E confirmed: memory peak 2.2 GiB / 3.8 GiB (57%), memory PSI full=0 across all windows, CPU PSI full=0, swap usage 524 KB during full analysis (vs session 27's heavy paging), MediaPipe now utilises both cores (111.87% CPU), analysis 150s vs 200s+ on single-vCPU.
**Consequences**: Infrastructure cost rises to $24/mo ($288/yr) — acceptable beta burn per STRATEGY.md. Single-user analyses now run with ~43% memory headroom; 2–3 concurrent analyses absorbable without swap hitting. Workers using both vCPUs means MediaPipe Tasks API's internal thread-pool is no longer starved, producing the ~25% speed-up. The 2 GiB swap is retained as insurance but no longer load-bearing. For any future need (>50 concurrent beta users, Phase 3 LangGraph agent with larger context), next upgrade target is `s-4vcpu-8gb` at $48/mo. Do not re-install Datadog unless a metrics dashboard is actively wired up and consuming its data.

## ADR-049: Landing V1 Built by Adapting a Framer Template, V1/V2 Split (Session 29)
**Context**: STRATEGY.md v3 set a hard gate for Landing V1 live on prod by end of Day 2 of the 19-day L2 sprint (2026-04-15) while a parallel Track B (expert PDF upload wiring) used the same days. Building a custom marketing surface from scratch under a ~6-hour total-dev budget was not compatible with also running the expert onboarding work in parallel.
**Decision**: Replicate the Framer "EvoTrack" template (AI/Smart-Tech landing) section-by-section: its dark-photo-hero + chartreuse-accent aesthetic, generous whitespace, accordion + card-grid + rounded-CTA-block primitives. Everything visual is copied; 100% of text is replaced with Spelix content from `landing-page/landing-page-plan.md` §6. Ship **V1 = 6 sections** (Hero, Problem, HowItWorks, Differentiators, Privacy, FinalCta) by Day 2; **V2 = Four Dimensions + Roadmap** deferred to Sprint BETA (May 4-14). Design tokens (chartreuse `#d5ff45`, Host Grotesk + DM Sans, container 1128px) committed as Tailwind 4 `@theme` in `frontend/src/index.css`. Hero-bg photo deferred to V2 polish — current hero uses a subtle chartreuse radial-gradient on `surface-dark` so the component works without an external WebP. ResultsPage screenshot captured via Playwright MCP against live prod.
**Consequences**: Total implementation landed in ~5.5 hrs (within §11 guardrail). 256 frontend tests pass (30 new for landing); 1436 backend tests pass (15 new for beta-request endpoint); 91% coverage preserved. Brand tokens are scoped to landing components only — product routes (`/upload`, `/results/:id`, `/history`) keep the existing slate/blue palette via explicit `className` overrides, avoiding a palette fork. The Framer template export itself is removed from the repo pre-PR-merge (licence-uncertain 435 KB HTML); design-tokens.json + extract-*.js are retained as historical reference. Any future landing iteration (V2, post-beta rebrand) can re-run the extract scripts against a new template URL.

## ADR-050: Manual Beta-Request Approval Flow Through Sprint BETA — No Auto-Gate (Session 29)
**Context**: The landing-page email capture (`POST /api/v1/beta/requests` + migration 008's `beta_requests` table) needs a policy for how invites actually get sent. Options: (a) auto-approve every submission → risks bot-flood + unvetted user quality; (b) full admin UI with approve/reject/reason → costs days of Tier 2 admin-panel work; (c) manual SQL/dashboard approval + transactional-email send → costs minutes, founder-eyeballs every applicant.
**Decision**: Private beta stays **manual-approval** through at least Sprint BETA (May 4-14) per STRATEGY.md v3. Anonymous POST captures email + source + GDPR consent to `beta_requests` with `status='pending'` (RLS enforces this on anon writes). Founder reviews the queue daily via Supabase SQL or the existing admin panel's future beta card (follow-up PR). `POST /api/v1/admin/beta/requests/{id}/approve` + transactional-email invite is a **follow-up PR, not V1**. The endpoint returns 409 on duplicate email by design — users who already submitted get a clear "you're on the list" message rather than silently creating duplicates. No automatic approval rule or rate-based gate is planned for L3 (2026-05-15) or L4 (2026-07-01) in v3. If submission volume exceeds ~30/week manual review becomes the bottleneck and we reconsider.
**Consequences**: Zero risk of bot-spam reaching a provisioned account in V1. Founder gets a selection filter and a qualitative read on every first-week signup (useful for product feedback). Admin infra cost deferred — no admin UI, no transactional email provider selection, no invite-token signup flow for V1. Any landing-page submission is a **lead**, not a **user**: the `auth.users` row is created only after the founder approves and the invitee follows the (future) `/signup?invite=TOKEN` link. The 409-on-duplicate-email is an intentional email-enumeration trade-off for better UX; flagged by `spelix-security-reviewer` as MEDIUM and accepted.

## ADR-051: PostHog in Cookieless / Memory-Persistence Mode to Avoid GDPR Cookie Banner (Session 29)
**Context**: STRATEGY.md v3 Day 1-2 required `landing_view` + `landing_email_submit_{attempt,success,error}` events for the landing page. Standard PostHog init uses localStorage for a persistent `$device_id` cookie and captures `$ip` — which under GDPR requires an explicit cookie-consent banner before the first event fires. Cookie banners hurt conversion on a beta-recruitment surface and add a compliance surface (banner implementation, consent-log storage, withdrawal flow) we don't need this week.
**Decision**: `src/lib/posthog.ts` initialises `posthog-js` with `persistence: "memory"` (no localStorage/cookie — each page load gets a fresh anonymous session), `ip: false` + `property_blacklist: ["$ip"]` (IP never captured), `autocapture: false` (we only fire explicit, hand-instrumented events — no click/pageview autocapture), `disable_session_recording: true`. Events fired: `landing_view` (LandingPage mount, anon only) + `landing_email_submit_{attempt,success,error}` from both Hero and FinalCTA forms with `cta_location` + `email_domain` (never full email).
**Consequences**: No cookie banner needed on landing. PostHog still gives us attempt/success/error funnel telemetry, per-CTA split, email-domain distribution. Trade-offs vs persistent-cookie mode: no cross-session user stitching (memory persistence resets on every page load), no auto-captured raw clicks, no session replay. For a private-beta marketing surface these are acceptable — we care about funnel volume + CTA attribution, not individual user paths. If this were a full acquisition funnel we'd revisit. The `.env.example` ships both `VITE_POSTHOG_KEY` and `VITE_POSTHOG_HOST` (default `https://eu.i.posthog.com`); the landing page is a no-op when `VITE_POSTHOG_KEY` is unset.

## ADR-052: BetaRequest.email 201-Response PII Removal + UNIQUE Index on Model (Session 29)
**Context**: Two defensive fixes landed during Landing V1 merge. (1) `BetaRequestResponse` originally echoed the submitted `email` field in the 201 response body — flagged CRITICAL by `spelix-security-reviewer` because observability tools (Sentry, Loki breadcrumbs) routinely index response payloads and an anonymous public endpoint should not write PII there (the client already has the email from form state). (2) The `uq_beta_requests_email` UNIQUE index existed only in alembic migration 008. The CI workflow uses `scripts/create_test_tables.py` (`Base.metadata.create_all`) instead of alembic — because the CI Postgres lacks Supabase's `auth` schema required by migration 002's RLS policies — so the integration test `test_create_duplicate_email_raises_integrity_error` passed locally (post-migration) but failed in CI with `DID NOT RAISE IntegrityError`.
**Decision**: (1) Remove `email: EmailStr` from `BetaRequestResponse` on both backend (`app/schemas/beta_request.py`) and frontend (`src/api/beta.ts`); the 201 body returns `{id, status, created_at}` only. Assertion in `test_beta_request_api.py::test_valid_submission_returns_201` updated to `assert "email" not in body`. (2) Add `Index("uq_beta_requests_email", "email", unique=True)` to `BetaRequest.__table_args__`. Both the model-declared index and the migration DDL produce the same end state — zero drift. Add regression-guard unit test `test_beta_request_email_has_unique_index_on_model` so a future edit that drops the `Index(...)` declaration fails locally, not only in CI.
**Consequences**: Any future SQLAlchemy model whose migration declares a UNIQUE/ordinary index must mirror that declaration on the model itself or CI's `create_all` DB will drift from prod. The pattern now exists as a precedent (see `beta_request.py` `__table_args__`). RLS policies remain migration-only because CI's Postgres can't host Supabase's `auth` schema — this is the same intentional divergence documented in `scripts/create_test_tables.py`'s docstring. The PII removal sets a "never echo user-submitted identifiers in public-endpoint response bodies" precedent across the backend — next review target if we add more public POST endpoints is `POST /api/v1/consent/anonymous-acknowledge` if that ever exists.

## ADR-053: Framing quality gate samples peak bbox across whole clip, not first 5 frames (Session 33)
**Context**: `check_framing` in `backend/app/cv/quality_gates.py:295` averages bbox area over `landmarks_per_frame[:5]`. For squat/bench the first 5 frames are the standing/lying start position — a representative sample. For deadlift those frames are the bent-over setup at the bar, where torso vertical extent is roughly halved, so the metric undershoots even when the rest of the rep is well framed. Surfaced 2026-04-15 during L2 Day 5 prod-watch: `atharva-deadlift.mp4` (analysis `8b5714ee-ac63-464d-8ff4-339e502885d9`) measured 0.1415 vs the portrait-scaled 0.1673 threshold (FR-CVPL-04). Prior D-013 / PR #26 scaled the threshold by aspect ratio for portrait video — this ADR complements that fix by addressing the temporal bias instead of the spatial bias.
**Decision**: Replace the `[:5]` window in `check_framing` with **peak (or 90th-percentile) bbox area across 20–30 evenly-spaced frames over the full clip**. Gate passes if the lifter is correctly framed at any point in the rep. Keep `_FRAMING_MIN_FRACTION=0.30`, the D-013 aspect scaling for portrait, and the `_LANDMARK_VISIBLE_THRESHOLD=0.50` visibility filter. Tracked as D-032; implementation deferred to the Day 5–9 buffer window of the L2 sprint.
**Consequences**: Gate becomes tolerant of short transient mis-framing (bent-over setup, brief walkout, rerack) but remains strict against videos where the lifter is never well framed. The extra pose-landmark decode across more frames is negligible next to MediaPipe's per-frame inference cost. Regression test must use a synthetic deadlift-shape fixture — narrow bbox in early frames, wide bbox in late frames — to prevent a future reversion to the `[:5]` window. Does not affect the separate resolution gate (`check_minimum_resolution`), which remains the authoritative guard against sub-720p inputs.

## ADR-054: Framing + single-person gates — separate occlusion/orientation bug from temporal bias (Session 33)
**Context**: Direct MediaPipe diagnostic run on Session 33 fixtures surfaced two failure modes independent of ADR-053's `[:5]` temporal bias. (1) MediaPipe BlazePose Heavy returns NO_POSE for frames 0–3 of `atharva-squat.mov` (analysis `cd459701-749a-4ba6-b1b2-b96f7b6e9a98`) when the lifter's upper body is obscured by 45lb plates at the rack — so even a future frame-skipping `check_framing` must drop NO_POSE frames before averaging. (2) The visible-landmark-bbox metric (landmarks with `sigmoid(vis) > 0.5`) undershoots body-in-frame ratio when joints are equipment-occluded: `atharva-bench.mov` peak bbox = 0.097 vs the `atharva-bench-no-weight.mov` same-camera-angle control at 0.337, difference being plates in scene. `check_single_person` exhibits a sibling first-10-frames bias in which MediaPipe's single-pose tracking hops to a background bystander, producing ≥15% hip-centroid jumps in consecutive frames (2 jumps on bench, 3 on squat vs 0 on bench-no-weight).
**Decision**: Expand D-032 scope beyond ADR-053's peak-bbox temporal fix to evaluate three candidate mitigations in an exploratory branch before committing one — (a) all-33-landmark bbox ignoring the visibility filter; (b) `presence` score instead of `visibility`; (c) per-exercise thresholds keyed off `exercise_type`. Pick the option that passes the 3 atharva-* fixtures AND the existing sub-720p / lifter-out-of-frame regression tests. Do NOT globally lower `_FRAMING_MIN_FRACTION`. Apply analogous change to `check_single_person` — replace the `[:10]` consecutive-jump count with a sustained-tracking signal over a longer window (e.g., cluster hip centroids and reject only if multiple distinct clusters persist).
**Consequences**: Gate becomes tolerant of equipment-occluded joints and busy-gym bystanders, at the cost of admitting videos where the lifter is legitimately not the primary subject — regression tests must add synthetic fixtures for (a) well-framed no-plate, (b) well-framed with plates at rack, (c) lifter genuinely out of frame, (d) actual two-lifters-in-frame. Affects FR-CVPL-04 (framing) and FR-CVPL-06 (single-person). Related backlog: D-032 (now covers both checks).

## ADR-055: streaq `process_analysis` task timeout raised to 900s (restore ADR-BRAIN-04 Phase-2 intent) (Session 33)
**Context**: ADR-BRAIN-04's Phase-2 update raised ARQ `job_timeout` from 300 → 900 ("bumped from 300 for ingestion") so CV analyses and Docling ingestion could complete on the 2-vCPU droplet. The ARQ → streaq migration (PR #48, session 31) wrote `@worker.task(timeout=300)` on every streaq task in `backend/app/workers/streaq_worker.py:144,156,170` with a comment claiming "drop-in parity with ARQ's WorkerSettings.job_timeout" — factually wrong, it silently reverted ADR-BRAIN-04's Phase-2 bump. Regression surfaced 2026-04-16 during session 33 prod-watch: `atharva-bench.mov` (1080×1920 @59fps, 23s, 1382 frames) timed out at 5:00, leaving analysis `2158536a-8df6-4fa0-8d68-b01129c0aadb` stranded in `quality_gate_pending`. `atharva-squat.mov` completed at 4:21 — within the 5-min limit only because the clip is slightly shorter. MediaPipe BlazePose Heavy on 2 vCPUs consistently costs ~150–180 ms/frame; a 20–30 s 59fps clip takes 3–7 minutes just for pose extraction before quality gates, rep detection, or coaching run.
**Decision**: Raise `process_analysis` task timeout from 300 → 900 seconds in `streaq_worker.py:144`. Keep `cascade_consent_withdrawal` and `ingest_paper` at 300s (both sub-second jobs in the common case). Update the adjacent comment to reference ADR-BRAIN-04's Phase-2 bump, not "drop-in parity". Do NOT introduce an analysis-specific queue — single-worker `max_jobs=1` is preserved per the MediaPipe 350 MB memory constraint.
**Consequences**: Coaching-stream startup delay becomes user-visible for ~6–7 min on large clips; acceptable for Phase 1–3 (no SLO set for analysis completion). Extended-mode clips up to 120s will still need a second bump (projected ~12–18 min) — decide at Phase 3 if `SPELIX_EXTENDED_MODE` sees real use. A secondary follow-up (tracked in D-033, not blocking this PR): timed-out `process_analysis` tasks leave analyses in `quality_gate_pending` with no cleanup — a nightly sweep or a streaq `finally`-style handler would help.

## ADR-056: Analysis pipeline memory budget on 4 GB droplet — post-MediaPipe OOM (Session 33)
**Context**: Immediately after ADR-055 lifted the 300 s timeout ceiling, a new failure mode surfaced on `atharva-bench-no-weight.mov` (37 MB, 1080×1920 @ 59fps, 22.8 s, 1352 frames). Analysis `4e19c62b-91c2-4f01-b269-3ac51e05db3f` passed the quality gate (predicted from local MediaPipe: peak bbox 0.337, 0 hip-centroid jumps), then the worker process **resident memory climbed from ~0.5 GB to 3.2 GB** in the post-gate phase (annotation video encoding + rep detection + Anthropic coaching + artifact upload), host RAM dropped to 99 MB free with 1.3 GB of 2 GB swap in use, and the worker process **exited with code 0** at ~7:50 elapsed — `docker inspect` reported `oomKilled=false`, so this is not a cgroup-level OOM kill. Deterministic across both attempts (initial + streaq retry). Distinct from D-026 (which covered concurrent-analyses OOM on the then-2 GB droplet and was resolved by resizing to 4 GB in ADR-048) — this is a **single-analysis memory blowup** on what is now our production droplet sizing.
**Decision**: No code fix in this PR. Log D-034 and track for investigation post-L2. Prior PR (ADR-055) stands — the timeout fix unblocks clips that fit within the 4 GB budget (`atharva-squat.mov` at 33 MB, 20.6 s completed successfully at 4:21 before the PR — it rejected at quality gate before reaching the memory peak). Short-term workaround for session 33 prod-watch: trim the fixture to 10 s so the post-gate phase stays under the memory ceiling. Long-term fix paths ranked by likely ROI — (a) downscale annotation video to 720p before H.264 encode; (b) stream-encode annotation frame-by-frame instead of buffering the full clip in OpenCV's VideoWriter; (c) free the `landmarks_per_frame` list after rep detection and before annotation generation; (d) skip annotation for clips above a duration threshold (SPELIX_MAX_ANNOTATION_SECONDS env var); (e) resize droplet to 8 GB (CapEx path, least clever).
**Consequences**: Real-user phone clips filmed at 1080p or higher will reliably OOM in this window until the fix lands — the beta smoke test in Week 4 must either use trimmed clips or accept failure rate. This escalates D-034 to a must-fix before opening beta beyond the kin expert. Phase 3 Batch 3's smoke-test plan (3–5 trusted test users) is at risk if their phones film at 1080p@60 or higher — verify with each tester before their first upload, or do the fix-path (a)+(c) bundle as a pre-smoke PR. Does not affect `atharva-squat.mov` class of clips that reject at the quality gate before the memory peak.

## ADR-057: Streaming barbell tracking eliminates 8.4 GB peak allocation (Session 34)
**Context**: ADR-056's "ranked fix paths" covered annotation-phase memory but missed the actual root cause. Session 34 E2E-verified PR #57 (fix path (a) downscale annotation + (c) `del frames`): worker RSS showed only 600-800 MB, but the worker still exit-137'd at ~8 min on `atharva-bench-no-weight.mov`. `docker inspect` this time showed the kernel SIGKILL signature — `extract_frames(video_path)` in `pose_extraction.py:189` was allocating a `list[np.ndarray]` of 1352 × 1080×1920×3 uint8 = **~8.4 GB virtual**, overwhelming the 4 GB droplet even though steady-state RSS stayed low. `del frames` in `pipeline.py:536` (PR #57) only released memory AFTER the peak. The fix path (b) from ADR-056 ("stream-encode frame-by-frame") was the correct framing, but it applied to barbell tracking, not annotation.
**Decision**: Add `track_barbell_from_video(video_path)` in `barbell_detection.py:84` that reads frames one at a time via `cv2.VideoCapture.read()` and calls `detect_barbell_in_frame` per frame, appending centroids. Update `pipeline.py:Step 9` to call this directly — eliminating both `extract_frames(video_path)` and the `del frames` mitigation. Max resident ~6 MB (one 1080p frame) instead of ~8.4 GB virtual. Keep the existing `track_barbell(frames: list[np.ndarray])` for unit-test fixtures (synthetic numpy arrays).
**Consequences**: D-034 OOM closed — E2E verified 2026-04-16 with `atharva-bench-no-weight.mov`: worker RSS rock-steady at 639 MB across the full 15-min `process_analysis` timeout. No SIGKILL, no `extract_frames` peak, no swap thrashing. **Surfaced a new bottleneck (D-035)**: MediaPipe BlazePose Heavy on 2 vCPUs cannot finish pose extraction on 1352 1080p frames within 900 s — the task times out cleanly (no OOM, just slow). Fix paths for D-035: downscale frames to 720p before pose extraction (mirrors the annotation 720p cap from PR #57), or switch to BlazePose Lite for 1080p, or raise the task timeout further. ADR-056's fix-path ranking was wrong — (b) streaming was the root fix, (a) annotation 720p is nice-to-have, (c) `del frames` became dead-weight with streaming. Leaving PR #57's fixes in place for future clip-size-safety even though they're now partially redundant.

## ADR-058: D-035 instrumentation tier — measure first, optimize second (Session 35.5)
**Context**: Sessions 33 → 34 → 35 chased the analysis-pipeline performance bug (`process_analysis` timeout on full-length 1080p@59fps clips) through three layers of guess-and-check: timeout bump (ADR-055), memory cap (ADR-056), streaming barbell (ADR-057), and 720p pose cap (PR #61). Each fix shipped without per-stage telemetry, so each subsequent failure mode surfaced as a surprise. Session 35 root-cause benchmarking finally measured per-stage cost on the failing clip in the worker container and discovered (a) BlazePose Heavy is ~150 ms/frame regardless of input resolution, (b) `RunningMode.IMAGE` is ~20% slower than `RunningMode.VIDEO`, (c) frame striding helps less than expected because `cv2.read()` dominates non-inference cost, and (d) **bench predicts ~290 s for pose extraction but production hits 900 s without finishing — a 3× unexplained gap**. Without instrumentation we cannot identify what amplifies in production.
**Decision**: Ship a four-part Tier 1 fix together: (A) add `analyses.timing_json` JSONB column + `StageTimer` context manager around every pipeline step so production has per-stage wall-time data on every analysis going forward, (B) switch `extract_landmarks` from `RunningMode.IMAGE` → `RunningMode.VIDEO` (5-line code change, ~20% inference speedup, within ±1° angle tolerance per CLAUDE.md), (D) raise streaq `process_analysis` timeout from 900 s → 1800 s as safety net while telemetry accumulates, (E) cap upload duration at 60 s free / 120 s Extended Mode, enforced both client-side (HTML5 `<video>.duration`) and server-side (ffprobe defense-in-depth in the worker). Skip in-loop frame-stride (Tier 2 fix C) and ffmpeg fps-normalize for now — both touch rep-detection and angle-smoothing math, which is SaMD-adjacent and should not be modified blind. Re-evaluate C after one week of timing_json data.
**Consequences**: Operations gain per-analysis stage breakdowns from day one (we will know within 24 hours where the 3× bench-vs-prod gap actually lives). Pose extraction gets a free ~20% speedup with low test churn. The 1800 s safety net keeps a stuck job from killing UX without hiding slowness — the next E2E shows actual stage durations, not just "timed out". Real-user clips longer than 60 s are now blocked at upload time with a clear message instead of running for many minutes and failing — this is intentional friction for L2 beta scope. **GPU offload deferred** — see D-036 for trigger conditions. **Telemetry-first principle** (see ADR-059) becomes the default for any future pipeline tuning.

## ADR-059: Telemetry-first principle for CV pipeline tuning (Session 35.5)
**Context**: Three sessions of fix-by-guess (ADR-055, ADR-056, ADR-057, PR #61) accumulated technical debt without resolving the underlying timeout. Each fix addressed a symptom that turned out not to be the root cause. The cost was ~6 hours of session time, 4 PRs, and a deferred private beta milestone.
**Decision**: For any future change to `app/services/pipeline.py`, `app/cv/pose_extraction.py`, `app/cv/barbell_detection.py`, `app/cv/artifact_generation.py`, or any other CV pipeline component motivated by performance: REQUIRE production timing_json data (post-ADR-058) showing the targeted stage is in the top 3 contributors before merging. The exception is correctness fixes (a stage produces wrong output) — those proceed normally. This rule is enforced by the spelix-cv-engineer agent in code review.
**Consequences**: Slower iteration on perf hunches, but no more ADR chains where the next fix invalidates the prior one's framing. The cost of one additional E2E run with telemetry is ~5–15 minutes; the cost of a wrong fix is multiple sessions. Net positive even on the second iteration.

## ADR-060: Downscale frames to 480p before HoughCircles to close D-035 (Session 39)
**Context**: Per-stage telemetry from ADR-058 (session 38, analysis `fc318bc3-3cf9-4f0e-85ee-0f5d61cb77b1`) revealed `barbell_tracking` consumed **1,465,647 ms (24.4 min)** on a 22.8 s / 1338-frame / 1080p@59fps bench clip — **83.4 %** of total pipeline wall time and ~5× the entire pose-extraction cost. Sessions 35.5–38 had repeatedly mis-attributed the bottleneck to BlazePose (ADR-058) when the real cost centre was `cv2.HoughCircles` inside `detect_barbell_in_frame` at source resolution with radius range 10–100. Session 39 worker benchmark (`backend/bench_barbell.py` mode 2 pre-fix) clocked **1037.6 ms/frame** on the same clip — within 5 % of the telemetry-derived number, confirming the hypothesis. Mode 1 (I/O only) was 89.7 ms/frame, so detection alone was **~947 ms/frame**. ADR-059's telemetry-first gate was satisfied before this ADR was written.
**Decision**: Introduce `_downscale_for_detection(frame, max_dim=480)` in `backend/app/cv/barbell_detection.py` that resizes every frame so its longest side is ≤ 480 px via `cv2.INTER_AREA`, returns `(scaled, scale_factor)`. Modify `detect_barbell_in_frame` to run the downscale → `cvtColor` → `GaussianBlur` → `HoughCircles` chain on the scaled frame with radii scaled to 480p (`_MIN_RADIUS_480P=3`, `_MAX_RADIUS_480P=40`, `_MIN_DIST_480P=12`), then multiply the detected centroid by `scale_factor` before return — callers continue to see source-resolution pixel coordinates unchanged. The existing streaming-per-frame loop from ADR-057 (session 34 memory fix) stays intact; this ADR is additive on top of it. Source-resolution constants `_MIN_DIST=50`, `_MIN_RADIUS=10`, `_MAX_RADIUS=100` are preserved as historical reference. FR-BDET-06 >50 %-detection-rate landmark fallback in `pipeline.py` is unchanged.
**Consequences**: Mode 2 post-fix = **99.6 ms/frame** (10.4× speedup); mode 3 at 480p = 99.4 ms/frame (identical — detect function IS the 480p path now). Detection rate preserved at 1338/1338 = 100 % on the bench clip. Barbell-tracking stage wall time drops **1388 s → 133 s (23.1 min → 2.2 min)**. Total pipeline on this clip projects to ~430 s, well under the 600 s target — which unblocks lowering `streaq` `process_analysis` task timeout from 1800 s back to 900 s (closes D-035, feeds into D-036 trigger condition). `_MAX_RADIUS_480P=40` (vs the algebraically-correct 25) preserves compatibility with the existing `TestDetectBarbellInFrame::test_detects_circle_centroid` 640×480 / radius-40 fixture — radius range was widened from 22 to 37 radii, adding ~1.7× HoughCircles cost vs a tighter range, but absolute cost (~10 ms/frame detection overhead above 90 ms I/O) is far below the I/O floor so further tightening is not justified (~13 s max savings on a 133 s stage). Sub-pixel error from scale-back is ≤ 4 source px at 1080p, below MediaPipe landmark noise. `test_streams_centroids_matching_track_barbell` tolerance widened 1 px → 5 px (mp4v codec round-trip drift × 1.33× scale-back = unreachable at 1 px). **Post-beta**: if template-matching or YOLO replace HoughCircles entirely (separate ADR, post-beta scope), this module can be deleted wholesale — the helper is intentionally trivial so its removal is trivial.

## ADR-EXPERT-01: Expert Paper Upload Security Model

**Date:** 2026-04-15
**Status:** Accepted
**Phase:** L2 sprint (Day 3-5)
**Related:** STRATEGY.md §Day 1-2 Track B; handoff.md §2 Track B; FR-EXPV-02

### Context

Expert reviewer portal shipped in Phase 2 with metadata-only `POST /api/v1/expert/papers` — no file input on frontend, no multipart on backend. L2 sprint requires the kin expert to upload real peer-reviewed PDFs directly into the `papers_rag` corpus by end of Day 2.

### Decision

Two-phase signed-URL upload to a dedicated Supabase Storage bucket named `papers`, matching the existing video upload pattern (`AnalysisService.create_analysis` + XHR PUT to signed URL).

**Phase 1** — `POST /api/v1/expert/papers` accepts JSON body `{metadata..., filename, file_size_bytes}`. Backend:
- Validates `file_size_bytes <= 52_428_800` (50 MB).
- Validates filename matches `^[A-Za-z0-9._-]+\.pdf$` after sanitisation (whitespace → `_`, non-allowed chars stripped, max 255 chars).
- Generates `paper_id = uuid4()`; builds `storage_path = f"papers/{paper_id}/{sanitized_filename}"`.
- Calls `PaperStorageService.generate_signed_upload_url(storage_path)` — TTL 3600 s.
- Inserts `rag_documents` row with `review_status='uploading'`, `storage_path=<path>`, user-supplied metadata.
- Returns `{id, upload_url, storage_path, expires_at}`.

**Phase 2** — Browser PUTs the file directly to `upload_url` with `Content-Type: application/pdf`. FastAPI never touches bytes.

**Phase 3** — `POST /api/v1/expert/papers/{id}/complete`. Backend:
- Downloads the first 8 bytes of the object via service-role Supabase client.
- Asserts bytes start with `b"%PDF-"`. If not, deletes the storage object + the `rag_documents` row, returns 422 `INVALID_PDF`.
- If ok, updates `review_status='pending'`, enqueues `ingest_paper(paper_id)` ARQ job.
- Returns `{id, review_status: 'pending'}`.

### Security posture

- **Bucket RLS**: `INSERT` allowed for JWT where `user_metadata.role IN ('expert_reviewer', 'admin')` AND `bucket_id='papers'`. `SELECT` only for `service_role`. No public read.
- **Magic-byte validation** happens post-upload via service-role download, not pre-upload, because signed-URL PUTs bypass the FastAPI handler. 8-byte head is enough to identify PDF (`%PDF-1.x`).
- **Size limit** enforced at schema (Phase 1 rejects large claims) + bucket config (Supabase enforces on PUT).
- **Filename sanitisation** prevents path traversal, command injection, and filesystem quirks. Rejected filenames fail Phase 1 with 422.
- **Role gate** via existing `get_expert_reviewer_user` dependency (admin + expert_reviewer only).
- **Service-role key** is server-side only, read from `SUPABASE_SERVICE_ROLE_KEY` env var. Never sent to the browser.

### Why two phases + completion endpoint (not one phase + worker poll)

A third endpoint is cheaper than making the ARQ worker poll Supabase Storage for "upload finished" state. It also lets the client signal intent to commit — orphaned rows with `review_status='uploading'` + expired `upload_url` can be swept by a cron later if abandonment becomes a real problem.

### Why not TUS protocol

Matches the pattern in `UploadPage.tsx` lines 9–18: Supabase REST signed upload URLs reject TUS protocol headers. Plain XHR PUT is the supported path.

### Why Docling is not in this ADR

P2-005 is open. The `ingest_paper` task in this scope downloads the PDF and logs `docling-pending`. Chunking + embedding fire when P2-005 ships. The May 3 gate is "expert uploaded end-to-end", not "papers appear in RAG queries".

### Consequences

- New Supabase bucket `papers` created via Alembic migration 009 (or dashboard if Alembic-over-storage is flaky on this Supabase project).
- `rag_documents.review_status` CHECK constraint widened to include `'uploading'`.
- Two new schemas: `RagDocumentUploadRequest`, `RagDocumentUploadResponse`, `RagDocumentCompleteResponse`.
- `StorageService` sprouts a papers-flavoured sibling (`PaperStorageService`) bound to bucket `papers`.
- Frontend page adds `<input type="file">` + XHR PUT + progress bar. Matches `UploadPage.tsx` conventions.
- ARQ worker registry adds `ingest_paper` (no-op stub until P2-005).

### Alternatives considered

- **Multipart/form-data on FastAPI** — rejected. Would make the backend a bandwidth bottleneck on the 4 GB droplet; violates ADR-048 memory budget. Signed-URL matches existing patterns.
- **One-phase upload + worker polls** — rejected. Worker is ARQ, not a long-running poller; adding poll loops adds complexity. A cheap completion endpoint is clearer.
- **Reuse `videos` bucket with `papers/` prefix** — rejected. Bucket-level RLS is clearer when one bucket = one purpose. Video RLS uses `user_id` path segments; papers RLS needs role claims.

## ADR-BRAIN-04-reversal — streaq migration pulled into L2 sprint (Day 3-9)

**Date:** 2026-04-15
**Status:** Accepted. Supersedes the deferral clause in ADR-BRAIN-04 (ARQ stays for Phase 2, migrate in Phase 3).
**Scope:** Drop-in replacement only — no streaq task graphs, middleware, priorities, or retry policies in this window.

**Decision:** Migrate from ARQ ≥0.27.0 to streaq ≥6.4.0 within the 7-day window Apr 16-22, 2026. All 5 current job types (`process_analysis`, `cascade_consent_withdrawal`, `ingest_paper`, `cleanup_expired_artifacts`, `ping_qdrant_health`) move to streaq. ARQ dependency drops entirely at end of sprint.

**Justification:**
- ARQ is in maintenance-only mode (tracking issue: https://github.com/python-arq/arq/issues/510; v0.27.0 Feb 2026 was the last release).
- streaq v6.4.0 shipped 2026-04-10 with anyio structured concurrency and self-reports 5× ARQ throughput.
- Being on an unmaintained queue weakens the interview-narrative "production-grade infrastructure" signal.
- Original ADR-BRAIN-04 budgeted 2 weeks; the L2 sprint compresses this to 7 days by limiting scope to drop-in replacement.

**Preserved behaviors (non-negotiable — regression test any breakage):**
- Idempotency at task level (terminal-state guard in `process_analysis`).
- Heartbeat at `spelix:worker:heartbeat` with 90s TTL, 30s refresh cadence (NFR-OPER-02).
- Concurrency=1 on the worker container (MediaPipe RAM peak ~350MB on 2GB droplet).
- Coaching SSE pub/sub via independent `redis.asyncio` client (not queue-coupled).
- Cron schedules: 02:00 UTC `ping_qdrant_health`, 03:00 UTC `cleanup_expired_artifacts`.

**Fallback (stop-loss trigger per STRATEGY.md):** if migration blocks Phase 3 start by >5 days, revert to ARQ with `max_jobs=1`, `job_timeout=900` and migrate post-interviews. Revert commit kept at the branch's base SHA.

**Files touched:**
- `backend/pyproject.toml`, `backend/uv.lock` — dep swap
- `backend/app/workers/streaq_worker.py` (new) — Worker + Context + task registry
- `backend/app/workers/{analysis_worker,consent_cascade,paper_ingestion,cleanup,keepalive}.py` — unchanged bodies
- `backend/app/api/v1/{analyses,consent,expert}.py` — enqueue-site rewrites
- `backend/app/services/analysis.py` — param rename
- `docker-compose.prod.yml` — CLI command change
- `backend/CLAUDE.md` — docs update
- `backend/app/workers/settings.py` — deleted at end

## ADR-LANGGRAPH-01 — LangGraph as agent orchestration framework (Phase 3)

**Date:** 2026-04-15 (Day 5 of 19-day L2 sprint)
**Status:** Accepted
**Supersedes:** Imperative coaching orchestration in `analysis_worker.py::_run_pipeline` (lines ~194–500)

### Context

Phase 3 requires an agent that (a) exposes composable tools per FR-AICP-18, (b) reasons adaptively over tool outputs per FR-AICP-19, (c) emits a plain-English trace for the Batch 3 reasoning sidebar per FR-AICP-20 + FR-RESL-07. The Phase 2 coaching pipeline is 300+ lines of imperative orchestration (retrieve → validate_output → CoVe → safety_filter → faithfulness_gate) wired directly inside `analysis_worker.py`. Adding branching, conditional verification, and adaptive tool selection to this imperative code would be error-prone and untestable.

### Decision

Adopt LangGraph 0.2+ as the agent orchestration framework. Six composable tools are pure async functions returning partial `AgentState` updates. Two graph modes ship together in Batch 1:

- **Deterministic mode** (default, per FR-AICP-18's "Phase 3 initial" clause) — conditional edges enforce `retrieve → flag → compare → generate → validate → cove → safety → faithfulness → END`. No LLM-driven tool choice; the flow is a state machine.
- **Adaptive mode** (per FR-AICP-19) — a single "reasoner" node with `ChatAnthropic.bind_tools([...])` picks tools by docstring. Reserved for observability-rich scenarios once the deterministic path is validated on prod traffic.

Mode is selected via env `SPELIX_AGENT_MODE=deterministic|adaptive` (default `deterministic`). The entire agent path is gated by `SPELIX_PHASE3_AGENT_ENABLED=0|1` (default `0` at first deploy; flip to `1` after smoke test).

### Alternatives considered

- **Custom orchestrator** — rejected: reinvents LangGraph's checkpointing, tracing, and branching primitives. Harder interview narrative.
- **LlamaIndex agent framework** — rejected: Phase 2 RAG already uses Qdrant + Cohere directly; LlamaIndex adds a second retrieval abstraction layer.
- **OpenAI assistants API** — rejected: vendor lock-in on a non-Anthropic model path; the coaching model IS Sonnet 4.6 per FR-AICP, and mixing vendors at the orchestration layer is architectural debt.

### Consequences

- Adds 4 dependencies (`langgraph`, `langchain-anthropic`, `langchain-core`, `langsmith`); footprint ~12 MB wheel-installed. Acceptable given the 4 GB droplet.
- `agent_trace_json` column shape changes from `{cove_iterations, converged}` to include `nodes_executed[]`, `tool_calls[]`, `mode`. Schema column is untyped `JSONB`, so no migration — consumers must tolerate both old and new shapes.
- The imperative path stays as a fallback; remove in a follow-up PR after 7+ days of stable agent traffic.
- LangSmith observability adds a recurring cost (~$40/mo free tier covers beta volume; budget for paid tier if beta exceeds 10k agent runs/month).

## ADR-TIMELINE-01 — Phase 3 pulled forward into the May 3 L2 sprint

**Date:** 2026-04-15
**Status:** Accepted

### Context

Original roadmap (STRATEGY.md v1, 2026-04-11) deferred Phase 3 to post-Saturniq. STRATEGY.md v3 (2026-04-14) pulled Phase 3 forward to a compressed 19-day sprint ending 2026-05-03, driven by mid-May AI-lab internship application deadlines and July interview start dates. The ARQ→streaq migration (Day 3-9) shipped on Day 4 via PR #48 + hotfix #49, freeing a 5-day buffer (Apr 16–22).

### Decision

Use the buffer to pull Phase 3 Batch 1 (P3-001/002/003) forward from the scheduled Day 10-13 window into Day 5-9. If Batch 1 ships cleanly by Day 9, Batches 2 + 3 proceed on the original cadence with additional buffer. If Batch 1 slips past Day 9, Batch 2 absorbs the remaining buffer and Batch 3 triggers the stop-loss in STRATEGY.md §Stop-Loss (re-scope to drop distillation, retain agent core + sidebar).

### Consequences

- Landing V1 (Day 1-2) + Expert PDF upload (Day 3) + streaq migration (Day 4) + Phase 3 Batch 1 (Day 5-9) + Phase 3 Batch 2 (Day 10-13) + Phase 3 Batch 3 (Day 14-19) + Smoke test (Day 19) + Gate audit (Day 20 = May 3).
- The `spelix-langgraph-engineer` agent activates today (Day 5) instead of Day 10.
- No change to the May 3 hard gate; buffer re-allocation only.

## ADR-AGENTSTATE-01: `AgentState` TypedDict uses `total=True` for pyright-safe reads
**Context**: First CI run on PR #52 produced ~25 `reportTypedDictNotRequiredAccess` errors because `AgentState` was declared `total=False`. Every `state["analysis_id"]` read in `backend/app/agents/tools.py` was flagged as a potential `KeyError` under pyright strict mode, even though `make_initial_state` always populates every field before the graph runs.
**Decision**: Change `backend/app/agents/state.py::AgentState` from `TypedDict(total=False)` to default `total=True`. All keys — `analysis_id`, `user_id`, `exercise_type`, `exercise_variant`, `confidence_score`, `mode`, `body_stats`, `keyframe_analysis_text`, `rep_metrics`, `papers_contexts`, `brain_contexts`, `retrieval_source`, `flagged_deviations`, `user_history_summary`, `coaching_output`, `cove_verified`, `eval_scores`, `degraded_mode`, `trace`, `messages` — are required. `make_initial_state` is the sole entry point and sets every field with safe defaults before `graph.ainvoke`.
**Consequences**: Pyright accepts `state["key"]` reads without narrowing. Node return values remain plain `dict[str, Any]` partials — LangGraph merges them shallowly into the typed running state, so partial updates still work. Future agent-graph state classes in Spelix (e.g., the Phase 3 Batch 2 distillation graph) MUST follow this pattern: `total=True` on the state, single `make_initial_state(...)`-style constructor, node returns as untyped partials. Adding a new field to `AgentState` now requires adding a default in `make_initial_state` in the same commit or pyright fails across every tool.

## ADR-DISTILL-01: Candidate storage in a new `coach_brain_candidates` table (Session 41)

**Context**: Phase 3 distillation needs a place to write unvetted entries until expert review promotes them. Options: (a) add `status='candidate'` to `coach_brain_entries` CHECK constraint and rely on retrieval filters; (b) new `coach_brain_candidates` table with a separate lifecycle column.

**Decision**: Option (b). The retrieval path (`DualCollectionOrchestrator`) filters on `status='active'`; extending the enum risks accidental leakage if any future predicate change drops that filter. A separate table also makes RLS admin-only trivially (migration 011 adds `FORCE ROW LEVEL SECURITY` + a single `service_role` policy), gives us a distinct primary-key space for Batch 3's `promoted_entry_id` pointer, and matches the session-40 handoff directive.

**Consequences**: Two tables to maintain. Batch 3 promotion writes BOTH — `INSERT INTO coach_brain_entries (status='active', ...)` + `UPDATE coach_brain_candidates SET review_status='approved', promoted_entry_id=...`. FR-BRAIN-16 cascade now targets both tables' `source_analysis_ids` GIN indexes (see `consent_cascade.py` extension in Task 11b, commit `8a1c568`).

## ADR-DISTILL-02: Invocation via streaq task, not `asyncio.create_task` (Session 41)

**Context**: FR-BRAIN-06 says "Invoked via `asyncio.create_task` (MVP) or task queue job (production)". We are on streaq already; production-grade invocation is cheap.

**Decision**: New `distill_analysis` streaq task in `app/workers/distillation_worker.py`, registered via a `@worker.task(timeout=300)` wrapper in `streaq_worker.py`, enqueued from the tail of `process_analysis` (both coaching paths — graph and imperative) via `_maybe_enqueue_distillation` gated on `SPELIX_DISTILLATION_ENABLED=1 AND eval_scores.overall >= 0.6`. `asyncio.create_task` loses retries, isolation, and heartbeat visibility; streaq gives all three with zero extra infra.

**Consequences**: Distillation queues up behind subsequent analyses (streaq `concurrency=1`). Acceptable at L2 beta volume (<10 analyses/day). Enqueue errors are SWALLOWED as warnings — the parent analysis must always finish successfully for the user. If p95 coaching latency regresses, split to a distillation-specific queue in a follow-up.

## ADR-DISTILL-03: Slim `BrainCoveService` for single-claim verification (Session 41)

**Context**: FR-BRAIN-14 requires CoVe against `papers_rag` before every Coach Brain promotion. The existing `CoveVerificationService` (P2-014) extracts claims from a full `CoachingOutput`. Distillation candidates are already atomic coaching cues.

**Decision**: Introduce `app/distillation/cove_brain.py::BrainCoveService.verify_claim(claim: str, contexts: list[RetrievedContext])` that skips claim-extraction and generates exactly one verification question per candidate. Uses Haiku 4.5 (same model as the coaching-path service). The coaching-path `CoveVerificationService` remains untouched.

**Consequences**: Two CoVe services in the codebase. Acceptable — they have different inputs. Consolidation deferred until one service sees zero traffic or prompt styles drift far enough to justify a common abstraction.

## ADR-DISTILL-04: `Chunk` added alongside `ChunkPayload` in `app/schemas/rag.py` (Session 41)

**Context**: The Phase 3 distillation pipeline (BrainCoveService, its tests, and the graph integration tests) needs a lightweight `RetrievedContext.chunk` that carries only `{id, document_id, text, title, year, collection}`. `ChunkPayload` requires ~10 additional fields (`paper_id`, `chunk_index`, `section`, `token_count`, `quality_tier`, `authors`, `doi`) that distillation does not populate.

**Decision**: Add a second Pydantic model `Chunk` to `app/schemas/rag.py` and widen `RetrievedContext.chunk: ChunkPayload | Chunk`. All 22 existing files that read `.chunk.*` use only the common fields (`.title`, `.year`, `.text`, `.id`), so the union widening is safe — no consumer breakage.

**Consequences**: Two chunk shapes coexist. Retrieval-path code continues to produce `ChunkPayload`; distillation test stubs produce `Chunk`. If a future consumer needs `ChunkPayload`-only fields (`authors`, `doi`, `quality_tier`), it must narrow with `isinstance(ctx.chunk, ChunkPayload)` before access.

## ADR-DISTILL-05: Never persist raw `str(exc)` to admin-visible DB columns (Session 41)

**Context**: `spelix-security-reviewer` (H-2 finding on PR #77) flagged that `BrainCoveService.verify_claim` was storing `f"evaluation_failed: {type(exc).__name__}: {exc}"` into `coach_brain_candidates.cove_explanation` + `str(exc)` into `cove_trace`. Python HTTP clients (httpx, aiohttp, the Anthropic SDK) can render the full request URL — including `api_key=...` or `Authorization: Bearer ...` query params — into exception messages. The column is admin-visible in Batch 3's review queue; any leaked secret would surface there and (worse) in any export of the candidates table.

**Decision**: In `app/distillation/cove_brain.py::verify_claim` the error path now stores ONLY `f"evaluation_failed: {type(exc).__name__}"` in `cove_explanation` and `{"claim": claim, "error_type": type(exc).__name__}` in `cove_trace`. Full exception detail (including `str(exc)`) still goes to `logger.warning(...)` above the error path for debugging — worker logs are an operator-only surface, not a user/admin one. Pattern codified: any LLM-backed service that persists error metadata to a DB column readable by users OR admins must strip `str(exc)` before write. Tests assert the raw exception text never appears in the persisted column.

**Consequences**: Debugging a failing distillation run requires cross-referencing the worker log (has full exception) with the candidate row (has type name + timestamp). Acceptable tradeoff — the alternative is leaking secrets every time an SDK wraps a URL into an HTTP error. Future services that land LLM-call failures in admin tables (Batch 3 review queue, future eval pipeline) MUST follow the same pattern. If a future reviewer needs more context on persisted failures, add a structured `error_category` enum (`timeout | rate_limit | malformed_response | network`) — not a free-text `str(exc)`.

## ADR-BRAIN-08: Seed Coach Brain entries are retrieval-eligible via cold-start fallback (Session 42)

**Context**: Migration 004 shipped a `coach_brain_entries.status` enum of `{seed, active, deprecated}` that diverged from SRS FR-BRAIN-02's intended `{candidate, approved, rejected}` + separate `source` column design. All 24 seed entries (bulk-ingested per FR-BRAIN-09) landed with `status='seed'`. But `retrieve_coach_brain` at `backend/app/agents/tools.py:131` hardcoded a `MatchValue(value="active")` filter. Consequence: every coaching analysis retrieved 0 brain contexts, which in turn forced `retrieval_source='papers_only_fallback'`, which combined with a parallel `papers_rag` exercise-index bug meant 0 retrieved sources of ANY kind, `degraded_mode=True`, and `analyses.eval_scores` permanently NULL. This silently blocked the Phase 3 Batch 2 distillation gate and made the flywheel appear to be working while actually delivering no grounding to the LLM.

**Decision**: Change the filter to `MatchAny(any=["active", "seed"])`. Rationale: FR-BRAIN-05 defines cold-start fallback as a dynamic mode — seeds form the initial retrievable population until distillation + expert review (Phase 3 Batch 3) produces `active` entries. `deprecated` remains excluded. Do NOT promote seeds to `active` via data migration — the semantic distinction matters for audit provenance (hand-curated vs distilled+reviewed).

**Consequences**: Seeds now surface in coaching prompts. Retrieval quality for the common bench/squat/deadlift corrections jumps from 0 brain contexts to up to 24 eligible cues. `retrieval_source` will register as `coach_brain_primary` or `hybrid_brain_supplementary` for real queries once scores are calibrated. The Phase 3 Batch 2 distillation gate starts firing because `eval_scores` begins populating. The Phase 3 Batch 3 review queue gets real candidate rows to process. Future caveat: if any code path adds a new `status` value (e.g., a `'draft'` or `'under_review'` state), the filter MUST be re-audited — use `MatchExcept` to exclude `deprecated` instead of `MatchAny` with a whitelist if this becomes frequent.

## ADR-PHASE2-EVAL-FALLBACK: Quality-score gates fall back to `faithfulness` until Phase 4 ships `overall` (Session 42)

**Context**: The distillation pipeline (`_maybe_enqueue_distillation` in `analysis_worker.py` and `validate_quality` in `app/distillation/validate.py`) was written against the SRS FR-BRAIN-06 spec, which assumes a multi-component RAGAS aggregate score: "eval_scores overall ≥ 0.85 AND correctness ≥ 0.8 for approval; ≥ 0.6 for expert review routing; below 0.6 exits." But ADR-RAG-04 (Session 16) deferred RAGAS to Phase 4 and shipped Phase 2 with a single LLM-as-judge `faithfulness` score only. So `eval_scores` on prod looks like `{"faithfulness": 0.82, "faithfulness_passed": true}` — no `overall`, no `correctness`. Both gate sites checked `eval_scores.overall` and silently rejected every analysis. Discovered during session 42 E2E verification when prod analyses had `eval_scores=NULL` *or* populated-but-rejected (post-PR-#80).

**Decision**: At every Phase 2 quality-score gate site, read `eval_scores.overall` first and fall back to `eval_scores.faithfulness` when overall is absent, applying the same numeric threshold (`>= 0.6` for the gate, `>= 0.85` for `pass`). Two sites fixed by this decision: PR #80 in `_maybe_enqueue_distillation` and PR #81 in `validate_quality`. Pattern documented here for any future Phase 2 code that gates on `eval_scores`. When Phase 4 RAGAS ships and `overall` becomes populated, the `or` chain automatically resolves to `overall` (correct precedence) and the fallback becomes inert — no migration required at Phase 4 kickoff.

**Consequences**:
- Distillation gate is now operable on Phase 2 prod traffic. The 11 candidate rows from analysis `73f9a137-c528-4f11-b833-48c638b5d5fc` are direct evidence.
- The `pass` route in `validate_quality` (which requires both `overall ≥ 0.85` AND `correctness ≥ 0.8`) is unreachable on faithfulness-only data — every Phase 2 candidate routes to `review` instead. This is correct: candidates from a single-score evaluator should not be auto-approved.
- Any future Phase 2 code that introduces a NEW `eval_scores`-gated decision MUST follow this fallback pattern. Add a code-quality reviewer check at the next eval-touching PR.
- M-06 backlog item: when Phase 4 ships `overall` + `correctness`, audit both fallback sites to confirm `overall` takes precedence and document the deprecation path for the fallback (don't remove it — Phase 2 analyses in the historical table still need it for replay/audit).
- Test coverage added: 4 regression tests across `tests/integration/test_distillation_worker_e2e.py` (2 new) and `tests/unit/test_distillation_validate.py` (2 new) explicitly assert the faithfulness-fallback semantics.

## ADR-BRAIN-REVIEW-01: Near-atomic approve — Postgres INSERT + Qdrant upsert in one request (Session 43)

**Context**: The expert review queue (P3-006) promotes `coach_brain_candidates.review_status='pending'` rows into `coach_brain_entries.status='active'` AND indexes them into the Qdrant `coach_brain` collection. Two options:

- (a) In-request: INSERT Postgres row → embed + upsert Qdrant → UPDATE candidate → COMMIT, rolling back DB on any failure.
- (b) Deferred: INSERT Postgres row → enqueue an embed job → COMMIT immediately; worker picks it up and back-fills the Qdrant point later.

**Decision**: Option (a). At L2 volume (<10 analyses/day → ≤~10 candidates/day), the review rate is bounded by the human reviewer (~30 sec/entry); Cohere embed + Qdrant upsert adds ~200–400 ms and is not the latency floor. The in-request path also prevents the most-likely failure mode — a Postgres `coach_brain_entries` row with no corresponding Qdrant point is retrievable by admin tools but invisible to real-time coaching. That's the exact "coach_brain_primary returns 0 hits so we silently degrade" failure that bit us in session 42.

**Not truly atomic — the narrow window**: The operation is NOT atomic in the strict 2-phase-commit sense. Execution order is INSERT+flush (Postgres) → Qdrant upsert → UPDATE candidate → `db.commit()`. If the final `db.commit()` fails after a successful Qdrant upsert, we have a Qdrant-only point with no Postgres entry row. In practice this is vanishingly rare: Postgres commits over PgBouncer at L2 volume have sub-ppm failure rates, and the in-session work just before commit is minimal. When it does happen, Qdrant upserts are idempotent by ID (point_id = `str(entry.id)`) so an admin retry re-upserts the same point without duplicates; the orphan is detectable by a nightly audit query (`SELECT point_id FROM qdrant WHERE id NOT IN (SELECT id FROM coach_brain_entries)`). Adding a second Qdrant `delete_points` call in a `try/except` around the commit would complicate the error envelope without materially reducing risk at this volume.

**FR-BRAIN-18 interpretation**: SRS says `confirmation_count` is "incremented when a human reviewer approves a candidate entry that was initially auto-held for review." Candidates don't have their own `confirmation_count` column — only the promoted `coach_brain_entries` row does. We set `confirmation_count=1` on the new entry at approval time. Semantically: the human approval IS the first confirmation, matching the seed-entry convention (FR-BRAIN-18 explicitly sets seed initial value = 1). Zero would mean "entry exists but nobody has vouched for it," which contradicts the approval act itself.

**Consequences**: One failed Cohere / Qdrant call fails the whole approve request with HTTP 502 `QDRANT_UPSERT_FAILED`. The admin retries. If Cohere is persistently down, approvals block — acceptable at current volume. At higher volume (>100/day), revisit with option (b): add a `pending_embed` sub-state on the entry that retrieval excludes until the Qdrant point lands.

**Implementation**: `CandidateReviewService.approve` owns the transaction. A `QdrantUpsertFailed` catch-block calls `db.rollback()` before raising. Reject path has no Qdrant side effects, so its transaction is a straight UPDATE + COMMIT.

**Related**: ADR-DISTILL-01 (candidate storage in a separate table); FR-ADMN-12; FR-BRAIN-07; FR-BRAIN-18.

**L2-launch deviations from FR-ADMN-12 (explicit down-scoping, session 43 audit)**:

The spelix-auditor (session 43) flagged three surface-coverage gaps against FR-ADMN-12's "Must" information set. All three are down-scoped to D-037 and D-038 follow-ups rather than blocking L2 launch:

1. **Top-2 similar existing approved entries** (auditor H-02). Implementation shows only the single nearest entry (`nearest_entry_id` + `nearest_cosine_sim` already persisted on the candidate by the distillation `lifecycle_decision` node). Showing a second requires a per-card Qdrant live search, adding ~50–150 ms per card view. At L2 volume (11 live candidates, <10/day new) the marginal safety gain is small. Tracked in D-037.

2. **confirmation_count field on the review card** (auditor H-03). The candidate row itself has no `confirmation_count` column — only `coach_brain_entries` does. SRS likely meant "show how often the nearest existing entry has been confirmed," which is redundant with the top-2-similar-entries feature (D-037). Bundled into D-037.

3. **entry_type='compensation' CHECK constraint** (auditor M-01). The UI banner is forward-compatible (TSX cast), so no live rows can land today. The CHECK migration and biomechanics reviewer routing are tracked in D-038.

**Security hardening applied from session 43 reviewer (inline, not deferred)**:

- HTTP 409 (`ALREADY_REVIEWED`) and 502 (`QDRANT_UPSERT_FAILED`) response bodies set `detail: null` instead of echoing `str(exc)`. Vendor SDK exception strings can include cluster hostnames or credential fragments in debug output. Full cause is retained via `logger.exception` at the service layer.
- `_get_review_service` wraps `get_cohere_client()` / `await get_qdrant_client()` in try/except and surfaces env-misconfiguration as a clean HTTP 503 (`VECTOR_STORE_UNAVAILABLE`) envelope.
- `CandidateReviewService.approve` runs a denylist regex against `content_override` to reject obvious prompt-injection separator sequences (`\n\nHuman:`, `<|im_end|>`, `[INST]`, `IGNORE PREVIOUS INSTRUCTIONS`, etc.) before the content flows to Cohere embed and Qdrant upsert. Raised as `PromptInjectionDetected`, mapped to HTTP 422 `PROMPT_INJECTION_DETECTED`. Expert-review workflow remains the primary defense; this is defence-in-depth for admin-editor compromise.

**Decision**: ship P3-006 at this scope for L2 launch. The core correctness properties (`confirmation_count=1` per FR-BRAIN-18, `SELECT FOR UPDATE` race guard, Qdrant rollback on upsert failure, admin-only RLS) are unaffected by the deferred surface work. D-037 and D-038 are explicitly prioritized ahead of Phase 4 eval work.

## ADR-REASONING-SIDEBAR-01: P3-007 "How AI Reasoned" sidebar design choices

**Date:** 2026-04-17 (Session 44, L2 Sprint Day 8)
**Status:** Accepted
**Related SRS:** FR-RESL-07 (Phase 3, Must), NFR-USAB-05 (Must)
**PR:** #83 (merge SHA `70d736c`)

**Context:** FR-RESL-07 requires a plain-English sidebar on ResultsPage rendering the LangGraph agent trace. The payload (`coaching_results.agent_trace_json`) has been persisted since Phase 3 Batch 1 (session 32); Batch 3 is the surface.

**Decisions:**

1. **Graph library: `@xyflow/react@12.10.2`.** React-Flow v12 renamed. React 19 compatible, MIT-licensed, `proOptions.hideAttribution` is free (not paywalled per [maintainer discussion #2961](https://github.com/xyflow/xyflow/discussions/2961)). Future-proofs adaptive-mode graphs (20+ nodes) and the Phase 4 eval dashboard over a hand-rolled SVG (would be ~40 LOC, ~2 KB, but no zoom/pan, no keyboard nav, no consistent styling).

2. **Edge inference: execution order.** `nodes_executed[i] → nodes_executed[i+1]`. `NodeEvent` has no `input_keys` field; the deterministic graph is a strict 10-node chain anyway. Adaptive mode renders a visually approximate loop (reasoner → tool → reasoner → tool → …) with index-based IDs.

3. **Node IDs: index-based** (`node-0, node-1, ...`). Adaptive-mode reasoner can repeat a node name (e.g. `reasoner` visited 3× in a loop); name-keyed IDs would collide in xyflow. Index-based works for both modes without special-casing.

4. **`AgentTracePayload` fields all optional.** Two producers write `coaching_results.agent_trace_json`:
   - Phase 3 graph path (`analysis_worker.py:~802`) writes the full shape: `{mode, nodes_executed, eval_scores, cove_iterations, converged, retrieval_source, degraded_mode}`.
   - Phase 2 imperative path (`analysis_worker.py:~483`) writes a partial: `{cove_iterations, converged}` only.

   Required-fields types would lie about Phase 2 data. The button-render gate `(agent_trace_json?.nodes_executed?.length ?? 0) > 0` distinguishes Phase 3 full writes from Phase 2 partials from legacy nulls in a single check.

5. **Degraded-mode visibility: sidebar SHOWN with banner, not hidden.** The trace itself is instructive — the user sees that `retrieve_papers` returned zero passages, why `degraded_mode=true`, etc. Transparency is the spirit of FR-RESL-07. The per-sidebar banner is in addition to (not replacing) the existing coaching-block `degraded_mode` banner.

6. **Drawer implementation: custom Tailwind `fixed` panel, not shadcn `Sheet`.** Repo has no shadcn today; adding it for one drawer is scope creep. The custom drawer is ~290 LOC inside the component, fully owned.

7. **A11y posture: Close-button autofocus + Escape + scrim close ship today; full focus trap deferred.** Root element is `<div role="dialog" aria-modal="true" aria-labelledby="agent-reasoning-sidebar-title">`. Escape and scrim click invoke `onClose`. Focus moves to the Close button on open via `useRef` + `useEffect`. A proper focus trap (cycling Tab within the drawer) requires ~15 LOC beyond the MVP and is a D-### follow-up.

8. **Plain-English mapping applies to node names AND output_keys AND retrieval sources.** `labelForNode`, `labelForOutputKey`, and `labelForRetrievalSource` all humanize unknown values as a defence-in-depth guarantee that no future backend addition leaks snake_case to users (NFR-USAB-05). This was the `spelix-auditor` H-1 + H-2 finding bundle addressed inline.

**Consequences:**

- New tool nodes added to the coaching LangGraph (Phase 3 Batch 4+) only need a label entry in `agentTraceLabels.ts` — the graph builder, detail pane, and all tests work unchanged.
- Adding a new AgentState key requires a label entry in `OUTPUT_KEY_LABELS`; humanizer fallback is safe in the interim.
- If the deterministic topology ever forks (parallel edges — e.g. Send-API fanout for concurrent retrieval), the graph builder must switch from sequential chaining to real topology inference, which means the trace payload will need edge metadata (new field).

**L2 deviations deferred to D-### follow-ups:**
- **D-### (M-05 unblock dependent):** Full focus trap inside the drawer (keyboard cycle, aria-modal semantics completion).
- **D-###:** Adaptive-mode reasoner-loop UI polish (iteration badges, in-line tool-call nesting). Prod runs deterministic only today.
- **D-###:** CoVe iteration drill-down pane (surface per-iteration question / answer / judgment). Summary currently shows only `converged: bool` + count.
- **D-###:** LangSmith run link-out from the summary header (admin-only).
- **D-###:** Sanitize `NodeEvent.error` strings in `serialize_trace_for_storage` to strip `/tmp/...` and other infrastructure paths before JSONB write (spelix-security-reviewer MED finding — low exploitability because owner-only visibility on rare error path).

**Related:** FR-RESL-07, NFR-USAB-05, ADR-BRAIN-REVIEW-01 (sibling in P3-006), FR-AICP-18 (deterministic graph shape).

## ADR-REPDET-01: Replace fixed-threshold rep detection state machine with peak/valley extraction (Session 45, Planned)

**Context:** Session 44 P3-007 E2E upload (`cea2312b-…`, bodyweight bench, camera on lifter's right side) returned **0 reps** despite the video containing ~3 clean rep cycles. Root cause investigation via `systematic-debugging` skill (Phase 1 — evidence-gathering only):
- MediaPipe pose extraction succeeded on 593/593 frames.
- Prod uses `_BENCH_ELBOW_L = 14` (despite the `_L` suffix, this is MediaPipe's `right_elbow` = subject's right = visible side in this video). Visibility on that landmark: mean 0.935, 593/593 frames > 0.5. Signal was clean.
- Right-side elbow angle peaked at **152.97°**, never crossing the prod STANDING threshold of 160° (with 5° hysteresis, effectively 155° going down). Signal clearly shows 3 rep cycles with minima at ~t=5.8s (38°) and ~t=9.8s (50°) and maxima at ~t=2.0s (152°) and ~t=7.5s (143°).
- State machine (`backend/app/cv/rep_detection.py::detect_reps`) never entered STANDING state → never transitioned → 0 reps emitted.
- Partial-lockout lifts (bodyweight, light-load bench, RDL, any beginner pressing) silently fail this way. The failure is silent: quality gates pass, pose extraction succeeds, state machine just stays in the initial state and `rep_metrics` is empty.

A second degenerate case compounded: with `rep_metrics=[]`, downstream scoring produced **Technique 10.0 / Control 10.0** (defaulting to max on empty input) alongside `form_score_overall=7.04` while the UI showed Confidence "Very Low / Unable to score reliably — please re-record". The contradiction (max per-dimension but Very Low confidence) is a trust-violating UX bug.

**Decision:** In session 45, replace the absolute-threshold state machine in `detect_reps` with a **peak/valley extraction algorithm** (`scipy.signal.find_peaks` on the smoothed angle series + its negation, filtered by prominence and min-distance). Tuning knobs become **signal-relative** (prominence in degrees, min-distance in seconds) rather than exercise-absolute (160°/90°). Applies to all three exercises — squat, bench, deadlift — via the same function; per-exercise tuning becomes a `prominence_deg` parameter rather than hard-coded standing/depth thresholds. Plan specified in new backlog items D-040 (rep detection rework) and D-041 (degenerate-input scoring fix). Both land in one PR next session.

**Consequences:**
- **Unlocks** partial-lockout detection for real user videos: bodyweight benches, fatigued final reps, parallel-only squats, RDLs that don't reach full hip extension. These fail the current state machine silently.
- **Preserves** the `DetectedRep` dataclass, per-rep metric extraction (`_bench_metrics` / `_squat_metrics` / `_dl_metrics`), the Tier 1–5 confidence aggregation, and artifact-generation boundaries — all consume `(start_frame, end_frame, angle_series)` and are agnostic to how reps are found.
- **Tuning risk:** `prominence_deg=20` is an initial guess. Too low → noise creates phantom reps; too high → low-ROM real reps disappear. First test pass must audit `backend/tests/unit/test_rep_detection.py` fixtures + hand-count reps on the in-repo fixture library (`e2e/fixtures/atharva-bench-*.mov/mp4`, `atharva-squat.mov`, `atharva-deadlift.mov`) to set defaults. Per-exercise `prominence_deg` may be needed.
- **Breaks tests** that assert specific rep counts on fixtures where the old state machine under-counted — those tests were encoding the bug, not the spec. Fix tests to reflect the true rep count in the fixture.
- **Independent of D-041 (degenerate scoring fix):** even after D-040 ships and rep counts go from 0 to N>0, the degenerate 10.0/10.0-on-empty-input path still exists for truly poseless videos or Very-Low-confidence analyses. D-041 (separate follow-up) changes ScoreComponent implementations to return `None` / "Not available" on empty input instead of defaulting to 10.0 — avoids the "Very Low confidence + 10.0 Technique" contradiction surfaced on the P3-007 E2E analysis.
- **Does not change** the SRS-specified thresholds for form-scoring evaluation (`FR-SCOR-*` thresholds for lockout quality, depth, etc.). Those are downstream of rep detection and still consume the detected boundaries.

**Related:** FR-CVPL-15, FR-REPM-01, FR-REPM-05 (rep detection spec), FR-SCOR-02 / FR-SCOR-04 (degenerate scoring path for D-041), `backend/app/cv/rep_detection.py`, `backend/app/cv/scoring.py`. Supersedes the per-exercise threshold dict in `rep_detection.py::_STANDING_THRESHOLD` and `_DEPTH_THRESHOLD` once D-040 ships.

## ADR-REPDET-02: Hybrid state-machine + peak/valley rep detection supersedes pure peak/valley (Session 45, Shipped in PR #84)

**Context:** ADR-REPDET-01 specified replacing the fixed-threshold state machine with pure `scipy.signal.find_peaks`. Session 45 hand-counted calibration across 6 in-repo fixtures (user-supplied ground truth: 1/1/5/5/5/5 reps) disproved that plan. Pure peak/valley fixed the 3 partial-lockout cases (`bench-nw-10s-720p/10s/no-weight` 0→1/1/7) but regressed 3 clean-lockout cases that state machine was getting right: `atharva-bench.mov` 13→21, `atharva-squat.mov` 5→14, `atharva-deadlift.mov` 5→4. Root cause: MediaPipe landmark flicker and Savgol-filter overshoot (window=7, polyorder=3) create sub-rep-amplitude valleys that any prominence/distance/clamp/percentile-sanity tuning (tested 20°–80° prominence × 3 filter variants) fails to separate from real rep bottoms. State-machine's absolute-threshold gating absorbed those artefacts because every rep requires a full `STANDING → BOTTOM → STANDING` traversal.

**Decision:** `backend/app/cv/rep_detection.py::detect_reps` runs the legacy state-machine (`_detect_reps_state_machine`) first; if it returns ≥1 rep, that result is used. Only when SM returns 0 (partial-lockout case) does it fall back to `_detect_reps_peak_valley` (find_peaks with `_PROMINENCE_DEG=20°` + `_MIN_REP_DURATION_S=0.5`). `_STANDING_THRESHOLD`, `_DEPTH_THRESHOLD`, `_HYSTERESIS_DEG` are restored in the module (were deleted in the pure-peak/valley commit `f237ccf`, re-added in the hybrid pivot `dffa59e`). New distinguishing test: `TestHybridStateMachineWins::test_hybrid_prefers_state_machine_over_peak_valley`.

**Consequences:**
- **Strict Pareto improvement over prod:** 3 partial-lockout fixtures unlocked (0→1/1/7), 0 clean-lockout regressions — `atharva-bench.mov` stays at 13 (unchanged from pre-PR prod), `squat.mov` stays at 5, `deadlift.mov` stays at 5.
- **Tuning simplification:** no per-exercise prominence-tuning needed. `20°` is conservative enough for the fallback path because the state machine already consumes all lockout-complete rep traffic. If future partial-lockout videos show false positives, tune `_PROMINENCE_DEG` per exercise.
- **Supersedes ADR-REPDET-01's core decision.** The "signal-relative tuning knobs replace exercise-absolute thresholds" claim in that ADR is rejected empirically. State-machine's absolute thresholds remain load-bearing — they're just scoped to the clean-lockout majority case.
- **`bench.mov` 13-rep over-count is unchanged** and still wrong vs hand count 5. This is pre-existing prod behaviour (state machine was doing it before this PR too). Captured as **D-044** for post-L2 investigation of signal quality — likely MediaPipe flicker or Savgol over-smoothing. Not a regression of this PR.
- **`_PROMINENCE_DEG` + `_STANDING_THRESHOLD` + `_DEPTH_THRESHOLD` + `_MIN_REP_DURATION_S` remain hardcoded** rather than flowing through `ThresholdConfig`. spelix-auditor H-1 flagged this as FR-SCOR-11 drift; deferred to **D-042** for a later ThresholdConfig-wiring pass.

**Related:** supersedes ADR-REPDET-01. FR-CVPL-15, FR-REPM-01, FR-REPM-05. `backend/app/cv/rep_detection.py`, `backend/tests/unit/test_rep_detection.py::TestHybridStateMachineWins`. PR #84 (`bc17250`), session 45.

## ADR-SCOR-DEGENERATE-01: Degenerate scoring guard lives at pipeline level, not inside `ScoreComponent` (Session 45, Shipped in PR #84)

**Context:** D-041 target: when `rep_metrics` is empty or `session_confidence < 0.50` ("Very Low" boundary per `confidence_label`), `form_score_*` columns must be `None` so frontend `FormScoreCards` renders "Not available" instead of defaulting to 10.0. Two implementation locations considered: (a) mutate each of the four `ScoreComponent` subclasses (`SafetyScore`, `TechniqueScore`, `PathBalanceScore`, `ControlScore`) to check for empty input and return `None`; (b) add a single guard at the pipeline step that runs the scorers. Verified via `rg "\.score_result" backend/app`: nothing outside `pipeline.py` reads `result.score_result`.

**Decision:** Add `_is_degenerate_scoring_input(rep_metrics, session_confidence) -> bool` in `backend/app/services/pipeline.py` (line ~172) and short-circuit `run_cv_pipeline` Step 9b with an `if/else`: degenerate → set all five `analysis.form_score_*` columns to `None` and skip `OverallFormScore.compute` entirely; otherwise → existing `agg_metrics + scorer.compute` path unchanged. The `0.50` threshold lives in `_DEGENERATE_CONFIDENCE_THRESHOLD` (module-level constant) and matches `confidence_label`'s "Low ≥ 0.50" boundary in `backend/app/cv/confidence.py`.

**Consequences:**
- **Zero changes to `ScoreComponent` subclasses** — the Protocol contract is preserved, all four scorers remain callable with their existing `(metrics, bar_path, cfg, exercise_type)` signature. Future 5th/6th scorers inherit the degenerate-input handling for free (pipeline layer gates them).
- **Single source of truth** for the `0.50` threshold — one module-level constant tied by comment to `confidence_label`, not repeated in four class bodies.
- **`result.score_result` stays at `PipelineResult.__init__` default `None`** in the degenerate branch. Verified safe: no external reader. If a future summary service or PDF generator starts consuming it, that code needs a None-guard — flagged in `backlog.md` for ADR review before adding such a consumer.
- **Threshold is signal-relative to the UI** (same `0.50` the user sees as the "Very Low" banner boundary) — if product ever shifts that boundary, both places update together.

**Related:** FR-SCOR-02, FR-SCOR-04, FR-SCOR-07, FR-SCOR-10 (confidence label). `backend/app/services/pipeline.py::_is_degenerate_scoring_input`, `backend/app/cv/confidence.py::confidence_label`, `frontend/src/pages/ResultsPage.tsx:123-203` (FormScoreCards null-handling). PR #84 (`bc17250`), session 45.

## ADR-DISTILL-06: BrainCoveService Haiku 4.5 max_tokens — 512 question / 2048 answer (Session 46)

**Context:** Session-42 distillation observed 11/11 `coach_brain_candidates` rows persisted with `cove_verified=false, cove_explanation="evaluation_failed: ValidationError"`. Root cause: `BrainCoveService.verify_claim` (`backend/app/distillation/cove_brain.py`) called `instructor.chat.completions.create` with `max_tokens=512` on the answer step, and Haiku 4.5's `_VerificationAnswerOut.reasoning` field routinely exceeded the budget when citing source numbers. Instructor's structured-output retry loop then re-sent the identical prompt three times, each time truncating the JSON mid-`reasoning` field, each time failing Pydantic validation, and finally returning `BrainCoveResult(verified=False, explanation="evaluation_failed: ValidationError", ...)`. M-05 (session 46) bumps both call sites.

**Decision:** Question-generation `max_tokens=512`; answer `max_tokens=2048`. Keep the full `_VerificationAnswerOut` schema (answer + reasoning) — do NOT shorten the prompt to compensate. Rationale: Haiku 4.5 pricing ($0.25/MTok input / $1.25/MTok output) puts the worst-case-per-verification cost at ~$0.0025, a rounding error at L2-beta volume (<10 analyses/day). Prompt-shortening trades cheap tokens for harder-to-reason-about prompt engineering — not worth it.

**Consequences:** `BrainCoveService` no longer hits the instructor retry loop on normal inputs. If Haiku 4.5 ever emits >2048 tokens of reasoning, the failure mode reverts to `evaluation_failed: ValidationError` — but that would now be a genuine model-pathology signal, not a budget-truncation signal, and it stays loud in `cove_explanation` for the Batch 3 review UI. If Haiku TPM throttling becomes a concern at higher volume, lower the answer budget back to 1536 and reassess. Do NOT drop below 1024 — that's the prior broken state.

**Scope note — coaching-path CoVe is a different service:** `app/services/cove.py::CoveVerificationService` has its own token budget and also exhibits max_tokens truncation in coaching-path runs (session 46 prod E2E observed output_tokens=1024→2048→3072 exponential retry, all truncated). That service is out of scope for M-05 / ADR-DISTILL-06; follow-up tracked as D-048.

**Related:** FR-BRAIN-14 (CoVe pre-promotion), ADR-DISTILL-03 (slim single-claim service), ADR-DISTILL-05 (never persist raw `str(exc)` to admin-visible columns). `backend/app/distillation/cove_brain.py:87,95`. PR #85 (`a0a86fc`), session 46.

## ADR-BRAIN-09: Agent retrieval queries need per-exercise vocabulary enrichment for Cohere Rerank to clear FR-BRAIN-05 thresholds (Session 47)

**Context:** D-045 investigation. Bench analyses on prod were stranded at `retrieval_source='papers_only_fallback'` even after M-04 re-embedded all 24 seeds with the FR-BRAIN-03 contextualized prefix. The diagnostic at `backend/scripts/oneoff/diagnose_coach_brain_retrieval.py` ran the live agent retrieval path (`hybrid_search(coach_brain, rerank=True)`) on prod and measured Cohere Rerank 4.0 scores per query construction. Findings:

- Bench Q1 (current agent query `"bench flat coaching cue correction"`): top reranked score = **0.32** → `papers_only_fallback`.
- Squat Q1 (`"squat high_bar coaching cue correction"`): top = **0.84** → `coach_brain_primary`.
- Deadlift Q1 (`"deadlift conventional coaching cue correction"`): top = **0.92** → `coach_brain_primary`.
- Q4 self-query ceiling (a seed's own content as the query): **0.99** for all three exercises — corpus is fine.
- Q2 vocab-rich queries (e.g. for bench: `"bench press eccentric tempo control elbow flare scapular retraction lat engagement bar path j curve"`): bench top = **0.92**, squat = 0.88, deadlift = 0.88 — bench lifts dramatically.

This **falsified** all four backlog hypotheses (a Cohere SEARCH_QUERY/SEARCH_DOCUMENT asymmetry, b ADR-BRAIN-02 prefix vocabulary mismatch with queries, c seed content too generic, d richer template helps short docs). Squat and deadlift coincidentally crossed FR-BRAIN-05's 0.82 threshold pre-fix because their exercise word (`"squat"` / `"deadlift"`) appears verbatim in seed content. Bench seeds use `"bench press"`, `"elbows"`, `"scapula"` instead of `"bench"` alone, so a 5-token agent query lacked lexical overlap with seed text and the cross-encoder scored ~0.32. The reranker (a cross-encoder) takes raw `(query, document_text)` pairs — and for `coach_brain` the `text` field falls back to raw `content` (no FR-BRAIN-03 prefix), so the indexing-side prefix never reaches the reranker and cannot rescue a thin query.

**Decision:** The Phase 3 agent retrieval tools (`app/agents/tools.py::retrieve_coach_brain`, and by extension future `retrieve_*` tools that hit small-corpus collections) MUST construct queries with enough lexical surface area to clear the Cohere Rerank cross-encoder's specificity bar. The minimum-viable mechanism is a per-exercise static vocabulary tail constant (`_COACH_BRAIN_QUERY_VOCAB: dict[str, str]` at module level) drawn from seed `trigger_tags` + content nouns (FR-BRAIN-09), appended to the existing exercise-type/variant query. The tail values are pure static English (no PII, no user data), maintained alongside the seed corpus.

**Consequences:**
- Bench rerank scores lift from ~0.32 to ~0.92 — confirmed end-to-end on prod via fresh upload `de316a7a-b4fd-4fb4-afc4-a1d6be596fa2` flipping to `retrieval_source='coach_brain_primary'`.
- A drift risk exists: if seed `trigger_tags` get curated upward (via expert review or re-ingestion), the static vocab tail in `tools.py` will go stale. Accepted risk — caller MUST sync the dict if seed vocabulary materially shifts. A future hardening would derive the dict at startup from a one-shot DB query against `coach_brain_entries.trigger_tags`, but the current approach is YAGNI-friendly given <10 analyses/day at L2-beta volume.
- Unknown `exercise_type` (e.g. future `overhead_press`) gracefully degrades: `dict.get(..., "")` returns empty, query stays well-formed without trailing whitespace, `retrieve_coach_brain` emits `logger.warning` so the gap is observable in worker logs.
- This ADR does NOT supersede ADR-BRAIN-02 (FR-BRAIN-03 contextualized prefix on indexing remains correct — it shapes the dense-retrieval candidate pool even when it can't rescue rerank). It supersedes the implicit assumption that exercise-type-only queries are sufficient at the agent-tool layer.

**Related:** FR-BRAIN-04 (status filter), FR-BRAIN-05 (retrieval_source thresholds 0.82 / 0.65), FR-BRAIN-09 (seed corpus + trigger_tags as vocabulary source), FR-AICP-18 (composable agent tools), ADR-BRAIN-02 (contextual padding before embedding — still in force; this ADR is an additive query-side mitigation), ADR-BRAIN-08 (seed cold-start eligibility — still in force). `backend/app/agents/tools.py:33-58,175-189` (constant + use site), `backend/scripts/oneoff/diagnose_coach_brain_retrieval.py` (read-only diagnostic — keep for future RAG investigations). PR #87 (`811a6c3`), session 47.

## ADR-COVE-01: CoveVerificationService Haiku 4.5 / Sonnet 4.6 max_tokens budgets (Session 48)

**Context**: Sessions 46 and 47 prod E2E on bench-fixture analyses (`6aa7b42b`, `de316a7a`) both observed `eval_scores.cove_verified=false` and `faithfulness=0.0` on completed analyses despite valid coaching output. Root cause: `CoveVerificationService._run_cove_loop` Step 3 `VerificationAnswers` call was capped at `max_tokens=1024` — too tight for Haiku 4.5's aggregated N-claim response (one `{question, answer, reasoning}` entry per claim, with reasoning citing source numbers). Instructor's structured-output retry loop failed three times; the service's top-level `try/except` swallowed the `ValidationError` and persisted `CoveResult(cove_verified=false, iterations_run=0, trace=[{"error": ...}])`. The faithfulness gate downstream read the swallowed result and stored `faithfulness=0.0`. Session 47 confirmed the failure survives the D-045 retrieval fix (Coach Brain retrieval now routes correctly; coaching-path CoVe still blew up) — proving independence from retrieval routing. D-048 bumps every `max_tokens=` in the CoVe loop.

**Decision**: Adopt the following per-step budgets in `app/services/cove.py::CoveVerificationService._run_cove_loop`:

| Step | Model | Response model | Budget | Rationale |
|------|-------|----------------|--------|-----------|
| 1: Claim extraction (pre-loop + iter > 1) | Haiku 4.5 | `ClaimList` | **1024** | Short-list output; cheap headroom against instructor retries. |
| 2: Question generation | Haiku 4.5 | `VerificationQuestions` | **1024** | Short-list output; cheap headroom against instructor retries. |
| 3: Independent verification | Haiku 4.5 | `VerificationAnswers` | **4096** | Documented blow-out path. N aggregated answers × ~60-token reasoning. Sessions 46 + 47 observed truncation at 1024, 2048, 3072. 4096 sits below Haiku 4.5's 8192 hard cap. |
| 4: Revision (both branches) | Sonnet 4.6 | `CoachingOutput` | **3072** | Regenerates full coaching output (summary + issues + correction_plan + cues + citations + disclaimer). 2048 was tight for multi-issue outputs. |

**Consequences**:
- `cove_verified` and `faithfulness` now reflect the actual coaching-vs-evidence verdict, not silent instructor failure. Session 48 post-fix prod E2E on bench fixture confirmed `faithfulness` flipped from `0.0` → **`0.92`** on analysis `bfbed270-1117-4a8a-8246-6d2dc9391781`. CoVe ran 2 iterations with 11 + 15 claims, producing real answers with source citations.
- **Surfaced a separate issue (tracked as D-050):** with CoVe now actually running, `cove_verified=false` still persists on this run because the claim-extraction prompt picks up lifter-specific numerical measurements ("elbow angle 38°", "eccentric 5.16s", "ascent 1.28s") as "falsifiable claims" — which research sources correctly report as Uncertain (papers describe the optimal 45–75° range and 2s eccentric target, but cannot confirm THIS lifter's values). The principles verify as Yes; the measurements verify as Uncertain. This is honest behavior, not a regression — but it means `cove_verified=true` (all-Yes convergence) is effectively unreachable under the current claim-extraction prompt whenever the coaching cites measured values. The follow-up (D-050) will refine claim-extraction to focus on principle-level claims, not measured-value claims.
- Cost impact at L2-beta volume (<10 analyses/day × ≤2 iterations × worst-case 4096 output × $1.25/MTok Haiku output): ~$0.10/day delta. Negligible.
- If Haiku 4.5 ever legitimately emits >4096 tokens of verification reasoning, the existing top-level `try/except` in `verify()` catches the `ValidationError` and falls back to `cove_verified=false, trace=[{"error": ...}]` — same loud signal the prior budget would have produced, just at a higher ceiling. If this becomes common, iterate (8192 is the Haiku hard cap) rather than dropping the budget back.
- Precedent: session-46 M-05 bump on the brain-path `BrainCoveService` (ADR-DISTILL-06). Coaching path and distillation path are intentionally separate services per ADR-DISTILL-03 — the budgets differ because they verify different input shapes (full `CoachingOutput` vs single atomic cue), but the design principle ("pay cheap Haiku 4.5 output tokens to avoid instructor retry pathology") is the same.
- Do NOT drop any budget below its prior value — that's the known-broken state.

**Related:** FR-AICP-08 Stage 2 (CoVe loop for coaching output), ADR-DISTILL-06 (precedent — brain-path max_tokens), ADR-DISTILL-03 (slim single-claim brain service — scope separation). `backend/app/services/cove.py:262,286,315,328,371,389`. PR #88 (`4ef4091`), session 48.

## ADR-COVE-02: CoVe claim extraction — principle-level, not measurement-level (Session 49)

**Context**: Session 48 PR #88 (D-048, `4ef4091`) bumped `CoveVerificationService._run_cove_loop` max_tokens budgets (ADR-COVE-01). Post-fix prod E2E on bench analysis `bfbed270` confirmed the fix worked (`faithfulness` flipped 0.0 → 0.92; 26 real verification answers with source citations across 2 iterations) but immediately surfaced a separate issue: the claim-extraction prompt (`_build_claim_extraction_prompt`) pulled lifter-specific numerical measurements ("elbow angle 38°", "eccentric 5.16s", "ascent 1.28s") as "falsifiable claims". Research sources describe optimal RANGES and TARGETS; they cannot confirm or refute any single lifter's measured value, so measurement claims systematically returned Uncertain. All-Yes convergence (`cove_verified=true`) was structurally unreachable as long as measurement claims were extracted. On `bfbed270`: every principle-claim (e.g. "45–75° optimal elbow range", "J-curve bar path", "2s eccentric target") answered Yes with source citation; every measurement-claim answered Uncertain.

**Decision**: Refine `_build_claim_extraction_prompt` to (a) explicitly name and distinguish PRINCIPLE-level vs MEASUREMENT-level claims, (b) instruct the extractor to SKIP measurement-level claims entirely, (c) when coaching cites a measurement AND the underlying principle ("your elbow was 38°, below the 45–75° optimal"), extract ONLY the principle ("Optimal bench press elbow angle is 45–75° from torso") — NEVER invent a principle from a bare measurement, (d) provide 2 positive and 2 negative worked examples matching session 48's observed coaching shape. Signature, call sites, max_tokens, model, and response schema unchanged.

**Consequences**:
- Core D-050 goal achieved: the extractor no longer emits lifter-specific measurement claims. Session 49 prod E2E on bench analysis `c46023c9-b098-4083-9c19-dad174b14a04` (same fixture `atharva-bench-nw-10s-720p.mp4`) produced 17 claims across 2 iterations — all principle-shaped ("Optimal elbow angle at the bottom of the bench press is 45–75° from the torso", "The recommended eccentric phase duration for bench press is approximately 2 seconds", "At lockout, the bar should be directly over the shoulder joint..."). Zero lifter-specific measurements.
- `faithfulness` dropped 0.92 → **0.82** — still above the 0.80 RAGAS gate (`faithfulness_passed=true`), within the D-050 plan's "acceptable 0.5–0.85" band (fewer claims in the denominator is expected when measurement claims are filtered). Not a regression; the drop reflects a denominator-shift, not a quality loss.
- `cove_verified` remained **false** on the verification run — NOT for the pre-D-050 reason (measurement Uncertains) but for a new reason: with principle-only extraction, the model occasionally HALLUCINATES principles not stated in the coaching output. On `c46023c9` the extractor invented "minimum of 60°" (coaching never stated a minimum), "60–100° reference range" (not in coaching or sources), "stretch-shortening cycle disruption from extreme eccentric" (not in sources), and inverted the source's fast-descent finding into "excessively slow eccentric makes bar path control harder" (source 2 says the opposite — a rushed/fast descent is what reduces time under tension). Iteration 2 reached 7/8 Yes but the one No (inverted eccentric-tempo claim) blocked convergence.
- The "translate-not-invent" rule in the refined prompt is insufficiently enforced against inversion. Tracked as **D-052**: tighten the translation rule with explicit inversion-guard language and add a negative-example for inverted-principle hallucination.
- For coaching outputs that cite NO principles (unlikely post-Phase-2 but theoretically possible), claim extraction returns an empty list. The existing `if not claim_list.claims:` short-circuit in `_run_cove_loop` returns `CoveResult(cove_verified=True, iterations_run=0)` — which is correct semantics: an extraction with no falsifiable principle has nothing to verify.
- Does NOT supersede ADR-COVE-01 (max_tokens budgets remain correct; this ADR is a prompt refinement only). The two ADRs compose: ADR-COVE-01 fixed the "CoVe crashes silently" layer; ADR-COVE-02 fixes the "CoVe runs but extracts the wrong shape of claim" layer. A third prompt refinement (D-052 / future ADR-COVE-03) may be needed to close the remaining hallucination gap.
- Does NOT apply to the distillation-path `BrainCoveService` (`app/distillation/cove_brain.py`) — that service verifies a SINGLE already-atomic coaching cue (claim extraction is skipped per ADR-DISTILL-03). If the distillation path ever adds claim extraction, this ADR's rules should be mirrored.

**Related:** FR-AICP-08 Stage 2 (CoVe loop for coaching output), ADR-COVE-01 (max_tokens budgets — precedent from the same E2E bench fixture), ADR-DISTILL-03 (coaching-path vs distillation-path CoVe scope separation). `backend/app/services/cove.py:109-166` (refined prompt body), `backend/tests/unit/test_cove.py::test_claim_extraction_prompt_*` (3 regression guards), `backend/scripts/oneoff/smoke_cove_claim_extraction_d050.py` (live-API qualitative gate). PR #90 (`6c41953`), session 49.

## ADR-COVE-03: CoVe claim extraction — inversion-guard + extrapolation-guard (Session 50)

**Context**: Session 49 PR #90 (D-050, `6c41953`) rewrote `_build_claim_extraction_prompt` to emit principle-level claims only (ADR-COVE-02). Post-fix prod E2E on bench analysis `c46023c9-b098-4083-9c19-dad174b14a04` confirmed the shift (17/17 claims across 2 iterations were principle-shaped; zero lifter-specific measurements) but immediately exposed two residual hallucination patterns: (a) **inversion** — iteration 2 reached 7/8 Yes, blocked by one No because the extractor paraphrased the coaching's "fast/rushed descent" criticism into a "slow descent" claim; source 2 verified that fast descent is the problem, so the inverted claim failed verification; (b) **extrapolation** — iteration 1 invented three principles not stated in the coaching: "minimum of 60°", "60–100° reference range", and "stretch-shortening cycle disruption from extreme eccentric". The first two are extrapolations of the coaching's stated 45–75° optimal range. The D-050 prompt's "do not invent a principle that was not written" rule catches bare-measurement-to-invented-principle transitions but not polarity-flipped paraphrases or over-reads of stated ranges.

**Decision**: Extend `_build_claim_extraction_prompt` with (a) an explicit inversion-guard paragraph forbidding the extractor from inverting, reversing, or negating the direction of a stated principle ("if coaching says fast descent is bad, do NOT extract slow descent is bad"), (b) an explicit extrapolation-guard paragraph forbidding extrapolation of a stated optimal range into an invented minimum, maximum, or alternative reference range, (c) one before/after worked example showing an inversion rejection (fast-descent issue → do-NOT-extract slow-descent claim), (d) one before/after worked example showing an extrapolation rejection (bare optimal-range issue → do-NOT-extract minimum/alternate-range claims). All D-050 content is preserved verbatim; signature, call sites, max_tokens, model, and schema unchanged.

**Consequences**:
- Core D-052 goal achieved: `cove_verified` flipped from **false → true** on the bench fixture. Session 50 prod E2E on analysis `43f25db8-c922-4211-bb98-5266c8ff6f74` (same `atharva-bench-nw-10s-720p.mp4` fixture sessions 46–49 used) returned `eval_scores.cove_verified=true` with iteration 2 converging at 7/7 Yes — all claims principle-shaped, all verified with source citations.
- `faithfulness` increased 0.82 → **0.88** (above the 0.80 RAGAS gate; `faithfulness_passed=true`). D-052 is net-neutral-or-positive on faithfulness; the prediction that further denominator-shift could lower it to 0.70–0.82 did not materialise.
- **Iteration 1 still produced one extrapolation** on the prod run (`c46023c9`'s "60–100° range" recurred as iteration 1 claim 1: "Optimal elbow angle at the bottom of the bench press is 60–100° from the torso"). The verification step correctly rejected it (answer: No, reasoning cites sources 1+4 specifying 45–75°). Step 4 revision then narrowed the iter-1 claim set to the correct "45–75°" principle and iter 2 converged. This is CoVe's self-correction working as designed — the guard is not a total barrier against extrapolation in iter 1, but the revision loop closes the gap.
- For coaching outputs that cite NO principles post-filter, claim extraction returns an empty list and the existing `if not claim_list.claims:` short-circuit in `_run_cove_loop` returns `CoveResult(cove_verified=True, iterations_run=0)`. This is correct semantics: an extraction with no falsifiable principle has nothing to verify.
- Does NOT supersede ADR-COVE-01 or ADR-COVE-02. The three ADRs compose: ADR-COVE-01 fixed "CoVe crashes silently"; ADR-COVE-02 fixed "CoVe runs but extracts measurement-level claims that always return Uncertain"; ADR-COVE-03 fixes "CoVe runs on principle-level claims but the extractor inverts or extrapolates in iter 1, now caught by verification + revision".
- Does NOT apply to the distillation-path `BrainCoveService` (`app/distillation/cove_brain.py`) — that service verifies a SINGLE already-atomic coaching cue (claim extraction skipped per ADR-DISTILL-03). If the distillation path ever adds claim extraction, this ADR's rules should be mirrored.
- Residual iter-1 extrapolation patterns are acceptable as long as convergence is reached in iter 2. If future prod E2E shows iter-2 convergence failing for inversion/extrapolation reasons (the two named D-052 failure modes), that warrants a new D-### refinement. `cove_verified=false` for any OTHER reason (new failure mode, retrieval quality, etc.) is a different follow-up.

**Related:** FR-AICP-08 Stage 2 (CoVe loop for coaching output), ADR-COVE-01 (max_tokens budgets), ADR-COVE-02 (D-050 principle-level extraction), ADR-DISTILL-03 (coaching-path vs distillation-path CoVe scope separation). `backend/app/services/cove.py:109-198` (tightened prompt body), `backend/tests/unit/test_cove.py::test_claim_extraction_prompt_prohibits_inversion`, `test_claim_extraction_prompt_prohibits_extrapolation`, `test_claim_extraction_prompt_has_negative_worked_examples` (3 regression guards), `backend/scripts/oneoff/smoke_cove_claim_extraction_d052.py` (adversarial qualitative gate). PR #92 (`8740388`), session 50.

## ADR-DISTILL-07: lifecycle_decision Qdrant API migration from search() to query_points() (Session 50)

**Context**: Since session 42 (`SPELIX_DISTILLATION_ENABLED=1` on prod), every distillation run's worker log contained `lifecycle_decision: qdrant search failed ('AsyncQdrantClient' object has no attribute 'search') — treating as ADD`. The pinned `qdrant-client==1.17.1` removed `search` on `AsyncQdrantClient`; only `query_points` is exposed. The try/except in `lifecycle_decision` collapsed the resulting `AttributeError` into `hits=[]`, which unconditionally routed every candidate to `ADD`. The 0.75–0.92 UPDATE band and the >0.92 NOOP band from FR-BRAIN-17 were structurally unreachable; duplicate candidates were over-admitted to the `coach_brain_candidates` review queue. Session 49 worker log inspection confirmed the warning on `c46023c9`'s distillation run; the tests never caught it because all mocks exposed `.search` via `MagicMock` auto-child-creation, so the assertion passed in-suite while the real API call failed in-prod.

**Decision**: Migrate `lifecycle_decision` to `query_points` via the project's canonical `QdrantClientWrapper` boundary. Unpack `response.points` instead of using the raw `search` return shape. Simultaneously drop the `wrapper._client` escape hatch in `app/workers/deps.py`, since the only caller that needed the raw client is now wrapper-compatible. Keep the try/except safety net — legitimate Qdrant outages still route to `ADD` with a warning log so distillation never crashes the graph for every candidate in a batch. Add `test_lifecycle_decision_never_calls_legacy_search` via `MagicMock(spec=QdrantClientWrapper)` to guard against future re-introduction of `.search` (the original `__getattr__` override plan from the D-053 plan proved brittle against MagicMock's `_unsupported_magics`; the `spec=` approach is stricter and self-documenting anyway).

**Consequences**:
- FR-BRAIN-17 cosine routing now actually routes: `>0.92 → NOOP`, `0.75–0.92 → UPDATE` (with same-transaction `confirmation_count` bump per FR-BRAIN-18), `<0.75 → ADD`. Post-D-053 prod E2E on analysis `0e5d755b-6506-4f2b-80ca-638eca1f7ccc` (fresh bench fixture upload) produced 5 candidate rows with real `nearest_cosine_sim` values: 2 UPDATE (0.8387, 0.8757) + 3 ADD (0.7258, 0.7420, 0.7205). Zero `search` warnings in worker logs post-deploy.
- The try/except was previously load-bearing (every path hit it). Post-D-053 it's a rare-path safety net — only fires on legitimate Qdrant outages. The warning-log message is rewritten to reference `query_points` so operators triaging future warnings can distinguish real outages from API drift. A noted operational gap: sustained 401/403 auth failures to Qdrant Cloud would be swallowed at WARNING level; a future improvement would inspect `exc` type and emit `logger.error` for 4xx specifically. Not blocking.
- `deps.py` no longer has a raw-client escape hatch — one less cross-cutting coupling. Any future wrapper-level instrumentation (request timing, circuit breaker, etc.) automatically covers distillation.
- Historical `coach_brain_candidates` rows created pre-D-053 retain `nearest_cosine_sim=0.0` and `lifecycle_decision=ADD`. D-053 does not retroactively rescore. Admin reviewers may see some historical `ADD` entries that should have been `UPDATE` — accepted as one-time residue, not backfilled.
- The `test_lifecycle_decision_never_calls_legacy_search` guard raises `AttributeError` if any future refactor touches `.search` on the injected `spec=QdrantClientWrapper` mock. This prevents silent re-introduction of the same class of drift. Also required a one-line update to `test_distillation_worker_body.py:276` (`ctx["qdrant_client"] is fake_qdrant_wrapper._client` → `is fake_qdrant_wrapper`) to match the new deps.py contract.
- Test-suite invisibility lesson: the pre-D-053 tests used `MagicMock` without `spec=`, which auto-creates any attribute accessed — so `.search` was silently satisfied in-suite even though the real API call failed in-prod. The class of bug (API-drift between pinned SDK and call-site code) is not catchable by unit tests unless the mock enforces the SDK surface via `spec=`. Going forward, prefer `MagicMock(spec=...)` when mocking external clients whose API surface may drift.

**Related:** FR-BRAIN-06 (distillation pipeline), FR-BRAIN-17 (cosine routing thresholds), FR-BRAIN-18 (UPDATE semantics: confirmation_count + source_analysis_ids append), ADR-DISTILL-01 (candidate table separation), ADR-DISTILL-03 (coaching-path vs distillation-path CoVe scope), ADR-RAG-03 (1024-dim dense vectors). `backend/app/distillation/lifecycle.py` (migrated call + docstring), `backend/app/workers/deps.py` (wrapper pass-through), `backend/CLAUDE.md` (updated gotcha), `backend/tests/unit/test_distillation_lifecycle.py::test_lifecycle_decision_never_calls_legacy_search`, `backend/tests/unit/test_distillation_worker_body.py:276` (review fix-up). PR #94 (`88fb0ae`), session 50.

## ADR-REPDET-03: D-044 atharva-bench.mov over-count — defer fix post-L2 after investigation rejects parameter-tuning and visibility-gating paths (Session 51, 2026-04-19)

**Context:** Session 45 ADR-REPDET-02 shipped the hybrid state-machine + peak/valley detector. On the `atharva-bench.mov` fixture (23s @ 59fps, hand-counted ground truth = 5 working reps), the hybrid reports 13 reps — a 2.6× over-count. Session 51 investigated whether a surgical parameter change or a structural signal filter could fix this without regressing the three other in-repo fixtures (`atharva-bench-nw-10s-720p.mp4` GT=1, `atharva-squat.mov` GT=5, `atharva-deadlift.mov` GT=5).

**Investigation** (tools preserved under `backend/scripts/oneoff/`):
- `diagnose_rep_detection_d044.py` — per-fixture pose extract + raw/smoothed elbow stats + SM vs PV split + matplotlib plot.
- `sweep_rep_detection_d044.py` — 640-combo grid over `(savgol_window ∈ {7,11,15,21}, polyorder ∈ {2,3}, prominence ∈ {20,25,30,35,40}, min_rep_s ∈ {0.5,0.75,1.0,1.5})`.
- `prototype_visibility_gate.py` — Tier-1 `sigmoid(visibility) * sigmoid(presence)` masking + linear interpolation at thresholds {0.25, 0.30, 0.35, 0.40}.

**Findings:**
1. The over-count on `atharva-bench.mov` comes from the **state machine, not the peak/valley fallback**. All 13 reps have `min_angle` below the 85° BOTTOM threshold; 4 have negative `min_angle` (Savgol polynomial overshoot below the [0°, 180°] valid range).
2. Raw elbow angle on `atharva-bench.mov` hits both 0° and 179.8° extremes — MediaPipe loses tracking during bar/elbow occlusion. Clean fixtures (`bench-nw-10s-720p`, `deadlift.mov`) stay well inside the valid range.
3. **Zero combos in the 640-combo sweep** land all four fixtures at exact ground truth (5/1/5/5). **Zero combos** get bench ≤ 7 while preserving squat=5 AND deadlift=5 exactly. The tightest preserving knob is `savgol_window: 7 → 11` which only moves bench 13 → 12 (marginal).
4. Tier-1 visibility gating is **ineffective**: raw `sigmoid(visibility) * sigmoid(presence)` on bench.mov ranges 0.25–0.49 (mean 0.37). Low-angle outlier frames (vis_min 0.26) correlate weakly with normal frames (vis_min 0.37). Thresholds 0.30 / 0.35 mask 16% / 24% of frames but bench still returns **13** reps. Threshold 0.40 masks 78% and drops bench to 8 but regresses squat to 4.

**Revised root-cause interpretation:** the 13 detected state-machine rep cycles on `atharva-bench.mov` correspond to **5 working reps + ~8 setup / re-grip / rack motions** the lifter actually performed in the 23s clip. The detector is NOT hallucinating — it faithfully counts every full `STANDING → BOTTOM → STANDING` traversal. Distinguishing "working reps" from "non-working bar motions" requires signal features (velocity profile, dwell time, ROM consistency) that are beyond both threshold tuning and single-frame visibility gating.

**Decision:**
- **Defer D-044 code fix to post-L2.** Ship ONLY the investigation artifacts (diagnostic + sweep + prototype scripts) and this ADR. No change to `rep_detection.py` or `signal_processing.py`.
- The L2 beta deadline (2026-05-03) is 14 days out. The maintenance bundle (D-046 / D-047 / D-049 / D-051 / D-054 / D-055) offers higher impact per hour than any of the three rejected D-044 paths.
- Re-scope the problem post-L2 from "fix a parameter" to "distinguish working reps from non-working bar motions" — likely via velocity/dwell-time gating, possibly a secondary ML classifier. Needs design work, not a one-line change. Tracked as new backlog row D-056.

**Consequences:**
- `atharva-bench.mov` continues to report 13 reps on prod. Users uploading multi-motion bench clips will see inflated rep counts. Mitigation: the UI already clamps rep detail to the first N reps; downstream form scoring is per-rep so scores don't inflate, only the count display does.
- No test-suite regression — no production code changed. Backend remains at 1704 passed / 27 skipped / 0 failed (post-D-053).
- Session 51 subagent-driven-development + main-agent investigation spent ~3 hours of MediaPipe-extraction + parameter-sweep time. This is captured in the three scripts for future re-use when D-044 is reopened.

**Rejected alternatives (documented so post-L2 reviewer does not retread):**
- **Widen Savgol window (Hypothesis D):** rejected — w=11 moves bench 13 → 12 only, insufficient gain; w=15/21 breaks squat.
- **Raise peak/valley prominence (Hypothesis A):** irrelevant — peak/valley fallback did not fire for bench.mov (SM returned 13).
- **Raise peak/valley distance (Hypothesis B):** same irrelevance.
- **Narrow fallback trigger (Hypothesis C):** same irrelevance.
- **Tier-1 visibility gating (Hypothesis F):** rejected — `sigmoid(visibility) × sigmoid(presence)` correlates weakly with landmark-position error; thresholds that catch tracking-loss frames also mask many good frames (78% at t=0.40) and break squat.
- **Post-hoc `min_angle` filter per exercise:** not implemented — would require per-exercise bounds tuning, fragile against future fixture variation, treats the symptom not the cause.
- **Parameter-tweak quick win (ship w=11):** rejected on cost/benefit — one full PR/CI/deploy cycle for a 13→12 improvement is not the best use of sprint time.

**Related:** ADR-REPDET-01, ADR-REPDET-02, FR-CVPL-15, FR-REPM-01, FR-REPM-05. Session 51, branch `fix/d044-bench-over-count`. Backlog: D-044 (deferred-post-L2), D-056 (post-L2 successor).


## ADR-REPDET-04: Rep-detection knobs flow through ThresholdConfig (Session 53, D-042)

**Context:** ADR-REPDET-02 (session 45) documented that `_PROMINENCE_DEG`,
`_STANDING_THRESHOLD`, `_DEPTH_THRESHOLD`, and `_MIN_REP_DURATION_S` in
`backend/app/cv/rep_detection.py` remained hardcoded rather than flowing
through `ThresholdConfig`, and deferred the fix to D-042. spelix-auditor
flagged this as H-1 (FR-SCOR-11 drift) — Expert Reviewers could edit
scoring/confidence thresholds via PR but not rep-detection thresholds.

**Decision:** All four knobs are now read from `ThresholdConfig` at
invocation time. Module-level dicts are deleted. New JSON keys live under
each exercise (`rep_detection_standing_angle_deg`,
`rep_detection_depth_angle_deg`, `rep_detection_prominence_deg`) plus
per-variant deadlift overrides (`rep_detection_depth_angle_{romanian,rdl}_deg`)
and a global `rep_detection.min_rep_duration_s` top-level section. Public
`detect_reps` and its two private paths (`_detect_reps_state_machine`,
`_detect_reps_peak_valley`) accept `cfg: ThresholdConfig` as a required
final positional parameter. `pipeline.py` hoists its existing
`cfg = ThresholdConfig()` instantiation from Step 7 (confidence scoring) to
above Step 5 (rep detection) and passes the same instance into `detect_reps`.

**Consequences:**
- Expert Reviewers can now tune rep-detection thresholds via PR against
  `config/thresholds_v1.json`, matching the FR-SCOR-11 workflow for all
  other thresholds.
- `analyses.threshold_version` already freezes the version per-analysis
  (from Phase 1 wiring), so threshold edits do not retroactively alter
  scored analyses.
- Hysteresis (`_HYSTERESIS_DEG = 5.0`) remains a module constant — it's a
  numerical-stability knob for state-machine transition edges, not a
  kinesiology threshold. Promoting it to cfg would invite confusion and
  offers no meaningful tunability.
- Supersedes the final bullet of ADR-REPDET-02 (`"_PROMINENCE_DEG +
  _STANDING_THRESHOLD + _DEPTH_THRESHOLD + _MIN_REP_DURATION_S remain
  hardcoded…"`). Closes spelix-auditor H-1 from PR #84. D-043 (additive
  regression test for <20° partial descent across both paths) closes
  M-2 from the same audit.

**Related:** FR-SCOR-11, FR-REPM-01, FR-REPM-05, FR-CVPL-15, FR-CVPL-07.
`backend/app/cv/rep_detection.py`, `config/thresholds_v1.json`,
`backend/app/services/pipeline.py`, `backend/tests/unit/test_rep_detection.py`,
`backend/tests/unit/test_rep_detection_cfg_helpers.py`,
`backend/tests/unit/test_threshold_config_rep_detection.py`,
`backend/tests/unit/test_pipeline_rep_detection_cfg.py`. ADR-018 (ThresholdConfig
design). Supersedes ADR-REPDET-02 final bullet; otherwise preserves
ADR-REPDET-02 hybrid-detection decisions.

### ADR-COVE-RERUN-01: CoVe re-run on admin content edit is best-effort

**Context:** D-039. When an admin edits a Coach Brain candidate's content during approval, the promoted entry should carry a CoVe result reflecting the edited content, not the stale distillation-time verification.

**Decision:** Re-run `BrainCoveService.verify_claim` with fresh `papers_rag` contexts fetched via `RetrievalService.hybrid_search`. The re-run is best-effort: if retrieval or verification fails, the original `cove_verified`/`cove_explanation` values are preserved and `cove_rerun_error` is logged in `extra_metadata`. The approve flow never blocks on CoVe failure.

**Rationale:** Blocking approval on CoVe would make the review queue unusable when Qdrant or Haiku is down. The admin has already reviewed the content and made a trust decision; CoVe is a secondary verification signal. Logging the error type in metadata provides an audit trail without blocking the reviewer's workflow.

**Consequences:** Entries promoted during a CoVe outage will carry stale verification. The admin dashboard could surface a "CoVe stale" badge in a future iteration. The `cove_rerun` boolean in extra_metadata distinguishes re-verified entries from passthrough entries.

### ADR-SECU-05: JWT role claim lives in `app_metadata`, not `user_metadata`

**Context:** Pre-beta audit L-09. Supabase JWTs have two metadata bags — `user_metadata` is user-editable via the client SDK, while `app_metadata` can only be written by service-role operations. Reading privilege claims from `user_metadata` is a privilege-escalation vector: any authenticated user can self-grant admin access via `supabase.auth.updateUser()`.

**Decision:** `backend/app/api/deps.py` reads `role` (and any future privilege claim such as `biomechanics_qualified`) exclusively from `payload["app_metadata"]`. `user_metadata` is ignored for all security-relevant parsing. Defaults are restrictive — missing `role` → `"user"`, missing `biomechanics_qualified` → `False`.

**Consequences:**
- A one-off backfill script (`backend/scripts/oneoff/migrate_roles_to_app_metadata.py`) copies existing roles from `user_metadata` to `app_metadata`. Ran successfully against prod on 2026-04-21: 0 users needed migration — all 2 privileged users already had their role in `app_metadata`, so the L-09 fix was a no-op for existing users.
- New privileged roles must be assigned via the Supabase admin dashboard or the service-role SDK, never via client-side `updateUser()`.
- Any new privilege claim follows the same rule: live in `app_metadata`, default-restrictive, defensive `.get(..., False)` parsing.

**Related:** L-09 audit finding, PR #111 (commit `0b5363c`). Supersedes no prior ADR — earlier code was an oversight.

### ADR-ADMN-03: Compensation candidates require `biomechanics_qualified` admin

**Context:** Phase 3 compliance audit H-02. FR-ADMN-12 states compensation Coach Brain entries "shall be routed to biomechanics-qualified reviewers." Previously any admin could approve any entry.

**Decision:** `coach_brain_candidates.requires_technical_review` is set to `True` at distillation time when `entry_type == "compensation"` (existing behavior from M-01 fix, extended in #108). `CandidateReviewService.approve()` now takes an `approver_qualified: bool` parameter. When `candidate.requires_technical_review` is True and `approver_qualified` is False, the service raises `NotBiomechanicsQualified`, which the router maps to HTTP 403 with error code `NOT_BIOMECHANICS_QUALIFIED`. The approver's qualification flag is sourced from the JWT `app_metadata.biomechanics_qualified` claim via `CurrentUser.biomechanics_qualified` (per ADR-SECU-05).

**Rationale:** Compensation entries encode clinical reasoning about movement dysfunction — approving the wrong compensation cue can put users at injury risk. Gating approval on an orthogonal-to-role qualification flag lets us expand admin access without loosening the biomechanics gate. Non-compensation entries (cues, corrections, principles, drills) remain approvable by any admin.

**Consequences:**
- New admins default to `biomechanics_qualified=False`. They can promote cue/correction/principle/drill candidates but receive HTTP 403 on compensation candidates.
- Set the flag via Supabase service-role: `PUT /auth/v1/admin/users/{id}` with `{"app_metadata": {"biomechanics_qualified": true}}`. Applied in this session for `atharva6905+admin-p3006@gmail.com`.
- Frontend gates the biomechanics banner on `candidate.requires_technical_review` (the authoritative DB flag), not on `entry_type === "compensation"`. The two are decoupled so future entry types can require technical review without a string match.
- The approve endpoint surfaces `NOT_BIOMECHANICS_QUALIFIED` specifically so the admin UI can render a clear "you can't approve this one" state rather than a generic 403.

**Related:** H-01, H-02 audit findings. FR-ADMN-12. PR #112 (commits `341779f`, `0e45401`). Builds on ADR-SECU-05.

### ADR-CONFIG-01: Runtime constants centralized in `app/config_constants.py`

**Context:** Pre-beta audit M-11 and L-05. Magic numbers (`recursion_limit=15`, JWKS TTL = 3600, various `MAX_TOKENS`, retry limits, timeout values) were scattered across a dozen files. Any tuning change required hunting them down; env-override wasn't possible without a code change.

**Decision:** A single module `backend/app/config_constants.py` defines all runtime constants as module-level `int | float` values sourced from `os.getenv("SPELIX_*", default)`. Consumers import with aliased names to preserve local readability (e.g. `from app.config_constants import LLM_MAX_TOKENS_CHAT as CHAT_MAX_TOKENS`). This is distinct from `ThresholdConfig` (FR-SCOR-11), which is reserved for kinesiology thresholds that Expert Reviewers tune via PR — `config_constants` holds infrastructure/runtime knobs that only engineers change.

**Consequences:**
- Every constant has a `SPELIX_*` env var for per-deploy override without code change (e.g. bump `SPELIX_AGENT_TIMEOUT=120` on the droplet to test a longer budget).
- New constants go in this module by default. The bar to introduce a new file-local magic number is now "why isn't this a config constant?"
- Changing a default requires a code change + review, preserving the architectural decision trail for hot spots like `AGENT_RECURSION_LIMIT` that are locked by SRS (NFR-RELI-09).
- Does NOT replace `ThresholdConfig` — coaching/scoring thresholds have a separate versioning flow via `config/thresholds_v1.json` with provenance citations. Don't mix the two.

**Related:** M-11, L-05 audit findings. ADR-018 (ThresholdConfig design) is the orthogonal file for kinesiology tuning. PRs #110 (commit `0a2fe8c`) and #111 (commit `2bed7d1`).

## ADR-CHAT-01: `ChatService.send_message` uses `get_by_id_with_relations` (Session 59)

**Context:** Production hit HTTP 500 on `POST /api/v1/analyses/{id}/chat` with `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`. Root cause: the service called `AnalysisRepository.get_by_id()` which issues a plain SELECT without eager loading, then accessed `analysis.coaching_result.structured_output_json` and `.retrieved_sources_json` to build the LLM system prompt. In SQLAlchemy 2.0 async, lazy-loading a relationship outside the greenlet context raises `MissingGreenlet` — which happened here because `coaching_result` is a default-lazy `relationship(...)` without `lazy="selectin"`.

**Decision:** `ChatService.send_message` uses `get_by_id_with_relations` (already existed, used by the analyses detail endpoint) which adds `.options(selectinload(Analysis.coaching_result), selectinload(Analysis.rep_metrics))`. `get_history` at line 151 is left on plain `get_by_id` because it only accesses `analysis.user_id` (a scalar column, no lazy-load risk). An integration test (`tests/integration/test_chat_greenlet.py`) uses two independent engines to prove the old path raises `MissingGreenlet` and the new path does not.

**Rejected alternatives:**
- **`lazy="selectin"` on `Analysis.coaching_result`** — would make every list query (`GET /analyses`, admin log, history page) do an N+1 with coaching_result, which is heavy JSONB. Relationship-level eager defaults are the wrong tool for one call site.
- **New `get_by_id_with_coaching`** method — would duplicate `get_by_id_with_relations` minus `rep_metrics`. The extra selectinload for `rep_metrics` is one cheap query per chat send; not worth a new method.

**Consequences:**
- Any future chat-service code that accesses new relationships (e.g. `chat_messages`) must either use a method that eager-loads them or live inside the same awaited session. Column access is still safe.
- Similar pattern applies anywhere we load an Analysis and then descend into a relationship: use `get_by_id_with_relations` OR refactor to hold the session alive through the access.
- Documented in `backend/CLAUDE.md` under a new "SQLAlchemy async relationship loading" gotcha (to-add as part of session 60 CLAUDE.md hygiene).

**Related:** PR #113 (commit `82cfa80`). FR-AICP-17 (follow-up chat). Also ADR-ROOTCAUSE-01 (fix at the source, not the symptom).

## ADR-ROOTCAUSE-01: Fix at the source, not the symptom (Session 59)

**Context:** Two bugs in session 59 required a second PR after the first fix failed:
1. `[object Object]` render on 404 — first fix (PR #115) added defensive type guards in `ResultsPage.tsx` and `useAnalysisDetail.ts`. After deploy, the UI still showed `[object Object]`. Investigation found the actual source: `api/analyses.ts` was coercing a nested-object backend response via `new Error(obj)` → `String(obj)` → `"[object Object]"`. The defensive guards downstream treated this string correctly but by then the content was already wrong. Second fix (PR #116) type-guarded the raw message before `new Error()`.
2. Worker `(unhealthy)` — first fix (PR #115) rewrote the healthcheck command (added `r.ping()`, extended `start_period`). After deploy, the worker stayed `(unhealthy)`. Running the command manually via `docker exec` revealed `ModuleNotFoundError: No module named 'redis'` — the healthcheck used `python` (system) instead of `/app/.venv/bin/python` (uv venv). Second fix (PR #116) switched interpreter.

In both cases the investigator's pre-fix report had identified the true source as a "possible" cause, but the implementer chose layered defensive coding over fixing the source directly. Net result: 2× PR/CI/merge/deploy cycles per bug.

**Decision:** When an investigation identifies a specific coercion site, API boundary, or execution site as the source of a symptom, fix THAT site first. Defensive coding at downstream layers is acceptable AS ADDITIONAL HARDENING, but must never substitute for a source fix.

**Concrete rules:**
- If a bug reaches the UI as garbled data, trace backwards to the point where the data was last correct. That is the fix site.
- If a healthcheck is failing, `docker exec <container> <exact-command>` before committing a new command. "The image has Python" is not equivalent to "our dependencies are on the system path."
- Investigator reports that say "X is a possible cause" are not "X is speculative" — treat them as "X is the likely cause; verify and fix". Ruling out X before fixing Y saves round trips.
- Defensive guards downstream of the root cause are fine, but commit them ALONGSIDE the source fix in one PR, not as a first pass that ships while the real fix waits for a second session.

**Rejected alternatives:**
- **"Ship defensive fixes first, iterate if prod shows the bug persists"** — this session proved exactly why that's wrong. Each deploy round costs 5-10 min of CI + verification, and the defensive code accumulates noise (typeof guards on already-typed values, etc.) that must be maintained forever.
- **"Always fix every possible site"** — goes too far; we'd be refactoring whole files. The rule is "fix the identified source site and the downstream display site if it's trivially tightened". The `ResultsPage` typeof guard and the `useAnalysisDetail` 3-arm ternary are retained as belt-and-suspenders, but the actual fix is in `api/analyses.ts`.

**Consequences:**
- Pre-commit mental checklist for bug fixes: "Is this the source or a symptom site? If symptom, where is the source?"
- Investigator prompts should emphasize "identify the source site, not just a possible source." See the investigator dispatch for L2-E2E-04 as a template.
- Retros on session 59 items L2-E2E-03 and L2-E2E-04 documented in `backlog.md`.

**Related:** Session 59 retro. PR #115 (first pass) + PR #116 (root cause) for both bugs. No code artifact — this is a process ADR.

## ADR-INFRA-02: Container healthchecks use `/app/.venv/bin/python` for dependency access (Session 59)

**Context:** The worker Dockerfile installs Python dependencies via `uv sync` into `/app/.venv`. The container's runtime command is `uv run --no-dev streaq run app.workers.streaq_worker:worker`, which activates the venv. But `docker-compose.prod.yml` healthcheck uses `["CMD", "python", "-c", "..."]` — `python` is the system Python (installed via the Dockerfile's `python:3.12-slim` base image), NOT the venv. System Python has zero app deps, so `import redis` fails immediately with `ModuleNotFoundError`, making the healthcheck a deterministic fail on every probe.

**Decision:** All container healthchecks that need app dependencies (`redis`, `httpx`, etc.) MUST use `/app/.venv/bin/python` explicitly as the interpreter. System `python` is only for no-deps scripts.

**Rejected alternatives:**
- **`uv run python -c "..."`** — `uv run` triggers a sync step that writes to the `.venv` directory. In a running container with `.venv` potentially mounted read-only OR with strict permissions, the sync fails with "Permission denied" (observed on prod during this session). `uv run` is for dev, not healthchecks.
- **Install deps to system Python via `pip install`** — defeats the purpose of `uv`-managed venvs; doubles dependency storage in the image.
- **`source /app/.venv/bin/activate && python -c "..."`** — Docker's `CMD ["a","b","c"]` form doesn't run through a shell, so `source` wouldn't expand. The explicit binary path is simpler.

**Consequences:**
- Healthcheck commands in `docker-compose.prod.yml` follow the pattern `["CMD", "/app/.venv/bin/python", "-c", "..."]`.
- Moving Python version (3.12 → 3.13 someday) requires updating the hardcoded path, but `uv` pins the venv's Python version in sync with `pyproject.toml` so the path is stable within a Python major.
- When adding new healthchecks: SSH to the droplet and run `docker exec <container> /app/.venv/bin/python -c "..."` manually to confirm the command works BEFORE committing a healthcheck change. This session proved the cost of skipping that step.

**Related:** PR #116 (commit `fea02e1`). Backend `Dockerfile`. Supersedes the healthcheck portion of PR #115's initial approach.

## ADR-EXPV-08 — Threshold validation UI uses a flag-only DB table; PR review remains the approval path

**Date:** 2026-04-21
**Context:** FR-EXPV-08 (Phase 3, Should) requires the Expert Reviewer to flag angle thresholds that conflict with literature. FR-SCOR-11 already mandates that threshold changes ship via PR review of `config/thresholds_v1.json`. We needed an in-portal workflow without breaking that approval model.

**Decision:** Add a `threshold_flags` table (migration 022) storing reviewer flags with `{section, key, current_value (snapshot), current_citation (snapshot), proposed_value, proposed_citation, rationale, status}`. Surface via `ExpertThresholdsPage` under `/expert/thresholds`. The UI never writes to `config/thresholds_v1.json`; an admin reviews flags via `/admin/threshold-flags` and, if accepted, opens a PR mutating the JSON. Flag rows are audit-only proposals.

**Rejected alternatives:**
- Auto-opening a GitHub issue per flag: rejected — requires GitHub API credentials in prod, couples the product DB to external issue state, and duplicates the audit trail.
- Append-only JSON file of flags in the repo: rejected — harder to query, no per-user RLS, no resolution workflow.
- Editing threshold values in the UI: rejected — violates FR-SCOR-11 (PR review IS the approval flow).

**Scope boundaries enforced in the plan:**
- Only angle-threshold sections surface: `squat`, `bench`, `deadlift`, `control`. Non-angle sections (`scoring_weights`, `phase_multipliers`, `experience_tolerance`, `score_descriptors`, `confidence_landmark_weights`) are filtered out of the listing.
- `current_value` + `current_citation` are snapshotted at submission time so a later config change doesn't retroactively rewrite a flag's context. The repository's `update_status` method writes only `status / resolution_note / resolved_by / resolved_at / updated_at` — snapshot columns are structurally unreachable from any update path.

**RLS model:** SELECT — reviewer sees own flags only; admin sees all. INSERT — expert_reviewer or admin; `reviewer_id` must equal `auth.uid()` (prevents impersonation). UPDATE — admin only, with `WITH CHECK` also admin-only (prevents admin from mutating `reviewer_id` to escape attribution). No DDL FK to `auth.users`; RLS is the integrity gate.

**Consequences:** New table + 5 endpoints + 1 page + 1 modal component. Reviewers get in-portal flag submission with ≥20-char rationale + ≥5-char citation enforced at both the Pydantic layer (fast 422) and DB CHECK layer (defense in depth). Admin resolution uses terminal-only status literal (`resolved | rejected`) — the UI cannot reset a flag back to `open`.

**Related:** Plan `docs/superpowers/plans/2026-04-21-fr-expv-08-threshold-validation-ui.md`. SRS FR-EXPV-08 (§3.15), FR-SCOR-11 (§3.9). Migration 022.

## ADR-E2E-01 — Per-role E2E test accounts via Supabase service-role script

**Context:** Session 60 FR-EXPV-08 E2E walkthrough required testing 3 distinct roles (regular user, expert_reviewer, admin) on spelix.app. Prior to this session, the only documented test account was `atharva6905@gmail.com` (admin) — insufficient for role-gate verification where we need to prove that a non-expert cannot reach `/expert/*` and that an expert flag becomes visible to an admin reviewer. Creating accounts by hand through the signup UI then manually toggling `app_metadata.role` via ad-hoc curl is slow and error-prone, especially when the service role key lives only on the prod droplet.

**Decision:** Per-role E2E test accounts are provisioned by a reusable one-off Python script at `backend/scripts/oneoff/e2e_fr_expv_08_test_accounts.py` that reads Supabase URL + service role key from a `CREDS_FILE` env-pointed `.env`-style file, calls `POST /auth/v1/admin/users` with `email_confirm=true` and inline `app_metadata`, and prints email + freshly-generated 20-char alphanumeric password to stdout. The creds file is retrieved via `ssh spelix-droplet "cat /home/deploy/spelix/.env.prod | grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)='" > /tmp/spelix_creds.env` and deleted at session end. Script uses stdlib `urllib` only (no supabase-py dependency) so it runs from any Python venv.

**Rejected alternatives:**
- Hardcoded credentials in a committed `.env.e2e`: rejected — secrets in git, high blast radius.
- Supabase CLI `supabase users create`: rejected — requires local Supabase project linkage and doesn't set `app_metadata` in one call.
- supabase-py `auth.admin.create_user()`: rejected — adds a heavy dependency to a 60-line script; urllib is sufficient.

**Consequences:** E2E test accounts are (a) reproducible via the script, (b) traceable by email convention (`e2e-<role>@spelix.internal`), (c) cheap to re-create if revoked. Passwords are per-invocation and printed once — they are NOT persisted anywhere, so losing the session output means re-running the script to get new passwords. The 3 session-60 accounts (`e2e-regular`, `e2e-expert`, `e2e-admin2`) were left in place for future E2E sessions to reuse; delete them with `DELETE /auth/v1/admin/users/{id}` when no longer needed. For future roles (e.g. `biomechanics_reviewer` when Coach Brain compensation routing lands) extend `TEST_ACCOUNTS` in the script rather than forking it.

**Related:** `backend/scripts/oneoff/e2e_fr_expv_08_test_accounts.py`. Previous practice documented in session 59 handoff §2 ("`app_metadata.role=admin + biomechanics_qualified=true` set on atharva6905@gmail.com via Supabase admin API"). Memory `feedback_rate_limit_testing` ("Use separate test accounts for E2E") — ADR-E2E-01 now codifies the "how".

## ADR-QGATE-COMMERCIAL-GYM — Anchor-based single_person gate + visibility-gated bbox framing gate

**Date:** 2026-04-24

**Context:** Three private-beta fixture videos (`atharva-squat.mov`, `atharva-bench.mov`, `atharva-deadlift.mov` — 1080×1920 portrait, ~60fps, 20-26s, shot in a commercial gym at ~3-4 m camera distance) were all rejected by the upload quality gate on prod. Rejection reasons: `single_person` (hip-midpoint jumps when MediaPipe briefly re-acquires onto background bystanders during occlusion) and `framing` (bbox underestimated because hallucinated low-visibility landmarks pulled the bbox area below 0.30 lab-calibrated threshold). Neither rejection reflected a genuine problem with the video — the lifter was alone in frame and clearly visible throughout.

**Decision:** Two coordinated changes to `backend/app/cv/quality_gates.py` only (no schema or API changes required):

1. **`check_single_person` — anchor-based identity-jump detection.** Replace the naïve "any large hip jump across >2 of 30 sampled frames = multiple people" rule with an anchor-relative test. The anchor is the median hip-midpoint x from the first 3 high-visibility samples. Reject only if the tracker is off-anchor (`|midpoint_x − anchor| > 0.25`) for 4+ consecutive samples OR for >30% of total samples. This tolerates brief MediaPipe re-acquisition events (≤3 frames) while still catching genuine dual-lifter or sustained-swap scenarios.

2. **`check_framing` — visibility-gated bbox + lower minimum fraction.** Skip any sample frame where fewer than 10 of 33 landmarks have `sigmoid(visibility) >= 0.50`. This prevents hallucinated off-body landmarks from inflating (or deflating) bbox estimates. Also lower `_FRAMING_MIN_FRACTION` from 0.30 to 0.20 to reflect real commercial-gym camera distances (3-4 m produces ~12-20% of portrait frame area vs ~30% in a lab at 1.5 m).

**Rejected alternatives:**
- Lowering thresholds globally without visibility gating: rejected — would allow genuinely bad videos (e.g. lifter at edge of frame) to pass framing gate.
- Disabling the single_person gate entirely: rejected — dual-lifter uploads are a real failure mode; we just need a smarter rule that tolerates brief tracker blips.
- Adding a per-user "commercial gym" flag that bypasses gates: rejected — adds UI surface area and a flag that is easy to forget to unset.
- Raising `_MAX_JUMP_COUNT` to 5 or 10 (the previous incremental approach): rejected — this is a patch on a bad predicate; anchor-relative detection is correct by design.

**Consequences:** The 3 private-beta fixtures now pass `run_quality_gates`. The framing and single_person gates remain meaningful for genuine quality issues (distant/partial shots, two lifters in frame). New constants documented in `backend/CLAUDE.md` "Quality gate" gotcha block. Integration test at `backend/tests/integration/test_quality_gates_atharva_fixtures.py` (marked `@pytest.mark.slow`) serves as the acceptance regression for all 3 fixtures.

**Related:** `backend/app/cv/quality_gates.py`, `backend/tests/unit/test_quality_gates.py`, `backend/tests/integration/test_quality_gates_atharva_fixtures.py`. Design spec: `docs/superpowers/specs/2026-04-24-commercial-gym-quality-gate-design.md`. Implementation plan: `docs/superpowers/plans/2026-04-24-commercial-gym-quality-gate-fix.md`. SRS FR-CVPL-06 (single person), FR-CVPL-07 (framing).

## ADR-QGATE-COMMERCIAL-GYM-CALIBRATION-01 — `_FRAMING_MIN_FRACTION` 0.20 → 0.18 follow-up

**Date:** 2026-04-25

**Context:** ADR-QGATE-COMMERCIAL-GYM lowered `_FRAMING_MIN_FRACTION` from 0.30 to 0.20 (portrait floor 0.1125) under the hypothesis that the visibility-gated bbox would also raise the metric for genuine commercial-gym videos. Empirically that hypothesis only partially held: the squat fixture (`atharva-squat.mov`, analysis `1b6a1312`) post-PR-#121 still failed framing at metric=0.1115 vs threshold=0.1125 — short by **0.0009**. Visibility gating barely shifted the squat metric because most landmarks on a commercial-gym lifter at 3-4 m have `sigmoid(visibility) ≥ 0.5`; the bbox-shrinkage pathology only dominates the 90th-percentile in deeply-occluded clips. The spec authorised an empirical follow-up: "If the visibility-gated metric still falls under 0.1125, the floor is reduced further as a follow-up commit."

**Decision:** Lower `_FRAMING_MIN_FRACTION` from 0.20 to 0.18 in `backend/app/cv/quality_gates.py:34`. Portrait floor becomes `0.18 × 0.5625 = 0.10125`. Updates 2 unit tests (`test_landscape_threshold_is_0_18`, `test_portrait_floor_is_0_10125`). Single constant change; no logic change to anchor algorithm or visibility-gating bbox logic from ADR-QGATE-COMMERCIAL-GYM.

**Consequences:** Squat fixture now passes prod E2E with framing=0.1116 (0.001 margin over 0.10125). Bench (0.2479) and deadlift (0.1673) remain comfortably above threshold. Lower bound makes the framing gate less discriminating against very-distant subjects, but the visibility-gated bbox skip (≥10 visible landmarks required) prevents truly absent subjects from passing. Future user reports of inflated/false-positive completion may need the gate revisited.

**Related:** PR #122 (`b5b9d80f`). `backend/app/cv/quality_gates.py`, `backend/tests/unit/test_quality_gates.py`. Supersedes the 0.20 calibration in ADR-QGATE-COMMERCIAL-GYM.

## ADR-STREAQ-TIMEOUT-01 — `process_analysis` per-task timeout 900 → 1800 s

**Date:** 2026-04-25

**Context:** ADR-060 lowered `process_analysis` streaq per-task timeout from 1800 s (the ADR-058 safety net) to 900 s after D-035 dropped barbell-tracking from 24.4 min to 2 min — the 670 s telemetry budget for a 22.8 s reference clip suggested 900 s was sufficient. That budget did NOT account for **CoVe verification iterations** in the LLM coaching phase: each rep adds claim-extraction + verification calls, so longer videos produce more reps and more claims linearly. Prod E2E of `atharva-deadlift.mov` (26.2 s, 1547 frames, 4 reps; analysis `435065d5`, streaq task `e6d23bc3`) hit the 900 s ceiling exactly during post-gate coaching — `task process_analysis … timed out` at `02:56:55 UTC` after starting `02:41:55 UTC`. DB row stuck at `status='processing'`, quality gate had passed cleanly (framing 0.1673, single_person 0.0).

**Decision:** Raise the `@worker.task(timeout=…)` decorator on `process_analysis` in `backend/app/workers/streaq_worker.py:150` from 900 → 1800 s. Restores the ADR-058 safety net. Adds regression test `test_process_analysis_timeout_at_least_1800_seconds` in `backend/tests/unit/test_streaq_worker.py` that string-checks the decorator (avoids streaq version coupling) — accidental future reduction below 1800 s fails CI rather than prod.

**Rejected alternatives:**
- Splitting scoring + coaching into separate streaq tasks (architecturally cleaner — each phase gets its own budget + retry semantics): rejected for L2 sprint; tracked as post-beta follow-up. Single-line bump unblocks beta launch immediately.
- Streaming coaching to bypass the per-task timeout: rejected — instructor's stream-then-reparse already doubles token cost (ADR-021); deeper refactor needed first.
- Per-video adaptive timeout: rejected — adds complexity without removing the underlying CoVe iteration cost.

**Consequences:** Long-video analyses (≥25 s with multiple reps) no longer time out mid-coaching. Concurrency=1 means a single 30-min task blocks the queue, so latency for the next user grows. Acceptable at current beta volume (<10 analyses/day). Verified end-to-end on prod: deadlift `0ac10ed6` reached `status=completed` in ~18 min.

**Related:** PR #124 (`2d62f108`). `backend/app/workers/streaq_worker.py`, `backend/tests/unit/test_streaq_worker.py`. Supersedes the 900 s value from ADR-060. Future: split `process_analysis` into pose+gate+score (CV-bound, fast) + coach+CoVe (LLM-bound, slow) tasks with independent budgets.

## ADR-BRAIN-10: FR-BRAIN-06 distillation graph has 7 nodes, not 5 (Session 62)

**Context.** SRS v2.1 FR-BRAIN-06 (2026-04-12) specifies the distillation graph as five nodes: `extract_insights → validate_quality → format_entry → store_entry → END`. Implementation (PRs #79–#100, Phase 3) added two more nodes between `validate_quality` and `format_entry`:
1. `lifecycle_decision` — FR-BRAIN-17 ADD/UPDATE/NOOP cosine-similarity routing.
2. `cove_verify` — FR-BRAIN-14 brain-side CoVe contradiction guard for UPDATE-path candidates.

The 2026-04-27 spelix-auditor sweep flagged the SRS-vs-runtime divergence (auditor finding H-03).

**Decision.** Update SRS FR-BRAIN-06 row to reflect the runtime: seven nodes, `extract_insights → validate_quality → lifecycle_decision → cove_verify → format_entry → store_entry → END`. The added nodes are required to satisfy independent SRS requirements: FR-BRAIN-14 (Should) for `cove_verify` and FR-BRAIN-17 (Must) for `lifecycle_decision`. Both rows are gate-relevant for Phase 3. Removing them to "match the spec" would violate independent SRS requirements. The SRS text is the bug, not the implementation.

**Consequences.**
- Phase 3 transition gate uses the corrected SRS row.
- Future ADRs that touch FR-BRAIN-06 nodes must update both the row and the implementation in lockstep.
- No code change required.

**Supersedes.** SRS v2.1 FR-BRAIN-06 5-node sequence (clarifies; does not contradict the rest of the row).

## ADR-BRAIN-11: Coach Brain tombstone pattern — `status='deprecated'` + `extra_metadata.rejected_reason` JSONB (Session 62)

**Context.** Two SRS Must rows soft-delete `coach_brain_entries` rows: FR-BRAIN-16 (consent withdrawal cascade) and FR-BRAIN-17 (contradicted-by-new-evidence). Both SRS rows literally specify `status='rejected'` + a `rejected_reason` column. But `coach_brain_entries.status` has a CHECK constraint allowing only `('seed','active','deprecated')` — and there is no `rejected_reason` column on the model. Phase 2 shipped FR-BRAIN-16 with a workaround (`backend/app/repositories/coach_brain.py:soft_delete_empty_unconfirmed`) using `status='deprecated'` + a `metadata || jsonb '{...}'` merge. The 2026-04-27 spelix-auditor sweep proposed adding `'rejected'` to the CHECK + a new column for FR-BRAIN-17 — that would have required a migration on a 6-day gate window AND introduced two distinct soft-delete paths.

**Decision.** All Coach Brain entry tombstones use the same pattern: `existing.status = 'deprecated'` + `existing.extra_metadata = {**existing.extra_metadata, 'rejected_reason': '<reason_string>'}`. Reasons are convention-driven free strings: `'source_consent_withdrawn'` (FR-BRAIN-16), `'contradicted_by_<candidate_uuid>'` (FR-BRAIN-17). Used in `backend/app/repositories/coach_brain.py:soft_delete_empty_unconfirmed` and `backend/app/distillation/store.py:store_entry`. No migration. No new column. SRS prose is the bug; the runtime invariant is canonical.

**Consequences.** New tombstone reasons are 1-line additions to either function — no migration, no model change. Consumers querying for "rejected" entries must filter by `status='deprecated'` AND `extra_metadata->>'rejected_reason' = ?` — there is no clean SQL boolean column for this. Adding `'rejected'` to the CHECK or a `rejected_reason` column at any future point requires migrating both call sites and rewriting downstream queries. If a Phase 4 reporting need surfaces and the JSONB query becomes hot, **then** consider promoting `rejected_reason` to a real column behind a feature flag; until that need is concrete, the JSONB convention stays.

## ADR-EXPERT-02: Docling for expert-uploaded PDF text extraction (Session 63)

**Context.** Expert-uploaded papers are stored in Supabase Storage as raw PDFs. The `ingest_paper` worker (ADR-EXPERT-01) was a stub that downloaded 8 magic bytes and logged `docling_pending`. The existing `IngestionService` (P2-004) accepts raw text + optional sections dict — it handles chunking, Cohere embedding, and Qdrant upsert. The missing piece was PDF → text extraction.

**Decision.** Use Docling (`docling>=2.0.0`) for PDF text extraction with section-aware parsing. `pdf_extraction.py` wraps `DocumentConverter` inside `asyncio.to_thread()` (CPU-bound). It returns `(full_text, sections_dict_or_None)` where sections are keyed by heading type (abstract, methods, results, discussion, conclusion). The worker calls this, then passes output to `IngestionService.ingest_document()`.

**Key constraints:**
- `IngestionService` has a hard guard: `review_status == "reviewed_approved"` required. Expert uploads arrive as `"pending"`. The worker returns `status="pending_review"` early.
- Ingestion is triggered when an admin approves the paper via `PATCH /expert/papers/{id}/review` with `decision="reviewed_approved"` — this enqueues `ingest_paper`.
- `WorkerContext` now wires `paper_storage` (PaperStorageService) and `db_session_maker` (async_session) in `lifespan()`, previously both `None`.
- `chunk_count` is written back to `rag_documents` after ingestion via new `RagDocumentRepository.update_chunk_count()`.

**Alternatives considered:**
- **PyMuPDF (fitz)**: lighter, faster, but no section-aware parsing. Docling's section extraction maps directly to IngestionService's `sections` parameter for section-aware chunking.
- **pymupdf4llm**: markdown output only, no structured section dict.
- **Unstructured.io**: heavier dependency, cloud-hosted API tier, overkill for straightforward PDF parsing.

**Consequences.** `docling` adds ~30 MB to the Docker image. The worker task timeout is 300s (may need increase for very large PDFs — monitor after first real uploads). Docling's `DocumentConverter` loads an ML model on first call (~2s cold start); subsequent calls reuse it within the worker process.

## ADR-CONSENT-GATE-01: Mandatory consent gate before upload (Session 64)

**Context.** Prod audit found only 3 of 38 users who submitted analyses had consent records. The consent page existed at `/consent` with 3 tiers (analytics, health_data_processing, coach_brain_contribution), but nothing forced users through it before uploading. This was a GDPR compliance gap — health data was being processed without explicit consent.

**Decision.** Dual-layer mandatory consent gate for `health_data_processing` (Tier 2):

1. **Frontend gate**: `RequireConsent` component wraps `/upload`, `/analysis/:id`, and `/results/:id` routes. Calls `getConsents()` on mount, checks for `health_data_processing` with `granted=true`. If absent, redirects to `/consent?redirect=<current-path>`. After granting, `ConsentPage.handleGrant` reads the `?redirect` param and navigates back. Conservative default: API errors deny access.

2. **Backend gate**: `create_analysis` endpoint checks `ConsentRepository.get_latest_by_type(user_id, "health_data_processing")` and returns HTTP 403 `CONSENT_REQUIRED` if absent or `granted=False`. Defense-in-depth — the frontend gate catches this first, the backend prevents API-only bypasses.

**Consequences.** Every existing test that hits `POST /analyses` needs `ConsentRepository` patched (affected: `test_analysis_api.py`, `test_rate_limit.py`, `test_full_flow.py`). The `RequireConsent` component makes one `GET /api/v1/consent` call per mount — acceptable at pre-beta scale. A React context for consent state would reduce API calls but is over-engineering at <50 users.

## ADR-BETA-OPS-01: Orphaned analysis cleanup cron (Session 64)

**Context.** 13 analyses on prod were stuck in non-terminal states (`queued`, `quality_gate_pending`, `processing`) since April 11 — oldest 31 days old. Users who submitted these saw a perpetually loading status page. All three transitions to `failed` are valid per the status.py transition table. There was no mechanism to auto-detect and resolve stuck analyses.

**Decision.** Add `cleanup_stuck_analyses` nightly cron at 03:30 UTC (between artifact cleanup at 03:00 and orphan-papers cleanup at 04:00). Queries analyses where `status IN ('queued', 'quality_gate_pending', 'processing') AND updated_at < NOW() - 2 hours`. Per-row UPDATE to `status='failed'` with descriptive `error_message`. Per-row commit with try/except — one DB failure doesn't block the rest.

**Consequences.** 2-hour window matches the worst-case pipeline duration (long clip + CoVe retries). Legitimately long analyses won't be touched because `updated_at` advances through status transitions. The cron catches both current orphans and any future ones from worker crashes, deploys, or OOM kills.

## ADR-EXPERT-03: Expose annotated video on expert analysis detail page (Session 68)

**Context.** FR-EXPV-03 defines the expert view scope as "anonymized rep metrics, AI-generated coaching output, retrieved citations, agent reasoning trace — but NOT the user's identity or personal data." The annotated video (`annotated_video_path`) was omitted from `ExpertAnalysisDetail` because FR-EXPV-03 did not explicitly list it. However, the expert was judging coaching accuracy from numbers and text alone with no way to verify what actually happened in the lift. The annotated video contains zero PII — it is a skeleton overlay with joint angle labels, no face, no identifiable background.

**Decision.** Add `annotated_video_url: str | None` to `ExpertAnalysisDetail` schema. Service passes the raw `annotated_video_path` from the ORM object. Endpoint signs it via `StorageService.create_signed_read_url` (1-hour TTL) and replaces via `model_copy(update=...)` — chosen over mutating the ORM object because the service returns a Pydantic model, not an ORM row. Frontend renders a `<video controls>` block below the score cards. Falls back silently if signing fails or the path is NULL (7-day artifact retention means many analyses won't have video).

**Consequences.** Expert can now cross-reference the skeleton overlay against the AI's coaching claims. No PII exposure — the overlay is anonymised by construction (MediaPipe skeleton + angle annotations, no raw pixels). The 7-day artifact retention means older analyses show no video, which is acceptable and documented in the Expert Reviewer Guide. Simultaneously replaced the raw `JSON.stringify` eval scores dump with structured `EvalScoresCard` (faithfulness percentage, CoVe pass/fail, unsupported claims list) — non-technical expert could not interpret raw JSON.


## ADR-AUDIT-2026-05-22: Sagittal-view scope and deferred multi-camera roadmap

**Context.** The 2026-05-11 audit (`docs/audit/cv-dimension-audit-2026-05-11.md`) found that the CV pipeline claimed to measure metrics that are physically unobservable from a single sagittal-view camera (knee valgus, elbow flare, grip width, lateral weight shift, true wrist alignment, scapular retraction, toe-out). These claims appeared in code (`scoring.py` elbow_flare branch), config (`thresholds_v0.json`, `thresholds_v1.json` dead entries), SRS prose (multiple sections of §3.7, §3.8, §3.9, Appendix D.5), and LLM-facing surfaces (coaching prompt, Coach Brain vocab, distillation examples — already addressed in PR #135). The audit also identified 16 sagittal-observable metrics not currently implemented but feasible from existing MediaPipe landmarks (Part 2 of the audit).

The pipeline ran a `lateral_deviation_px` JSONB key on every `rep_metrics` row, but a sagittal camera observes anterior-posterior drift, not lateral.

**Decision.**

1. **Sagittal scope is the single source of truth for what the system measures.** All code, config, SRS prose, CLAUDE.md, and LLM-facing surfaces reflect only metrics computable from one side-view camera. Frontal-plane and top-down metrics are explicitly marked "deferred to multi-camera phase" wherever they appear in documentation.

2. **Dead scoring code is removed.** The `elbow_flare_deg` branch in `scoring.py::TechniqueScore._score_bench` is deleted (not annotated as "retained for multi-camera"). The MC/DC truth table and tests for the deleted branch are removed in the same change. Future multi-camera work introduces fresh branches when the supporting CV is built.

3. **Dead config entries are relocated, not deleted, in v1.** `thresholds_v1.json` gets a new top-level `deferred_multi_camera` subsection containing the frontal-plane threshold values + literature citations (knee_valgus, lumbar_flexion, grip_width, wrist_alignment, elbow_flare, toe_out). No code reads this subsection. `thresholds_v0.json` (Phase 0 frozen snapshot) deletes the dead entries outright — vestigial roadmap items do not belong in a frozen snapshot.

4. **The `lateral_deviation_px` mislabel is corrected to `ap_deviation_px`.** From a sagittal camera the metric measures anterior-posterior drift, not lateral. The rename propagates through `barbell_detection.py` (dict key + docstring), `scoring.py` (local variable, badge `issue_key`, message text), `pdf.py` (annotation label), and every test fixture. Alembic migration `2371965f8072` rewrites the JSONB key in all historical `rep_metrics.metrics_json` rows. Migration is idempotent (`WHERE metrics_json ? 'lateral_deviation_px'`) and reversible (downgrade reverses the rename).

5. **16 Part-2 sagittal-observable metrics are deferred to Sessions 2–7 of this cv-audit effort.** They ship as compute-only (visible to expert reviewer via FR-EXPV-08 panel) until expert validates thresholds. Two refinement metrics (`depth_classification`, `ecc_con_ratio`) auto-flow into existing scoring on first ship.

**Consequences.**

- Expert reviewer onboarding gates can begin without the system over-claiming. Future expert-flagged threshold refinements happen via the existing FR-EXPV-08 workflow against real measured metrics.
- LLM coaching can no longer be biased toward unmeasurable phenomena (PR #135 already cleaned the LLM-facing surfaces; this ADR locks the broader cleanup in).
- Multi-camera work is no longer a code-level claim — it's a roadmap entry in config and an ADR reference. Any future multi-camera scope opens with a fresh ADR superseding nothing (this ADR doesn't preclude multi-camera; it just stops pretending we have it).
- The 14 compute-only metrics from Sessions 2–7 must NOT affect scoring until expert validates each via FR-EXPV-08. Standing Rules in `docs/superpowers/goals/2026-05-22-cv-audit-master.md` Section "Standing Rules" enforce this for the autonomous effort.
- One regression test guards each removal: `test_technique_score_ignores_elbow_flare_deg_metric` (scoring), `test_emits_ap_deviation_px_not_lateral` (bar-path key), `TestThresholdsCvAuditCleanup` (no dead keys in active sections). These prevent silent re-introduction.

**Related.** Audit source — `docs/audit/cv-dimension-audit-2026-05-11.md`. Design spec — `docs/superpowers/specs/2026-05-22-cv-audit-fixes-design.md`. Goal manifest — `docs/superpowers/goals/2026-05-22-cv-audit-master.md`. ADRs scheduled for later sessions: ADR-LIFTER-SIDE-DETECTION (Session 2), ADR-SAGITTAL-METRICS-REGISTRY (Session 3), ADR-AUTO-FLOW-REFINEMENTS (Session 4), ADR-LUMBAR-FLEXION-PROXY-NAMING (Session 7).


## ADR-LIFTER-SIDE-DETECTION: Visibility-weighted lifter-side detection with anchor robustness (Session 2)

**Context.** Before Session 2, every metric extractor and angle calculator in `backend/app/cv/` hardcoded even-numbered MediaPipe landmark indices (12, 14, 16, 24, 26, 28). MediaPipe BlazePose names odd indices = subject's left, even = subject's right; the codebase silently assumed every video was filmed from the lifter's right side. Fixtures filmed from the left returned subtly wrong angles because we read the offside body landmarks. The CV audit (`docs/audit/cv-dimension-audit-2026-05-11.md` E-1) called for a single side-detection helper to drive all current and Part-2 sagittal metrics.

**Decision.**

1. **Detection algorithm — visibility-weighted, anchor-restricted.** Compute mean visibility for the 8 left-side landmarks (11/13/15/23/25/27/29/31) vs the 8 right-side landmarks (12/14/16/24/26/28/30/32) across the first ~3 seconds of pose data (or full session when fps is unknown). Higher mean wins. Visibility samples are restricted to landmarks within ±0.25 (normalised) of the lifter centroid x to suppress bystander interference — re-uses the `check_single_person` anchor pattern from ADR-QGATE-COMMERCIAL-GYM (`_ANCHOR_FROM_FIRST_N_SAMPLES=3`, `_OFF_ANCHOR_DISTANCE_FRAC=0.25`).

2. **Tie-break and ambiguous-default to `"right"`.** When the relative visibility difference is <5% (`_AMBIGUOUS_RELATIVE_DIFF=0.05`), log a WARNING with both means and return `"right"`. This matches the pre-refactor hardcoded default, so right-side fixtures see zero behavioural change. Existing test assertions remain green without modification (verified by the Session 2 invariant gate: `git diff main tests/unit/test_metric_extraction.py tests/unit/test_signal_processing.py` is empty).

3. **Persist detected side on `analyses.lifter_side`.** Nullable `VARCHAR(10) CHECK (lifter_side IN ('left','right'))`. Expert portal (Session 3) surfaces this; users do not see it. Alembic migration `616609f042ed` adds the column; reversible.

4. **`barbell_detection.py` wrist-midpoint fallback stays unchanged.** That function averages both wrists (15 + 16) by design; it is already side-agnostic.

5. **Public entry points accept `lifter_side: Literal["left","right"]` with default `"right"`.** Default preserves all pre-existing test assertions verbatim; the pipeline (`services/pipeline.py::run_cv_pipeline` Step 3.5) supplies the detected value at runtime to `compute_angle_timeseries`, `extract_rep_metrics`, and lockout/torso helpers.

**Consequences.**

- Fixtures filmed from the lifter's left now read the correct landmarks and yield correct angles. Right-side fixtures see ≤0.5% drift per the calibration gate in Session 2 (any larger drift is a hard STOP).
- Adding any Part-2 sagittal metric (Sessions 4–7) requires no side-handling code in the new extractor — it just takes a `SideIndices` and reads the requested landmarks.
- Ambiguous-detection WARNING logs surface during routine pipeline runs in worker logs; pipeline never blocks on ambiguity.
- Mock factories for `Analysis` must explicitly set `lifter_side=None` (per the standing MagicMock + Pydantic gotcha). `test_analysis_api.py::_make_detail_analysis` and `test_analysis_crud.py::_make_mock_analysis` updated in the same PR.

**Alternatives considered.**

- **Always trust the higher-indexed-landmark visibility.** Rejected: encodes the same hardcoded-right assumption we are removing.
- **Ask the user at upload time which side they are filming.** Rejected: every other CV feature is fully automatic; this would add a UX burden for a piece of metadata the system can infer reliably.
- **Use only the first frame.** Rejected: MediaPipe needs several frames to stabilise; a single-frame visibility check is noisier than the 3-second mean.

**Related.** ADR-AUDIT-2026-05-22, ADR-QGATE-COMMERCIAL-GYM. Migration `616609f042ed`. Module `backend/app/cv/lifter_side.py`. Backlog IDs `L2-LIFTER-SIDE-01` through `-05`.


## ADR-SAGITTAL-METRICS-REGISTRY: Frozenset as single source of truth for the 16 sagittal-view metrics (Session 3)

**Context.** The CV audit (`docs/audit/cv-dimension-audit-2026-05-11.md` Part-2) identified 16 sagittal-view metrics that the system can observe but doesn't compute. Sessions 4–7 add the extractors. Before extractors land, both backend and frontend need a single, immutable list of `(key_name, display_label, unit, description, exercise_applicability)` so the expert portal can show "Not yet computed" rows that flip to "computed + flaggable" as each session ships. Without a registry, backend extractors would write to JSONB keys the frontend doesn't know about, and the frontend panel would be a hardcoded list that drifts from reality.

**Decision.**

1. **Backend Python module is the source of truth.** `backend/app/cv/sagittal_metrics_registry.py` exposes `SAGITTAL_METRICS_REGISTRY: frozenset[SagittalMetricEntry]` with all 16 entries. Frozen dataclass, frozenset container — neither can be mutated at runtime. Companion key `heel_rise_flag` (written alongside `ankle_dorsiflexion_deg`) is noted in the latter's description rather than carrying its own registry row, keeping the count at 16 (matches design §Section-4 entry #1 framing).

2. **Expose via `GET /api/v1/expert/sagittal-metrics-registry`** (auth: `expert_reviewer` + `admin` via `get_expert_reviewer_user`). The frontend fetches the list on mount; no hardcoded duplicate on the client. Response is deterministically sorted by `display_label`.

3. **Sessions 4–7 only flip `computed_yet` and (for two metrics) `in_scoring` — they do NOT rename keys.** Key names are final. Renaming is a breaking change requiring a JSONB key migration.

4. **`threshold_flags.section` accepts `'unvalidated_metrics'` via the existing FR-EXPV-08 flow.** The 14 compute-only metrics inherit the expert-flagging workflow used for `squat`/`bench`/`deadlift`/`control` threshold values; `ThresholdFlagService.create_flag` short-circuits the v1-config current-value lookup when section is `unvalidated_metrics` (returns `current_value=0.0`, `current_citation=None`). Alembic migration `7c4af3e51f08` adds the DB-level `CHECK (section IN (...))` constraint enumerating all 5 allowed values.

5. **Naming honesty in descriptions.** `lumbar_flexion_proxy_delta_deg` description explicitly disclaims "Not lumbar-isolated" (R4 mitigation; ADR-LUMBAR-FLEXION-PROXY-NAMING forward-ref). `bar_path_classification` description names "Heuristic v0 — expect post-onboarding refinement" (R5 mitigation). `technique_consistency_std` description identifies it as a std-dev derivative.

6. **No metric extraction, scoring, or coaching prompt changes ship in Session 3.** The panel renders empty rows; the LLM is not yet given new context.

**Consequences.**

- Adding a metric in Sessions 4–7 = three places: (a) extractor in `metric_extraction.py`, (b) flip `computed_yet=True` on the existing registry entry (do NOT add new entries — the 16 are fixed), (c) integration test asserting the key appears in `rep_metrics`. Frontend automatically picks up the new computed status via the registry response.
- A drifted registry (entry exists but no extractor) silently shows "Not yet computed" — no crash, no missing data. Safe-by-default.
- Threshold flagging the new metrics requires no schema changes for Sessions 4–7 — the section is already in the CHECK constraint.
- Frontend `ThresholdSection` union widened to include `'unvalidated_metrics'`; `ExpertThresholdsPage`'s `SECTION_LABELS` narrowed to a local `ConfigBackedSection` subset since the `/thresholds` endpoint never returns unvalidated rows.

**Alternatives considered.**

- **Hardcode the 16-entry list on the frontend.** Rejected: drift risk between backend extractor output (JSONB keys) and frontend panel rendering.
- **Database table for the registry.** Rejected: the list is static across deployments; a Python frozenset is simpler, faster, and ships with the code.
- **Treat `heel_rise_flag` as a separate 17th registry entry.** Rejected: design §Section-4 entry #1 explicitly bundles it with `ankle_dorsiflexion_deg`; matching that framing keeps the registry count synchronised with the audit's 16-metric framing.

**Related.** ADR-AUDIT-2026-05-22, ADR-LIFTER-SIDE-DETECTION, future ADR-AUTO-FLOW-REFINEMENTS (Session 4), future ADR-LUMBAR-FLEXION-PROXY-NAMING (Session 7). Migration `7c4af3e51f08`. Module `backend/app/cv/sagittal_metrics_registry.py`. Endpoint `GET /api/v1/expert/sagittal-metrics-registry`. Component `frontend/src/components/UnvalidatedMetricsPanel.tsx`. Backlog IDs `L2-SAGITTAL-INFRA-01` through `-04`.


## ADR-AUTO-FLOW-REFINEMENTS: Two refinement metrics bypass the compute-only-until-validated rule (Session 4)

**Context.** ADR-SAGITTAL-METRICS-REGISTRY (Session 3) established that the 14 newly-added sagittal-view metrics are compute-only until an expert reviewer validates their threshold values via the FR-EXPV-08 flagging workflow. Two of the 16 metrics, however, are *refinements* of measurements whose underlying math is already validated and live in production scoring:

- `depth_classification` is a categorical relabel of the existing `depth_angle` (already used by `TechniqueScore._score_squat`). The expert validates the categorical *label* (above/at/below parallel) and the band width (currently ±5°), but the angle math itself is unchanged.
- `ecc_con_ratio` is a derived ratio of the existing per-rep `descent_duration_s` / `ascent_duration_s` (already exposed in `RepMetrics.metrics`). The expert validates the *target window* (`control.ecc_con_ratio_target_min..max`, currently 1.0..3.0), but the ratio computation is unchanged.

The other 12 metrics (Sessions 5–7) introduce new measurements; they remain compute-only.

**Decision.** `depth_classification` and `ecc_con_ratio` flip `in_scoring=True` in `sagittal_metrics_registry.py` on Session-4 day one. New scoring branches in `TechniqueScore._score_squat` (depth_classification: -1.5 with `at_parallel` threshold or -2.5 with `below_parallel`, severity Medium) and `ControlScore.compute` (ecc_con_ratio: -1.0/High when below `target_min`, -0.5/Medium when above `target_max`) dock the form score directly. `pause_duration_s` and `lockout_torso_lean_deg` flip `computed_yet=True` only and remain compute-only.

Pipeline-level aggregator (`_aggregate_rep_metrics` in `services/pipeline.py`) forwards both keys to scoring: `depth_classification` as the modal label across reps; `ecc_con_ratio` as the mean across positive-valued reps (existing numeric-mean path).

Frontend renders the same two values on the regular user's `ResultsPage` as small chips above the rep-metrics table (`<AutoFlowMetricsChips />`). The expert `UnvalidatedMetricsPanel` already renders values automatically via the registry's `computed_yet` flag (Session 3 wiring).

**Consequences.**

- (+) First user-visible scoring impact of the cv-audit work — squats above parallel and rushed eccentrics are now reflected in form scores AND in user-facing chips.
- (+) Establishes a precedent: refinements of already-validated metrics may auto-flow; new measurements stay compute-only.
- (+) The two new badge `issue_key`s (`squat_depth_classification_above`, `ecc_con_ratio_rushed`, `ecc_con_ratio_excessive`) flow into the LLM coaching prompt via the existing badges-in-prompt path with no template changes (per cv-audit design §Section-2).
- (−) If the expert reviewer disagrees with either band width (±5°) or the ecc/con target window (1.0..3.0), thresholds are flipped via FR-EXPV-08 without code changes — but form scores produced between Session-4 deploy and the expert's revision use the initial defaults. Mitigated by conservative defaults and badge text written defensively ("aim for", "consider"), per design §Section-5 R3.
- (−) `ControlScore.ecc_con_ratio` uses session-aggregate granularity (mean across reps) rather than per-rep docking. Per-rep docking is deferred to a post-onboarding refinement once thresholds are validated.

**Stop condition (master manifest §Section-6).** If the expert validates the panel surface but objects to auto-flow scoring, revert both branches and downgrade both metrics to compute-only. Plan path back: single-commit revert of the scoring branches + flag flip on the two registry entries.

**Alternatives considered.**

- **Defer all 16 metrics to compute-only until expert review.** Rejected: leaves Session 4 with no user-visible deliverable and gives the expert nothing concrete to react to on the first onboarding pass.
- **Auto-flow all 4 Session-4 metrics.** Rejected: `pause_duration_s` and `lockout_torso_lean_deg` are *new* measurements, not refinements; expert needs to validate the threshold values first per the master ADR-SAGITTAL-METRICS-REGISTRY contract.
- **Persist `score_result.dimensions[].badges` to the DB and render directly on the ResultsPage.** Considered for the user-facing surface; rejected for scope — the new chip path reads existing JSONB without a schema change. Persisting scoring badges to the DB is a separate (worthy) refactor.

**Related.** ADR-AUDIT-2026-05-22, ADR-SAGITTAL-METRICS-REGISTRY. Threshold config keys `squat.depth_classification_min`, `control.ecc_con_ratio_target_min`, `control.ecc_con_ratio_target_max`. Files `backend/app/cv/metric_extraction.py` (helpers `_classify_depth`, `_pause_duration_s`, `_lockout_torso_lean_deg`, `_default_parallel_angle`), `backend/app/cv/scoring.py` (TechniqueScore + ControlScore branches), `backend/app/cv/sagittal_metrics_registry.py` (flag flips), `backend/app/services/pipeline.py` (`_aggregate_rep_metrics` modal forwarding), `frontend/src/pages/ResultsPage.tsx` (`<AutoFlowMetricsChips />`). Backlog rows `L2-SAGITTAL-TRIVIAL-01..04`.


## ADR-LUMBAR-FLEXION-PROXY-NAMING: Naming honesty + baseline/heuristic/consistency choices for the 3 complex metrics (Session 7)

**Context.** Session 7 implements the final 3 of the 16 sagittal metrics, all compute-only: #2 `lumbar_flexion_proxy_delta_deg` (squat + DL), #6 `bar_path_classification` (bench), #16 `technique_consistency_std` (squat + DL). These are the highest-calibration-risk metrics in the cv-audit effort (design R4/R5): #2 is biomechanically misleading if presented as a true lumbar measurement; #6's J-curve heuristic is fragile; #16 aggregates across reps. A mandatory `/plan` spike (`docs/superpowers/plans/2026-05-23-session-7-complex-metrics-plan.md`) resolved the open design questions before implementation.

**Decision.**

1. **Naming honesty (#2).** The JSONB key carries an explicit `_proxy` suffix: `lumbar_flexion_proxy_delta_deg`. The function is `extract_lumbar_flexion_proxy_delta_deg`. The registry `description` reads "Lumbar flexion proxy (composite torso angle — not lumbar-isolated): …". The metric is `degrees(atan2((shoulder_x − hip_x)·facing_sign, hip_y − shoulder_y))` at the rep-bottom frame minus the same at a standing-baseline frame — a composite trunk-flexion proxy, NOT a lumbar-isolated measurement (true lumbar flexion needs spinal landmarks unavailable from BlazePose). Naming what it isn't is load-bearing for expert trust.

2. **Standing-baseline frame identification (#2).** Squat: one global baseline = `reps[0].start_frame` (cleanest upright posture; preserves set-level drift as signal). Deadlift: previous rep's `end_frame` (lockout). **First DL rep (no previous rep): use the last frame before liftoff (`identify_liftoff_frame − 1`), falling back to `rep.start_frame` when liftoff is undetectable.** Options (b) hip-y stability scan and (c) skip-first-rep were rejected — the pre-liftoff set position is a valid standing reference and wastes no data. Cross-rep context reaches the per-rep analyzers via new optional `all_reps` / `rep_position` args (defaults preserve existing call sites, mirroring Session 5's `lifter_side`).

3. **J-curve heuristic v0 (#6).** Per-rep label from the bilateral wrist-midpoint x-trajectory: `j_curve` if `abs(ascent_end_x − bottom_x) > 0.03`; elif `abs(descent_start_x − ascent_end_x) < 0.02` → `vertical`; else `drift`. The design's one-directional `<` was symmetrized to `abs()` — REQUIRED to pass the mandated side-agnosticism mirror test (a left-facing lifter's j-curve sweeps toward higher x). v0 heuristic; expect post-onboarding refinement (design R5).

4. **Consistency metric (#16).** Population std (`np.std`, ddof=0) across reps of `depth_angle` (squat) / `lockout_torso_lean_deg` (DL). Single-rep → None. Computed in a post-pass inside `extract_rep_metrics`, written into every rep's dict.

5. **None storage, not 0.0.** A cannot-compute result is JSON null (`RepMetricValue` widened to `float | str | dict[str, float | None] | None`). 0.0 is a valid biomechanical outcome for a delta (no flexion change) and an std (perfectly consistent), so it cannot double as a sentinel.

6. **Occlusion guard (calibration remediation, PR #168).** Post-merge calibration on `atharva-squat.mov` produced `lumbar_flexion_proxy_delta_deg = −165°` — outside [−90°, 90°]. Root cause: deep-squat hip-fold occlusion (a known high-occlusion phase) mis-places a landmark so the shoulder appears below the hip (`hip_y − shoulder_y ≤ 0`); `atan2` then wraps toward ±180°. `_lumbar_proxy_angle` now returns None when `dy ≤ 0`, bounding the proxy to (−90°, 90°). The integration sanity range was NOT loosened (Standing Rule 1). Post-fix the squat fixture yields a plausible 6.31° on its one clean rep, None on occluded reps.

**Consequences.**

- (+) Honest naming + a documented occlusion guard make #2 safe to surface as a v0 proxy. All 16 sagittal metrics now `computed_yet=True`; 2 scored, 14 compute-only pending expert threshold validation (FR-EXPV-08).
- (−) On deep, occluded squats #2 returns None for most reps (only clean depth frames resolve) — the panel shows "—" rather than a wrong number. Post-onboarding work may add bar-detection-assisted landmark recovery.
- (−) #6 v0 may misclassify strong monotonic forward-drift as `j_curve` (the `abs()` symmetrization trades directional purity for side-agnosticism). Flagged for post-onboarding refinement.

**Alternatives considered.**

- **0.0 sentinel for cannot-compute.** Rejected — conflates "no data" with a valid zero outcome (silent correctness bug).
- **Loosen the [−90,90] integration range to admit −165°.** Rejected — violates Standing Rule 1; the value is a genuine artifact.
- **Defer #2 to post-onboarding (ship #6/#16 only).** Considered per the design's Session-7 stop guidance; unnecessary once the occlusion guard brought the metric in range within the remediation cap.

**Related.** ADR-AUDIT-2026-05-22, ADR-SAGITTAL-METRICS-REGISTRY, ADR-AUTO-FLOW-REFINEMENTS, ADR-LIFTER-SIDE-DETECTION (`_facing_sign`). Files `backend/app/cv/metric_extraction.py` (`identify_standing_baseline_frame`, `_lumbar_proxy_angle`, `extract_lumbar_flexion_proxy_delta_deg`, `_classify_bar_path`, `_inject_technique_consistency_std`, `session_modal_bar_path_classification`), `backend/app/cv/sagittal_metrics_registry.py` (3 flag flips). PRs #167 (impl) `f93d1ee`, #168 (occlusion guard) `75f6d0d`. Backlog rows `L2-SAGITTAL-COMPLEX-01..03`.

## ADR-DEPTHFRAME-DROPOUT-GATE: Dropout-aware depth-frame selection + auxiliary-metric plausibility None-guards (2026-05-23, cv-audit R1)

**Context.** A post-Session-7 deep-dive (`docs/superpowers/investigations/2026-05-23-cv-occlusion-rootcause.md`) instrumented per-frame MediaPipe landmarks on the three `atharva-{squat,bench,deadlift}` fixtures to root-cause why `lumbar_flexion_proxy_delta_deg` returned None on 5 of 6 squat reps. The evidence **corrects the root-cause attribution in ADR-LUMBAR-FLEXION-PROXY-NAMING §6**: the −165° artifact and the `dy ≤ 0` guard covered only the *minority* failure (1 of 6 squat reps — a confident inverted-pose mis-track). The *dominant* failure (4 of 6 reps) was **total pose dropout** — MediaPipe in `RunningMode.VIDEO` (`pose_extraction.py`, D-035/ADR-058) loses tracking near the deep-squat bottom and emits zero-filled frames (13–46 % of frames per rep). The *highest-impact* defect was downstream: zero/degenerate frames inject impossible angles (squat `hip_angle` range observed −32°…192°), and `_find_depth_frame` was a plain `argmin`, so it **selected dropout frames as the rep "bottom"** — corrupting every bottom-anchored squat metric (depth_angle, knee_angle_at_depth, torso_lean, lumbar proxy), not just the proxy. Deadlift, which keeps the torso unoccluded, tracked cleanly with the identical code — confirming the failure is occlusion-specific, not a universal pipeline bug.

**Decision.**

1. **Dropout-aware depth-frame selection (squat + deadlift).** `_find_depth_frame` gains an optional `valid_mask: np.ndarray | None = None`; when given and ≥1 frame in `[start, end]` is valid, `argmin` runs only over valid frames (invalid → `np.inf`); otherwise it falls back to the original plain `argmin` (backward-compatible — `None` reproduces prior behaviour, so existing call sites/tests are unchanged). Squat and deadlift build the mask via `_vis_ok` on the angle-defining landmark triple `{shoulder, hip, knee}`. This recovers sane `depth_angle` + computable lumbar proxy for **all 6** squat reps (was 1/6), with the previously-clean rep byte-identical.

2. **Bench excluded from the mask (deferred to R3).** Bench wrist visibility on this footage is ~0.04–0.5, so masking on `{shoulder, elbow, wrist}` either falls back to the same dropout frame (no benefit) or selects a marginal wrist-visible frame that yields an extreme `bar_touch_height_pct` (76.4). The bench bottom-frame call site keeps the plain `argmin`; bench bar-path robustness needs barbell detection, not a wrist proxy — tracked as R3.

3. **Auxiliary squat metrics return None on mis-tracking, never garbage.** Gating the depth frame on `{shoulder, hip, knee}` can shift it onto a frame whose *other* landmarks (knee/ankle/foot) are mis-placed — visibility ≥ 0.30 yet geometrically wrong — producing impossible `ankle_dorsiflexion_deg` (138–170°) and `shin_angle_deg` (−81…−104°). Neither visibility (knee 0.43→good vs 0.55→garbage) nor y-ordering alone separates good from garbage. So both metrics now apply **two guards**: (a) a geometric ordering check (`knee_y < ankle_y`; ankle also requires `ankle_y ≤ foot_y`) — same philosophy as the lumbar `dy ≤ 0` guard; and (b) an **anatomical-plausibility envelope** returning None outside `ankle_dorsiflexion ∈ [10°, 120°)` and `shin_angle ∈ [−45°, 80°]`. Envelopes are deliberately *wider* than the old integration sanity ranges (`[0,120]`, `[−30,60]`) so the check is not tautological; the integration test now asserts float-or-None (the numeric plausibility moved into code, which is strictly stronger).

**Consequences.**

- (+) All bottom-anchored squat metrics read a valid frame when one exists; the proxy resolves for every squat rep with a trackable bottom.
- (+) Auxiliary metrics surface "—" (None) on occluded reps instead of a confidently-wrong number — consistent with the None-not-0.0 sentinel (ADR-LUMBAR-FLEXION-PROXY-NAMING §5).
- (−) R1 (frame selection) cannot recover a metric when *no* frame in a rep tracks the needed joints; e.g. squat rep 1's true depth was fully occluded, so its reported `depth_angle` is the deepest *valid* frame (shallower), not the true bottom. This is honest (no fabrication) but means depth can read shallow on heavily-occluded reps.
- (−) Bench bar-path quality is unchanged (deferred to R3).

**Alternatives considered.**

- **Gate at the angle time-series (R2): mask zero/low-vis frames as NaN + clamp to [0,180] upstream of rep detection.** Larger blast radius (also changes rep detection); deferred — R1 is the bounded, lower-risk first step.
- **Raise the visibility threshold instead of plausibility guards.** Rejected — visibility does not separate good from garbage on this footage (proven empirically).
- **Output-range clamp equal to the test's sanity bounds.** Rejected — makes the integration assertion tautological; envelopes are set wider, from anatomy.
- **Revert R1 entirely.** Rejected — depth_angle/lumbar recovery is a real correctness win on robust landmarks.

**Related.** Supersedes the root-cause attribution in **ADR-LUMBAR-FLEXION-PROXY-NAMING §6** (the `dy ≤ 0` guard remains correct but covered only 1/6 reps; the dominant cause was dropout + un-gated `argmin`). ADR-058 (VIDEO running mode), ADR-AUDIT-2026-05-22, ADR-SAGITTAL-METRICS-REGISTRY. Files `backend/app/cv/metric_extraction.py` (`_find_depth_frame`, `_ankle_dorsiflexion_deg`, `_shin_angle_deg`, `_squat_metrics`, `_bench_metrics`, `_deadlift_metrics`), `backend/tests/unit/test_metric_extraction{,_sagittal}.py`, `backend/tests/integration/test_pipeline_sagittal_metrics.py`. Backlog row `L2-CV-DEPTHFRAME-DROPOUT`. R3 (bench wrist/bar-path) and R2/R4/R5/R6 remain open per the investigation doc.

## ADR-BENCH-BARPATH-NONE-INTERIM: Bench bar-path is visibility-gated to None until a real bar-tracker exists (2026-05-23, cv-audit R3)

**Context.** R3 set out to make bench `bar_path_classification` (#6) robust — R1 had deferred bench because its wrist-midpoint proxy is unreliable. A feasibility spike (instrumentation in `backend/scripts/oneoff/investigate_bench_barpath_r3.py` + `spike_bench_bar_tracker_r3.py`, local-only) tested the obvious alternative — the existing HoughCircles barbell detector — and a temporal nearest-circle association tracker on top of it:

- **Raw HoughCircles** detects a circle in 100% of bench frames but cannot isolate the lifter's plate from background plates/racks: the picked-circle x swings ~0.4 of frame width *within a single rep* (per-rep x-std 0.13–0.24), physically impossible for a controlled press.
- **Temporal association** (seed largest-radius, track nearest within a gate) stabilises x-std to <0.03 on most reps but locks onto a near-*stationary* circle (track y-range ~0.02 — far too small for real bar travel) and loses the bar at the bottom where it is occluded by the torso/arms — exactly where the j-curve discriminator needs data.
- **Wrist-midpoint fallback** hallucinates: wrist-midpoint y jumps ~0.72 of frame height on ~half the reps, with impossible >180° elbow ranges on the same reps.

Conclusion: **no current building block reliably yields a bench bar path.** A genuine solution is a dedicated CV effort (motion-correlation bar identification, occlusion handling, or a trained/optical-flow tracker), not a quick fix.

**Decision.** Ship the honest **None-interim** (chosen by the user over a speculative tracker build): in `_bench_metrics`, each of the three bar-path anchors (`descent_start` / `bottom` / `ascent_end`) is gated on **bilateral wrist visibility** — `_vis_ok(frame, 15, 16)` (≥ `_S5_MIN_VIS` 0.30); an unreliable anchor → `None` → `_classify_bar_path` returns `None`. Net: `bar_path_classification` is `None` (cannot-classify, shows "—") on the supine-occluded footage that dominates real bench clips, while it still classifies when both wrists are genuinely visible. Same None-over-garbage philosophy as ADR-DEPTHFRAME-DROPOUT-GATE / ADR-LUMBAR-FLEXION-PROXY-NAMING §5. Wrists 15/16 are bilateral (the midpoint averages both) and are NOT routed through `side_idx`.

**Consequences.**
- (+) Bench stops emitting noise (the prior wrist proxy produced ~9/13 artifact `j_curve` labels, 5 from `bottom_x=0` dropout frames). "—" is honest; the metric is compute-only (`in_scoring=False`), so no scoring impact.
- (+) The metric remains functional on footage where wrists are reliably visible — the gate suppresses only unreliable frames.
- (−) On typical commercial-gym bench footage the metric will almost always be `None`. That is the truthful state until R3b.
- (−) `bar_path_classification` is already a nullable key (ADR-LUMBAR-FLEXION-PROXY-NAMING §5) — no type/schema/invariant change.

**Alternatives considered.**
- **Switch bench bar-path to HoughCircles** — rejected; raw detection cannot isolate the lifter's bar (spike evidence).
- **Build the temporal-association tracker now** — rejected for R3 scope; the spike showed seeding + bottom-occlusion are unsolved, making payoff uncertain. Logged as **R3b** (`L2-CV-DEPTHFRAME-R3b`).
- **Unconditional None for bench** — rejected; over-suppresses on footage where wrists are visible. The visibility gate is the honest, footage-adaptive version.

**Related.** Follows ADR-DEPTHFRAME-DROPOUT-GATE (R1) and the same investigation (`docs/superpowers/investigations/2026-05-23-cv-occlusion-rootcause.md`, local). Files `backend/app/cv/metric_extraction.py` (`_bench_metrics` anchor gate), `backend/tests/unit/test_metric_extraction_sagittal.py` (2 R3 tests). Backlog `L2-CV-DEPTHFRAME-R3` (done, this interim) + `L2-CV-DEPTHFRAME-R3b` (open, real bar-tracker).

## ADR-DEADLIFT-FIRSTREP-BASELINE: Deadlift first-rep lumbar baseline anchors to its own lockout, not the pre-liftoff setup frame (2026-05-23, cv-audit R6)

**Context.** R6 (logged in the occlusion investigation) flagged that the deadlift first-rep standing baseline could land on a non-standing frame. Instrumenting the real `atharva-deadlift.mov` fixture (5 reps, `backend/scripts/oneoff/investigate_occlusion_session7.py`) made the defect quantitative: `lumbar_flexion_proxy_delta_deg` measured **0.19° on rep 0** versus **64–69° on reps 1–4** — rep 0 was ~360× too small, a clear outlier. Root cause: `identify_standing_baseline_frame`'s first-rep deadlift branch used the pre-liftoff frame (`identify_liftoff_frame − 1`, fallback `rep.start_frame`). For a deadlift that frame is the **hinged setup pose at the floor** (trunk ≈ 76° from vertical), not standing. The bottom frame is *also* the setup pose (≈ 76°), so `delta = proxy(bottom) − proxy(baseline) ≈ 0`. Reps 1–4 were correct because their baseline is the **previous** rep's `end_frame` (lockout = standing-upright, trunk ≈ 7°), giving the true ~68° trunk-hinge ROM. The original first-rep logic carried over squat intuition (squat `start_frame` *is* standing); for a deadlift the start is the floor.

**Decision.** The deadlift first rep (no previous lockout) now anchors its standing baseline to its **own** `end_frame` — the standing-upright top of the pull — instead of the pre-liftoff setup frame. Reps with `rep_position > 0` are unchanged (previous rep's `end_frame`). Squat is unchanged (global `all_reps[0].start_frame`). The `bar_y_series` parameter — whose sole purpose was the now-removed first-rep liftoff detection — is dropped from `identify_standing_baseline_frame`'s signature (both call sites updated; `identify_liftoff_frame` itself stays, still used by `_bar_to_hip_distance_dict`). Hand-computed and then fixture-verified: rep 0 moves from 0.19° to **69.18°**, consistent with reps 1–4; reps 1–4 byte-identical.

**Consequences.**
- (+) The deadlift first rep now reports a physically meaningful trunk-flexion delta consistent with the rest of the set — the expert portal no longer shows a misleading ≈0° on rep 0 for a clearly-hinged pull.
- (+) The `_lumbar_proxy_angle` None-guards (low visibility, `dy ≤ 0`) still apply at `end_frame`, so a first rep that never reaches a clean lockout honestly returns None rather than a fabricated value.
- (−) Anchoring rep 0 to its own (later) lockout rather than a prior-in-time standing frame is a within-rep reference, not a strictly-before-the-descent one; acceptable because the proxy measures flexion *magnitude* relative to neutral, not a temporal sequence.
- (−) No type/schema/invariant change — `lumbar_flexion_proxy_delta_deg` was already nullable (ADR-LUMBAR-FLEXION-PROXY-NAMING §5).

**Alternatives considered.**
- **Keep the pre-liftoff frame but add a "is-standing" check.** Rejected — `identify_standing_baseline_frame` has no landmark access to test trunk verticality; the own-lockout frame is already known-standing by construction (it is the lockout the rep detector found).
- **Use a session-global standing frame for all deadlift reps (mirror the squat design).** Rejected as out-of-scope churn — reps 1–4 are already correct via the previous-lockout rule; the minimal fix touches only the broken first-rep path (systematic-debugging: smallest change that fixes the root cause).
- **Leave `bar_y_series` in the signature unused.** Rejected — a parameter every caller computes-and-passes but the body ignores is misleading; removed for honesty.

**Related.** Same investigation as ADR-DEPTHFRAME-DROPOUT-GATE (R1) and ADR-BENCH-BARPATH-NONE-INTERIM (R3). Files `backend/app/cv/metric_extraction.py` (`identify_standing_baseline_frame` + 2 call sites), `backend/tests/unit/test_metric_extraction_sagittal.py` (first-rep contract tests). Backlog row `L2-CV-DEPTHFRAME-R6`. R2/R4/R5 remain open per the investigation doc.
