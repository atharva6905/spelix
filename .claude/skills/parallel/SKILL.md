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
- More than 7 simultaneous agents (Claude Code hard limit)
- Any task that runs `alembic upgrade head` or modifies DB schema

## Dispatch Procedure

1. Read `backlog.md` to identify the next batch of `todo` tasks with no unmet dependencies
2. Announce the dispatch plan to the user before spawning:

```
Dispatching Batch N — X background agents with worktree isolation:
  Agent 1: B-0XX (title) → files
  Agent 2: B-0XX (title) → files
  ...

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
X agents dispatched in background. Use these to monitor:
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

## Block Reference (Phase 0)

Blocks 1-3 are complete. Blocks 4-9 map to Prompt A and Prompt B sessions.

| Block | After | Tasks | Agents | Status |
|-------|-------|-------|--------|--------|
| 1 | B-002 | B-003, B-004, B-005 | 3 | ✅ DONE |
| 2 | B-002 | B-006, B-007 | 2 | ✅ DONE |
| 3 | B-014 | B-012, B-013, B-014 | 3 | ✅ DONE |
| 4 | B-014 | B-015, B-016, B-019, B-020, B-023+025, B-027+028+029, B-033 | 7 | Prompt A Batch 1 |
| 5 | Block 4 | B-017, B-026, B-034, B-036, B-037, B-038, B-039 | 7 | Prompt A Batch 2 |
| 6 | Block 5 | B-018, B-040 | 2 | Prompt A Batch 3 |
| 7 | Block 6 | B-021 → B-022 → B-024 (sequential) | 1 | Prompt B Steps 1-3 |
| 8 | Block 7 | B-030, B-035, B-032 | 3 | Prompt B Step 4 |
| 9 | Block 8 | B-031 → B-041 → B-042 (sequential) | 1 | Prompt B Steps 5-7 |

## Post-Merge Checklist

After merging parallel worktrees back to main:
1. Run `/check` — full lint + type check
2. Run `/test` — full test suite
3. Resolve any conflicts (should be rare if dispatch was correct)
4. Update `backlog.md` — mark completed tasks as `done`
5. Update `memory.md` — log last_modified files, next task
6. Commit merged state to main