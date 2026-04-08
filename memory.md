# memory.md — Agent Persistent State

phase: 0
task: B-002
status: blocked
last_modified: [docker-compose.dev.yml, backend/pyproject.toml, backend/app/main.py, frontend/package.json, frontend/vite.config.ts]
failing_tests: []
blockers: [supabase_project_not_created, droplet_not_provisioned]
srs_deviations: []
next_action: "Create Supabase project manually, then start B-002 (SQLAlchemy models + migration 001)"
session_count: 1
last_session: 2026-04-08

## decisions_since_plan
- ADR-015: openapi-typescript deferred to B-040 — TypeScript 6 peer dep conflict with current version. Will resolve when openapi-typescript releases TS6 support.
- Vite 8 `create-vite` scaffold defaulted to vanilla TS template; manually added React 19 + SWC plugin + types.
- Tailwind CSS v4 installed (not v3 as in CLAUDE.md stack section) — v4 uses `@import "tailwindcss"` and `@tailwindcss/vite` plugin.

## notes
- B-001 complete: all TDD gates pass (Redis PONG, /health 200, frontend builds)
- Python 3.12.10 available via `py -3.12`, default Python is 3.13.1
- uv init auto-creates .venv with Python 3.12
- Docker Desktop must be started manually on this machine
- GSD hooks active — read-before-edit guard fires on Write/Edit
- Supabase project must be created before B-002
- DO droplet deferred — dev runs locally against Supabase cloud
