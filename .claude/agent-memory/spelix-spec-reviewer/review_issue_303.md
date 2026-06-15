---
name: review-issue-303
description: Issue #303 redesign (Option 1 retry-then-gate) — 5x retry loop for alembic, then MIGRATED gate wrapping health loop: PASS, 2026-06-15
metadata:
  type: project
---

## Attempt 1 (PR #305, reverted #306, 2026-06-14)

Wrapped bare alembic in a single inner if-then; broke prod because `docker compose up -d` returns before the backend container is ready to accept alembic connections → gate immediately false-rolled-back. #303 reopened needs-design.

**Lesson learned:** spec-review traces control flow correctly but CANNOT catch prod-deploy timing races — deploy-script changes need real-deploy validation (see ADR-DEPLOY-01).

## Attempt 2 (Option 1 retry-then-gate, 2026-06-15) — PASS

Design: replace bare alembic with a 5-iteration retry loop (absorbs backend-readiness race), then gate health loop on MIGRATED=1.

Control-flow paths confirmed (all 4):
- (a) Build ok + migrate ok (any iteration) + health pass: MIGRATED=1; break → `if [ "$MIGRATED" = 1 ]` → health loop → exit 0. No rollback.
- (b) Build ok + migrate ok + health fail x6: MIGRATED=1 → health loop exhausts → "Health check failed after 6 attempts — ROLLING BACK" → rollback → exit 1.
- (c) Build ok + migrate FAIL x5: MIGRATED=0 → else → "Migration failed after 5 attempts — ROLLING BACK" → rollback → exit 1. Health loop NOT run.
- (d) Build timeout/fail: outer else → "Primary build timed out or failed (exit $?) — ROLLING BACK" → rollback → exit 1.

Key spec confirmations (all PASS):
- `for m in 1 2 3 4 5` — 5 iterations. Confirmed.
- Success: `MIGRATED=1; break`. Confirmed.
- Failure echo: `"Migrate attempt $m failed (backend may be starting), retrying..."` — exact text. Confirmed.
- `sleep 10` after echo (not inside else — shell idiom after fi with break in then is correct). Confirmed.
- `if [ "$MIGRATED" = 1 ]; then` gate wrapping health loop. Confirmed.
- `else echo "Migration failed after 5 attempts — ROLLING BACK"`. Confirmed.
- No `timeout` prefix on alembic command. Confirmed.
- No `alembic downgrade`. Confirmed.
- Rollback block byte-identical: `git checkout "$PREVIOUS_SHA"` + `docker compose ... up -d --build` + "NOT downgraded —" echo + `exit 1`. Confirmed.
- SHA pin `0ff4204d59e8e51228ff73bce53f80d53301dee2  # v1.2.5`. Confirmed.
- `command_timeout: 30m`. Confirmed.
- `timeout 1320` on primary build. Confirmed.
- Em-dashes: 4x total ("Health check failed — ROLLING BACK", "Migration failed — ROLLING BACK", "Primary build timed out — ROLLING BACK", "NOT downgraded —"). All confirmed.
- Diff confined to script: body only. No other job/step/key touched. Confirmed.
- No auto-downgrade, no health-first reordering, no `alembic current==head` assertion. Confirmed.

**MIGRATED=0 initialization note:** task spec does not explicitly mention initializing MIGRATED=0 before the loop, but the implementation does so correctly — this is required for the gate to work and is not over-building.

**Sleep-on-last-failure note:** on the 5th failed attempt, echo + sleep 10 still runs before the MIGRATED gate. This is a minor behavioral quirk (unnecessary 10s sleep before rollback message) but does NOT violate the spec text.

**Why:** the 5-retry loop absorbs the post-`docker compose up -d` backend-readiness race that broke #305 — alembic connects before the backend container is ready. Health loop only runs after confirmed migration success.
**How to apply:** retry loops on deploy-script commands that target containers must absorb container-readiness lag; a single gate (attempt 1) is insufficient if the container takes time to become exec-ready.
