# Spelix

Science-based barbell form coaching platform. Users upload squat/bench/deadlift videos → CV pipeline extracts pose + reps + metrics → AI generates structured coaching feedback. Private web app at spelix.app.

**Current phase: Phase 1 COMPLETE → Phase 2 PLANNING** — Phase 0 complete (93 items, B-001–B-093). Phase 1 complete (44 items, B-094–B-137) delivered: GPT-4o keyframe analysis, 4-dimension scoring + composite, SSE streaming coaching, Tier 1–5 confidence, ThresholdConfig v1, prompt caching, exercise auto-detection with GPT-4o fallback, full Phase 1 PDF report, per-rep metrics (eccentric/lockout/phase of max dev/consistency). Phase 2 delivers: RAG (Qdrant dual-collection, Cohere embed-v4 + Rerank 4.0), document ingestion (Docling), hybrid retrieval (dense+BM25+RRF), citation-grounded coaching, CoVe verification, follow-up chat, Coach Brain foundation (seed corpus 50–100 entries, contextual embedding pipeline, cold-start fallback), GDPR Article 9 health data consent flow, consent withdrawal handling (FR-BRAIN-16), per-analysis eval scores (RAGAS/HHEM), DPIA, retrieval metrics logging. SRS v2.1 (north star — set in stone).

Authoritative requirements: `@docs/SRS.md`. Phase-specific architecture: `backend/CLAUDE.md` + `frontend/CLAUDE.md`. Decisions: `decisions.md`. Task list: `backlog.md`.

Greenfield build — no migration from WorkoutFormAnalyzer. Alembic starts at migration 001.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 + Alembic, ARQ + Redis, MediaPipe BlazePose Heavy, OpenCV headless, WeasyPrint. See `backend/CLAUDE.md`.
- **Database**: Supabase Postgres (public schema only; auth schema is Supabase-managed)
- **Storage/Auth/Realtime**: Supabase (Storage for artifacts, Auth for JWT, Realtime for status push)
- **AI (Phase 1)**: Claude Sonnet 4.6 (`claude-sonnet-4-6`) for coaching with prompt caching; OpenAI GPT-4o (`gpt-4o`) for keyframe analysis + exercise auto-detect fallback
- **Frontend**: React 19, Vite 8, TypeScript strict, Tailwind CSS 4, shadcn/ui, Recharts. See `frontend/CLAUDE.md`.
- **Infra**: DigitalOcean 2GB droplet behind Caddy, Vercel for frontend, Qdrant Cloud (Phase 2+)

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

**Active agents (Phase 1+, still needed for Phase 2):**
- `spelix-cv-engineer` — all tasks in `backend/app/cv/`
- `spelix-coaching-engineer` — coaching service, SSE, LLM prompt work

**Active agents (Phase 2):**
- `spelix-rag-engineer` — Qdrant, Cohere embed/rerank, hybrid retrieval, ingestion
- `spelix-corpus-curator` — research document ingestion, metadata, citation provenance

**Activate at Phase 3:** `spelix-langgraph-engineer`
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

