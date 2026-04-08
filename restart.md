# restart.md — Compaction Recovery

## Orientation Sequence

1. Read `CLAUDE.md` (repo root) — project context, stack, gotchas
2. Read `memory.md` — current task, blockers, failing tests
3. Read `backlog.md` — task statuses
4. Run `/status` — verify Docker, Redis, DB connectivity
5. Run `/check` — verify lint/type state
6. Resume the task listed in `memory.md → task`

## What Is This Project

Spelix is a barbell form coaching platform. Users upload squat/bench/deadlift videos → MediaPipe CV pipeline extracts pose + reps + metrics → Claude Sonnet generates coaching → results page. Phase 0 only — no RAG, no agents, no GPT-4o.

## Five Critical Gotchas (each burns a day if forgotten)

1. **Python 3.12 ONLY** — MediaPipe has no 3.13 wheels. Every Dockerfile, every venv, every CI runner must be 3.12. Check before any pip/uv install.

2. **MediaPipe config is EXACT** — `model_complexity=2, static_image_mode=True, min_detection_confidence=0.5, min_tracking_confidence=0.5, num_threads=1`. Any deviation breaks determinism guarantees. Config is in `backend/app/cv/pose_extraction.py`.

3. **Status transitions are STRICT** — Only valid transitions per SRS 5.2a table (see `backend/app/services/status.py`). Invalid transition = defect. Terminal states: completed, quality_gate_rejected, failed@retry=3.

4. **Supabase FK: NO DDL constraint to auth.users** — Enforce via RLS only. `user_id UUID NOT NULL` but no FOREIGN KEY. If you add an FK to auth.users, Supabase will reject the migration.

5. **Never use "injury risk" in UI** — User-facing label for `form_score_safety` is "Movement Quality". Applies to all user-facing strings, coaching prompts, component text. See Appendix B in SRS.

## Restore Working State

```bash
docker compose -f docker-compose.dev.yml up -d    # Redis
cd backend && uv run uvicorn app.main:app --reload # API (uses .venv)
cd frontend && npm run dev                         # UI
redis-cli ping                                     # Verify Redis
```

After restore, run `/mcp` to verify MCP servers are connected. If any show disconnected, check that shell env vars (`GITHUB_TOKEN`, `REDIS_URL`, `DATABASE_URL`, `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF`) are set.

## Key File Locations

- SRS (authoritative requirements): `docs/SRS.md`
- Thresholds config: `config/thresholds_v0.json`
- Models: `backend/app/models/`
- CV pipeline: `backend/app/cv/`
- Worker: `backend/app/workers/analysis_worker.py`
- Frontend pages: `frontend/src/pages/`
- This file: `restart.md`
- Agent state: `memory.md`
- Task list: `backlog.md`
- Decision log: `decisions.md`

## MCP Reminder

Context7 MCP is installed. Before writing code against ANY library for the first time, use Context7 `resolve` tool to get current docs. This is mandatory — stale API usage is a defect.
