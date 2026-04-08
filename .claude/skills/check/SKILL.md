---
name: check
description: Lint and type-check changed files
allowed-tools: Bash
---
1. `cd backend && uv run ruff check . && uv run pyright`
2. `cd frontend && npx tsc --noEmit && npx eslint src/`
3. Report all errors grouped by file.
