---
name: backlog
description: Add, update, or close items in backlog.md. Run whenever a task is completed, a new task is discovered, or a status changes. The backlog is the single source of truth for "what's left" — keep it accurate so future sessions don't have to reconstruct context from git log.
argument-hint: "operation, e.g. 'add P2-031: post-deploy smoke check' or 'close B-149c with commit 7bf8361'"
effort: low
---

# Backlog Update — Capture

Run this command whenever the work-in-progress changes. The backlog is the project's
authoritative task list, complementing the ADR log (architectural decisions) and the
handoff file (session-to-session state).

**File location**: `backlog.md` at the **repo root**, not `docs/backlog.md`.

## When to run /backlog

Run /backlog for:
- A backlog item is completed → add commit SHA + change status to `done`
- A new task is discovered mid-session that won't ship in the current PR → add as a new row
- A task's scope changes (split, merge, blocked, deferred) → update its row
- A new section is needed for a phase, sub-phase, or category of work
- An entire batch of tasks completes → add a "Completed — [section]" header above them

Do NOT run /backlog for:
- Trivial in-session todos (use the TaskCreate tool instead)
- Scratch notes that won't survive the session
- Tasks already represented in `docs/SRS.md` MUST tables (those are auto-generated
  via the rg filter at phase start, not hand-tracked)

---

## Backlog Format

The backlog uses GitHub-flavored Markdown tables, one per section. Match the existing
columns exactly so the file stays parseable:

```markdown
| ID | Title | Status | Size | Deps | SRS IDs | Commit | Files |
|----|-------|--------|------|------|---------|--------|-------|
| B-XXX | [imperative title] | done\|in_progress\|pending\|blocked | S\|M\|L\|XL | [comma-separated IDs or —] | [FR-IDs or —] | `[short SHA]` | [paths or —] |
```

**ID prefixes**:
- `B-NNN` — Phase 0/1 backlog items (sequential)
- `P2-NNN` — Phase 2 planned tasks
- `P3-NNN` — Phase 3 planned tasks
- `P4-NNN` — Phase 4 planned tasks
- `D-NNN` — Deferred items / known tech debt across phases

**Title style**: imperative present tense, concrete. "Add login button" not "Login is missing".

**Size**: rough effort estimate, not story points. S = <1h, M = 1–4h, L = 4–8h, XL = multi-session.

**Deps**: other backlog IDs that must complete first, or `—` if none.

**SRS IDs**: which functional/non-functional requirement this implements (FR-XXX, NFR-XXX),
or `—` if it's pure tech debt / cleanup.

**Commit**: short SHA of the commit that closes the task. Required when status flips
to `done`. Use the squash-merge commit on `main`, not the branch commit.

**Files**: comma-separated list of the most important files touched. Helps future
greppers find the work without reading every PR.

---

## After updating

Backlog updates are committed immediately as small standalone docs commits, OR
bundled with the code commit that closes the task:

```bash
git add backlog.md
git commit -m "docs(backlog): close B-XXX [title] — [short reason]"
```

For batch updates (e.g. closing 10 tasks at the end of a session), use:

```bash
git add backlog.md
git commit -m "docs(backlog): close [N] tasks from session [N]"
```

---

## Backlog Quality Check

Before committing, verify:
- [ ] Every newly-closed item has a real commit SHA (not `—` or `TBD`)
- [ ] New items have a clear ID following the prefix convention
- [ ] Dependencies form a DAG (no cycles)
- [ ] The status field is one of `done`, `in_progress`, `pending`, `blocked`
- [ ] The Files column points at actual files that exist in the repo

---

## When to add a new section vs append to an existing one

**Append** to an existing section if the new task is the same kind of work (e.g. another
Phase 2 cleanup task → goes under "Phase 2 Cleanup").

**Add a new section** when:
- Starting a new phase (`## Phase N — Planning`)
- Closing a major batch of work (`## Completed — [Description] (YYYY-MM-DD)`)
- The new tasks form a distinct theme that doesn't fit any existing section

When adding a "Completed —" section, place it chronologically among the other
"Completed —" sections (newest at the bottom of the completed group, before the
"Known Deferred Items" and "Phase N — Planning" sections).
