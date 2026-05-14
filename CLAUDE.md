# Spelix

Science-based barbell form coaching platform. Users upload squat/bench/deadlift videos → CV pipeline extracts pose + reps + metrics → AI generates structured coaching feedback. Private web app at spelix.app.

**Current phase: Post-L2 sprint — private beta live.** Phase 0 complete (93 items). Phase 1 complete (44 items). Phase 2 complete (44 items). Phase 3 complete (LangGraph agent, distillation pipeline, landing page, expert portal, beta flow, streaq migration — all on prod since 2026-05-03). L2 sprint hard gate met. Now in beta ops: real users, expert reviews, Coach Brain growing. Next: internship applications (mid-May 2026), Phase 4 eval infrastructure when needed. SRS v2.1 (north star — set in stone).

Authoritative requirements: `@docs/SRS.md`. Phase-specific architecture: `backend/CLAUDE.md` + `frontend/CLAUDE.md`. Decisions: `decisions.md`. Task list: `backlog.md`. **Strategy & priorities: `STRATEGY.md`** — L2 beta launch plan, internship timeline, time budgets, stop-loss triggers. Read before suggesting new features or scope changes.

Greenfield build — no migration from WorkoutFormAnalyzer. Alembic starts at migration 001.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 + Alembic, streaq + Redis, MediaPipe BlazePose Heavy, OpenCV headless, WeasyPrint, LangGraph. See `backend/CLAUDE.md`.
- **Database**: Supabase Postgres (public schema only; auth schema is Supabase-managed)
- **Storage/Auth/Realtime**: Supabase (Storage for artifacts, Auth for JWT, Realtime for status push)
- **AI**: Claude Sonnet 4.6 (`claude-sonnet-4-6`) for coaching with prompt caching; OpenAI GPT-4o (`gpt-4o`) for keyframe analysis + exercise auto-detect fallback; LangGraph for Phase 3 agent orchestration; LangSmith for tracing
- **Frontend**: React 19, Vite 8, TypeScript strict, Tailwind CSS 4, shadcn/ui, Recharts. See `frontend/CLAUDE.md`.
- **Infra**: DigitalOcean 4GB droplet behind Caddy, Vercel for frontend, Qdrant Cloud (Phase 2+)

## Structure

```
spelix/
  backend/     CLAUDE.md — backend architecture, CV, API, worker, all backend gotchas
  frontend/    CLAUDE.md — frontend architecture, components, hooks, all frontend gotchas
  config/
    thresholds_v0.json  # Phase 0 hardcoded defaults (FR-SCOR-00)
    thresholds_v1.json  # Phase 1 versioned ThresholdConfig (FR-SCOR-11)
  reports/templates/analysis_report.html  # WeasyPrint PDF template
  docs/SRS.md
  decisions.md  # ADR log
  backlog.md    # Task list, cross-phase
  .claude/
    settings.json
    agents/    # Specialist agent definitions
    handoff.md # Session-to-session state
```

## Commands

```bash
docker compose up -d                    # Start Redis (backend runs locally via uv)
cd frontend && npm run dev              # Frontend dev server
uv run pytest tests/unit/test_X.py -x  # Single test file (from backend/)
uv run alembic revision --autogenerate -m "desc" && uv run alembic upgrade head  # Migration
docker compose exec redis redis-cli llen arq:queue  # ARQ queue depth
```

## Session Start — Environment Verification

At the start of every session, run `/status` to load live environment state.


## CLAUDE.md Organization Rules

**Keep root CLAUDE.md under 200 lines.** It is loaded on every session start and competes for context budget with the actual work. Root is for cross-cutting concerns only.

- **Root CLAUDE.md**: project purpose, phase status, high-level stack, directory tree, commands, general rules, agent architecture, git conventions, compaction survival, memory protocol.
- **backend/CLAUDE.md**: Python/FastAPI/ARQ/CV/coaching/DB architecture, all backend-specific gotchas, backend testing conventions. Can grow as long as needed.
- **frontend/CLAUDE.md**: React/Vite/components/hooks/Supabase client architecture, all frontend-specific gotchas, frontend testing conventions. Can grow as long as needed.
- **When adding a new rule or gotcha**: decide which file it belongs in first. If it's touching backend code, write it in `backend/CLAUDE.md`. If it's touching frontend code, write it in `frontend/CLAUDE.md`. Only write it in root if it's truly cross-cutting (git, agents, process).
- **When root grows past 200 lines**: audit for items that should move to backend/ or frontend/ CLAUDE.md and migrate them. Do not let root bloat.
- **ADRs live in `decisions.md`**, not in CLAUDE.md. CLAUDE.md can cross-reference ADR IDs but should not duplicate their body text.

