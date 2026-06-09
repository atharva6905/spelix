---
description: Risk-tier merge governance — what any agent may do autonomously
---
# Merge Governance (Risk Tiers)

Tier is computed from the ACTUAL DIFF (file paths + diffstat), never from the task
description. Mixed-tier diff → highest tier wins. Any uncertainty → escalate one tier.
Never down-tier. SaMD language check (no "injury" strings user-facing) applies to every
tier, every PR.

## Tier 0 — agent MAY self-merge
Categories: docs (`*.md`, `docs/**` excluding `docs/SRS.md`), `.claude/**` EXCLUDING
`settings.json`/`settings.local.json`/`hooks/**`/`rules/governance.md`, dependency PATCH
bumps (diff confined to manifest version pins + lockfile, one dependency per PR),
test-only additions under `tests/**`, CI workflow comment/typo-only fixes.
Self-merge conditions (ALL required):
1. CI fully green (including Deploy to Production where applicable)
2. spelix-governance-reviewer verdict PASS (reviewer receives ONLY the diff + this
   file + its own agent memory; never the implementing agent's session — self-review
   is a hard error)
3. Diff re-validated as Tier 0 at merge time (not just at PR creation)
4. Merge via `mcp__github__merge_pull_request` with `merge_method: "merge"`
After any T0 merge that triggers a deploy: verify droplet SHA + container health.

## Tier 1 — agent PRs, human merges
Categories: feature code, new endpoints, frontend components, dependency MINOR bumps,
refactors not touching Tier 2 paths.
Agent: branch → implement (TDD) → PR → run /code-review → post findings as PR comment →
STOP. Label `needs-human`. Never merge.

## Tier 2 — human-gated
Paths/categories: `backend/app/models/**`, `backend/app/schemas/**`, `backend/alembic/**`,
auth/RLS/JWT code, user-facing strings, `.claude/settings.json` + `.claude/hooks/**` +
`.claude/rules/governance.md`, `.mcp.json`, CI deploy steps, `docs/SRS.md`.
spelix-security-reviewer PASS required before PR. Never autonomous merge. Explicit human
diff review.

## Tier 3 — human + deep review
Categories: migrations touching existing data, RLS policy changes, coaching prompt
changes, payment/consent flows.
Tier 2 requirements PLUS `/code-review ultra` or the `review-panel` workflow before merge.

## Meta-safety
The harness may never autonomously modify its own guardrails: `settings.json`,
`.claude/hooks/**`, and this file are Tier 2 by definition.
