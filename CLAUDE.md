# Spelix

Science-based barbell form coaching platform. Users upload squat/bench/deadlift videos → CV pipeline extracts pose + reps + metrics → AI generates structured coaching feedback. Private web app at spelix.app.
**Current phase: Phase 0** (core platform). Authoritative requirements: `@docs/SRS.md` — use it for phase definitions, requirement IDs, threshold values. Do not duplicate SRS content here.
Greenfield build — no migration from WorkoutFormAnalyzer. Alembic starts at migration 001.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 + Alembic, ARQ + Redis, MediaPipe BlazePose Heavy, OpenCV (headless), WeasyPrint
- **Database**: Supabase Postgres (public schema only; auth schema is Supabase-managed)
- **Storage/Auth/Realtime**: Supabase (Storage for artifacts, Auth for JWT, Realtime for status push)
- **AI (Phase 0)**: Claude Sonnet 4.6 (`claude-sonnet-4-6`) for coaching — no RAG, no vision yet
- **Frontend**: React 19, Vite 7, TypeScript strict, Tailwind CSS 3, shadcn/ui, Recharts
- **Infra**: DigitalOcean 2GB droplet behind Caddy, Vercel for frontend, Qdrant Cloud (Phase 2+)

## Structure

```
spelix/
  backend/
    app/
      api/v1/           # FastAPI routers
      services/         # Business logic
      repositories/     # DB access (Repository pattern)
      cv/               # MediaPipe pipeline, quality gates, scoring
      workers/          # ARQ job functions
      models/           # SQLAlchemy models
      schemas/          # Pydantic v2 schemas
    tests/
      unit/
      integration/
      e2e/
      fixtures/         # Video fixtures (~10s each, 720p)
    alembic/
    CLAUDE.md
  frontend/
    src/
      components/
      pages/
      hooks/
      api/              # Centralized API calls
    CLAUDE.md
  config/
    thresholds_v0.json  # Phase 0 hardcoded defaults (FR-SCOR-00)
  reports/
    templates/
      analysis_report.html  # WeasyPrint Phase 0 PDF template
  docs/
    SRS.md
    erd.png
    [13 diagram PNGs]
  .claude/
    settings.json
    settings.local.json
    commands/
```

## Commands

```bash
docker compose up -d                    # Start full dev environment
docker compose up backend -d            # Backend only
cd frontend && npm run dev              # Frontend only
pytest tests/unit/test_quality_gates.py -x  # Single test file
alembic revision --autogenerate -m "desc" && alembic upgrade head  # Migration
docker compose exec redis redis-cli llen arq:queue  # Inspect ARQ queue
docker compose ps && docker compose exec redis redis-cli ping      # Health check
```

## Architecture Decisions

- All CPU-bound CV work: `loop.run_in_executor(None, fn)` — never block the ARQ event loop
- Repository pattern: all DB access behind interfaces; services receive repos via dependency injection
- Status transitions: only valid per SRS Section 5.2a transition table — invalid transitions are defects
- Video lifecycle: downloaded to `/tmp/spelix/{analysis_id}.mp4`; deleted after pipeline completes; Storage copy deleted after pipeline (not after quality gate)
- Artifact retention: 7 days default (cost constraint — keeps active Storage at ~413 MB within Supabase free 1 GB tier). Scheduled ARQ cron job deletes annotated MP4, PDF, and plot PNG nightly. Sets paths to NULL in analyses row after deletion. History and scores are preserved — only artifact bytes are removed. Users see a 7-day download banner on results page.
- Confidence score: Phase 0 = mean landmark visibility (FR-CVPL-16); Phase 1+ = Tier 5 (FR-CVPL-24)
- Form scores (`form_score_*`): all NULL in Phase 0; Phase 1 writes them — columns exist in migration 001
- Phase 0 coaching: static render (not SSE); stored in `coaching_results.structured_output_json`; full response synchronous
- ThresholdConfig: Phase 0 uses named constants from `config/thresholds_v0.json`; Phase 1 uses `config/thresholds_v{N}.json` with version field read at startup
- Never use "injury risk" or "injury prevention" in any user-facing string — use "Movement Quality"
- All JSONB (not JSON) for schema columns
- Supabase FK: no DDL FK to `auth.users` — enforce via RLS only

## Database

8 tables: `users` (Supabase-managed), `user_profiles`, `analyses`, `rep_metrics`, `coaching_results`, `expert_annotations`, `rag_documents`, `admin_events`.
Migration 001: `analyses`, `user_profiles`, `rep_metrics`, `coaching_results` only. `rag_documents`/`expert_annotations`/`admin_events` deferred to Phase 2.
Required indexes in migration 001: `(user_id, created_at DESC)` on `analyses`; `(analysis_id)` on `rep_metrics` and `coaching_results`.
Status column: `VARCHAR(30)` with CHECK constraint listing all 7 valid values.
JSONB columns: `summary_json`, `quality_gate_result`, `metrics_json`, `structured_output_json`, `agent_trace_json`, `retrieved_sources_json`.

