---
name: test
description: Run full test suite with coverage
allowed-tools: Bash
---
Run the test suite:
1. `cd backend && python -m pytest --cov=app --cov-report=term-missing -x`
2. `cd frontend && npx vitest run --coverage`
3. Report any failures with file paths and line numbers.