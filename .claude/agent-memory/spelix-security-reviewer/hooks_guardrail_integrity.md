# Hooks guardrail integrity (#237) — 2026-06-10

Type: project. Reviewed: issue #237 worktree-safe hooks → PASS (no CRITICAL/HIGH).

- BLOCKING guards = `safety-blocklist.js` + `secret-scan.js` (PreToolUse Bash, exit 2). No `_lib.js` dependency, no worktree skip — they fire everywhere including linked worktrees. If a future diff adds an `inLinkedWorktree()`/conditional `exit(0)` before the block check in either → CRITICAL.
- Warn-only (always exit 0): safety-caution, worktree-freshness, graphify-hint, post-edit-lint, session-start/end, pre-compact. `stop-gate.js` is the only other exit-2 hook.
- `inLinkedWorktree()` invariant (`_lib.js`): `git rev-parse --absolute-git-dir` vs `--git-common-dir`; equal in main checkout (→ false, gate runs), differ in a linked worktree (→ true, skip); git error → false (fails toward running the gate). Main-checkout false positive not reachable. Re-verify whenever `_lib.js` is edited.
- stop-gate's linked-worktree skip is an intentional human decision (2026-06-10) — worktrees lack `.venv`/`node_modules`; worktree code is gated by the /implement review chain + CI. Not a weakening.
- Failure-mode contract for every hook: infrastructure error → exit 0 (never trap a session); exit 2 = deliberate block only.
- CAVEAT (pre-existing, NOT introduced by #237): `post-edit-lint.js` interpolates `${JSON.stringify(f)}` into execSync — JSON-escaping ≠ shell-escaping; safe only because `file_path` comes from Claude's own Write/Edit tool input. Escalate to HIGH if external/untrusted paths ever reach this sink, or if the pattern is copied into a hook that receives external Bash command strings.
- settings.json deny rules to preserve: `Read(.env*)`, `Bash(rm -rf *)`. Hook commands are `$CLAUDE_PROJECT_DIR`-anchored as of #237.
