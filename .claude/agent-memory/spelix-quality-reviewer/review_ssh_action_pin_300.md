---
name: review-ssh-action-pin-300
description: Issue #300 review — pin appleboy/ssh-action @v1 → @0ff4204d SHA on the deploy step (T2 CI); PASS, partial-pin scope boundary is sound, 2026-06-14
metadata:
  type: project
---

# Issue #300 — pin appleboy/ssh-action to commit SHA (T2 CI) → PASS (0 blocking)

One-line change `.github/workflows/ci.yml:161`, commit `d7f8cb4`: `uses: appleboy/ssh-action@v1` → `uses: appleboy/ssh-action@0ff4204d59e8e51228ff73bce53f80d53301dee2  # v1.2.5`.

Quality confirmations:
- **Pin style / consistency:** `@<sha>  # vX.Y.Z` mirrors the existing `trufflesecurity/trufflehog@47e7b7cd…  # v3.94.3` pin (ci.yml:150) exactly — full 40-char SHA + trailing version comment. Convention-consistent; comment matches the SHA (caller-verified `v1.2.5` → `0ff4204d…`).
- **Zero behavior change:** both `v1` and `v1.2.5` resolve to the same commit, so the pinned action is byte-identical to what `@v1` resolved to. Deploy cannot regress.
- **CI-gotcha clean:** `command_timeout: 30m` (#275) and the entire inline `script:` (pull → up -d --build → alembic upgrade → 6×10s health loop → rollback) untouched. No interaction with the #211 deploy false-negative posture.
- **Maintainability:** SHA pin now requires a manual SHA bump on upgrade — acceptable trade for supply-chain safety; Dependabot/Renovate can bump SHA pins automatically. Net positive.

**Non-blocking observations (follow-up, did NOT expand the PR):**
- `astral-sh/setup-uv@v4` (ci.yml:26,75) — third-party, no secrets but still supply-chain — remains on a mutable tag. Minor consistency smell now that the file mixes pinned/unpinned third-party actions. Pin in a follow-up; lower blast radius than the deploy action so correctly deferred here.
- First-party `actions/checkout@v4` / `setup-python@v5` / `setup-node@v4` on mutable tags — lowest priority (GitHub-owned); pin in the same follow-up if pursuing full-file pinning.

**How to apply:** for CI action-pin reviews, the partial-pin boundary (pin the secret-bearing/highest-blast-radius action first, defer the rest) is sound scope discipline — the mixed pinned/unpinned state is a cosmetic smell, not a maintainability defect, best resolved in a dedicated follow-up rather than scope-creeping a single-line security PR.
