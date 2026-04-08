# Backend — CLAUDE.md

## API Layer

Route prefix: `/api/v1/`. One router file per resource in `app/api/v1/`: `analyses.py`, `profiles.py`, `admin.py`.
Auth: FastAPI dependency `get_current_user` validates Supabase JWT via `SUPABASE_JWT_SECRET` env var; inject into all protected routes.
Error format: `{"error": {"code": str, "message": str, "detail": any}}` — never return raw exceptions.
Upload flow: `POST /analyses` → create DB record (status=queued) → return signed TUS URL + analysis ID (201). `POST /analyses/{id}/start` → enqueue ARQ job, transition status to queued → return 202.
Status poll: `GET /analyses/{id}/status` returns `{id, status, updated_at}` — fallback when Realtime disconnects.
Rate limit: `POST /analyses` capped at 10/user/day via slowapi + Redis counter.
Admin routes: server-side role check; non-admins receive 403. No RLS bypass — admin queries use service role key scoped to read-only admin views.
Request body for `POST /analyses`: `{exercise_type, exercise_variant, filename, file_size_bytes}`. Response 201: `{id, upload_url, status, expires_at}`.
Signed TUS URL TTL: 1 hour. Video validation (FFprobe codec check) runs in ARQ worker, not in the upload endpoint.
OpenAPI schema auto-generated — frontend types derived from it. Keep response models in `app/schemas/` aligned with actual responses.

## Service and Repository Layer

Services in `app/services/`: business logic only, no DB calls, no imports from `repositories` internals.
Repositories in `app/repositories/`: all DB access. Each repository takes `AsyncSession` in constructor.
Session injected via FastAPI dependency — never import a global session.
Pattern: `class AnalysisRepository: def __init__(self, db: AsyncSession)` → services receive repos via DI.
Status transitions: use a `transition(current, target)` guard function — raise `InvalidTransition` on illegal moves per SRS 5.2a table.

## CV Pipeline

Pipeline lives in `app/cv/`: `quality_gates.py`, `pose_extraction.py`, `rep_detection.py`, `metric_extraction.py`, `scoring.py`, `artifact_generation.py`.
All CV functions are pure (no side effects) — stateless, injectable, independently testable.
Quality gate return type: `GateCheckResult(passed: bool, name: str, level: str, metric_value: float, threshold: float, user_message: str)`; aggregated into `QualityGateResult(passed: bool, status: str, checks: list[GateCheckResult])`.
Phase 0 rep detection: threshold-crossing on primary angle per exercise:
- **Squat**: hip angle — standing >160°, depth <90°
- **Deadlift**: hip angle — standing >160°, bottom <70° (conventional/sumo), <90° (RDL)
- **Bench**: elbow angle — lockout >160°, bottom <90°
- Min rep duration 0.5s, hysteresis ±5°
Rep state machine: STANDING → DESCENDING → BOTTOM → ASCENDING → STANDING.
`analyses.confidence_score` = mean of per-rep confidence scores — written after all reps processed.
Phase 0 per-rep confidence = mean(visibility) across exercise-relevant landmarks per frame (squat/DL: {23,24,25,26,27,28}; bench: {11,12,13,14,15,16}), averaged across frames in that rep (FR-CVPL-16).
Annotated video: skeleton connections exercise-specific (squat/DL: hips/knees/ankles/shoulders; bench: shoulders/elbows/wrists/hips). `#00FF88` 2px lines. Angle labels at 3 key joints. Rep counter top-left `"Rep: N / M"` cumulative completed only.
Quality gate predicate (P0 — body visibility): `REJECT IF mean(visibility[frames=0:5][landmarks∈{11,12,13,14,23,24,25,26}]) < 0.30`. Gate results stored in `analyses.quality_gate_result` as JSONB.
Quality gate P0 (framing): reject if subject bounding box area < 30% or > 80% of total frame area across first 5 frames.
Phase 0 sagittal (side) view only. Coaching framing guidance must reflect this — diagonal/oblique views are Phase 1.
Artifact generation: annotated MP4, angle time-series plot (PNG via matplotlib), angle CSV at `artifacts/{analysis_id}/angles.csv`.
All artifacts uploaded to Supabase Storage; paths written to `analyses.annotated_video_path`, `analyses.plot_path`.
Summary metrics: each completed analysis writes `analyses.summary_json` with trend inputs for the history page (FR-HIST-04).

