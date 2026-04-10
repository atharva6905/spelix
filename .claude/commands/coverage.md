---
name: coverage
description: Coverage-driven test generation to reach threshold
---
Run `cd backend && uv run pytest --cov=app --cov-report=term-missing` and analyze output. Goal: 95% line coverage.

1. Rank files by uncovered lines (descending).
2. For each of the top 10: read source, identify untested branches, write focused tests in the matching test file. Each test targets specific uncovered lines.
3. Run suite after each file — fix any failures before moving to next.
4. Re-run coverage and report delta.
5. Repeat until 95% or all meaningful branches covered.

Dispatch sub-agents for independent modules. Skip config files and type stubs. Produce before/after coverage delta per file.