## General Rules

- When asked to start fixing or implementing immediately, skip broad codebase exploration. Read only the specific files needed for the task and begin.
- Use terminology exactly as defined in SRS.md. Never invent names, categories, or subsystem labels not present in the spec.
- **Phase task lists come from SRS, not memory**: at the start of each phase, generate the authoritative MUST list by filtering `docs/SRS.md` (`rg "\| \*\*Must\*\*.*\| N \s*\|" docs/SRS.md` where N is the phase number). Paste IDs into `backlog.md`. Never schedule batches from session memory alone — Phase 1 missed FR-REPM-08/09 this way and had to scramble at the transition gate.
- **Run `spelix-auditor` after every batch merge**, not just at phase gates. Incremental audits catch missing requirements when they're still cheap to add.
- **Apply migrations immediately**. Never let an alembic revision sit unapplied across sessions. Run `uv run alembic upgrade head` the same session you write the revision.
- Never use "injury risk" or "injury prevention" in any user-facing string — use "Movement Quality". Internal field is `form_score_safety`, user-facing label is "Movement Quality". Enforced in backend prompts, frontend copy, PDF templates, and error messages.
- All JSONB (not JSON) for schema columns.
- Supabase FK: no DDL FK to `auth.users` — enforce via RLS only.

## Agent Architecture

Named specialist agents carry permanent domain knowledge. Main agent auto-delegates when a task matches an agent's description, or invoke explicitly: `"Use the spelix-cv-engineer agent to implement FR-CVPL-08"`.

**Active agents (always):**
- `spelix-tdd` — TDD-first implementation for any feature or fix
- `spelix-auditor` — read-only SRS compliance checker (Haiku model)
- `spelix-security-reviewer` — pre-merge auth/RLS/language checks
- `spelix-migration` — Alembic migrations and schema changes

**Active agents (Phase 1+):**
- `spelix-cv-engineer` — all tasks in `backend/app/cv/`
- `spelix-coaching-engineer` — coaching service, SSE, LLM prompt work

**Active agents (Phase 2+):**
- `spelix-rag-engineer` — Qdrant, Cohere embed/rerank, hybrid retrieval, ingestion
- `spelix-corpus-curator` — research document ingestion, metadata, citation provenance

**Active agents (Phase 3+):**
- `spelix-langgraph-engineer` — Phase 3 agent core, distillation StateGraph, CoVe verification, Coach Brain review queue, reasoning sidebar

**Activate at Phase 4:** `spelix-eval-engineer`

### Delegation Rules

For ANY task touching 3+ files or with an SRS requirement ID:
1. Run `/plan` — Explore and plan first, never jump to code
2. Dispatch execution to the matching specialist agent
3. Main agent reviews output, runs /check + /test, merges

For tasks in `backend/app/cv/`: always use `spelix-cv-engineer`.
For Alembic or schema changes: always use `spelix-migration`.
For any commit touching auth, user data, or user-facing strings: invoke `spelix-security-reviewer` first.

### Parallelism — Decision Rules

**Decision question: do the workers need to talk to each other to produce correct output?**
- No → `/parallel` (subagents, max 7, max 3 on droplet) or `claude --worktree name` (separate terminals, 2–4 at a time).
- Yes → `/team [scenario]` (Agent Teams with shared task list + mailbox).

**MANDATORY**: When a batch has cross-task coordination needs (shared API contracts, shared client interfaces, backend↔frontend data shapes), use `/team` — NOT background `Agent()` calls. `/team` provides a shared task list + mailbox that background agents lack. Session 23 demonstrated this: P2-029 backend published the consent API contract to the frontend teammate via team messaging, and P2-034 published the Langfuse client interface for P2-033. Background agents cannot coordinate like this.

**When to use `/team` vs `/parallel`**:
- Backend API + frontend consuming it → `/team` (API contract coordination)
- Service A produces interface that Service B consumes → `/team`
- Independent bug fixes, independent test files, docs → `/parallel`
- If in doubt and batch has 2+ tasks with a Deps arrow → `/team`

**Workflow**: always `/plan` first → create tasks with dependencies → spawn teammates with focused prompts → lead works on independent tasks while team executes → review + merge.

