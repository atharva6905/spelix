# Backend — CLAUDE.md

Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, ARQ + Redis, MediaPipe BlazePose Heavy, OpenCV headless, WeasyPrint, Anthropic SDK, OpenAI SDK, instructor, Pydantic v2.

**Current phase: Phase 1 COMPLETE → Phase 2 PLANNING.** Phase 1 added: 5-tier confidence, 4-dimension scoring, SSE coaching, GPT-4o keyframe analysis, exercise auto-detection, Phase 1 PDF, per-rep metrics (FR-REPM-07/08/09/12), detection_result JSONB column (migration 003).

Test counts as of Phase 1 gate: **895 passing, 2 skipped, 0 failures, 91% coverage.** Current alembic head: `003_add_detection_result`.

**Backend changes ship via PR, not direct push to main** — see root `CLAUDE.md` "Checkpoint Workflow" section. Any backend change that touches the analysis pipeline, coaching, upload endpoint, auth, or a schema migration is a meaningful checkpoint that requires: (1) a feature branch, (2) a PR with green CI, (3) `gh pr merge --squash --delete-branch`, (4) Playwright MCP E2E verification against spelix.app after the deploy settles. Unit tests green is not enough — prod has a different Supabase project and different env vars, and production-only bugs (PgBouncer asyncpg, JWT issuer, CORS) have burned us before.

## Directory Layout

```
backend/
  app/
    api/v1/           # FastAPI routers (one file per resource)
    services/         # Business logic — no DB calls
    repositories/     # DB access — all queries live here
    cv/               # MediaPipe pipeline, quality gates, scoring, detection
    workers/          # ARQ job functions
    models/           # SQLAlchemy models
    schemas/          # Pydantic v2 schemas
    config.py         # ThresholdConfig loader
  tests/
    unit/             # Pure-function tests + mocked API tests
    integration/      # Real Postgres, real Redis
    e2e/              # Full flow via httpx AsyncClient
    fixtures/         # Synthetic video files (~10s, 720p)
  alembic/versions/   # Migration files
```

## API Layer

Route prefix: `/api/v1/`. One router file per resource in `app/api/v1/`: `analyses.py`, `profiles.py`, `admin.py`, `coaching_sse.py`, `insights.py`.

Auth: FastAPI dependency `get_current_user` validates Supabase JWT via `SUPABASE_JWT_SECRET`; inject into all protected routes. JWT issuer validation added in B-075.

Error format: `{"error": {"code": str, "message": str, "detail": any}}` — never return raw exceptions.

Upload flow: `POST /analyses` → create DB record (status=queued) → return signed TUS URL + analysis ID (201). `POST /analyses/{id}/start` → enqueue ARQ job → 202. TUS upload goes directly from browser to Supabase Storage — FastAPI never handles video bytes.

Status poll: `GET /analyses/{id}/status` returns `{id, status, updated_at, detection_result}` — fallback when Realtime disconnects. `detection_result` added in Phase 1 (FR-XDET-07).

Detail: `GET /analyses/{id}` returns `AnalysisDetail` with nested `coaching_result` and `rep_metrics`. Phase 1 added all `form_score_*` fields.

Admin routes: server-side role check; non-admins receive 403. Admin queries use service role key scoped to read-only admin views.

Request body for `POST /analyses`: `{exercise_type, exercise_variant, filename, file_size_bytes, weight_kg?}`. Response 201: `{id, upload_url, status, expires_at}`.

Signed TUS URL TTL: 1 hour. Video validation (FFprobe codec check) runs in ARQ worker, not in the upload endpoint.

Rate limit: `POST /api/v1/analyses` limited to 10/user/day via slowapi + Redis counter.

SSE coaching: `GET /api/v1/analyses/{id}/coaching/stream` subscribes to Redis pub/sub `coaching:{id}` and forwards chunks as SSE events. See "SSE Coaching Architecture" below.

OpenAPI schema auto-generated. Frontend types derived via `npm run gen-types`. Keep response models in `app/schemas/` aligned with actual responses.

## Service and Repository Layer

