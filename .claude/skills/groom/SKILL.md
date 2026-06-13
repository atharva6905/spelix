---
name: groom
description: Parked-session maintenance loop — issue triage, stale-PR babysitting, dep bumps, flaky-test detection, hygiene. Run via /loop in a session you leave open. Report-first; T0 merges only when --merge is passed.
argument-hint: "[--merge] [--sweeps triage,prs,deps,flaky,hygiene]"
disable-model-invocation: true
disallowed-tools: AskUserQuestion
---
# Groom Loop

Maintenance autonomy. Governance (`.claude/rules/governance.md`) is BINDING.
Default mode is REPORT-ONLY: no merges unless invoked with `--merge`.
Never touch Tier 2 paths in any sweep. Max 3 T0 merges per session even with --merge.
T0 self-merge gate: dispatch `spelix-governance-reviewer` with ONLY the diff +
governance.md (it brings its own agent memory; never this session's context).
No agent teams. Pace via /loop + ScheduleWakeup (idle ticks 1200–1800s).

## Sweeps (run in order; skip any not in --sweeps)

### 1. Issue triage (output ceiling: labels + comments only)
New/unlabeled issues via mcp__github__list_issues → add labels (bug/feat/docs) and a
`size/XS|S|M|L|XL` label (from the body's inline `Size:` line when present, else judge),
link SRS IDs when the issue text matches an FR-*, comment on likely duplicates.
Feature issues with open design questions or no task checklist → add `needs-design`
label and comment that `/design <issue#>` is the follow-up.

### 2. Stale-PR babysitting (ceiling: fix commits to agent branches; NEVER merge T1+)
Open PRs via mcp__github__list_pull_requests:
- CI red on T0/T1 agent branches → diagnose, push minimal fix commit, re-watch once.
- Merge conflicts → mcp__github__update_pull_request_branch.
- PRs idle >7 days → comment a status nudge.

### 3. Dep bumps (weekly cadence — skip if a dep-bump PR merged in the last 6 days)
A "dep-bump PR" means a real manifest/lockfile version change (`pyproject.toml`/`uv.lock`,
`package.json`/`package-lock.json`) — docs-only dependency inventories don't count.
Backend: `cd backend && uv lock --upgrade --dry-run` to list candidates.
Frontend: `cd frontend && npm outdated --json`.
Candidate enumeration ALWAYS runs (including report-only mode — list candidates in the
digest). PR creation only outside report-only:
PATCH bumps → one PR per dependency (T0; self-merge only with --merge + governance gates).
MINOR bumps → T1 PRs, `needs-human` label. MAJOR → issue only, no PR.

### 4. Flaky-test detection (ceiling: issue only)
Pull recent CI runs (gh run list --limit 30 --json conclusion,name,headSha,databaseId).
Group by headSha: a fail-then-pass on the SAME SHA (re-run attempt, not a fix-forward
commit) → file one issue per flaky test with the failure pattern.

### 5. Hygiene (ceiling: direct commits, docs/T0 only)
- .claude/handoff.md stale (>7 days since stamp) → refresh from git state.
- backlog.md: closed issues missing from the archive → append rows with merge SHAs.
- decisions.md: Decision Index rows missing for ADR bodies present → fix index only.
- Stale worktrees: `git fetch origin main`, then for each `git worktree list` entry test
  `git merge-base --is-ancestor <branch> origin/main` — merged branches → REPORT in the
  digest for manual pruning (note locked worktrees need `git worktree unlock` first).
  NEVER auto-remove a worktree. Compare against origin/main everywhere, never local main.

### 6. Claims (ceiling: reclaim stale claim labels + GC orphan label defs; NEVER claim)
Report the claim board into the digest: `node .claude/lib/claims.mjs board` (issue → sid →
ageMin → live → worktreePresent). Then:
- `node .claude/lib/claims.mjs reclaim-stale` — strips `claim:*` labels whose heartbeat is
  stale (>30 min) AND whose worktree is gone, returning them to the ready pool. Report reclaimed.
- `node .claude/lib/claims.mjs gc-labels` — deletes `claim:<sid>` label *definitions* applied to
  no open issue. Report removed.
groom NEVER auto-claims and its triage/label sweeps only ADD labels, so they never clobber a
`claim:` label. This sweep is T0 and runs even in report-only mode (it is self-healing hygiene).

## Digest (always, last)
Append to `.claude/groom-digest.md`: timestamp, per-sweep actions taken/skipped, merges
(if any) with SHAs, stale worktrees flagged, claims (board snapshot + reclaimed + gc'd
labels), open questions for the human. The digest
write itself is T0 — commit it directly, never PR it; it is exempt from report-only.
Post the same digest as the final message. Then ScheduleWakeup for the next cycle if
running under /loop.
