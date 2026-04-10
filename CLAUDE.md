# Spelix

Science-based barbell form coaching platform. Users upload squat/bench/deadlift videos → CV pipeline extracts pose + reps + metrics → AI generates structured coaching feedback. Private web app at spelix.app.
**Current phase: Phase 1 IN PROGRESS** — Phase 0 complete (93 backlog items, B-001–B-093). Phase 1 delivers: GPT-4o keyframe analysis, form scoring system (4 dimensions + composite), SSE streaming coaching, Tier 1–5 confidence, ThresholdConfig v1, prompt caching. Authoritative requirements: `@docs/SRS.md` — use it for phase definitions, requirement IDs, threshold values. Do not duplicate SRS content here.
Greenfield build — no migration from WorkoutFormAnalyzer. Alembic starts at migration 001.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 + Alembic, ARQ + Redis, MediaPipe BlazePose Heavy, OpenCV (headless), WeasyPrint
- **Database**: Supabase Postgres (public schema only; auth schema is Supabase-managed)
- **Storage/Auth/Realtime**: Supabase (Storage for artifacts, Auth for JWT, Realtime for status push)
- **AI (Phase 1)**: Claude Sonnet 4.6 (`claude-sonnet-4-6`) for coaching with prompt caching; OpenAI GPT-4o (`gpt-4o`) for keyframe analysis + exercise auto-detect fallback
- **Frontend**: React 19, Vite 8, TypeScript strict, Tailwind CSS 4, shadcn/ui, Recharts
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
uv run pytest tests/unit/test_quality_gates.py -x  # Single test file
uv run alembic revision --autogenerate -m "desc" && alembic upgrade head  # Migration
docker compose exec redis redis-cli llen arq:queue  # Inspect ARQ queue
docker compose ps && docker compose exec redis redis-cli ping      # Health check
```

## General Rules

- When asked to start fixing or implementing immediately, skip broad codebase exploration. Read only the specific files needed for the task and begin.
- Use terminology exactly as defined in SRS.md and CLAUDE.md. Never invent names, categories, or subsystem labels not present in the spec.

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

## Agent Architecture

### Specialist Agents (`.claude/agents/`)

Named specialist agents carry permanent domain knowledge. The main agent auto-delegates
when a task matches an agent's description, or invoke explicitly:
`"Use the spelix-cv-engineer agent to implement FR-CVPL-08"`

**Active agents (always):**
- `spelix-tdd` — TDD-first implementation for any feature or fix
- `spelix-auditor` — read-only SRS compliance checker (Haiku model)
- `spelix-security-reviewer` — pre-merge auth/RLS/language checks
- `spelix-migration` — Alembic migrations and schema changes

**Active agents (Phase 1):**
- `spelix-cv-engineer` — all tasks in `backend/app/cv/`
- `spelix-coaching-engineer` — coaching service, SSE, LLM prompt work

**Activate at Phase 2:** `spelix-rag-engineer`, `spelix-corpus-curator`
**Activate at Phase 3:** `spelix-langgraph-engineer`
**Activate at Phase 4:** `spelix-eval-engineer`

### Agent Delegation Rules

For ANY task touching 3+ files or with an SRS requirement ID:
1. Run `/plan` — Explore and plan first, never jump to code
2. Dispatch execution to the matching specialist agent
3. Main agent reviews output, runs /check + /test, merges

For tasks in `backend/app/cv/`: always use `spelix-cv-engineer`
For Alembic or schema changes: always use `spelix-migration`
For any commit touching auth, user data, or user-facing strings: invoke `spelix-security-reviewer` first

### Parallelism — Decision Rules

**Three patterns. Choose based on whether workers need to talk to each other.**

`/parallel` (subagents) — independent tasks, result only matters, no cross-agent
negotiation. Max 7 agents; max 3 on 2GB droplet.

`claude --worktree name` (separate terminals) — independent tasks each needing their
own full context window. Open 2–4 terminals, each running a named specialist.

`/team` (Agent Teams) — cross-domain tasks where specialists must negotiate an
interface, debug competing hypotheses, or coordinate on shared types. Teammates
communicate directly via shared task list and mailbox. Run `/team [scenario]`.
Always shut the team down when work is done — idle teammates burn tokens.

**Decision question: do the workers need to talk to each other to produce correct output?**
No → /parallel or worktrees. Yes → /team.

**Cost rules for /team**: Sonnet for all teammates, max 3 teammates, focused spawn
prompts (CLAUDE.md loads automatically — don't repeat it), shut down when done.

**Never parallelise** (any method): `models/`, `schemas/`, `alembic/`, tasks with Deps arrows.
Sub-agents and worktrees commit freely. Main agent asks for confirmation before committing.

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

- Python imports: always add imports inline with the code that uses them in the
same edit operation. Never add imports in a separate edit — ruff/isort will
strip the unused import before the usage edit is applied.
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

Context budget: keep below 60% capacity. Watch the statusline.
At 60%: finish current task, run /handoff, start fresh session.
Use the Explore built-in subagent for file discovery — its reads stay out of main context.
When asked to summarize for compaction: always preserve current phase, last 5 modified files, any failing tests, and the current task.
After compaction: re-read `@docs/SRS.md` Section 3 for current phase requirements before resuming.
After compaction: run `/status` to confirm environment state.
Phase 0 complete when: all pytest tests pass and `docker compose up` runs cleanly end-to-end.
At the end of any session that didn't complete all planned batches, write a
handoff note to .claude/handoff.md containing: (1) completed tasks with commit
SHAs, (2) remaining tasks with backlog IDs, (3) current test count and any
failures, (4) any blockers discovered.

## memory.md Update Protocol

After every session commit, update memory.md with:
  phase: [current]
  task: [current task ID]
  status: [in_progress | blocked | escalated | done]
  last_modified: [last 5 files modified]
  failing_tests: [list or empty]
  blockers: [list or empty]
  next_action: "[specific next step — exact command or task]"
  session_count: [increment by 1]
  last_session: [today's date]