Services in `app/services/`: business logic only, no DB calls, no imports from `repositories` internals.
Repositories in `app/repositories/`: all DB access. Each repository takes `AsyncSession` in constructor.
Session injected via FastAPI dependency — never import a global session.
Pattern: `class AnalysisRepository: def __init__(self, db: AsyncSession)` → services receive repos via DI.
Status transitions: use the `transition(current, target)` guard function in `app/services/status.py` — raise `InvalidTransition` on illegal moves per SRS 5.2a table.

## Database

8 tables: `users` (Supabase-managed), `user_profiles`, `analyses`, `rep_metrics`, `coaching_results`, `expert_annotations`, `rag_documents`, `admin_events`.

### Migration history
- **001** — `analyses`, `user_profiles`, `rep_metrics`, `coaching_results` (core tables)
- **002** — RLS policies on all user-owned tables
- **003** — `detection_result` JSONB column on `analyses` (FR-XDET-07)
- **004** (Phase 2, not started) — `rag_documents` + `expert_annotations` tables (P2-001)

Current alembic head: `003_add_detection_result`. `admin_events` deferred further.

### Schema rules
- Required indexes in migration 001: `(user_id, created_at DESC)` on `analyses`; `(analysis_id)` on `rep_metrics` and `coaching_results`.
- Status column: `VARCHAR(30)` with CHECK constraint listing all 7 valid values (`queued`, `quality_gate_pending`, `quality_gate_rejected`, `processing`, `coaching`, `completed`, `failed`).
- JSONB columns: `summary_json`, `quality_gate_result`, `metrics_json`, `structured_output_json`, `detection_result`, `agent_trace_json` (P2+), `retrieved_sources_json` (P2+).
- No DDL FK to `auth.users` — enforce via RLS only.

### Artifact retention
- 7 days default (cost constraint — keeps active Storage at ~413 MB within Supabase free 1 GB tier).
- Scheduled ARQ cron job deletes annotated MP4, PDF, plot PNG nightly.
- Sets paths to NULL in analyses row after deletion.
- History and scores are preserved — only artifact bytes are removed.
- Users see a 7-day download banner on results page.

## CV Pipeline

Pipeline lives in `app/cv/`: `quality_gates.py`, `pose_extraction.py`, `rep_detection.py`, `metric_extraction.py`, `scoring.py`, `confidence.py`, `exercise_detection.py`, `keyframe_extraction.py`, `barbell_detection.py`, `artifact_generation.py`.

All CV functions are pure — stateless, injectable, independently testable. The orchestration lives in `app/services/pipeline.py::run_cv_pipeline`.

### Pipeline stages
1. **Download** video from Supabase Storage to `/tmp/spelix/{analysis_id}.mp4`
2. **Pose extraction** (`extract_landmarks`) → `list[np.ndarray]` of (33, 5) frames
3. **Step 2b: Exercise auto-detection** (Phase 1, FR-XDET-03/04) — heuristic first, GPT-4o vision fallback if `confidence < 0.7` and `openai_client` available. Stores on `analysis.detection_result` JSONB but NEVER overrides user-selected `exercise_type` (ADR-023). Fallback threshold is `_FALLBACK_CONFIDENCE_THRESHOLD = 0.7` (ADR-017).
4. **Quality gates** (`run_quality_gates`) — body visibility, framing, lighting, stability. Runs in ARQ worker, not FastAPI. Reject predicate: `mean(visibility[frames=0:5][landmarks∈{11,12,13,14,23,24,25,26}]) < 0.30`.
5. **Angle time-series** (`compute_angle_timeseries`)
6. **Rep detection** (`detect_reps`) — threshold-crossing state machine (`STANDING → DESCENDING → BOTTOM → ASCENDING → STANDING`), min rep duration 0.5s, hysteresis ±5°. Thresholds: squat hip 160°/90°, deadlift hip 160°/70° (70° RDL 90°), bench elbow 160°/90°.
7. **Per-rep metrics** (`extract_rep_metrics`) — see "Per-Rep Metrics Schema" below.
8. **Confidence scoring** — Tier 1–5 pipeline, see "Confidence Architecture".
9. **Bar path** (`compute_bar_path_from_landmarks`) — always-on in Phase 0, tracks wrist midpoint.
10. **Keyframe extraction** (`extract_keyframes`) — start/depth/end frames per rep as base64 JPEG (Phase 1, FR-AICP-01).
11. **Form scoring** — 4-dimension ScoreComponent system.
12. **Artifact generation** — annotated MP4, angle time-series plot, angles CSV.
13. **Upload to Supabase Storage**, write paths to `analyses` row.
14. **Cleanup** — delete `/tmp` video; Storage copy deleted after pipeline completes (not after quality gate).

