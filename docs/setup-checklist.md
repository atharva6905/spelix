# Claude Code Setup Checklist — Spelix Phase 0

Complete every step in order. Do not write application code until all checks pass.

---

## 1. Environment Verification

```bash
# Python — MUST be 3.12.x (MediaPipe has no 3.13 wheels)
python3 --version   # expect: Python 3.12.x

# Node.js — MUST be 22.x (Vite 8 requires 20.19+ or 22.12+)
node --version      # expect: v22.x.x

# uv — Python package manager
uv --version

# Docker Compose
docker compose version   # expect: v2.x

# Redis CLI (for local testing)
redis-cli --version
```

If any version is wrong, fix it before proceeding. Create `.python-version` with `3.12` and `.nvmrc` with `22`.

### 1a. Install Global Dev Tools

Ruff and pyright must be globally available because Claude Code hooks call them directly on every file write (not through `uv run`). Slash commands use `uv run` instead, but hooks need global access.

```bash
# Install ruff and pyright globally (hooks need these on PATH)
uv tool install ruff
uv tool install pyright

# Verify they're on PATH
ruff --version
pyright --version
```

## 2. Verify Claude Code Configuration

```bash
# Check model
# Should be claude-opus-4-6 (set in .claude/settings.local.json)

# Check sub-agent model
echo $CLAUDE_CODE_SUBAGENT_MODEL   # expect: claude-sonnet-4-6
```

### 2a. Verify Hooks Fire

Create a throwaway Python file, write it, confirm you see:
- "Running ruff check --fix..." on Write
- "Running pyright..." on Write

Create a throwaway .tsx file, write it, confirm you see:
- "Running tsc --noEmit..." on Write

Delete both files.

### 2b. Verify Slash Commands

Run each, confirm no errors:
- `/status` — will fail (no Docker yet), but should attempt the commands
- `/check` — will fail (no code yet), but should run
- `/test` — will fail (no tests yet), but should attempt pytest + vitest

### 2c. GSD Hooks Awareness

The local PC has GSD framework hooks (SessionStart, PostToolUse, PreToolUse). These are additive to project hooks. Potential conflicts:
- `gsd-prompt-guard.js` and `gsd-read-guard.js` run on PreToolUse Write|Edit — may warn on first writes to new files. This is expected, not a blocker.
- `gsd-context-monitor.js` runs on PostToolUse — monitors context size. May suggest compaction. Follow its guidance.
- `gsd-workflow-guard.js` — may enforce workflow patterns. If it blocks a legitimate write, note in `.claude/handoff.md`.

### 2d. MCP Servers (auto-connect via .mcp.json)

MCPs are configured in `.mcp.json` at the repo root. Claude Code auto-connects them at every session start — no `claude mcp add` needed. The file is version-controlled so every session gets the same MCPs.

**Copy `.mcp.json` to the repo root** (provided as a deliverable). It configures all 6 servers with Windows `cmd /c` wrappers for npx.

**Required env vars** (set in your shell profile, NOT in `.env` — MCPs read from your shell environment):

```powershell
# PowerShell $PROFILE (or bash equivalent)

# GitHub — create a PAT at https://github.com/settings/tokens (repo scope)
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"

# Redis — works once Docker Compose is up
$env:REDIS_URL = "redis://localhost:6379/0"

# Supabase — get from https://supabase.com/dashboard/account/tokens
# Set AFTER creating the Supabase project (step 3)
$env:SUPABASE_ACCESS_TOKEN = "sbp_xxxxxxxxxxxx"
$env:SUPABASE_PROJECT_REF = "xxxxxxxxxxxx"  # from project URL: supabase.com/dashboard/project/<this>

# PostgreSQL — same connection string as DATABASE_URL
$env:DATABASE_URL = "postgresql://postgres.xxxxx:password@aws-0-region.pooler.supabase.com:6543/postgres"
```

**Availability timeline:**
| MCP | Available when | Env vars needed |
|-----|---------------|-----------------|
| Context7 | Immediately | None |
| Playwright | Immediately | None |
| GitHub | Immediately | `GITHUB_TOKEN` |
| Redis | After step 7 (Docker up) | `REDIS_URL` |
| Supabase | After step 3 (project created) | `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF` |
| PostgreSQL | After step 3 (project created) | `DATABASE_URL` |

