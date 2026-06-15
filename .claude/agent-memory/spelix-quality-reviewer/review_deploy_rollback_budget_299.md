---
name: review-deploy-rollback-budget-299
description: Issue #299 review — bound deploy build with timeout 1320 so rollback retains budget (T2 CI); PASS; appleboy/ssh-action runs WITHOUT set -e (load-bearing), 2026-06-14
metadata:
  type: project
---

# Issue #299 — bound deploy build phase so rollback retains budget (T2 CI) → PASS (0 blocking)

`.github/workflows/ci.yml` `deploy` job "Deploy via SSH" `script:` body rewritten (commit `cb6ed93`): wraps the primary `docker compose up -d --build` in `timeout 1320` (22m) inside `if/else`; migrate (`alembic upgrade head`) + the 6×10s health loop run ONLY on build success; both the build-timeout `else` branch and the post-loop fall-through route to `git checkout $PREVIOUS_SHA` rollback + rebuild + `exit 1`. Closes the shared-budget rollback gap I flagged in my own #275 review.

## LOAD-BEARING FACT for all future deploy-script reviews
**`appleboy/ssh-action` runs the remote script WITHOUT `set -e` (errexit OFF)** — both pre- and post-patch scripts are plain sequential bash. Therefore:
- The `if timeout 1320 ...; then` wrapper does NOT "suppress errexit" (there was none). Its real job is to CAPTURE the build's exit status so a build failure OR timeout routes into the rollback block within the same SSH session.
- The actual bug fixed: on a `command_timeout` (30m) fire, the action kills the whole SSH session, so the pre-patch rollback (which sat AFTER the unbounded build) never ran. `timeout 1320` converts that session-kill into an in-script `else` with ~8m of budget still live. Strictly better, no regression.

## Confirmations
- `timeout 1320` = coreutils (present on Ubuntu droplet); SIGTERM on fire (exit 124) → half-built state → rollback rebuilds cached `PREVIOUS_SHA` over it. Acceptable.
- `exit $?` is the first stmt in `else` → it's the `if`-condition (timeout pipeline) status: 124 on timeout, build code otherwise. Correct/informative.
- Budget: 22m build + ~1m migrate + ~1m health ≈ 24m, leaving ≥6m of 30m for the (cached, ~2m) rollback. 22m exceeds the observed >10m #263 docling cold bake. Sane both ends.
- `command_timeout: 30m` (#275) + `appleboy/ssh-action@0ff4204d…` pin (#300) unchanged; only the `script:` body changed.

## Non-blocking observations (NOT findings against #299)
- **OBS-1 (pre-existing, identical pre-patch → now filed as #303):** a failing `alembic upgrade head` inside the `then` branch does NOT trigger rollback (errexit off) — prints its error and proceeds into the health loop; if `/health` doesn't validate the schema rev, the script can `exit 0` on a half-migrated DB. Candidate hardening: wrap migrate in its own `if`, and/or have `/health` assert `alembic current` == head.
- **OBS-2:** rollback-without-downgrade remains the documented intentional gap (#275).

**How to apply:** for deploy-script reviews, ALWAYS account for errexit being OFF in appleboy/ssh-action — unchecked sequential commands proceed on failure. Wrapping a command in `if` is the idiom to capture its status; the health check is the only real gate to `exit 0`.
