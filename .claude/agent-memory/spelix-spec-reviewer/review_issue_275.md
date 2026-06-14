---
name: review-issue-275
description: Issue #275 review — appleboy/ssh-action command_timeout raise to 30m for cold rebuild timeouts (T2 CI deploy step): PASS, 2026-06-14
metadata:
  type: project
---

Issue #275 fix: single-line addition of `command_timeout: 30m` to the `appleboy/ssh-action@v1` step's `with:` block in `.github/workflows/ci.yml`.

Key distinctions confirmed:
- `command_timeout` is the correct parameter name (controls how long the remote commands may run); `timeout` is the SSH *connection* timeout — a different parameter.
- Default for appleboy/ssh-action `command_timeout` is 10m; 30m is a genuine raise.
- The optional "split build and restart into separate steps" was NOT done — correct scope discipline.
- Script body, health-check loop, rollback logic, connection timeout, and all other steps/jobs/files were untouched.
- Diff is exactly +1 line; commit dec6644.

**Why:** cold rebuild after lockfile change (#274) triggered full docling model bake (~7 min layer export alone), exceeding the ~10m default before `docker compose up -d` could complete.
**How to apply:** for future CI timeout reviews, verify `command_timeout` vs `timeout` distinction in appleboy/ssh-action — they are different parameters with different effects.
