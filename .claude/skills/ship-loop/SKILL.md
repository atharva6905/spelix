---
name: ship-loop
description: In-session continuous delivery loop — implement, PR, watch CI, gated merge, next. Use when the user provides a queue of GitHub issues or milestone items to ship autonomously.
argument-hint: "issue numbers (e.g. 201 203 207) or milestone name [--max N]"
disable-model-invocation: true
---
# Ship Loop

Continuous delivery over a task queue, fully in-session. Governance:
`.claude/rules/governance.md` is BINDING — read it before the first task.

## Inputs
- Queue: GitHub issue numbers or a milestone (resolve via mcp__github__list_issues).
- `--max N`: task cap for this run (default 5).

## Hard guards (check before starting)
- Working tree clean, on `main`, up to date (`git pull`).
- HARD STOP after 2 consecutive blocked tasks — something systemic is wrong; write
  blockers to .claude/handoff.md and end the loop with a summary.
- NEVER modify Tier 2 guardrail files (settings.json, .claude/hooks/**, governance.md).

## Per-task cycle
1. Read the issue. Classify PROVISIONAL tier from description (governance.md table).
2. `EnterWorktree` → branch `<type>/issue-<N>-<slug>`.
3. Implement via the matching specialist agent (spelix-tdd default; spelix-cv-engineer for
   backend/app/cv/**; spelix-migration for alembic/models — note: migration tasks are T2,
   implement + PR + `needs-human` label only). TDD gate: failing test first.
4. Local checks: ruff + pyright + scoped pytest + (if frontend touched) tsc + vitest.
   Exclude tests/unit/test_pose_extraction.py locally (Windows crash; CI is the gate).
5. Push branch; PR via mcp__github__create_pull_request. PR body: issue link, tier
   classification + justification, test evidence.
6. RE-CLASSIFY tier from the ACTUAL diff (mcp__github__get_pull_request_files). Mixed →
   highest. Record both classifications in the PR body.
7. Watch CI via mcp__github__get_pull_request_status (or `gh pr checks <N> --watch` in
   background). Poll with ScheduleWakeup ~270s if watching manually.
8. CI red → /bugfix loop on the branch (max 3 iterations) → still red → label `blocked`,
   comment root-cause summary on PR, count as blocked, NEXT task.
9. CI green:
   - **T0**: spawn a FRESH reviewer subagent (Agent tool, no shared context) with ONLY the
     diff + governance.md; prompt it to verify tier + adversarially review. PASS → merge
     via mcp__github__merge_pull_request (merge_method: "merge") → if deploy triggered,
     verify droplet SHA + container health (ssh spelix-droplet) → if user-facing, run
     Playwright E2E per .claude/rules/git-github.md. FAIL → demote to T1 handling.
   - **T1+**: run /code-review; post findings as PR comment
     (mcp__github__add_issue_comment); label `needs-human`; NEXT task.
10. `git checkout main && git pull`. Update backlog.md (if issue closed) and
    .claude/handoff.md inline. Next task.

## End of run
Summary table: | Issue | Tier (prov→actual) | PR | CI | Outcome (merged/needs-human/blocked) |.
Update .claude/handoff.md with the table and any blockers.
