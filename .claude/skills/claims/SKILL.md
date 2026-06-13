---
name: claims
description: Read-only view of which GitHub issues are currently claimed by which parallel ship-loop session. Use to see cross-session ownership before launching another ship-loop.
argument-hint: "(no args)"
disable-model-invocation: true
---
# Claims Status

Read-only snapshot of the cross-session claim board (`.claude/rules/claims.md`). Mutates nothing.

1. Run: `node .claude/lib/claims.mjs board`
2. Render the JSON as a table: **Issue | Owner (sid) | Title | Age (min) | Live? | Worktree?**
3. Flag any row where `live` is false or `worktreePresent` is false as a **stale claim**
   (recoverable by groom's Claims sweep or the next ship-loop `claim`).
4. Also show the ready queue depth: `node .claude/lib/claims.mjs ready` → count + top 5.

Never call `claim`, `release`, `reclaim-stale`, or `gc-labels` from this skill — it is read-only.