`/team` cost rules: Sonnet for all teammates, max 3 teammates, focused spawn prompts (CLAUDE.md loads automatically — don't repeat it), shut down when done.

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

## Checkpoint Workflow (branch + PR + merge — NEVER direct push to main)

`main` auto-deploys to spelix.app. A broken push breaks production. For every meaningful checkpoint, work on a branch, open a PR, let CI run, then merge via `gh pr merge --squash --delete-branch`. The main agent merges its own PR once CI is green.

**Meaningful checkpoints** (PR required): phase batch completion, FR-ID implementations with user-facing changes, schema migrations, bug fixes touching auth/coaching/upload/pipeline, dependency upgrades, infra changes, CI fixes.

**Not meaningful** (direct commit on current branch is fine): handoff notes, typo-only doc fixes, scratch commits during active development before the checkpoint.

**Workflow**: `git checkout -b <type>/<name>` → implement → local checks (`ruff`/`pyright`/`tsc`/`vitest`) → `git push -u origin <branch>` → `gh pr create` → wait for CI → `gh pr merge --squash --delete-branch` → `git checkout main && git pull` → if user-facing, run E2E verification (next section).

**Never force-push to main. Never bypass CI. Never merge a PR with red CI.**

## E2E Verification via Playwright MCP

After any meaningful production feature lands on `main` and auto-deploys to **spelix.app**, verify the live flow end-to-end with the Playwright MCP browser tools BEFORE moving on. "Unit tests pass" ≠ "works in production" — prod has different env vars, different Supabase project, different everything.

**Verify on prod after merging any PR that**: touches upload/pipeline/results/coaching/PDF/auth flows, changes API response shapes, adds or modifies a Phase MUST requirement, or fixes a production bug. Also periodically at phase gates.

**Skip verification for**: docs-only changes, CI fixes that don't change runtime behavior, agent prompt edits, commits not touching `backend/app/`, `frontend/src/`, or migrations.

**Procedure**:
1. Wait ~1–2 min after merge for Vercel deploy to settle
2. `mcp__playwright__browser_navigate` → `https://spelix.app`
3. `mcp__playwright__browser_snapshot` to capture accessibility tree
4. Walk the affected flow: click/fill/type/wait through login → upload → status → results → download
5. At the end: `browser_console_messages` (level=error) + `browser_network_requests` (filter for 4xx/5xx)
6. **If broken**: write findings to `.claude/handoff.md` under a new "E2E Findings" section and STOP — do not continue until fixed
7. **If green**: record verification as a bullet in the handoff and move on

Authenticated flows use persistent cookies from the browse daemon. Never verify on localhost when prod is the question.

**Test artifacts live in `e2e/`** — `e2e/fixtures/` holds video inputs (e.g. `squat-high-bar.mp4`) attached via `browser_file_upload` with an absolute path; `e2e/screenshots/` holds PNG captures from runs. The noisy auto-generated `.playwright-mcp/` folder (accessibility snapshots, console logs, network dumps) is gitignored — reference those files from handoff notes only. See `e2e/README.md`.

## Droplet Debugging (SSH)
 
**When any droplet debugging is needed: SSH in directly. Never ask the user to run commands on the droplet — do it yourself.**
 
Start every debugging session with `ssh spelix-droplet "docker ps -a"` to confirm connectivity and container state before running anything else. If SSH fails, report the error and stop — do not ask the user to run it instead.
 
Claude Code connects directly to the droplet via SSH using a dedicated key. No DO MCP — not configured, not needed.
 
**SSH alias**: `spelix-droplet` (configured in `~/.ssh/config` with `IdentityFile ~/.ssh/claude_spelix`).
 
**Verify access**:
```bash
ssh spelix-droplet "echo ok && whoami"
```
 
**Common debugging commands**:
```bash
# Container status
ssh spelix-droplet "docker ps -a"
 
# Live backend logs (last 100 lines + follow)
ssh spelix-droplet "docker logs spelix-backend --tail 100 -f"
 
# Worker logs
ssh spelix-droplet "docker logs spelix-worker --tail 100 -f"
 
# Caddy access/error logs
ssh spelix-droplet "docker logs spelix-caddy --tail 50"
 
# ARQ queue depth
ssh spelix-droplet "docker exec spelix-redis redis-cli llen arq:queue"
 
# Restart a container
ssh spelix-droplet "docker restart spelix-backend"
 
# Run a one-off command inside the backend container
ssh spelix-droplet "docker exec spelix-backend <cmd>"
```
 
**Key management**: The private key is `~/.ssh/claude_spelix` on the local machine. The public key is in `~deploy/.ssh/authorized_keys` on the droplet. 

## Compaction Survival

Context budget: keep below 60% capacity. Watch the statusline.
At 60%: finish current task, run `/handoff`, start fresh session.
Use the Explore built-in subagent for file discovery — its reads stay out of main context.
When asked to summarize for compaction: preserve current phase, last 5 modified files, failing tests, current task.
After compaction: re-read `@docs/SRS.md` Section 3 for current phase requirements before resuming. Run `/status` to confirm environment state.

**Phase completion criterion**: All MUST requirements for the phase implemented + full test suite green + migration applied + specialist audit clean. Phase 1 passed 2026-04-10 (895 backend tests, 177 frontend, 91% coverage, migration 003 applied).

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
