---
name: parallel
description: Dispatch parallel sub-agents with worktree isolation for independent tasks
argument-hint: [task-ids, e.g. "B-003 B-004 B-005"]
allowed-tools: Bash, Read, Agent, Task
isolation: worktree
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
2. For each parallelizable task, spawn a sub-agent with worktree isolation:

```
Use the Task tool to dispatch these tasks in parallel with worktree isolation:

Task 1: [task description from implementation plan]
- Working directory: [specific directory scope]
- Files to create/modify: [list]
- TDD gate: [test that must pass]
- SRS requirements: [FR-IDs]

Task 2: [same structure]
```

3. Each sub-agent:
   - Gets its own git worktree (auto-created)
   - Reads CLAUDE.md for project context
   - Uses Context7 MCP for library docs
   - Writes tests first (TDD), then implementation
   - Commits when TDD gate passes
4. Main agent waits for all sub-agents to complete
5. Main agent reviews each worktree's changes
6. Main agent merges results to main branch
7. Main agent updates `memory.md` and `backlog.md`

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
