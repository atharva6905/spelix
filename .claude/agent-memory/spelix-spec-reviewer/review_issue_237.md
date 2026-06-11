---
name: review_issue_237
description: Spec review of issue #237 — worktree-safe hooks (_lib.js, smoke-test upgrade, 5 hooks root-anchored, settings.json): PASS, 2026-06-10
metadata:
  type: project
---

## Reviewed: issue #237 (worktree-safe hooks, 2026-06-10) → PASS

Branch: fix/issue-237-worktree-safe-hooks. Commits: f4727ca, 9420917, 4820d1e, d1c2b88.
Files changed: `.claude/hooks/_lib.js` (new), `graphify-hint.js`, `post-edit-lint.js`, `pre-compact.js`, `session-end.js`, `session-start.js`, `smoke-test.mjs`, `stop-gate.js`, `.claude/settings.json`.

**All 4 tasks implemented and tested:**

Task 1 (_lib.js): resolveRoot() + inLinkedWorktree() with correct git flags, try/catch, 5000ms timeout, module.exports.

Task 2 (smoke-test.mjs): Extended case tuple with opts {cwd,env,noSmoke,timeoutMs,after}; ephemeral worktree at .claude/worktrees/smoke-<pid>; branch smoke/hooks-<pid>; dirty backend/_smoke_dirty.py; all 3 worktree cases (stop-gate skip, pre-compact root-anchor, CLAUDE_PROJECT_DIR fallback); handoff.md snapshot+restore; cleanup in finally block.

Task 3 (5 hooks): stop-gate exits 0 after HOOK_SMOKE check; pre-compact+session-end write to resolveRoot()/.claude/handoff.md and stamp worktree cwd; session-start adds 'session cwd' probe with LINKED WORKTREE message and reads handoff from resolveRoot(); graphify-hint checks path.join(resolveRoot(),'graphify-out','graph.json'); post-edit-lint skips pyright only in linked worktree (ruff runs always).

Task 4 (settings.json): All 10 hook entries converted to node "$CLAUDE_PROJECT_DIR/.claude/hooks/<x>.js"; timeout/statusMessage preserved.

MUST NOT touch: safety-blocklist.js, safety-caution.js, secret-scan.js, worktree-freshness.js — all untouched (confirmed via diff).

**Patterns for future reviews:**
- require('./_lib.js') in CJS hooks resolves relative to __dirname (script dir), not cwd — correct even when settings.json passes absolute path via $CLAUDE_PROJECT_DIR.
- --path-format=absolute --git-common-dir is needed for inLinkedWorktree to get an absolute common git dir (bare --git-common-dir outputs relative path from cwd, unreliable in worktrees).
- session-end worktree anchoring is implemented but has no dedicated smoke-test case — the task spec did not require it; pre-compact covers the pattern.
- Smoke handoffAnchoredToRoot() uses after <= before (correct: checks length grew).