### Phase 0 sagittal (side) view only
Coaching framing guidance must reflect this — diagonal/oblique views are Phase 1+.

### Annotated video rendering
- Skeleton overlay: `#00FF88`, 2px lines, exercise-specific connections (squat/DL: hips/knees/ankles/shoulders; bench: shoulders/elbows/wrists/hips).
- Angle labels: Arial 18px white + 1px black outline, at 3 key joints.
- Rep counter: top-left Arial 24px bold `"Rep: N / M"` cumulative completed only.

## Confidence Architecture (Phase 1)

5-tier composite, implemented in `app/cv/confidence.py::compute_confidence_result`. Replaces Phase 0 `compute_rep_confidence` which still lives in the tree as dead code (to be removed in P2-024).

- **Tier 1** (FR-CVPL-20): `landmark_conf = sigmoid(visibility) × sigmoid(presence)` per landmark. Handles MediaPipe pre-logit values.
- **Tier 2** (FR-CVPL-21): `angle_conf = min(conf_A, conf_B, conf_C)` for angle at landmarks A-B-C. **Minimum, not mean** — one unreliable landmark invalidates the angle.
- **Tier 3** (FR-CVPL-22): `frame_conf = weighted_mean(landmark_conf[i] × weight[i])` with exercise-specific weights (hips/knees/ankles for squat; shoulders/elbows/wrists for bench).
- **Tier 4** (FR-CVPL-23): `frame_conf × phase_multiplier`. Multipliers: 1.0 static peaks, 0.85–0.95 transitions, 0.70–0.80 known high-occlusion (deep squat hip fold, sumo stance, bench supine). Configurable in ThresholdConfig.
- **Tier 5** (FR-CVPL-24, ADR-015): **10th percentile** of phase-adjusted frame confidences across the rep. Pessimistic bound, not mean — replaces FR-CVPL-16 from Phase 1 onward.

UI labels (FR-CVPL-25): ≥0.80 High (green); 0.65–0.79 Moderate (yellow); 0.50–0.64 Low (orange); <0.50 Very Low (red, suppress per-rep scores). **Categorical labels only — never display raw decimal confidence to users.**

## Form Scoring (Phase 1)

4-dimension Composite via `ScoreComponent` Protocol in `app/cv/scoring.py` (ADR-016):
- **SafetyScore** (FR-SCOR-01) — user-facing label "Movement Quality Score". Lumbar flexion, knee valgus, wrist misalignment, shoulder retraction loss, heel rise. Score < 3.0 triggers mandatory top-of-page warning.
- **TechniqueScore** (FR-SCOR-02) — depth, torso lean, hip/knee angles, elbow flare, bar touch, grip/stance width.
- **PathBalanceScore** (FR-SCOR-03) — bar path deviation, lateral weight shift, heel rise magnitude. Nuckols bar-over-midfoot anchor.
- **ControlScore** (FR-SCOR-04) — eccentric duration, lockout quality, phase of max deviation, rep-to-rep std dev. Sheiko consistency-under-load anchor.

**OverallFormScore** (FR-SCOR-05) = weighted composite. Default weights: Movement Quality 40%, Technique 30%, Path & Balance 20%, Control 10%. Admin-configurable via ThresholdConfig without code changes.

**Score descriptors** (FR-SCOR-07): 9.0–10.0 Elite, 7.5–8.9 Advanced, 5.0–7.4 Intermediate, 3.0–4.9 Needs Work, <3.0 Needs Attention.

