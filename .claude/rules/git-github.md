---
description: Git, GitHub MCP, checkpoint/PR workflow, deployment, E2E verification, ADR/backlog protocol
---
# Git & GitHub Process Rules

## Git Conventions

Use conventional commits. No co-authored-by, no emoji prefixes, no "Generated with Claude" footers.

Format: `type(scope): short description` — optional body with context.

Types: `feat`, `fix`, `test`, `refactor`, `chore`, `docs`.
Scopes: `api`, `cv`, `auth`, `models`, `worker`, `frontend`, `admin`, `config`, `ci`, `pdf`, `coaching`.

- **Main agent**: always ask for confirmation before committing.
- **Sub-agents in worktrees**: commit freely without confirmation — reviewed at merge time.
- **When to commit**: after each TDD gate passes (test green = commit point).
- **Commit scope**: one logical change per commit. Don't bundle unrelated changes.

## GitHub Operations — Use GitHub MCP First

**Always prefer GitHub MCP tools over `gh` CLI or direct git commands for GitHub API operations.**

| Operation | Use | Not |
|-----------|-----|-----|
| Check PR status/details | `mcp__github__get_pull_request` | `gh pr view` |
| Check CI/check runs | `mcp__github__get_pull_request_status` | `gh pr checks` |
| Create PR | `mcp__github__create_pull_request` | `gh pr create` |
| Create branch | `mcp__github__create_branch` | `git push -u origin` |
| Read file on GitHub | `mcp__github__get_file_contents` | `gh api` |
| List/search issues | `mcp__github__list_issues` / `search_issues` | `gh issue list` |
| Create/update issues | `mcp__github__create_issue` / `update_issue` | `gh issue create` |
| Comment on issues/PRs | `mcp__github__add_issue_comment` | `gh issue comment` |
| Review PRs | `mcp__github__create_pull_request_review` | `gh pr review` |
| View PR files/diff | `mcp__github__get_pull_request_files` | `gh pr diff` |
| Merge PR | `mcp__github__merge_pull_request` (merge_method: "merge") | `gh pr merge` |
| Push files | `mcp__github__push_files` | manual git add/commit/push |

**Fall back to `gh` CLI only for**: `gh pr checks --watch` (streaming), or operations not covered by MCP tools. Always merge with `merge_method: "merge"` (never `squash`).

## Checkpoint Workflow (branch + PR + merge — NEVER direct push to main)

`main` auto-deploys to spelix.app. A broken push breaks production. For every meaningful checkpoint, work on a branch, open a PR, let CI run, then merge via `mcp__github__merge_pull_request` (merge method: `merge`). The main agent merges its own PR once CI is green.

**Meaningful checkpoints** (PR required): phase batch completion, FR-ID implementations with user-facing changes, schema migrations, bug fixes touching auth/coaching/upload/pipeline, dependency upgrades, infra changes, CI fixes.

**Not meaningful** (direct commit on current branch is fine): handoff notes, typo-only doc fixes, scratch commits during active development before the checkpoint.

**Workflow**: `git checkout -b <type>/<name>` → implement → local checks (`ruff`/`pyright`/`tsc`/`vitest`) → `git push -u origin <branch>` → create PR via `mcp__github__create_pull_request` → wait for CI → merge via `mcp__github__merge_pull_request` (merge method: `merge`, NOT `squash`) → `git checkout main && git pull` → wait for "Deploy to Production" CI step to finish → if user-facing, run E2E verification (below).

**Merge rules**:
- **NEVER squash merge.** Use `merge_method: "merge"` always. Squash merges lose individual commit history and cause local/remote divergence that requires `git checkout -B main origin/main` to fix.
- **Use `mcp__github__merge_pull_request`** for all merges — not `gh pr merge` CLI.
- Never force-push to main. Never bypass CI. Never merge a PR with red CI.

## Post-Merge Deployment — WAIT for CI, NEVER SSH deploy manually

After merging to `main`, **"Deploy to Production" runs automatically as a CI step** (frontend via Vercel + backend Docker rebuild on the droplet).

**STRICT RULE: Do NOT SSH into the droplet to run `docker compose up --build` or `git pull` manually after a merge.** Manual deploys cause state divergence and race conditions with CI (burned time in session 26 with stale env vars).

**Procedure after merge**:
1. Check CI status via `mcp__github__get_pull_request_status` or `gh pr checks` — wait until ALL checks including "Deploy to Production" show `pass`
2. Verify the droplet is running the new code: `ssh spelix-droplet "git log --oneline -1"` — must match the merge commit
3. Verify containers are healthy: `ssh spelix-droplet "docker ps --format '{{.Names}} {{.Status}}'"` — all should show `(healthy)`
4. Only THEN proceed to E2E verification

**The only exception for SSH deploy**: when CI's "Deploy to Production" step fails and you need to debug why — check CI logs first, diagnose, fix, re-trigger.

## E2E Verification via Playwright MCP

After "Deploy to Production" CI step is green, verify the live flow with Playwright MCP BEFORE moving on. Verify on prod after any PR touching upload/pipeline/results/coaching/PDF/auth, API shapes, Phase MUST requirements, or production bugs. Skip for docs-only, CI-only, or prompt-only changes.

**Procedure**: wait for deploy → `browser_navigate` → `https://spelix.app` → `browser_snapshot` → walk affected flow → check `browser_console_messages` (level=error) + `browser_network_requests` (4xx/5xx). If broken: write to `.claude/handoff.md` and STOP. If green: record in handoff.

Test artifacts: `e2e/fixtures/` (video inputs), `e2e/screenshots/` (captures). `.playwright-mcp/` is gitignored.

## decisions.md & backlog.md Update Protocol

`decisions.md` and `backlog.md` live at the **repo root**. They are project-owned across sessions — treat them with care. **Do NOT batch updates at end-of-session**; run inline with the code changes that triggered them. You do NOT need user permission to invoke `/adr` or `/backlog` — they are normal session hygiene.

**Open work lives in [GitHub Issues](https://github.com/atharva6905/spelix/issues), not in `backlog.md`.** `backlog.md` is the completed-work archive, grouped by phase (newest first). When an Issue closes, append its entry to the relevant phase section with the merge SHA. New/discovered work → open a GitHub Issue (`mcp__github__create_issue`).

**Run `/adr`** when: a library choice is made; a design pattern adopted across >1 file; a constraint is added; a bugfix reveals a systemic design choice; a migration between approaches happens; a test pattern is adopted to prevent a bug class. If you'd write a `backend/CLAUDE.md` gotcha for it, you also need an ADR. **File new ADRs under the matching domain section in `decisions.md` and append a row to the Decision Index at the top.**

**Run `/backlog`** when: an Issue closes (append a `done` row under its phase section with the merge SHA); a batch of work finishes (add a `## Completed —` subsection); a new phase begins.

**File ownership**: `decisions.md` is **append-only across phases** — old ADRs are NEVER edited for substance; if a decision is reversed, write a new ADR that supersedes the old one by ID and cross-link both ways. `backlog.md` archive rows are edited in place only to record completion. Both files commit alongside normal code changes — atomic with the PR that introduces the decision/closes the task.