MCPs with missing env vars show errors at session start but don't block other MCPs. They auto-connect once vars are set and Claude Code is restarted.

**Verify after restart:**
```
/mcp
```
Should show connected servers. Re-run after each new env var is set.

**Context7 usage protocol — MANDATORY:**

Before writing code that uses any library, the agent MUST query Context7 for current documentation. This prevents writing code against stale APIs (e.g., Vite 8's Rolldown config, Tailwind v4's CSS-first @theme, SQLAlchemy 2.0's select() API, shadcn/ui v4 changes).

Libraries that MUST be looked up via Context7 before first use:
- FastAPI, SQLAlchemy 2.0, Alembic (async env.py), ARQ, MediaPipe
- Supabase-py, @supabase/supabase-js v2 (Realtime channel API)
- React 19, Vite 8, Tailwind CSS 4, shadcn/ui v4
- Recharts, React Router v6, instructor (Pydantic v2)

This is not optional — it's the primary defense against stale training data.


## 3. Create Supabase Project

**This must happen before any backend code.**

1. Go to https://supabase.com → New Project
2. Name: `spelix`
3. Region: closest to you (US East or Canada)
4. Generate a strong DB password — save it
5. Wait for project to provision (~2 minutes)

Collect these values and add to `.env` (gitignored):
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...  # NEVER in frontend
SUPABASE_JWT_SECRET=super-secret-jwt-token-...
DATABASE_URL=postgresql+asyncpg://postgres.xxxxx:password@aws-0-region.pooler.supabase.com:6543/postgres
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...
```

**Also set MCP env vars in your shell** (MCPs read from shell, not `.env`):
```powershell
# Add to PowerShell $PROFILE (or .bashrc on Linux/Mac)
$env:SUPABASE_ACCESS_TOKEN = "sbp_..."     # from supabase.com/dashboard/account/tokens
$env:SUPABASE_PROJECT_REF = "xxxxxxxxxxxx" # from project URL
$env:DATABASE_URL = "postgresql://..."      # same as above but WITHOUT +asyncpg prefix
$env:GITHUB_TOKEN = "ghp_..."              # from github.com/settings/tokens
$env:REDIS_URL = "redis://localhost:6379/0"
```
Then restart Claude Code so MCPs pick up the new vars.

### 3a. Enable Supabase Features

In Supabase Dashboard:
- [ ] Auth → Providers → Enable Email/Password
- [ ] Auth → Providers → Enable Google OAuth (configure later)
- [ ] Storage → Create bucket `videos` (private)
- [ ] Storage → Create bucket `artifacts` (private)
- [ ] Realtime → Confirm enabled (on by default)

### 3b. Configure Supabase Auth

- Auth → URL Configuration → Site URL: `https://spelix.app`
- Auth → URL Configuration → Redirect URLs: add `http://localhost:5173` for dev

## 4. Repository Structure Scaffold

Run from repo root:

```bash
# Backend
mkdir -p backend/app/{api/v1,services,repositories,cv,workers,models,schemas}
mkdir -p backend/tests/{unit,integration,e2e,fixtures}
mkdir -p backend/alembic
touch backend/app/__init__.py
touch backend/app/api/__init__.py
touch backend/app/api/v1/__init__.py
touch backend/app/services/__init__.py
touch backend/app/repositories/__init__.py
touch backend/app/cv/__init__.py
touch backend/app/workers/__init__.py
touch backend/app/models/__init__.py
touch backend/app/schemas/__init__.py
touch backend/tests/__init__.py
touch backend/tests/unit/__init__.py
touch backend/tests/integration/__init__.py
touch backend/tests/e2e/__init__.py

# Frontend
mkdir -p frontend/src/{components,pages,hooks,api,lib}
touch frontend/src/vite-env.d.ts

# Config and reports
mkdir -p config
mkdir -p reports/templates

# Agent files
touch backlog.md restart.md decisions.md
```

## 5. Backend Dependency Setup

**How uv manages the virtual environment:**
- `uv init` creates `backend/.venv/` automatically — no manual `python -m venv` needed.
- All `uv add` / `uv run` commands use this `.venv` implicitly.
- Claude Code hooks (ruff, pyright) and pytest need packages importable locally, which is why we use a local venv rather than Docker-only deps.
- The `.venv/` directory is gitignored (already in `.gitignore` as `.venv`).
- To run any backend command, either `cd backend && uv run <cmd>` (auto-activates) or activate manually with `source backend/.venv/bin/activate` (Windows: `backend\.venv\Scripts\activate`).

```bash
cd backend

# Create pyproject.toml + .venv (auto-created by uv init)
uv init --python 3.12 --name spelix-backend

# Verify .venv was created
ls -la .venv/   # should exist with bin/python pointing to 3.12

# Install core dependencies (into .venv automatically)
uv add fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic arq redis
uv add mediapipe opencv-python-headless instructor anthropic
uv add weasyprint slowapi pydantic httpx python-jose[cryptography]
uv add supabase python-multipart scipy matplotlib numpy

# Dev dependencies (also into .venv)
uv add --dev pytest pytest-asyncio pytest-cov ruff pyright httpx

# Verify packages installed correctly
uv run python -c "import fastapi; import mediapipe; print('OK')"

# Generate pinned requirements.txt for Docker production image
uv pip compile pyproject.toml -o requirements.txt
```

**Important for Claude Code agent**: When running backend commands directly (not via `uv run`), ensure the venv is activated or use `uv run` as prefix. Examples:
- `uv run pytest tests/unit/ -x` — runs pytest inside .venv
- `uv run uvicorn app.main:app --reload` — runs server inside .venv
- `uv run alembic upgrade head` — runs migration inside .venv
- `uv run ruff check .` — runs linter inside .venv (hooks do this automatically)

## 6. Frontend Setup

```bash
cd frontend

# Create Vite project (React + TypeScript + SWC)
npm create vite@latest . -- --template react-swc-ts

# Install dependencies
npm install @supabase/supabase-js react-router recharts
npm install -D tailwindcss @tailwindcss/vite
npm install openapi-typescript

# shadcn/ui init (uses Tailwind v4)
npx shadcn@latest init
```

Create `.nvmrc`:
```
22
```

## 7. Docker Compose Dev Setup

Create `docker-compose.dev.yml` with:
- `redis`: redis:7-alpine, port 6379
- No Postgres (using Supabase cloud)
- No backend/frontend containers for dev (run locally)

## 8. Alembic Init

```bash
cd backend
uv run alembic init alembic

# Edit alembic.ini: sqlalchemy.url = (leave empty, set via env)
# Edit alembic/env.py: import models, configure async engine from DATABASE_URL
```

## 9. Create .env.example

```bash
# Copy from .env but with placeholder values
# NEVER commit actual secrets
```

## 10. Verify Full Stack Boots

```bash
# Terminal 1: Redis
docker compose -f docker-compose.dev.yml up -d

# Terminal 2: Backend (uv run activates .venv automatically)
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Terminal 3: Frontend
cd frontend && npm run dev

# Verify:
# - http://localhost:8000/docs shows FastAPI OpenAPI
# - http://localhost:5173 shows React app
# - redis-cli ping returns PONG
```

## 11. Initial Commit

```bash
git add -A
git status  # review — no secrets, no .env
git commit -m "chore: scaffold project structure and dependencies"
```

## 12. Update Agent Files

- Write initial `memory.md`
- Write initial `backlog.md` with all Phase 0 tasks
- Write `restart.md`
- Write `decisions.md` with pre-existing ADRs
- Commit agent files

---

**Setup is complete when:**
- [ ] Python 3.12 and Node 22 verified
- [ ] Hooks fire correctly on .py and .tsx writes
- [ ] Supabase project created with auth + storage + realtime enabled
- [ ] Repo structure scaffolded with all directories
- [ ] Backend deps installed via uv
- [ ] Frontend created with Vite 8 + React 19 + Tailwind 4
- [ ] Redis running via Docker Compose
- [ ] FastAPI boots and serves /docs
- [ ] Frontend boots and renders
- [ ] Agent files committed