`/team` cost rules: Sonnet for all teammates, max 3 teammates, focused spawn prompts (CLAUDE.md loads automatically — don't repeat it), shut down idle teammates immediately.

**Never parallelise** (any method): `backend/app/models/`, `backend/app/schemas/`, `backend/alembic/`, tasks with Deps arrows.

Sub-agents and worktrees commit freely. Main agent asks for confirmation before committing.

## Git Conventions

Use conventional commits. No co-authored-by, no emoji prefixes, no "Generated with Claude" footers.

Format: `type(scope): short description` — optional body with context.

Types: `feat`, `fix`, `test`, `refactor`, `chore`, `docs`.
Scopes: `api`, `cv`, `auth`, `models`, `worker`, `frontend`, `admin`, `config`, `ci`, `pdf`, `coaching`.

- **Main agent**: always ask for confirmation before committing.
- **Sub-agents in worktrees**: commit freely without confirmation — reviewed at merge time.
- **When to commit**: after each TDD gate passes (test green = commit point).
- **Commit scope**: one logical change per commit. Don't bundle unrelated changes.

## GitHub Operations — Use GitHub MCP First

**Always prefer GitHub MCP tools over `gh` CLI or direct git commands for GitHub API operations.** The MCP tools provide structured responses and are the primary interface for GitHub interactions.

| Operation | Use | Not |
|-----------|-----|-----|
| Check PR status/details | `mcp__github__get_pull_request` | `gh pr view` |
| Check CI/check runs | `mcp__github__get_pull_request_status` | `gh pr checks` |
| Create PR | `mcp__github__create_pull_request` | `gh pr create` |
| Create branch | `mcp__github__create_branch` | `git push -u origin` |
| Read file on GitHub | `mcp__github__get_file_contents` | `gh api` |
| List/search issues | `mcp__github__list_issues` / `search_issues` | `gh issue list` |
| Create/update issues | `mcp__github__create_issue` / `update_issue` | `gh issue create` |
| Comment on issues/PRs | `mcp__github__add_issue_comment` | `gh issue comment` |
| Review PRs | `mcp__github__create_pull_request_review` | `gh pr review` |
| View PR files/diff | `mcp__github__get_pull_request_files` | `gh pr diff` |
| Merge PR | `mcp__github__merge_pull_request` (merge_method: "merge") | `gh pr merge` |
| Push files | `mcp__github__push_files` | manual git add/commit/push |

**Fall back to `gh` CLI only for**: `gh pr checks --watch` (streaming), or operations not covered by MCP tools. Merge is available via `mcp__github__merge_pull_request` — always use it with `merge_method: "merge"` (never `squash`).

## Checkpoint Workflow (branch + PR + merge — NEVER direct push to main)

`main` auto-deploys to spelix.app. A broken push breaks production. For every meaningful checkpoint, work on a branch, open a PR, let CI run, then merge via `mcp__github__merge_pull_request` (merge method: `merge`). The main agent merges its own PR once CI is green.

**Meaningful checkpoints** (PR required): phase batch completion, FR-ID implementations with user-facing changes, schema migrations, bug fixes touching auth/coaching/upload/pipeline, dependency upgrades, infra changes, CI fixes.

**Not meaningful** (direct commit on current branch is fine): handoff notes, typo-only doc fixes, scratch commits during active development before the checkpoint.

**Workflow**: `git checkout -b <type>/<name>` → implement → local checks (`ruff`/`pyright`/`tsc`/`vitest`) → `git push -u origin <branch>` → create PR via `mcp__github__create_pull_request` → wait for CI → merge via `mcp__github__merge_pull_request` (merge method: `merge`, NOT `squash`) → `git checkout main && git pull` → wait for "Deploy to Production" CI step to finish → if user-facing, run E2E verification (next section).

**Merge rules**:
- **NEVER squash merge.** Use `merge_method: "merge"` always. Squash merges lose individual commit history and cause local/remote divergence that requires `git checkout -B main origin/main` to fix.
- **Use `mcp__github__merge_pull_request`** for all merges — not `gh pr merge` CLI.
- Never force-push to main. Never bypass CI. Never merge a PR with red CI.

## Post-Merge Deployment — WAIT for CI, NEVER SSH deploy manually

After merging to `main`, **"Deploy to Production" runs automatically as a CI step**. This deploys both the frontend (Vercel) and the backend (Docker rebuild on the droplet).

**STRICT RULE: Do NOT SSH into the droplet to run `docker compose up --build` or `git pull` manually after a merge.** The CI pipeline handles this. Manual deploys cause state divergence, race conditions with CI, and have burned time in session 26 when manual rebuilds used stale env vars.

**Procedure after merge**:
1. Check CI status via `mcp__github__get_pull_request_status` or `gh pr checks` — wait until ALL checks including "Deploy to Production" show `pass`
2. Verify the droplet is running the new code: `ssh spelix-droplet "git log --oneline -1"` — must match the merge commit
3. Verify containers are healthy: `ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"` — all should show `(healthy)`
4. Only THEN proceed to E2E verification

**The only exception for SSH deploy**: when CI's "Deploy to Production" step fails and you need to debug why. In that case, check CI logs first, diagnose, fix, and re-trigger — don't work around it.

## E2E Verification via Playwright MCP

After "Deploy to Production" CI step is green, verify the live flow with Playwright MCP BEFORE moving on. Verify on prod after any PR touching upload/pipeline/results/coaching/PDF/auth, API shapes, Phase MUST requirements, or production bugs. Skip for docs-only, CI-only, or prompt-only changes.

**Procedure**: wait for deploy → `browser_navigate` → `https://spelix.app` → `browser_snapshot` → walk affected flow → check `browser_console_messages` (level=error) + `browser_network_requests` (4xx/5xx). If broken: write to `.claude/handoff.md` and STOP. If green: record in handoff.

Test artifacts: `e2e/fixtures/` (video inputs), `e2e/screenshots/` (captures). `.playwright-mcp/` is gitignored.

## Droplet Debugging (SSH)

SSH in directly — never ask the user. See `backend/CLAUDE.md` "Droplet Debugging" for full command reference. SSH alias: `spelix-droplet`. Start with `ssh spelix-droplet "docker ps -a"`.

## Compaction Survival

Context budget: keep below 60% capacity. Watch the statusline.
At 60%: finish current task, run `/handoff`, start fresh session.
Use the Explore built-in subagent for file discovery — its reads stay out of main context.
When asked to summarize for compaction: preserve current phase, last 5 modified files, failing tests, current task.
After compaction: re-read `@docs/SRS.md` Section 3 for current phase requirements before resuming. Run `/status` to confirm environment state.

**Phase completion criterion**: All MUST requirements for the phase implemented + full test suite green + migration applied + specialist audit clean. Phase 1 passed 2026-04-10. Phase 2 passed 2026-04-14. Phase 3 + L2 sprint passed 2026-05-03. Current: **2225 backend tests, 746 frontend tests, 23 migrations applied** (head: `0906139da711`).

At the end of any session that didn't complete all planned batches, write a handoff note to `.claude/handoff.md` containing: (1) completed tasks with commit SHAs, (2) remaining tasks with backlog IDs, (3) current test count and any failures, (4) any blockers discovered.

## memory.md Update Protocol

After every session commit, update memory.md with:
```
phase: [current]
task: [current task ID]
status: [in_progress | blocked | escalated | done]
last_modified: [last 5 files modified]
failing_tests: [list or empty]
blockers: [list or empty]
next_action: "[specific next step — exact command or task]"
session_count: [increment by 1]
last_session: [today's date]
```

## decisions.md & backlog.md Update Protocol

`decisions.md` and `backlog.md` live at the **repo root** (not `.claude/`). They are project-owned across sessions and survive every Claude Code session — treat with the same discipline as `memory.md`. **Do NOT batch updates at end-of-session**; run inline with the code changes that triggered them. Session 13 batched and lost track of half the decisions; the cost was ~30 min of reconstruction from git log. You do NOT need user permission to invoke `/adr` or `/backlog` — they are part of normal session hygiene.

**Run `/adr`** when: a library choice is made; a design pattern adopted across >1 file; a constraint is added (file path, env var, runtime dep); a bugfix reveals a systemic design choice; a migration between approaches happens; a test pattern is adopted to prevent a bug class. If you'd write a `backend/CLAUDE.md` gotcha for it, you also need an ADR — gotchas explain symptoms, ADRs explain choices.

**Run `/backlog`** when: a task is completed (mark `done` + add squash-merge SHA); a new task is discovered mid-session; a task's scope changes (split/merge/blocked/deferred); a batch of work finishes (add `## Completed —` header); a new phase begins (seed from SRS Must filter).

**File ownership**: `decisions.md` is **append-only across phases** — old ADRs are NEVER edited; if a decision is reversed, write a new ADR that supersedes the old one by ID. `backlog.md` rows ARE edited in place (status, commits, scope). Both files commit alongside normal code changes — atomic with the PR that introduces the decision/closes the task, never as a follow-up cleanup PR.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- ALWAYS read graphify-out/GRAPH_REPORT.md before reading any source files, running grep/glob searches, or answering codebase questions. The graph is your primary map of the codebase.
- IF graphify-out/wiki/index.md EXISTS, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
