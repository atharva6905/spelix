---
name: check
description: Lint and type-check changed files
allowed-tools: Bash
---
1. `cd backend && ruff check . && pyright`
2. `cd frontend && npx tsc --noEmit && npx eslint src/`
3. Report all errors grouped by file.