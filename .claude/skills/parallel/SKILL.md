---
name: parallel
description: Dispatch parallel sub-agents with worktree isolation for independent tasks
argument-hint: "task-ids from backlog.md, e.g. B-071 B-072 B-073"
---

# Parallel Dispatch Protocol

## Pre-Flight Checklist — Run Before Every Dispatch

**Do not skip this. Every coordination failure traced back to skipping one of these steps.**

```bash
# 1. Sync main to HEAD
git fetch origin && git checkout main && git pull --ff-only

# 2. Audit stale worktrees from prior sessions and remove them
git worktree list
git worktree prune
# If stale entries remain: git worktree remove <path> --force

# 3. Confirm clean working tree — no uncommitted changes on main
git status

# 4. Record the commit SHA agents will branch from
git rev-parse HEAD   # paste this into the dispatch announcement
```

The `PreToolUse` hook in `settings.json` already fires a stale-branch warning
whenever `git worktree add` runs — treat any warning as a hard stop, not advice.

---

## When to Parallelize

Read `backlog.md` for tasks marked `todo` with all dependencies satisfied. Parallelize when:

1. Tasks write to **non-overlapping directory subtrees** — e.g., `backend/app/api/` vs `backend/app/cv/` vs `frontend/src/`
2. Tasks are **pure-function work** with no shared state — quality gates, confidence scoring, signal processing
3. Frontend and backend tasks that share no schema

## When NOT to Parallelize

- Any task touching `models/`, `schemas/`, or `alembic/` — one sequential agent owns these; others read the result
- Tasks with unsatisfied `Deps` entries in `backlog.md`
- More than **7 simultaneous agents** (Claude Code hard limit)
- More than **3 simultaneous agents on the DigitalOcean droplet** (2 GB RAM — MediaPipe peaks at ~350 MB)
- Any task that runs `alembic upgrade head` or modifies DB schema
- Tasks that need to read each other's output before completing

---

## Dispatch Procedure

1. **Read `backlog.md`** — identify the next batch of `todo` tasks with no unmet `Deps`.

2. **Run the Pre-Flight Checklist** above and confirm main is current.

3. **Announce the plan before spawning** — do not spawn silently:

```
Pre-flight: main is at <SHA>. Stale worktrees: none.

Dispatching Batch N — X background agents:
  Agent 1: B-0XX (<title>) → <files>
  Agent 2: B-0XX (<title>) → <files>
  Agent 3: B-0XX (<title>) → <files>

Monitor: /tasks to see progress. Shift+Up/Down to cycle agents.
```

4. **Spawn all agents in a single message** with multiple Agent tool calls so they launch simultaneously. Each call MUST include:

   - `run_in_background: true`
   - `isolation: "worktree"` — each agent gets its own branch and working directory
   - `description` field = task ID for `/tasks` display, e.g. `"B-071 repo refactor"`
   - Full task prompt from the **Agent Prompt Template** below

5. **After dispatching**, tell the user:

```
X agents dispatched. Monitor with:
  /tasks         — all agent status
  Shift+Up/Down  — cycle agent sessions
  Ctrl+T         — shared task list
  Enter          — expand selected agent output
  Escape         — interrupt a stuck agent
```

6. Main agent may continue independent work (updating docs, planning next batch) while agents run.

7. **When all agents complete**, main agent:
   - Reviews each worktree's changes and test output
   - Merges each branch into main
   - Runs `/check` then `/test`
   - Updates `backlog.md` (mark tasks `done`) and `memory.md`
   - Runs the **Post-Merge Checklist** below

---

## Agent Prompt Template

Every sub-agent receives this prompt verbatim — fill in the bracketed fields:

