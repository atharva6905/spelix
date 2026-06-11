# Hooks worktree review (#237) — 2026-06-10

Type: project.

Production fix (`.claude/hooks/_lib.js` — `resolveRoot()` via parent of `git rev-parse --git-common-dir`, `inLinkedWorktree()` via git-dir ≠ common-git-dir) is sound and was verified empirically from inside a linked worktree.

**The trap was the test**: `smoke-test.mjs` used `process.cwd()` as ROOT, but the hooks under test write via `resolveRoot()` (the git MAIN checkout). When the suite runs from a linked worktree, these diverge → (a) spurious `pre-compact [worktree-mode]` failure ("ROOT handoff did not grow"), and (b) the snapshot/restore targets the wrong file, leaving permanent `## Auto mini-handoff` pollution in the main checkout's real `.claude/handoff.md`. Fix: anchor the test's snapshot/assert to the same `_lib.resolveRoot()` the hooks use, or hard-enforce "run from main checkout" at startup.

**Recurring shape to check for**: an unenforced precondition (documented in a header comment only) under which a test silently corrupts shared local state. Also: fixture setup placed OUTSIDE the try/finally cleanup guard leaks worktrees/branches on setup failure.

Post-review correction (main agent, verified line-by-line): only 1 of the 5 `## Auto mini-handoff` blocks in handoff.md was test pollution (the one with `branch: smoke/hooks-<pid>` + a `worktree:` line); the other 4 were legitimate pre-compact snapshots from real sessions (`branch: main`). Leak signature = `worktree:` line + `smoke/` branch — count by signature, not by heading.
