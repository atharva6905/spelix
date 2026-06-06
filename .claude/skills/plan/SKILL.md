---
name: plan
description: Structured Explore → Plan → Execute workflow for any task touching 3+ files or requiring architectural decisions. Enforces Plan Mode separation before implementation.
argument-hint: "task ID or description, e.g. B-093 or 'implement SSE streaming'"
context: fork
---

# Explore → Plan → Execute

This command runs the three-phase workflow that prevents "solving the wrong problem."
Never skip directly to implementation on multi-file or architecturally complex tasks.

## When to use /plan

Use /plan for:
- Any task touching 3+ files
- Any task with an SRS requirement ID
- Any new subsystem or integration (new library, new API, new service)
- Any task where the approach is uncertain

Skip /plan for:
- Single-file fixes under ~20 lines
- Bug fixes where the failing test already defines the scope exactly
- Tasks where the diff could be described in one sentence

---

## Phase 1: Explore (Plan Mode — read-only)

Enter Plan Mode. Claude reads files without making changes.

Read exactly the files relevant to this task. Use the Explore built-in subagent for
file discovery — its reads stay out of main context.

Answer these questions before moving to Phase 2:
1. What files will change?
2. What tests need to be written or modified?
3. Which SRS requirement IDs apply? Read them in docs/SRS.md.
4. Which CLAUDE.md Gotchas apply to this task?
5. Will this require a new ADR? (If yes, run /adr before implementing)

Do NOT read files that aren't needed. Context is the most constrained resource.

---

## Phase 2: Plan

Still in Plan Mode. Produce a structured plan:

```
## Implementation Plan: [task ID or title]

### Files to change
- `path/to/file.py` — [what changes and why]
- `tests/unit/test_X.py` — [TDD gate description]

### Approach
[2-4 sentences: the implementation strategy and key design decisions]

### TDD gate
Test name: [test_function_name]
Assertion: [specific assertion that constitutes passing]

### Risks / gotchas that apply
[From CLAUDE.md Gotchas, or any uncertainty in approach]

### ADR needed?
[Yes — /adr [decision title] | No]

### Scope
[S = 1-2 files <50 lines | M = 3-5 files | L = 5+ files / new subsystem]
```

Press Ctrl+G to open the plan in the editor. Edit if needed. Confirm before proceeding.

---

## Phase 3: Execute

Switch to Normal Mode.

1. Write the failing test first. Confirm it fails for the right reason, not an import error.
2. Implement the minimal code to make it pass.
3. Run: `uv run pytest tests/unit/test_{file}.py -x` (backend)
   or `cd frontend && npx vitest run src/{path}.test.tsx` (frontend)
4. If failing after 3 fix iterations: write to `.claude/escalation.md` and stop.
5. Run full suite: `uv run pytest --cov=app -x` (backend) and `npx vitest run` (frontend)
6. Run /check — lint + type check must be clean.
7. Commit: `git commit -m "type(scope): description"`

For tasks dispatched to a named specialist agent: use /plan for Phases 1-2 in main
context, then hand the approved plan to the agent for Phase 3 only.

---

## Post-Execute (always)

1. Archive the closed Issue's entry in backlog.md (with merge SHA)
2. Update `.claude/handoff.md`: `next_action`, `last_modified`, current test count
3. If new architectural decision made: run /adr
4. If a new gotcha was discovered (a bug that cost >30 min): add to CLAUDE.md Gotchas

---

## Context Management

Watch the statusline. Keep context below 60% capacity.
If exploration is generating large tool outputs, use the Explore subagent — its
results stay in its own context.
At 60% context: finish current task, run /handoff, start fresh session.
