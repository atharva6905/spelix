---
name: issue-303-migrate-rollback
description: Issue #303 (T2 CI deploy) — alembic upgrade head nested in inner if so migrate failure routes to existing rollback+exit 1 instead of silently proceeding to health loop; clean on all four axes → PASS, 2026-06-15, commit fbac6a6. RESOLVES the #299 OBS-1.
metadata:
  type: project
---

# Issue #303 — deploy migrate-failure → rollback (T2 CI deploy step) → PASS

Commit `fbac6a6`, `.github/workflows/ci.yml` `deploy` job "Deploy via SSH" `script:` body (L167-189). The ONLY change vs #299: `alembic upgrade head` (L173) is now nested in an inner `if ... ; then ... else echo "Migration failed — ROLLING BACK"; fi` so a migrate failure routes to the existing `git checkout "$PREVIOUS_SHA"` rollback + rebuild + `exit 1` (L186-189) instead of falling through to the health loop on a half-migrated DB. No `alembic downgrade` added. Rollback block byte-identical. `command_timeout: 30m` (#275) + `appleboy/ssh-action@0ff4204d…` pin (#300) + `timeout 1320` (#299) UNCHANGED.

This RESOLVES the #299 OBS-1 (alembic-fail-doesn't-rollback) — the gap #299 filed as issue #303.

Reviewed clean on all four security axes:
- Secret exposure: none. secrets.DROPLET_IP (L163) + secrets.DEPLOY_SSH_KEY (L165) are with: inputs only, never in script:. Every echo carries only git SHA / $i loop counter / $? exit code / static strings (incl. new "Migration failed — ROLLING BACK" L181). No secret interpolated/echoed/logged.
- Injection / command surface: only interpolations are server-derived $PREVIOUS_SHA (quoted L186/188, git rev-parse HEAD) + literal $i. New inner `if docker compose ... alembic upgrade head; then` runs the SAME static command, now as an if condition — no new untrusted input, no new command surface.
- Pipeline integrity: deploy guard (L157), needs: incl secret-scan (L156), command_timeout 30m (L166), SHA pin @0ff4204d… (L161), both secrets.* refs (L163/165) UNCHANGED — only script: body changed. STRENGTHENING: failed migration fails red + rolls back instead of passing green on half-migrated DB. Success path NOT weakened — health loop still gates exit 0.
- SaMD / FTC: N/A (CI YAML, no user-facing string).

Not a finding: rollback note "migrations were NOT downgraded — manual alembic downgrade may be required" (L188) is an honest operator caveat. No auto-downgrade added — correct (auto-downgrade on failed deploy riskier than human-gated manual).

How to apply: CI-deploy-step T2 review surface = (1) secret echo/exposure in remote script, (2) deploy guard + needs: gate chain, (3) action pin + untrusted interpolation, (4) does a control-flow rewrite weaken the success/health gate. A pure control-flow strengthening that routes a fixed command's failure into an existing rollback touches none of (1)-(3) and improves (4) → PASS. Related: [[issue_275_deploy_ssh_timeout]], [[issue_300_ssh_action_pin]].
