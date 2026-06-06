---
name: status
description: >
  Load live environment state at session start, or any time the user asks
  for current project status, environment check, or "where are we".
  Run automatically when starting a new session.
effort: low
---

## Spelix — Live Environment State

Git:
- Branch: !`git branch --show-current`
- Last commit: !`git log --oneline -1`
- Dirty files: !`git status --short | head -10`

Database:
- Alembic head: !`cd backend && uv run alembic current 2>/dev/null | tail -1`
- Pending migrations: !`cd backend && uv run alembic heads 2>/dev/null`

Workers:
- Redis: !`docker compose exec redis redis-cli ping 2>/dev/null || echo "OFFLINE"`
- streaq queue depth: !`docker compose exec redis redis-cli llen streaq:queue 2>/dev/null`

Tests (last run):
- !`cd backend && cat .pytest_cache/v/cache/lastfailed 2>/dev/null || echo "No failures cached"`
- Count: !`cd backend && uv run pytest tests/ --co -q 2>/dev/null | tail -1`

Session context:
- Handoff note: !`cat .claude/handoff.md 2>/dev/null | head -20 || echo "No handoff note"`
- Current backlog: !`grep -E "^\- \[ \]" backlog.md 2>/dev/null | head -10 || echo "Check backlog.md"`