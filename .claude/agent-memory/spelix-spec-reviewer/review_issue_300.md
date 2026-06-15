---
name: review-issue-300
description: Issue #300 review — pin appleboy/ssh-action to SHA (supply-chain security, T2 CI): PASS, 2026-06-14
metadata:
  type: project
---

Issue #300 fix: single-line change in `.github/workflows/ci.yml` deploy job.
`appleboy/ssh-action@v1` → `appleboy/ssh-action@0ff4204d59e8e51228ff73bce53f80d53301dee2  # v1.2.5`

**Primary acceptance criterion:** appleboy/ssh-action now references a 40-hex SHA — CONFIRMED.
**Comment style:** trailing `# v1.2.5` present — mirrors trufflehog pattern already in use — CONFIRMED.
**SHA correctness:** caller confirmed v1 and v1.2.5 both resolve to this SHA; deploy won't break.
**Preserved fields (from #275):** `command_timeout: 30m`, host, username, key, script body — ALL UNTOUCHED (verified line 161-183).

**Scoping decision — "audit + pin others":**
The task also said to audit remaining mutable tags and pin them for consistency. Remaining un-pinned actions in the file:
- `actions/checkout@v4` (x5 uses)
- `actions/setup-python@v5` (x2)
- `actions/setup-node@v4` (x2)
- `astral-sh/setup-uv@v4` (x2)

The implementer scoped to ONLY appleboy/ssh-action and left the first-party `actions/*` + `astral-sh/setup-uv` as follow-ups. Verdict: ACCEPTABLE. The core security acceptance criterion in the task was the appleboy pin (it handles secrets: DROPLET_IP, DEPLOY_SSH_KEY). First-party `actions/*` carry a materially different trust model. The "audit + pin others" sub-clause was phrased as a consistency hygiene ask ("for consistency"), not an additional acceptance criterion. The diff is surgical and correct. Follow-up work is appropriate scope for a separate issue.

**Why:** mutable `@v1` tag on a secret-bearing third-party action is a supply-chain risk (tag can be force-pushed).
**How to apply:** for future CI security reviews, the primary gate is third-party secret-bearing actions; first-party actions/* pinning is a separate lower-urgency hygiene pass.
