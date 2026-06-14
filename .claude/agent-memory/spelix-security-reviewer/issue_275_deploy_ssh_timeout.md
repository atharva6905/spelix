---
name: issue-275-deploy-ssh-timeout
description: Issue #275 (T2 CI deploy) — command_timeout 30m added to appleboy/ssh-action deploy step; clean on all four axes → PASS, 2026-06-14
metadata:
  type: project
---

# Issue #275 — deploy SSH `command_timeout: 30m` (T2 CI deploy step) → PASS

Single-line addition `command_timeout: 30m` at `.github/workflows/ci.yml:166`, in the `deploy` job's "Deploy via SSH" step (`appleboy/ssh-action@v1`), commit `dec6644`.

Reviewed clean on all four security axes:
- **Secret exposure:** none — static duration literal. `secrets.DROPLET_IP` (L163) and `secrets.DEPLOY_SSH_KEY` (L165) unchanged; remote `script:` echoes only the git SHA + static health/rollback status strings, no secret interpolation. A longer command window surfaces no new value.
- **Pipeline integrity:** deploy guard `if: github.ref == 'refs/heads/main' && github.event_name == 'push'` (L157) and `needs:` incl. the TruffleHog secret-scan job (L156) unchanged — deploy still fires only on push-to-main after all gates. Extending 10m→30m only holds an already-trusted CI-initiated SSH session open longer; no new auth surface.
- **Injection / supply chain:** action pin `appleboy/ssh-action@v1` (L161) unchanged; `command_timeout: 30m` is a static literal with no `${{ }}` interpolation of untrusted input.
- **SaMD / FTC:** N/A (CI YAML, no user-facing string).

**Standing observation (NOT a finding; pre-existing, out of scope for #275):** `appleboy/ssh-action@v1` is a mutable major-version tag, not SHA-pinned — asymmetric with the SHA-pinned `trufflesecurity/trufflehog@47e7b7c...` (L150). Worth a standalone action-pin-hardening PR; recorded so a later reviewer can pick it up rather than re-derive it.

**How to apply:** for CI-deploy-step T2 reviews, the security surface is (1) secret echo/exposure in the remote script, (2) the deploy trigger guard + `needs:` gate chain, (3) action pin + untrusted interpolation. A timeout/duration literal touches none of these → PASS. Memory for security-reviewer is persisted by the main agent (reviewer ran read-only / no Write tool). Related: [[harness_governance_t1_t2_approval_gate]].