**Extensibility** (FR-SCOR-06): adding a 5th dimension means implementing one `ScoreComponent` subclass and registering it. No DB/UI/PDF/eval changes required.

## ThresholdConfig (Phase 1, FR-SCOR-11, ADR-018)

Versioned JSON at `config/thresholds_v1.json` with top-level `version` field read at startup via `ThresholdConfigLoader`. Every entry carries `{value, unit, provenance_citation, last_modified_by}`.

Expert Reviewer proposes changes via PR. PR review IS the approval flow — no admin UI.

`analyses.threshold_version` freezes version at analysis time. Changing config never retroactively alters scored analyses.

Phase 0 path: `config/thresholds_v0.json` with hardcoded named constants (FR-SCOR-00).

## Per-Rep Metrics Schema

`RepMetrics.metrics: dict[str, float | str]` — widened in Phase 1 for `phase_of_max_deviation` which is a categorical string (ADR-022).

**All exercises** — `rep_duration_s`, `descent_duration_s`, `eccentric_duration_s` (alias of descent, FR-REPM-07), `ascent_duration_s`, `lockout_passed` (float 0/1), `lockout_confidence` (FR-REPM-08), `phase_of_max_deviation` (string: setup/descent/bottom/ascent/lockout, FR-REPM-09).

**Squat** — `depth_angle` (min hip), `knee_angle_at_depth`, `torso_lean`. Lockout: hip+knee ≥ 165°.

**Bench** — `elbow_angle_at_bottom`, `shoulder_angle_at_bottom`. Lockout: elbow ≥ 165°.

**Deadlift** — `hip_angle_at_bottom`, `knee_angle_at_lockout`, `torso_lean_at_start`. Lockout: hip ≥ 165° AND shoulders at/behind hip x.

**Rep-to-rep consistency** (FR-REPM-12): std devs of all numeric metric keys stored in `analyses.summary_json.consistency_metrics` by `SummaryService._compute_consistency_metrics`. Sheiko consistency-under-load principle.

## ARQ Worker

Entry point: `app/workers/analysis_worker.py::process_analysis(ctx, analysis_id: UUID) -> None`.

WorkerSettings: `queue_name="arq:queue"`, `job_timeout=300`, `max_jobs=1`, `keep_result=0`, `redis_settings=RedisSettings.from_url(os.environ["REDIS_URL"])`.

`max_jobs=1` on 2GB droplet (MediaPipe peak ~350MB RAM).

Heartbeat: write Redis key `spelix:worker:heartbeat` with 90s TTL every 30s.

Status transition sequence: `queued → quality_gate_pending → (quality_gate_rejected | processing) → coaching → completed`.

On any exception: catch, write `error_message` to DB, set `status=failed`, increment `retry_count`. If `retry_count >= 3`, terminal.

Idempotent: check status at job start; return immediately if already in terminal state (`completed`, `quality_gate_rejected`, or `failed` with `retry_count=3`).

Video download: fetch from Supabase Storage to `/tmp/spelix/{analysis_id}.mp4` at job start. Delete local temp on job exit regardless of outcome. Delete Storage copy after CV pipeline completes (not after quality gate).

**All CPU-bound work must go through `await loop.run_in_executor(None, fn)`** — never block the async event loop.

### Artifact cleanup cron
Separate ARQ periodic job runs nightly. Deletes `annotated_video_path`, `plot_path`, `pdf_path` from Supabase Storage for analyses older than 7 days. Sets columns to NULL after deletion. The analyses row and all metrics are retained indefinitely.

### Single OpenAI client pattern (ADR-024)
Worker creates a single `openai.AsyncOpenAI()` at start, wrapped in try/except (missing `OPENAI_API_KEY` → `None`, GPT-4o features no-op gracefully). Pass the same instance to `run_cv_pipeline(openai_client=...)` and reuse for `KeyframeAnalysisService`. **Do NOT instantiate per-feature.**

## LLM Coaching

### Model + config
- **Claude Sonnet 4.6** (`claude-sonnet-4-6`) for coaching, `temperature=0.3`, `max_tokens=2048`.
- **GPT-4o** (`gpt-4o`) for keyframe vision analysis and exercise auto-detect fallback, `temperature=0.2`.

