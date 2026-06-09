---
name: implement
description: Execute one implementation task or GitHub issue through the worktree + specialist-agent + tier-scaled review pipeline. Use for every per-issue execution inside /ship-loop and for standalone one-off tasks with a known tier. Not for ideation or planning (use /design) and not for diagnosing failing tests (use /bugfix).
argument-hint: "<issue# | task description> [--tier T0|T1|T2|T3]"
---
# Implement

The execution layer between harnesses and specialist agents. Input: one task (a GitHub
issue number, or task text + `--tier`). Output: a worktree branch with green local
checks, fully review-gated for its tier. PR creation, CI watching, and merging belong
to the CALLER (ship-loop or the user) — never to this skill.

Governance (`.claude/rules/governance.md`) is BINDING.

## Step 1 — Preflight

1. `git fetch origin && git checkout main && git pull --ff-only`
2. `git worktree prune`; audit `git worktree list` for stale entries.
3. Confirm clean working tree (`git status`). Record base SHA (`git rev-parse HEAD`).
4. `EnterWorktree` → branch `<type>/issue-<N>-<slug>` (or `<type>/<slug>` for non-issue
   tasks).

If the input is an issue number: read it via `mcp__github__get_issue`. The embedded
task checklist in the issue body is the task text. Classify the provisional tier from
governance.md if `--tier` was not given.

## Step 2 — Dispatch the implementer

Routing table:

| Task touches | Implementer |
|---|---|
| backend/app/cv/** | spelix-cv-engineer |
| Alembic / backend/app/models/** / schemas | spelix-migration |
| coaching / RAG / LangGraph / Coach Brain / prompts | spelix-ai-engineer |
| everything else (incl. frontend) | spelix-tdd |

Dispatch rules:
- The prompt contains the FULL task text VERBATIM — never "read the plan file" or
  "see issue #N".
- Include: scene-setting context (what subsystem, why now), FR-ID(s), the TDD gate
  command, and the worktree scope.
- The implementer reports one of: `DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED`.

| Status | Handling |
|---|---|
| DONE | proceed to review chain |
| DONE_WITH_CONCERNS | read concerns; correctness/scope concerns → resolve before review; observations → note and proceed |
| NEEDS_CONTEXT | provide the missing context via SendMessage, continue same instance |
| BLOCKED | assess: context gap → provide; task too large → split (report back to caller); task wrong → escalate to human |

## Step 3 — Tier-scaled review chain

| Tier | Review chain (in order; each gate must PASS before the next starts) |
|---|---|
| T0 or size/XS | implementer self-review only |
| T1 | + spelix-spec-reviewer |
| T2 / T3 | spelix-spec-reviewer → spelix-quality-reviewer → spelix-security-reviewer (final pre-PR gate) |

Loop mechanics: reviewer findings → the SAME implementer instance fixes (SendMessage —
context intact, never a fresh dispatch) → the SAME reviewer re-reviews. Max 3 fix
iterations per gate, then escalate (Step 4). Quality review never starts before spec
compliance passes; security review never starts before quality passes.

Reviewer dispatch template (every reviewer):
- The branch/diff ref + the task text verbatim + the spec-review PASS statement (for
  quality reviewer) + relevant rule files (quality: backend/frontend CLAUDE.md gotchas;
  security: `.claude/rules/coaching.md` + governance SaMD rule).
- Memory bookends: "FIRST read your MEMORY.md and consult prior findings. … Update
  your MEMORY.md BEFORE returning your verdict — required, not optional."
- Require the structured verdict format (PASS or findings table) — never prose-only.

## Step 4 — Escalation (after 3 failed iterations on any gate)

Write a structured blocker report and STOP working the task:

```markdown
## Blocked: <task> — gate: <implementer|spec|quality|security>
**Attempts**: 3
**Failing gate output**: [exact error/finding verbatim]
### Attempt 1/2/3
Hypothesis / Change made / Result
**Current hypothesis**: [best theory]
```

Post it as an issue comment (`mcp__github__add_issue_comment`), mirror to
`.claude/handoff.md`, label the issue `blocked`. Report status `blocked` to the caller.

## Step 5 — Terminal state

1. Local checks, all green: `ruff` + `pyright` + scoped `pytest` (exclude
   `tests/unit/test_pose_extraction.py` locally — Windows crash, CI is the gate) +
   (if frontend touched) `tsc` + `vitest`.
2. Commits exist in the worktree (conventional format, committed at TDD gate passes).
3. Report to caller: `{branch, commits, checks, review_verdicts, status}`.

Never `git push` to main, never merge, never create the PR from inside this skill.
