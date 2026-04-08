---
name: test
description: Run full test suite with coverage
---
Run the test suite:
1. `cd backend && uv run pytest --cov=app --cov-report=term-missing -x`
2. `cd frontend && npx vitest run --coverage`
3. Report any failures with file paths and line numbers.