### Structured output
`instructor` + Pydantic v2 schema enforcement. `CoachingOutput` in `app/schemas/coaching.py` carries Phase 1 fields: `summary`, `strengths`, `issues[]`, `correction_plan[]`, `recommended_cues[]`, `citations[]` (Phase 2 populated), `safety_warnings[]`, `confidence_level`, `dimension_addressed`, `disclaimer`, `raw_prompt_tokens`, `raw_completion_tokens`.

`Issue = {rep_number: int, joint: str, description: str, severity: Literal["High", "Medium", "Low"]}`.

### Coaching priority (FR-AICP-04)
Movement Quality → Technique → Path & Balance → Control. Enforced in system prompt. Follows Sjöberg, Myer et al., and JTS ordering (fix dangerous patterns → build movement quality → optimize performance).

### Body stats personalization (FR-AICP-05, FR-PROF-06)
Worker fetches `UserProfile` via `UserProfileRepository.get_by_user_id` and injects `{height_cm, weight_kg, age, experience_level, arm_span_cm, femur_length_cm}` into the coaching prompt. When adding a profile field, update the `getattr` loop in `analysis_worker.py` — hardcoded attr list is a known drift risk.

### Error handling
429/529 → exponential backoff 1s/2s/4s (3 retries). 401 → fail immediately + CRITICAL log. Network timeout 60s.

### Mandatory disclaimer
Verbatim at end of every coaching response: *"This feedback is for educational purposes only and is not a substitute for in-person coaching or medical advice."*

### Prompt caching (FR-AICP-21, ADR-020)
System prompt, persona, coaching priority hierarchy, and tool schemas are marked with `cache_control: {"type": "ephemeral"}` in the Anthropic API call. Rep metrics, body stats, keyframe analysis text, and user-specific context are **not** cached. RAG docs (Phase 2) are per-analysis and typically uncacheable.

## SSE Coaching Architecture (Phase 1, FR-AICP-07, ADR-019)

Worker and FastAPI web process are separate. Coaching runs in the worker; streaming endpoint lives in FastAPI. They communicate via Redis pub/sub.

### Worker side
`CoachingService.generate_coaching_streaming` streams Claude Sonnet text chunks and publishes each to Redis channel `coaching:{analysis_id}`:
```python
pubsub_redis = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
```
**Critical**: this is NOT `ctx["redis"]`. ARQ's Redis client blocks on pub/sub — use a dedicated client and close it in `finally:`.

Sends `{"type": "chunk", "text": "..."}` messages per chunk, then `{"type": "done"}` sentinel.

### Endpoint side (`api/v1/coaching_sse.py`)
`GET /api/v1/analyses/{id}/coaching/stream` subscribes to the channel BEFORE checking `stream_complete` in DB (race prevention). If coaching already completed, returns stored output as a single `event: complete`. Otherwise forwards chunks as SSE `data:` events, then on `"done"` sentinel fetches final validated `CoachingOutput` from DB and emits `event: complete`.

### Known tech debt: stream-then-reparse (ADR-021, P2-023)
Current implementation streams text, then makes a SECOND `instructor` call with accumulated text as an assistant message to re-validate into `CoachingOutput`. This doubles token cost per analysis. Phase 2 will replace with instructor's native streaming structured extraction. Do NOT optimize other parts of the coaching pipeline until this is addressed.

## Exercise Auto-Detection (Phase 1, FR-XDET-03/04/07)

Implementation in `app/cv/exercise_detection.py` (heuristic) and `app/services/keyframe_analysis.py` (GPT-4o fallback, `KeyframeAnalysisService.classify_exercise`).

**Heuristic** (`detect_exercise_heuristic`): joint-geometry classifier using torso vertical angle, hip/knee/elbow angle ranges, shoulder-hip vertical distance. Samples up to 20 evenly-spaced frames, filters by mean visibility > 0.3. Returns `DetectionResult(detected_type, detected_variant, confidence, method="heuristic", details)`.

