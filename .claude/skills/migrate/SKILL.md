---
name: migrate
description: Create and review an Alembic migration
argument-hint: [description]
allowed-tools: Bash, Read, Write
---
1. Run: `cd backend && uv run alembic revision --autogenerate -m "$1"`
2. Read the generated migration file in `alembic/versions/`
3. Show me the upgrade() and downgrade() functions
4. Ask for confirmation before running `uv run alembic upgrade head`
5. After upgrade, verify with `uv run alembic current`
