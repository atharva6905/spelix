---
name: bugfix
description: Autonomous diagnose-fix-verify loop for failing tests
context: fork
---
You are in autonomous bug-fix mode. For each failure:

1. DIAGNOSE: Read the failing test output. Grep relevant code paths. State root cause in 2 sentences.
2. FIX: Apply the minimal change. Do not refactor unrelated code.
3. VERIFY: Run `cd backend && uv run pytest -x` (backend) or `cd frontend && npx vitest run` (frontend). If still failing, return to step 1 with new output. Max 3 iterations.
4. COMMIT: Once green, commit: `fix(scope): concise description`

Start by running the full suite. Group related failures. Fix in order: models → services → api → frontend. Report a summary table: | Bug | Root Cause | Files Changed | Iterations | Status |