```
Read CLAUDE.md for project context. You are working in an isolated git worktree.

TASK: [task ID] — [title]
SRS REQUIREMENTS: [FR-IDs, or "none" if infra/config task]
FILES TO CREATE/MODIFY: [explicit list]
WORKING DIRECTORY SCOPE: [specific subtree, e.g. backend/app/cv/]

STRICT ISOLATION RULES (these are non-negotiable):
- Work ONLY inside your assigned worktree directory. Never read from or write to the
  main repo directory or any other agent's worktree.
- Never run `git push`, `git merge`, or `alembic upgrade head`.
- Never modify files/dirs not listed in FILES TO CREATE/MODIFY above.

INSTRUCTIONS:
1. Use Context7 MCP to look up current API docs before writing any library code.
2. Write the failing test FIRST (TDD). Place it in the matching tests/ path.
3. Implement until the test passes.
4. Verify:
   Backend:  uv run pytest [test file] -x
   Frontend: npx vitest run [test file]
5. If tests fail after implementation, diagnose, fix, and re-run — up to 3 iterations.
   On the 3rd failure, report the error and stop; do not commit broken code.
6. When the TDD gate passes, commit:
   git add [files]
   git commit -m "type(scope): short description"
   Types: feat fix test refactor chore docs
   Scopes: api cv auth models worker frontend admin config ci
   No co-authored-by. No emoji. No "Generated with Claude" footers.
7. Report: files created/modified, test counts, commit SHA, any blockers.

TDD GATE (must pass before committing): [specific test name or assertion criteria]
```

---

## Post-Merge Checklist

After merging all worktrees back to main:

```bash
# 1. Full lint + type check
/check

# 2. Full test suite
/test

# 3. Resolve any conflicts (rare with correct dispatch)
# 4. Update backlog.md — mark completed tasks done
# 5. Update .claude/handoff.md — log last_modified files, next task, current test count
# 6. Commit merged state
git commit -m "chore: merge batch N (B-0XX–B-0XX)"

# 7. Clean up worktrees
git worktree list                                           # identify completed
git worktree remove .claude/worktrees/agent-[id] --force  # repeat per agent
git worktree prune
```

---

## Batch Planning Reference

Phase 0 core (B-001–B-042) and all audit fixes (B-043–B-070) are complete.

**Active backlog** starts at B-071. Read `backlog.md` for current `todo` status and
`Deps` before planning any batch. The safe parallelization groups from `backlog.md`
are reproduced here for convenience — always verify against the live file first:

| Batch | Tasks | Safe to Parallelize | Notes |
|-------|-------|--------------------|----|
| Infra | B-074–B-078, B-080 | Yes — different files | Pin versions, .nvmrc, CI flags |
| Backend schemas | B-072, B-073 | Yes — same file, but no shared state | Can be one agent |
| Backend services | B-071 | Sequential after B-072/073 | Touches services/, repos |
| Frontend fixes | B-081–B-083 | Yes — different components | TrendChart, AdminPage, API constants |
| Tests batch 1 | B-084–B-089 | Yes — different test files | All under tests/unit/ |
| Tests batch 2 | B-090–B-092 | Yes — different test files | Frontend tests + datetime fix |
| Quality gates | B-093 | Yes — cv/ only | Lighting + stability gates |
| Docker | B-079 | Sequential after B-064, B-065 | Multi-stage Dockerfile |

**Future phases**: same protocol applies. Before each phase, append a new batch
table here with the phase's parallelizable task groups from the updated `backlog.md`.

---

## Known Failure Modes (from past sessions)

These have all caused wasted sessions — the checklist above prevents them:

- **Agents writing to main repo instead of worktrees** → prevented by `isolation: "worktree"` + explicit scope in prompt
- **Agents branching from stale commits** → prevented by pre-flight fetch + the `PreToolUse` hook warning on `git worktree add`
- **Agents committing broken code** → prevented by the 3-iteration self-fix gate in the prompt
- **Formatter stripping imports mid-session** → prevented by the `PostToolUse` ruff hook in `settings.json` + the Python import rule in `CLAUDE.md`
- **Context exhaustion mid-batch** → prevent by keeping batches to ≤7 agents and running `/handoff` before ending any session