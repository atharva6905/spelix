---
name: review-deploy-migrate-rollback-303
description: Issue #303 review — roll back deploy on alembic migration failure (T2 CI); PASS; closes #299 OBS-1 by nesting migrate in its own if, 2026-06-15
metadata:
  type: project
---

# Issue #303 — roll back deploy on alembic migration failure (T2 CI) → PASS (0 blocking)

`.github/workflows/ci.yml` "Deploy via SSH" `script:` body (commit `fbac6a6`). DIRECTLY closes my own #299 OBS-1 (bare unchecked `alembic upgrade head` that proceeded to health on failure). Diff +4/-2: migrate line now wrapped in `if docker compose ... exec -T backend uv run alembic upgrade head; then <health loop> else echo "Migration failed — ROLLING BACK" fi`, nested inside the existing `if timeout 1320 ... up -d --build; then` block.

## Structure trace (errexit OFF — see [[review-deploy-rollback-budget-299]])
- Outer `if` (build) closed by `fi` line 185; inner `if` (migrate) closed by `fi` line 182. 2 if / 2 fi, balanced.
- Migrate SUCCESS → health loop; `/health` 200 → `exit 0` (rollback never reached). 6 fails → shared rollback 186-189 + `exit 1`.
- Migrate FAILURE → inner `else` → falls through BOTH `fi`s to shared rollback 186-189 + `exit 1`. **This is the fix.**
- Build fail/timeout → outer `else` → shared rollback. No double-rollback, no unreachable code, 2-space indentation under `script: |`.

## Confirmations
- `docker compose exec` propagates alembic's exit code as the `if` condition. Backend container down → `exec` errors non-zero → also routes to rollback (desirable).
- Migrate deliberately NOT timeout-bounded (partial-migration risk) — preserved.
- `timeout 1320` (#299) + `command_timeout: 30m` (#275) + appleboy pin (#300) unchanged. Rollback block byte-identical.
- Rollback-without-downgrade (#275 OBS-2) remains the documented intentional gap — NOT a finding.

## Non-blocking observation (cosmetic, NOT a finding)
- Shared rollback no longer echoes the migrate's exit code; only the build path's `else` has `exit $?` (line 184). Migrate-fail echo (181) is a plain string. Outcome (rollback + exit 1) correct; only failure-cause logging is coarser. Left design-faithful (approved design specified the exact echo string).

## ⚠️ INCIDENT — this change BROKE PROD and was REVERTED (#306, 2026-06-15)
The structure/inspection review was clean, but #305's OWN deploy FALSE-ROLLED-BACK on the **happy path**: the new `if docker compose exec -T backend uv run alembic upgrade head; then …` gate runs IMMEDIATELY after `up -d` — before the freshly-recreated backend is ready — so a transient not-ready/connection condition made the gate non-zero → "Migration failed — ROLLING BACK" → rollback to 324a296. Prod stayed safe (rollback worked), but main carried a deploy script that failed every deploy → reverted via #306 (`7de82b0`). #303 reopened `needs-design`.

**BIG LESSON (deploy-script reviews):** inspection + CI canNOT exercise post-`up -d` timing. Gating a command that depends on container/app readiness (DB connect, `exec`, migrate) right after `up -d` will false-fail on the readiness race. The OLD bare line "worked" precisely BECAUSE errexit-OFF ignored the transient and the 6×10s health-retry covered for it. When a review sees a NEW gate added on a readiness-dependent command, FLAG that it needs a readiness-retry (or to run only after `/health` passes) and that it MUST be validated on a real deploy, not just inspection. "PASS on inspection" ≠ "prod-safe" for deploy-script control-flow.

## Durable heuristic for deploy-script reviews
Wrapping an unchecked sequential command in `if cmd; then ... else <rollback marker> fi` is the canonical idiom to make a failure routable under errexit-OFF. When a new gate is nested before the health loop, verify: (a) `fi` count balances, (b) the new `else` falls through to the SHARED rollback (not a duplicate), (c) `exit 0` stays inside the health loop so ONLY a passing health check yields green CI. **AND (d) — the #303 lesson — does the gated command depend on backend readiness? If so it must retry/wait, else it false-rollbacks on the post-`up -d` race.**
