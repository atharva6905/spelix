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
No agent teams. Pace via /loop + ScheduleWakeup (idle ticks 1200–1800s).

## Sweeps (run in order; skip any not in --sweeps)

### 1. Issue triage (output ceiling: labels + comments only)
New/unlabeled issues via mcp__github__list_issues → add labels (bug/feat/docs, size
S/M/L), link SRS IDs when the issue text matches an FR-*, comment on likely duplicates.

### 2. Stale-PR babysitting (ceiling: fix commits to agent branches; NEVER merge T1+)
Open PRs via mcp__github__list_pull_requests:
- CI red on T0/T1 agent branches → diagnose, push minimal fix commit, re-watch once.
- Merge conflicts → mcp__github__update_pull_request_branch.
- PRs idle >7 days → comment a status nudge.

### 3. Dep bumps (weekly cadence — skip if a dep-bump PR merged in the last 6 days)
Backend: `cd backend && uv lock --upgrade --dry-run` to list candidates.
Frontend: `cd frontend && npm outdated --json`.
PATCH bumps → one PR per dependency (T0; self-merge only with --merge + governance gates).
MINOR bumps → T1 PRs, `needs-human` label. MAJOR → issue only, no PR.

### 4. Flaky-test detection (ceiling: issue only)
Pull recent CI runs (gh run list --limit 30 --json conclusion,name,headSha). Tests that
fail then pass on the same SHA → file one issue per flaky test with the failure pattern.

### 5. Hygiene (ceiling: direct commits, docs/T0 only)
- .claude/handoff.md stale (>7 days since stamp) → refresh from git state.
- backlog.md: closed issues missing from the archive → append rows with merge SHAs.
- decisions.md: Decision Index rows missing for ADR bodies present → fix index only.
- Stale worktrees: `git worktree list` entries whose branch is already merged into main →
  REPORT them in the digest for manual pruning. NEVER auto-remove a worktree.

## Digest (always, last)
Append to `.claude/groom-digest.md`: timestamp, per-sweep actions taken/skipped, merges
(if any) with SHAs, stale worktrees flagged, open questions for the human. Post the same
digest as the final message. Then ScheduleWakeup for the next cycle if running under /loop.
