---
description: Schema and migration rules
paths:
  - "backend/alembic/**"
  - "backend/app/models/**"
  - "backend/app/schemas/**"
---
# Migration & Schema Rules

- All JSONB (not JSON) for schema columns. Autogenerate emits JSON — correct it.
- No DDL FK to `auth.users` — enforce via RLS only (Supabase-managed schema).
- Status columns: VARCHAR(30) + CHECK constraint; required indexes per spelix-migration agent.
- **Apply migrations immediately**: run `uv run alembic upgrade head` in the same session the revision is written. Never let a revision sit unapplied.
- Always use the `spelix-migration` agent for Alembic/schema changes; it generates, never applies autonomously — the main agent applies after review.
- Never parallelise work in `backend/app/models/`, `backend/app/schemas/`, `backend/alembic/`.
