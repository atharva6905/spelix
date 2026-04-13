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
