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
