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
