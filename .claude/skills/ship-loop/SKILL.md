---
name: ship-loop
description: In-session continuous delivery loop — implement, PR, watch CI, gated merge, next. Use when the user provides a queue of GitHub issues or milestone items to ship autonomously.
argument-hint: "issue numbers | milestone | --auto [--watch] [--max N]"
disable-model-invocation: true
---
# Ship Loop

Continuous delivery over a task queue, fully in-session. Governance:
`.claude/rules/governance.md` is BINDING — read it before the first task.

## Inputs
- Queue: GitHub issue numbers or a milestone (resolve via mcp__github__list_issues).
- `--max N`: task cap for this run (default 5).
- `--auto`: self-feeding mode — no explicit queue; pull the next issue from the ready
  queue (`.claude/rules/claims.md`) until `--max N` shipped or the queue is dry.
- `--watch` (with `--auto`): when the queue is dry before `--max`, ScheduleWakeup ~1200s
  and recheck instead of ending. Without it, dry → end the run.
- Session id: mint `sl-<4hex>` at start
  (`node -e "console.log('sl-'+require('crypto').randomBytes(2).toString('hex'))"`),
  print it, reuse for all claims this run. Export `CLAIMS_WORKTREE` per task so heartbeat
  records the worktree path.

## Hard guards (check before starting)
- Isolation check FIRST (superpowers:using-git-worktrees Step 0, nested via /implement
  Step 0): if the session starts inside a leftover worktree, `ExitWorktree`
  (action: "keep") back to the main checkout before anything else.
- Working tree clean, on `main`, up to date (`git pull`).
- HARD STOP after 2 consecutive blocked tasks — something systemic is wrong; write
  blockers to .claude/handoff.md and end the loop with a summary.
