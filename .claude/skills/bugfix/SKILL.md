---
name: bugfix
description: Autonomous diagnose-fix-verify loop for failing tests
context: fork
---
You are in autonomous bug-fix mode.

**REQUIRED SUB-SKILL:** invoke `superpowers:systematic-debugging` via the Skill tool
before proposing ANY fix. Its four phases are binding — no "just try this" changes.
Spelix overrides (take precedence over the skill's defaults):
1. Phase 1 evidence commands: backend `cd backend && uv run pytest -x` (exclude
   `tests/unit/test_pose_extraction.py` locally — Windows crash, CI is the gate);
   frontend `cd frontend && npx vitest run`.
2. Phase 4 fix is TDD: write the failing test reproducing the bug first
   (`superpowers:test-driven-development`), then the minimal fix.
3. Max 3 fix iterations per root cause (= the skill's Phase 4.5 stop). After 3, STOP
   and emit the structured blocker report from /implement Step 4 — do not try harder.
4. Once green, commit `fix(scope): concise description`.

Start by running the full suite. Group related failures — one root cause may explain
many. Fix in order: models → services → api → frontend.
Report: | Bug | Root Cause | Evidence | Files Changed | Iterations | Status |
