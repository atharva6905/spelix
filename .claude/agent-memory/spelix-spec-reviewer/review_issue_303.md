---
name: review-issue-303
description: Issue #303 review — nest alembic upgrade head in its own if-then to gate health loop and rollback on migrate failure (T2 CI): PASS, 2026-06-14
metadata:
  type: project
---

Issue #303 fix: wraps bare `docker compose ... alembic upgrade head` (from #299 state) in an inner `if ... then ... else ... fi` nested inside the build-success outer `then` in `.github/workflows/ci.yml`.

The bug being fixed: previously alembic was a bare unchecked line — a migration failure was silently ignored and the health-check loop ran anyway, giving a false green or a confusing health rollback instead of a migrate rollback.

Control-flow paths confirmed (all 4):
- (a) Build ok + migrate ok + health pass: exit 0 inside for-loop — no rollback. L172 outer then -> L173 inner then -> L174-178 loop -> exit 0.
- (b) Build ok + migrate ok + health fail x6: inner then -> loop exhausts -> L179 "Health check failed" echo -> L182 fi -> L185 fi -> L186 rollback -> exit 1.
- (c) Build ok + migrate FAIL (the new path): L173 inner if -> exit non-zero -> L180 else -> L181 "Migration failed — ROLLING BACK" -> L182 fi -> L185 fi -> L186 rollback -> exit 1. Health loop NOT run.
- (d) Build timeout/fail: L172 outer else -> L184 "Primary build timed out or failed (exit $?) — ROLLING BACK" -> L185 fi -> L186 rollback -> exit 1.

Key spec confirmations:
- No `timeout` prefix on the alembic command (no timeout bound on migrate). Confirmed.
- No `alembic downgrade` added anywhere. Confirmed.
- Rollback block L186-189 byte-identical to #299 state. Confirmed.
- command_timeout: 30m (#275), SHA pin 0ff4204d (#300), timeout 1320 (#299), host/username/key/needs/if guard: ALL UNCHANGED. Confirmed.
- Em-dashes: 3x "— ROLLING BACK" + "NOT downgraded —" all present. Confirmed.
- Diff confined to script: body only (+8 lines / -7 lines). No other files touched. No over-build.

**Why:** bare unchecked alembic run let migration failures silently fall through to health-check loop, masking the real failure mode and running health against a possibly corrupt DB state.
**How to apply:** in CI deploy script reviews, each stage (build / migrate / health) must either be the condition of an if-then or have explicit non-zero exit handling — bare commands inside a build-success then are insufficient if failure should abort downstream stages.
