---
name: review-issue-299
description: Issue #299 review — deploy rollback budget: timeout 1320 + if/then migrate guard in CI deploy script (T2 CI): PASS, 2026-06-14
metadata:
  type: project
---

Issue #299 fix: wraps `docker compose up -d --build` in `if timeout 1320 ...; then ... else ... fi` in `.github/workflows/ci.yml` Deploy via SSH step.

Control-flow paths confirmed:
- (a) Build succeeds + health passes: `exit 0` inside the for-loop — no rollback triggered.
- (b) Build succeeds + health fails all 6: falls through to "Health check failed" echo, then `fi`, then rollback + `exit 1`.
- (c) Build times out/fails: `else` branch echo, then `fi`, then rollback + `exit 1`. Migrate NOT run.
- `alembic upgrade head` is inside `then` (line 173), before the `for` loop (line 174) — correct.
- No path runs migrate after a failed build.

Unchanged items confirmed:
- `uses: appleboy/ssh-action@0ff4204d59e8e51228ff73bce53f80d53301dee2` pin (from #300): unchanged.
- `command_timeout: 30m` (from #275): unchanged.
- `host`, `username`, `key`, `needs`, `if` guard, all other jobs: unchanged.
- Rollback block (git checkout + rebuild + "NOT downgraded" warning + exit 1): unchanged.
- 1320 seconds == 22 minutes: correct per design.
- Em-dash in "Health check failed after 6 attempts — ROLLING BACK" and "Primary build timed out or failed (exit $?) — ROLLING BACK": present.

No over-build: only the `script:` body changed (+10 lines / -7 lines net).

**Why:** Without a timeout on the primary build, a hung docker build could exhaust the 30m command_timeout, leaving zero budget for the rollback rebuild — causing the rollback to be killed mid-flight.
**How to apply:** For future CI deploy reviews, check that `timeout <seconds>` wraps only the build, NOT migrate or health-check (those need their own natural budget inside the 30m window).