- NEVER modify Tier 2 guardrail files (settings.json, .claude/hooks/**, governance.md).

## Per-task cycle
0. **Acquire next task (claim).** In `--auto`: `node .claude/lib/claims.mjs claim --sid <sid>`.
   - Returns `null` → queue dry: if `--watch`, ScheduleWakeup ~1200s and retry; else end run.
   - Returns `{number,...}` → that issue is now labelled `claim:<sid>`; proceed with it.
   In explicit-queue mode: claim each listed issue the same way before working it; skip (with a
   log line) any where `claim` returns null because another live session owns it.
   Refresh the heartbeat at the start of every cycle and on each CI-poll wake:
   `node .claude/lib/claims.mjs heartbeat --sid <sid> --issue <n>`.
1. Read the issue. Classify PROVISIONAL tier from description (governance.md table).
2. Run `/implement <issue#> --tier <provisional>` — it owns preflight, EnterWorktree,
   specialist dispatch (routing table lives there), the tier-scaled review chain
   (spec → quality → security per tier), local checks, and 3-strike escalation.
   Consume its report: `{branch, commits, checks, review_verdicts, status}`.
   `status: blocked` → count as blocked, NEXT task. (Migration tasks are T2:
   implement + PR + `needs-human` label only.)
3. Push branch; PR via mcp__github__create_pull_request. PR body: issue link, tier
   classification + justification, review verdicts from /implement, test evidence.
4. RE-CLASSIFY tier from the ACTUAL diff (mcp__github__get_pull_request_files). Mixed →
   highest. Record both classifications in the PR body. If actual tier > provisional:
   re-enter the /implement review chain at the higher rigor (run only the gates not
   yet passed) before continuing.
5. Watch CI via mcp__github__get_pull_request_status (or `gh pr checks <N> --watch` in
   background). Poll with ScheduleWakeup ~270s if watching manually.
   Claims discipline (superpowers:verification-before-completion): "CI green" may only
   be stated after reading the actual check conclusions; "deployed" only after the
   droplet SHA/health command output is in hand. Never claim from expectation.
6. CI red → /bugfix loop on the branch (max 3 iterations) → still red → label `blocked`,
   comment root-cause summary on PR, count as blocked, NEXT task. If the session has
   already left the task worktree, re-enter it with `EnterWorktree` (`path:` the
   existing worktree — re-entry of an EXISTING worktree: pass path:,
   never create a second worktree for the same task; /implement Step 0 detection
   rules apply) before /bugfix; exit again afterwards.
7. CI green:
   - **T0**: dispatch `spelix-governance-reviewer` with ONLY the diff + governance.md
     (it brings its own agent memory; NEVER this session's context or the implementer's
     reasoning). PASS → merge via mcp__github__merge_pull_request (merge_method:
     "merge") → if deploy triggered, verify droplet SHA + container health
     (ssh spelix-droplet) → if user-facing, run Playwright E2E per
     .claude/rules/git-github.md. FAIL → demote to T1 handling.
   - **T1+**: run /code-review; post findings as PR comment
     (mcp__github__add_issue_comment). Then run the APPROVAL GATE:
     1. Present the PR gist in plain text: what changed and why (issue link), tier
        prov→actual, per-file diff summary (mcp__github__get_pull_request_files),
        review-chain verdicts, /code-review findings (open vs fixed), CI status,
        deploy implications (user-facing? E2E needed per git-github.md?), and an
        explicit "needs your judgment" list. For T2 the gist MUST include the
        verbatim spelix-security-reviewer verdict and call out every sensitive-path
        file touched — this presentation IS the explicit human diff review.
        T3 additionally requires /code-review ultra BEFORE the gate (governance).
     2. AskUserQuestion (single question, options depend on state):
        - No open blockers: "Approve & merge" / "Fix something first" /
          "Defer (label needs-human)" / "Skip to next task (leave PR open)".
        - Open blockers (unresolved findings, failed optional checks, tier
          escalation mid-flight): "Fix in this PR" / "Merge anyway (override —
          recorded)" / "Defer (label needs-human)" / "Close PR & abandon".
     3. Approve/override → comment "Merged on explicit in-session human approval"
        (override: include what was overridden) on the PR → merge via
        mcp__github__merge_pull_request (merge_method: "merge") → post-merge
        verification per .claude/rules/git-github.md (wait for Deploy to
        Production; droplet SHA + container health; Playwright E2E if user-facing).
     4. Fix-first → SendMessage to the SAME implementer instance in the worktree
        (re-enter via EnterWorktree path: if needed — re-entry of an EXISTING
        worktree: pass path:, never create a second worktree for the same task;
        /implement Step 0 detection rules apply); re-run only the review gates
        invalidated by the fix; push; re-watch CI; re-present the gate.
     5. Defer → label `needs-human`, record the open questions as a PR comment.
     6. Whatever the outcome, proceed to step 8 cleanup — per-outcome worktree
        rules live there.
     The gate is for INTERACTIVE sessions: if the human does not respond or the
     session is autonomous/headless, fall back to label `needs-human` + NEXT task.
8. Cleanup — runs for EVERY outcome before the next task:
   - **Release the claim** matching the outcome:
     `node .claude/lib/claims.mjs release --sid <sid> --issue <n> --outcome <merged|blocked|needs-human|skipped>`
     (merged → on a clean merge; blocked → CI red after 3 fixes or status:blocked;
     needs-human → T2/T3 PR or human deferral; skipped → human chose skip / left PR open).
   - Agent-memory preservation FIRST, before ANY ExitWorktree: reviewer/implementer
     agents inherit the session cwd, so their `.claude/agent-memory/**` writes land in
     the TASK WORKTREE — removing it destroys them. Check
     `git -C <worktree> status --short -- .claude/agent-memory/` and copy any
     modified/untracked files to the same path in the main checkout, then revert the
     worktree copies (`git checkout -- .claude/agent-memory/` + delete untracked).
     Commit the main-checkout copies as docs hygiene (`docs: <agent> memory from
     <PR> gate`).
   - Merged: `ExitWorktree` (action: "remove") — deletes the worktree and its local
     branch (the work is on main). If the tool refuses citing unmerged changes,
     STOP and reconcile — never pass discard_changes blind.
   - Deferred (needs-human), skipped (PR left open), or blocked: `ExitWorktree`
     (action: "keep") — worktree and branch survive for later fixes; record the
     worktree path in handoff.
   - Closed/abandoned: `ExitWorktree` (action: "remove", discard_changes: true) —
     permitted here ONLY because the human chose "Close PR & abandon" at the gate;
     this is the sole sanctioned use of discard_changes.
   - Back in the main checkout (ExitWorktree restores it, already on main):
     `git pull --ff-only`, then `git worktree prune`.
   - Update backlog.md (if issue closed) and .claude/handoff.md inline. Next task.

## End of run
In `--auto`, the run ends when `--max` tasks have shipped OR `claim` returned null and `--watch`
was not set. Always release the current claim before ending. Stale claims from a crash are
recovered by any later session or by groom's Claims sweep.

Summary table: | Issue | Tier (prov→actual) | PR | CI | Outcome (merged/needs-human/blocked/skipped/closed) |.
Update .claude/handoff.md with the table and any blockers.