**GPT-4o fallback**: triggered when heuristic `confidence < 0.7` and `openai_client` is not None. Extracts 3 evenly-spaced frames from the video as base64 JPEG via `_extract_sample_frames_b64`, calls `KeyframeAnalysisService.classify_exercise(frame_images_b64=[...])`. On any failure, falls back to heuristic result. Never blocks the pipeline.

**Stored on `analyses.detection_result` JSONB** for FR-XDET-07 display. **Does NOT override user-selected `exercise_type`** — detection is informational only (ADR-023). Quality gates, rep detection, and scoring all use the user's original choice.

## Testing

Unit tests: pure functions only — quality gates, confidence, rep detection, metric extraction, scoring. Use synthetic landmark data (no real video).

Integration tests: inject test `AsyncSession` via parameter — never use production session.

Video fixtures: `tests/fixtures/` — one squat, one deadlift, one bench (~10s each, 720p).

E2E API tests: httpx `AsyncClient` against full FastAPI app with mocked dependencies.

Mock LLM responses in coaching tests — never call Anthropic or OpenAI API in CI.

Quality gate tests: use synthetic numpy arrays mimicking MediaPipe landmark output with known visibility values.

### Run commands
```bash
uv run pytest tests/unit/ -x                     # Fast unit tests
uv run pytest tests/integration/ -x              # Needs real DB/Redis
uv run pytest -x --cov=app                       # Full coverage
uv run pytest tests/unit/test_pipeline.py -xvs  # Single file verbose
```

Coverage target: 90% minimum, enforced in CI. Current: **91%** (Phase 1 gate).

## Dependencies

