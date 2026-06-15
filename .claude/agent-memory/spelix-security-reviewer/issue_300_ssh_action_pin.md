---
name: issue-300-ssh-action-pin
description: Issue #300 (T2 CI deploy) — appleboy/ssh-action @v1 → @0ff4204d SHA pin on the secret-bearing deploy step; RESOLVES the #275 standing mutable-tag observation → PASS, 2026-06-14
metadata:
  type: project
---

# Issue #300 — SHA-pin `appleboy/ssh-action` on the deploy step (T2 CI deploy) → PASS

Single-line change `.github/workflows/ci.yml:161`, commit `d7f8cb4`:
`uses: appleboy/ssh-action@v1` → `uses: appleboy/ssh-action@0ff4204d59e8e51228ff73bce53f80d53301dee2  # v1.2.5`.
This is the `deploy` job "Deploy via SSH" step that receives `secrets.DROPLET_IP` (L163) and `secrets.DEPLOY_SSH_KEY` (L165) — the highest-blast-radius action in the workflow.

## RESOLVES the #275 standing observation
The mutable major-version tag flagged during #275 (asymmetric with SHA-pinned `trufflesecurity/trufflehog@47e7b7cd...`) is now closed: pinned to an immutable 40-hex SHA, removing the "upstream retags/compromises `v1`, malicious commit runs in the SSH step + exfiltrates deploy key" vector. Standing note in [[issue-275-deploy-ssh-timeout]] CLOSED — do NOT re-report unless the ref reverts to a mutable tag.

## Verified clean on all four axes
- **Pin correctness:** `0ff4204d59e8e51228ff73bce53f80d53301dee2` is valid 40-hex. Caller confirmed (gh api) both `v1` and `v1.2.5` resolve to it → same code `@v1` already ran; no behavior change, deploy won't break. Inline `# v1.2.5` matches.
- **No new surface / no regression:** diff touches ONLY the `uses:` ref. Unchanged: `secrets.*` (L163/L165), deploy guard `if: github.ref=='refs/heads/main' && github.event_name=='push'` (L157), `needs:` incl. secret-scan (L156), `command_timeout: 30m` (L166), remote `script:` (L167-183, echoes only git SHA + static strings, no secret interp). No secret newly exposed. SaMD N/A.
- **TOFU caveat (non-blocking):** SHA trusts the commit `v1` resolves to TODAY — honest ratchet vs FUTURE retag/compromise, not retroactive proof current code is clean. Same posture as [[docling_weight_checksum]] + the trufflehog pin.

## Residual (accepted for THIS PR — follow-up, not blocker)
`actions/checkout@v4` / `setup-python@v5` / `setup-node@v4` + `astral-sh/setup-uv@v4` remain on mutable tags. Acceptable: lint/test/build jobs (lower blast radius, NOT secret-bearing deploy); first-party `actions/*` carry GitHub provenance. Separate action-pin PR. RE-FLAG only if a deploy secret is later routed into one of those jobs.

## How to apply
CI action-pin reviews: confirm (1) ref is immutable 40-hex SHA, (2) it resolves to the comment's claimed tag (caller / `gh api`), (3) diff touches ONLY the ref — no secret/guard/script drift, (4) note TOFU anchor honestly. SHA-pinning the secret-bearing third-party action is priority; first-party `actions/*` on tags is lower-priority residual.