## ARQ Worker

Entry point: `app/workers/analysis_worker.py` — `async def process_analysis(ctx, analysis_id: UUID) -> None`.
WorkerSettings: `queue_name="arq:queue"`, `job_timeout=300`, `max_jobs=1`, `keep_result=0`, `redis_settings=RedisSettings.from_url(os.environ["REDIS_URL"])`.
Heartbeat: write Redis key `spelix:worker:heartbeat` with 90s TTL every 30s.
Status transition sequence: `queued → quality_gate_pending → (quality_gate_rejected | processing) → coaching → completed`.
On any exception: catch, write `error_message` to DB, set `status=failed`, increment `retry_count`. If `retry_count >= 3`, terminal.
Idempotent: check status at job start; return immediately if already in terminal state (`completed`, `quality_gate_rejected`, or `failed` with `retry_count=3`).
Video download: fetch from Supabase Storage to `/tmp/spelix/{analysis_id}.mp4` at job start. Delete local temp on job exit regardless of outcome. Delete Storage copy after CV pipeline completes (not after quality gate).
All CPU-bound work: `await loop.run_in_executor(None, fn)` — never block the async event loop.
Artifact cleanup: a separate ARQ periodic job runs nightly — deletes annotated_video_path, plot_path, pdf_path from Supabase Storage for analyses older than 7 days. Sets columns to NULL after deletion. The analyses row and all metrics are retained indefinitely.

## LLM Coaching (Phase 0)

Model: `claude-sonnet-4-6`, temperature=0.3, max_tokens=2048.
Use `instructor` + Pydantic v2 schema enforcement: `CoachingOutput(summary: str, strengths: list[str], issues: list[Issue], correction_plan: list[str], disclaimer: str, raw_prompt_tokens: int, raw_completion_tokens: int)`.
`Issue = {rep_number: int, joint: str, description: str, severity: Literal["High", "Medium", "Low"]}`.
Error handling: 429/529 → exponential backoff 1s/2s/4s (3 retries); 401 → fail immediately + CRITICAL log; network timeout 60s.
Coaching output stored in `coaching_results.structured_output_json` as JSONB.
Prompt template defined in Appendix D of `@docs/SRS.md` — do not redefine here.
Mandatory disclaimer verbatim at end: "This feedback is for educational purposes only and is not a substitute for in-person coaching or medical advice."
Phase 0 coaching is synchronous (no SSE). Phase 1 adds streaming — the `CoachingOutput` schema extends additively.

## Testing

Unit tests: pure functions only — quality gates, confidence calculation, rep detection, metric extraction. Use synthetic landmark data (no real video).
Integration tests: inject test `AsyncSession` via parameter — never use production session.
Video fixtures: `tests/fixtures/` — one squat, one deadlift, one bench (~10s each, 720p).
Run: `pytest tests/unit/ -x` (fast), `pytest tests/integration/ -x` (needs Docker), `pytest -x --cov=app` (full).
TDD discipline: write failing test before implementing the function it tests.
Coverage target: 90% minimum, enforced in CI.
E2E API tests: httpx `AsyncClient` against full FastAPI app with real Postgres test database.
Mock LLM responses in coaching tests — never call Anthropic API in CI.
Quality gate tests: use synthetic numpy arrays mimicking MediaPipe landmark output with known visibility values.

## Dependencies

Managed by `uv`, pinned in `requirements.txt`. Key packages:
`fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `arq`, `redis`, `mediapipe`, `opencv-python-headless`, `instructor`, `anthropic`, `weasyprint`, `slowapi`, `pydantic>=2.0`, `httpx`, `pytest`, `pytest-asyncio`, `pytest-cov`.
