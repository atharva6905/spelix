---
name: review-issue-311
description: Issue #311 — prod migrate never ran (--no-dev missing + alembic not baked into image) + re-add #303 retry-gate: PASS, 2026-06-15
metadata:
  type: project
---

## Outcome: PASS

Three files changed: `backend/Dockerfile` (+8), `.github/workflows/ci.yml` (deploy script body), `backend/tests/unit/test_deploy_workflow.py` (new, 3 tests → 4 assertions after delta).

### Root defects fixed
1. Bare `uv run alembic` → `uv run --no-dev alembic -c /app/alembic.ini upgrade head` (--no-dev matches the read-only prod venv; -c is explicit-config insurance).
2. `alembic.ini` + `alembic/` never COPYd into image → added `COPY alembic.ini ./` + `COPY alembic/ ./alembic/` after `COPY app/ ./app/`.
3. #303 retry-then-gate re-introduced: 5-attempt loop + MIGRATED flag + health loop gated on MIGRATED=1.

### Key spec details confirmed
- `[ "$m" = 5 ] || sleep 10` — no trailing sleep on final migrate failure. Correct.
- Health loop now inside `if [ "$MIGRATED" = 1 ]` — was previously unconditional. Correct.
- Lines before `if timeout 1320` untouched. No `set -e`. No `alembic downgrade`.
- Rollback block unchanged from #303 design: `git checkout "$PREVIOUS_SHA"` + rebuild + "NOT downgraded" echo + `exit 1`.
- Test regex `r"^\s*COPY\s+alembic/\s"` correctly matches `COPY alembic/ ./alembic/` (space after trailing slash).

**Why:** the prod migrate command had NEVER run successfully since the feature was written — both defects (missing --no-dev and missing alembic files in image) were present from day one.
**How to apply:** any future deploy-script review must trace all 4 control-flow paths (build ok+migrate ok+health ok, build ok+migrate ok+health fail, build ok+migrate fail, build fail) and confirm health loop is gated on MIGRATED.

## Delta review — commit 669228a (PR #313 hardening)

Single assertion added to `test_deploy_has_migrate_retry_then_gate`:
`re.search(r"^\s*exit 1\b", text, re.MULTILINE)` — asserts rollback terminates
with `exit 1` (fail-red), which is explicitly required by the #311 task spec.
In-scope, no over-build, assertion is true against ci.yml line 198. PASS.

## VALIDATED LIVE (2026-06-15)
Merged PR #313 (merge `b4377889`); real Deploy to Production ran GREEN (3m21s) — droplet `alembic current` = `9fffb59ba45f (head)`, containers healthy, /health 200. The migrate command that never ran now runs cleanly. ADR-DEPLOY-01 satisfied. Relates to [[review-issue-303]] (the gate that exposed this), [[review-issue-299]], [[review-issue-300]].