## Sub-Agent Routing
 
- Sub-agents use Sonnet 4.6 (set via CLAUDE_CODE_SUBAGENT_MODEL env var)
- All sub-agents run with **worktree isolation** — each gets its own git branch and working directory, auto-cleaned on completion
- Maximum 3 concurrent sub-agents (2GB RAM constraint — MediaPipe peak ~350MB)
 
### When to Dispatch Parallel Sub-Agents
 
Run `/parallel` (reads the parallel skill) when the next batch of tasks in `backlog.md` contains 2+ tasks with:
- Status: `todo`
- All dependencies satisfied (check `Deps` column)
- Non-overlapping file paths
 
The `/parallel` skill contains pre-planned dispatch blocks for Phase 0. Follow them.
 
### Safe Parallelization Rules
 
- **Safe to parallelise**: `backend/app/api/` vs `backend/app/cv/` vs `frontend/src/` — different directory subtrees
- **Safe to parallelise**: any pure function task (quality gates, confidence, signal processing) — no shared state
- **Never parallelise**: anything touching `models/`, `schemas/`, or `alembic/` — one agent owns these, others read results
- **Never parallelise**: tasks with dependency arrows in the implementation plan
 
### Sub-Agent Instructions Template
 
When dispatching via Task tool, each sub-agent receives:
1. "Read CLAUDE.md for project context"
2. "Use Context7 MCP to look up current API docs before writing library code"
3. The specific task description, file list, SRS requirement IDs, and TDD gate from the implementation plan
4. "Write failing test first, then implement. Commit when TDD gate passes."
 
### Post-Merge
 
After all sub-agents complete and their worktrees are merged:
1. Run `/check` — catch any cross-agent type conflicts
2. Run `/test` — catch any integration issues
3. Update `backlog.md` and `memory.md`

## Git Conventions
 
### Commit Messages
Use conventional commits. No co-authored-by, no emoji prefixes, no "Generated with Claude" footers.
 
Format:
```
type(scope): short description
 
Optional body with context if needed.
```
 
Types: `feat`, `fix`, `test`, `refactor`, `chore`, `docs`
Scopes: `api`, `cv`, `auth`, `models`, `worker`, `frontend`, `admin`, `config`, `ci`
 
Examples:
- `feat(cv): add quality gate body visibility check`
- `test(cv): unit tests for rep detection state machine`
- `feat(api): POST /analyses upload endpoint with signed URL`
- `chore: scaffold project structure and dependencies`
- `fix(worker): handle sigmoid on pre-logit MediaPipe visibility`
 
### Commit Behavior
- **Main agent**: always ask for confirmation before committing (git commit is NOT auto-approved)
- **Sub-agents in worktrees**: commit freely without confirmation — their work is reviewed at merge time
- **When to commit**: after each TDD gate passes (test green = commit point)
- **Commit scope**: one logical change per commit. Don't bundle unrelated changes.

## Gotchas

- MediaPipe: `model_complexity=2, static_image_mode=True, min_detection_confidence=0.5, min_tracking_confidence=0.5, num_threads=1` — exact config, no deviation
- MediaPipe visibility/presence scores may be pre-sigmoid logits (values outside [0,1]): apply `sigmoid()` before using (GitHub #4411, #4462)
- MediaPipe is not bit-exact deterministic — ±1° angle variance acceptable; `static_image_mode=True` + `num_threads=1` is the maximum reproducibility setting
- Docker: use `opencv-python-headless` not `opencv-python`; `libgl1` not `libgl1-mesa-glx` on Debian trixie+
- Supabase: connect via PgBouncer pooler at port 6543, not direct Postgres 5432 — use `DATABASE_URL` env var
- ARQ: `max_jobs=1` on 2GB droplet (MediaPipe peak ~350MB RAM); `job_timeout=300`; `queue_name="arq:queue"`
- Supabase Realtime: subscribe via `postgres_changes` on table `analyses` filtered by `id=eq.{id}`, listen for UPDATE events
- Rate limiting: `POST /api/v1/analyses` limited to 10/user/day via slowapi + Redis
- TUS upload: browser uploads directly to Supabase Storage signed URL — FastAPI never handles video bytes
- Quality gate: runs in ARQ worker (not FastAPI); reject predicate uses `mean(visibility[frames=0:5][landmarks∈{11,12,13,14,23,24,25,26}]) < 0.30`
- Annotated video: skeleton overlay `#00FF88`, 2px lines; angle labels Arial 18px white + 1px black outline; rep counter top-left Arial 24px bold `"Rep: N / M"`
- PDF: WeasyPrint, HTML template at `reports/templates/analysis_report.html`; see FR-XPRT-02 for page-by-page layout

## Compaction Survival

When asked to summarise for compaction: always preserve current phase, last 5 modified files, any failing tests, and the current task.
After compaction: re-read `@docs/SRS.md` Section 3 for current phase requirements before resuming.
After compaction: run `/status` to confirm environment state.
Phase 0 complete when: all pytest tests pass and `docker compose up` runs cleanly end-to-end.
