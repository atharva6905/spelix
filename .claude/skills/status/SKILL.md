---
name: status
description: Show system health
allowed-tools: Bash
---
1. `docker compose ps` — show service states
2. `redis-cli -h localhost info keyspace` — show ARQ queue depth
3. `cd backend && python -c "from app.db import engine; from sqlalchemy import text; print(engine.connect().execute(text('SELECT 1')).scalar())"` — DB connectivity
4. Summarize health in a table.