Managed by `uv`, pinned in `requirements.txt` (or `pyproject.toml`). Key packages:
`fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `arq`, `redis`, `mediapipe`, `opencv-python-headless`, `instructor`, `anthropic`, `openai`, `weasyprint`, `matplotlib`, `slowapi`, `pydantic>=2.0`, `httpx`, `pytest`, `pytest-asyncio`, `pytest-cov`.

## Backend Gotchas

### Python imports
Always add imports inline with the code that uses them in the same edit operation. Never add imports in a separate edit — ruff/isort will strip the unused import before the usage edit is applied.

### MediaPipe
- Exact config: `model_complexity=2, static_image_mode=True, min_detection_confidence=0.5, min_tracking_confidence=0.5, num_threads=1`. No deviation.
- Visibility/presence scores may be pre-sigmoid logits (values outside [0,1]): apply `sigmoid()` before using (GitHub #4411, #4462).
- Not bit-exact deterministic — ±1° angle variance acceptable. `static_image_mode=True` + `num_threads=1` is the maximum reproducibility setting.
- Pin to an exact version — no `>=` or `~=` in requirements.

### Docker
- Use `opencv-python-headless`, not `opencv-python` (no GUI libs).
- On Debian trixie+: install `libgl1`, NOT `libgl1-mesa-glx` (package renamed).

### Supabase
- Connect via PgBouncer pooler at port **6543**, not direct Postgres 5432.
- Set `DATABASE_URL` env var. PgBouncer transaction mode requires `statement_cache_size=0` in asyncpg `connect_args`.

### ARQ
- `max_jobs=1` on 2GB droplet (MediaPipe peak ~350MB RAM).
- `job_timeout=300`, `queue_name="arq:queue"`, `keep_result=0`.

### SSE coaching Redis
The SSE pub/sub client is NOT `ctx["redis"]` (that one blocks on pub/sub). Open a dedicated `redis.asyncio.from_url(...)` with `decode_responses=True` and close it in `finally:` (ADR-019).

### Worker OpenAI client
Create ONE `openai.AsyncOpenAI()` at worker start, wrapped in try/except. Pass the same instance to `run_cv_pipeline(openai_client=...)` and reuse for `KeyframeAnalysisService`. Never instantiate per-feature (ADR-024).

### PDF generation
WeasyPrint, HTML template at `reports/templates/analysis_report.html`. See FR-XPRT-02 for page-by-page layout. Matplotlib is imported lazily inside `pdf.py::generate_bar_path_plot` (ADR-025) — do not hoist the import to module top.

### `RepMetrics.metrics` type
Typed `dict[str, float | str]` — `phase_of_max_deviation` is a categorical string. When adding a new non-numeric field, update the type, the three `_*_metrics` function return annotations, and the `test_all_*_metric_values_are_floats` invariant test in the same edit (ADR-022).

### `MagicMock` + Pydantic `from_attributes=True`
When extending a response schema (e.g., adding `detection_result`, `form_score_*`), you MUST explicitly set every new field to `None` in test mock factories. `MagicMock` auto-creates truthy child mocks that Pydantic then fails to validate, producing 500 errors in API tests. This bit us on every Phase 1 schema extension. Files to update: `test_analysis_api.py::_make_detail_analysis`, `test_analysis_crud.py::_make_mock_analysis`.

### Patching deferred imports
If a function does `from X import Y` inline (not at module top), patch at `X.Y`, not at the module that defers-imports it. `patch("app.services.pipeline.detect_exercise_heuristic")` raises `AttributeError` because the name doesn't exist on that module until runtime — patch `app.cv.exercise_detection.detect_exercise_heuristic` instead.

### Quality gate predicate
Runs in ARQ worker (not FastAPI). Reject: `mean(visibility[frames=0:5][landmarks∈{11,12,13,14,23,24,25,26}]) < 0.30`. Gate results stored in `analyses.quality_gate_result` as JSONB.

### Exercise detection does NOT override
`analyses.detection_result` is informational only for FR-XDET-07 display. User's `exercise_type` drives quality gates, rep detection, scoring. Never confuse the two (ADR-023).

### Rate limiting
`POST /api/v1/analyses` capped at 10/user/day via slowapi + Redis counter.

### TUS upload
Browser uploads directly to Supabase Storage signed URL. FastAPI never handles video bytes. FFprobe codec check runs in worker.

### MediaPipe fixture: ALL 5 columns required
Every synthetic landmark fixture must populate all 5 columns [x, y, z, visibility, presence]. The Tier 1 formula is sigmoid(visibility) × sigmoid(presence). If presence (column index 4) is left at zero, sigmoid(0) = 0.5 collapses the result regardless of visibility — producing a silent wrong answer, not an error. The fix: frame[:, 4] = visibility in the _make_landmark_frame helper. Add a comment: # col 4 = presence (required for Tier 1–5 confidence — do not omit).

### Phase task list must come from SRS filter, not from session memory
This is already in root CLAUDE.md as a General Rule, but worth repeating here because it manifests in backend batches: run rg "\| \*\*Must\*\*.*\| N \s*\|" docs/SRS.md before writing any batch plan. FR-REPM-08 (lockout quality), FR-REPM-09 (phase of max deviation), and FR-REPM-12 (consistency metrics) all slipped through Phase 1 Batches 0–3 because they weren't top-of-mind. Cost: 2 hours of gate-pressure scramble.

### Mock factories must be updated in the same commit as schema extensions
Already present, but add the complete list of files to check: test_analysis_api.py::_make_detail_analysis, test_analysis_crud.py::_make_mock_analysis, test_analysis_crud.py::_make_status_analysis. When adding Phase 2 fields (retrieved_sources, cove_trace, etc.), set every new field to None explicitly. Consider moving to spec=Analysis or a typed factory to make this automatic.

### "No extra fields" tests are brittle against schema growth
A test like assert set(body.keys()) == {"id", "status", "updated_at"} must be updated every time the schema grows. Prefer asserting a minimum required set ({"id", "status", "updated_at"}.issubset(body.keys())) for envelope fields, and reserve exact-set assertions only for sealed schemas that will never change.

### Hardcoded attribute loops drift when models grow
The Phase 1 body-stats injection missed arm_span_cm and femur_length_cm because the worker used for attr in ("height_cm", "weight_kg", "age", "experience_level"). When a model gains fields, the loop doesn't. Prefer profile.model_dump(include=COACHING_FIELDS) with an explicit COACHING_FIELDS: frozenset constant at the top of the file, updated whenever UserProfile grows.