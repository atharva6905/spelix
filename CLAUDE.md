# Spelix

Science-based barbell form coaching platform. Users upload squat/bench/deadlift videos → CV pipeline extracts pose + reps + metrics → AI generates structured coaching feedback. Private web app at spelix.app.

**Current phase: Post-L2 sprint — private beta live.** Phase 0 complete (93 items). Phase 1 complete (44 items). Phase 2 complete (44 items). Phase 3 complete (LangGraph agent, distillation pipeline, landing page, expert portal, beta flow, streaq migration — all on prod since 2026-05-03). L2 sprint hard gate met. Now in beta ops: real users, expert reviews, Coach Brain growing. Phase 4 eval infrastructure when needed. SRS v2.1 (north star — set in stone).

Authoritative requirements: `@docs/SRS.md`. Phase-specific architecture: `backend/CLAUDE.md` + `frontend/CLAUDE.md`. Decisions: `decisions.md`. Open work: [GitHub Issues](https://github.com/atharva6905/spelix/issues); completed archive: `backlog.md`. Strategy & priorities are kept in a local-only strategy note (not in the public repo) — consult it before suggesting new features or scope changes.

Greenfield build — no migration from WorkoutFormAnalyzer. Alembic starts at migration 001.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 + Alembic, streaq + Redis, MediaPipe BlazePose Heavy, OpenCV headless, WeasyPrint, LangGraph. See `backend/CLAUDE.md`.
- **Database**: Supabase Postgres (public schema only; auth schema is Supabase-managed)
- **Storage/Auth/Realtime**: Supabase (Storage for artifacts, Auth for JWT, Realtime for status push)
- **AI**: Claude Sonnet 4.6 (`claude-sonnet-4-6`) for coaching with prompt caching; OpenAI GPT-4o (`gpt-4o`) for keyframe analysis + exercise auto-detect fallback; LangGraph for agent orchestration; LangSmith for tracing
- **Frontend**: React 19, Vite 8, TypeScript strict, Tailwind CSS 4, shadcn/ui, Recharts. See `frontend/CLAUDE.md`.
- **Infra**: DigitalOcean 4GB droplet behind Caddy, Vercel for frontend, Qdrant Cloud (Phase 2+)

## Structure

```
spelix/
  backend/     CLAUDE.md — backend architecture, CV, API, worker, all backend gotchas
  frontend/    CLAUDE.md — frontend architecture, components, hooks, all frontend gotchas
  config/      thresholds_v0.json + thresholds_v1.json (FR-SCOR-00/11)
  reports/templates/analysis_report.html  # WeasyPrint PDF template
  docs/SRS.md
  decisions.md  # ADR log
  backlog.md    # Completed-work archive
  .claude/
    settings.json
    agents/     # Specialist agent definitions
    hooks/      # Hook scripts (smoke-test: node .claude/hooks/smoke-test.mjs)
    rules/      # Path-scoped + always-on rules (git/deploy, governance, cv, coaching, migrations, frontend)
    skills/     # Project skills (/design, /implement, /ship-loop, /groom, /bugfix, ...)
    handoff.md  # Session-to-session state (local-only)
```

## Commands

```bash
docker compose up -d                    # Start Redis (backend runs locally via uv)
cd frontend && npm run dev              # Frontend dev server
uv run pytest tests/unit/test_X.py -x  # Single test file (from backend/)
uv run alembic revision --autogenerate -m "desc" && uv run alembic upgrade head  # Migration
docker compose exec redis redis-cli llen streaq:queue  # streaq queue depth
node .claude/hooks/smoke-test.mjs       # Verify hook scripts after editing them
```

Session start: live environment state is injected automatically by the SessionStart hook. Run `/status` only for an on-demand refresh.

## CLAUDE.md Organization Rules

**Keep root CLAUDE.md under 200 lines.** Root is for cross-cutting concerns only.

- **Root**: purpose, phase status, stack, structure, commands, general rules, agent architecture, compaction survival.
- **backend/CLAUDE.md** / **frontend/CLAUDE.md**: domain architecture + gotchas. Can grow as needed.
- **`.claude/rules/`**: enforced process rules — `git-github.md` + `governance.md` (always-on), `cv-pipeline.md`, `coaching.md`, `migrations.md`, `frontend.md` (path-scoped, load only when matching files are touched). New hard rules go here, not in root.
- **ADRs live in `decisions.md`** — CLAUDE.md cross-references IDs, never duplicates body text.

## General Rules

- When asked to start fixing or implementing immediately, skip broad codebase exploration. Read only the specific files needed and begin.
- Use terminology exactly as defined in SRS.md. Never invent names, categories, or subsystem labels not present in the spec.
- **Phase task lists come from SRS, not memory**: generate the authoritative MUST list by filtering `docs/SRS.md` (`rg "\| \*\*Must\*\*.*\| N \s*\|" docs/SRS.md`). Never schedule batches from session memory alone.
- **Run `spelix-auditor` after every batch merge**, not just at phase gates.
- Language, schema, git/deploy, and merge-governance rules are enforced via `.claude/rules/` — they load automatically. Headline: user-facing copy says "Movement Quality", never "injury risk".
- For any task with a testable completion condition, prefer `/goal "<condition>"` (e.g., `/goal "pytest tests/unit/test_coaching.py passes and pyright is clean"`) — Claude iterates until the condition holds. The Stop gate is the deterministic backstop.

## Agent Architecture

Named specialist agents carry permanent domain knowledge. Main agent auto-delegates when a task matches an agent's description, or invoke explicitly: `"Use the spelix-cv-engineer agent to implement FR-CVPL-08"`.

**Implementers:** `spelix-tdd` (general TDD-first, incl. frontend), `spelix-cv-engineer` (all of `backend/app/cv/`), `spelix-migration` (Alembic/schema), `spelix-ai-engineer` (coaching/RAG/LangGraph/Coach Brain/prompts).
**Reviewers (read-only, project memory):** `spelix-spec-reviewer` (diff vs task requirements, T1+), `spelix-quality-reviewer` (architecture/tests/gotchas, T2/T3), `spelix-security-reviewer` (JWT/RLS/SaMD/secrets, T2+ pre-PR gate), `spelix-governance-reviewer` (tier validation + T0 self-merge gate), `spelix-auditor` (SRS compliance fan-out, Haiku).
**Activate at Phase 4:** `spelix-eval-engineer`.

### Delegation Rules

For ANY task with open design questions, new user-facing surface, or 3+ files:
1. `/design <idea|issue#>` — routed ideation → spec → plan → groomed GitHub issues
2. `/ship-loop <issue#s>` — execution; each issue runs through `/implement`
   (worktree + routed specialist + tier-scaled review chain)

For one-off tasks with a known tier: `/implement <task> --tier <T>` directly.
Specialist routing (cv/migration/ai/tdd) lives in the `/implement` routing table.
For any commit touching auth, user data, or user-facing strings: `spelix-security-reviewer` PASS first.

### Parallelism

Independent tasks → Workflow tool (saved workflows in `.claude/workflows/`) or background agents with `isolation: "worktree"`. `/implement` owns per-task worktree isolation. Agent Teams and the /team and /parallel skills are retired.
Cross-domain shared interfaces (API shape + consumer) → make the contract an explicit early task; never parallelize across it.
**Never parallelise**: `backend/app/models/`, `backend/app/schemas/`, `backend/alembic/`, tasks with Deps arrows.

Sub-agents and worktrees commit freely. Main agent asks for confirmation before committing.

## Droplet Debugging (SSH)

SSH in directly — never ask the user. See `backend/CLAUDE.md` "Droplet Debugging" for full command reference. SSH alias: `spelix-droplet`. Start with `ssh spelix-droplet "docker ps -a"`.

## Compaction Survival

Context budget: keep below 60% capacity. Watch the statusline.
At 60%: finish current task, run `/handoff`, start fresh session.
Use the Explore built-in subagent for file discovery — its reads stay out of main context.
The PreCompact hook auto-writes a mini-handoff to `.claude/handoff.md` before any compaction.
After compaction: re-read `@docs/SRS.md` Section 3 for current phase requirements before resuming.

**Phase completion criterion**: All MUST requirements implemented + full test suite green + migration applied + specialist audit clean. Phase 1 passed 2026-04-10. Phase 2 passed 2026-04-14. Phase 3 + L2 passed 2026-05-03. Current: **2301 backend unit tests, 765 frontend tests, 27 migrations applied** (head: `47c8e446162e`).

## Session State Protocol

Current session state lives in `.claude/handoff.md` (local-only, gitignored). SessionEnd/PreCompact hooks stamp it automatically; run `/handoff` for the full structured note at deliberate session ends. Durable cross-session facts live in the file-based memory at `~/.claude/projects/.../memory/`. There is no tracked agent-state file in the repo.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- ALWAYS read graphify-out/GRAPH_REPORT.md before reading any source files, running grep/glob searches, or answering codebase questions.
- IF graphify-out/wiki/index.md EXISTS, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query/path/explain` over grep.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
