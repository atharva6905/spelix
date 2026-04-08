---
name: parallel
description: Dispatch parallel sub-agents with worktree isolation for independent tasks
argument-hint: "task-ids, e.g. B-003 B-004 B-005"
---

# Parallel Dispatch Protocol

## When to Parallelize

Check `backlog.md` for tasks marked with no shared dependencies. Parallelize when:
1. Tasks write to **non-overlapping directories** (e.g., `backend/app/api/` vs `backend/app/cv/` vs `frontend/src/`)
2. Tasks are **pure functions** with no shared state (e.g., quality gates, confidence scoring)
3. Frontend and backend tasks run simultaneously

## When NOT to Parallelize

- Tasks touching `models/`, `schemas/`, or `alembic/` — one agent owns these
- Tasks with dependency arrows in the implementation plan
- More than 3 simultaneous agents on the 2GB droplet constraint (MediaPipe peak ~350MB RAM)
- Any task that runs `alembic upgrade head` or modifies DB schema

## Dispatch Procedure

1. Read `backlog.md` to identify the next batch of `todo` tasks with `Parallel: Yes` and no unmet dependencies
2. Announce the dispatch plan to the user before spawning:

```
Dispatching Block N — 3 background agents with worktree isolation:
  Agent A: B-0XX (title) → files
  Agent B: B-0XX (title) → files
  Agent C: B-0XX (title) → files

Monitor: /tasks to see progress. Shift+Up/Down to cycle agents.
I'll continue working on [sequential task or wait for results].
```

3. Spawn all agents **in a single message with multiple Agent tool calls** so they launch simultaneously. Each agent call MUST include:
   - `run_in_background: true` — agents run async, main agent stays free
   - `isolation: "worktree"` — each gets its own branch + directory
   - A `description` field with the task ID for easy identification in `/tasks` (e.g., `"B-003 status transitions"`)
   - Full task prompt (see Agent Prompt Template below)

4. After dispatching, the main agent tells the user:
```
3 agents dispatched in background. Use these to monitor:
  /tasks         — see all agent status + progress
  Shift+Up/Down  — cycle through agent sessions
  Ctrl+T         — shared task list
  Enter          — expand selected agent's full output
  Escape         — interrupt a stuck agent

I'll collect results when all agents complete.
```

5. Main agent can continue with independent work (e.g., updating docs, planning next block) while agents run in background.
6. When all agents complete (notification appears), main agent:
   - Reviews each worktree's changes
   - Merges each branch into main (squash or regular merge)
   - Runs `/check` + `/test`
   - Updates `memory.md` and `backlog.md`

## Agent Prompt Template

Each sub-agent receives this prompt:

```
Read CLAUDE.md for project context. You are working in an isolated worktree.

TASK: [task ID] — [title]
SRS REQUIREMENTS: [FR-IDs]
FILES TO CREATE/MODIFY: [list]
WORKING DIRECTORY SCOPE: [specific directory — do NOT touch files outside this scope]

INSTRUCTIONS:
1. Use Context7 MCP to look up current API docs for any library before writing code
2. Write failing test FIRST (TDD)
3. Implement until test passes
4. Run: uv run pytest [test file] -x  (backend) or npx vitest run [test file] (frontend)
5. When TDD gate passes, commit with conventional format:
   git add [files]
   git commit -m "feat(scope): short description"
   Scope = module name (cv, api, auth, models, frontend, worker, config)
   No co-authored-by. No emoji.
6. Report: files created, tests passed, any issues encountered

TDD GATE (must pass before committing): [specific test criteria]
```

## Parallel Dispatch Blocks (Phase 0)

These are the pre-planned parallel dispatch points from the implementation plan:

### Block 1 (after B-002):
- Agent A: B-003 (status transitions) → `backend/app/services/status.py`
- Agent B: B-004 (repositories) → `backend/app/repositories/`
- Agent C: B-005 (JWT auth) → `backend/app/api/deps.py`

### Block 2 (after B-001):
- Agent A: B-006 (RLS policies) → `backend/alembic/versions/`
- Agent B: B-007 (frontend auth) → `frontend/src/`

### Block 3 (Week 2):
- Agent A: B-012 (quality gates) → `backend/app/cv/quality_gates.py`
- Agent B: B-013 (upload page) → `frontend/src/pages/UploadPage.tsx`
- Agent C: B-014 (status page) → `frontend/src/pages/AnalysisStatusPage.tsx`

### Block 4 (Week 3):
- Agent A: B-016 (signal processing) → `backend/app/cv/signal_processing.py`
- Agent B: B-019 (confidence scoring) → `backend/app/cv/confidence.py`
- Agent C: B-020 (barbell detection) → `backend/app/cv/barbell_detection.py`

### Block 5 (Week 4):
- Agent A: B-023 (coaching service) → `backend/app/services/coaching.py`
- Agent B: B-025 (thresholds config) → `config/thresholds_v0.json`
- Agent C: B-026 (results page) → `frontend/src/pages/ResultsPage.tsx`

### Block 6 (Week 5):
- Agent A: B-033 (admin API) → `backend/app/api/v1/admin.py`
- Agent B: B-035 (PDF generation) → `backend/app/services/pdf.py`
- Agent C: B-036 + B-037 (CSV export + account deletion) → `backend/app/services/export.py`
- Agent D: B-038 (cleanup cron) → `backend/app/workers/cleanup.py`

## Post-Merge Checklist

After merging parallel worktrees back to main:
1. Run `/check` — full lint + type check
2. Run `/test` — full test suite
3. Resolve any conflicts (should be rare if dispatch was correct)
4. Update `backlog.md` — mark completed tasks as `done`
5. Update `memory.md` — log last_modified files, next task
6. Commit merged state to main