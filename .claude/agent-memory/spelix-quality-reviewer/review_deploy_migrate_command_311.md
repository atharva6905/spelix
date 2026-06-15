---
name: review-deploy-migrate-command-311
description: Issue #311 review — fix prod migrate that never ran (bare uv run synced dev deps into read-only --no-dev venv; alembic.ini+alembic/ never COPYd); PASS 0 findings, 2026-06-15
metadata:
  type: project
---

# Issue #311 — fix prod deploy migrate command → PASS (0 findings)

Commit `11b3e02` (+ hardening `669228a`) on base `4c9cdf9`. Two root causes fixed: (1) bare `uv run alembic` synced DEV deps into the read-only `--no-dev` venv → Permission denied; (2) `alembic.ini`+`alembic/` were never in the image → no `script_location`. Fix: Dockerfile `COPY alembic.ini ./` + `COPY alembic/ ./alembic/` (before `USER spelix`); ci.yml migrate line → `uv run --no-dev alembic -c /app/alembic.ini upgrade head`, wrapped in the #303-redesign 5×retry MIGRATED-gate.

## Verified runtime facts (reusable for any future migrate/alembic-in-container review)
- `alembic>=1.18.4` is a MAIN dep in backend/pyproject.toml (NOT dev) → `uv run --no-dev alembic` resolves it. Always confirm this when reviewing a `--no-dev` invocation of any tool.
- `script_location = %(here)s/alembic` in alembic.ini: `%(here)s` = the INI file's own dir, so `-c /app/alembic.ini` → `/app/alembic` REGARDLESS of cwd. No cwd dependency for script_location.
- `prepend_sys_path = .` DOES depend on cwd — but `docker compose exec` defaults to the image WORKDIR (`/app`), where the `app/` package lives, so `from app.models import Base` in env.py resolves. If a future exec sets a different workdir, this breaks.
- env.py needs ONLY `DATABASE_URL` env (present via .env.prod) + already sets `connect_args={"statement_cache_size": 0}` (PgBouncer-safe, NullPool). No app/config beyond `app/` package.
- COPY lands before `USER spelix` → root-owned world-readable; alembic only reads. `__pycache__` excluded by backend/.dockerignore line 3. Baking migrations = text files, negligible image size.

## Shell-logic (errexit OFF — see [[review_deploy_rollback_budget_299]], [[review_deploy_migrate_rollback_303]])
- This is the #303-redesign retry-then-gate carried forward (the #305 false-rollback was reverted #306/#310; redesign re-applied here). 3 if / 3 fi balanced. Migrate-5×fail else AND health-6×fail fall-through AND build-fail outer-else all route to the SHARED rollback. `exit 0` only inside health loop.
- The 5×retry (×10s sleeps, ~40s) is the readiness-race mitigation satisfying #303 heuristic (d): `exec -T backend` after `up -d` can hit a not-ready backend; retry absorbs it instead of false-rolling-back.
- `\`-continuation inside `script: |` literal block scalar is SAFE (bash collapses continuation indentation).
- Improvement over #303 redesign: loop tail `[ "$m" = 5 ] || sleep 10` skips the wasted final-attempt sleep.
- Rollback path (`up -d --build` after checkout) does NOT re-migrate — same documented intentional no-downgrade gap (#275 OBS-2).

## Test pattern (string-assertion deploy guards — the RIGHT tool when CI can't run a real deploy)
backend/tests/unit/test_deploy_workflow.py parses ci.yml + Dockerfile text. Robust because:
- multiline + `^\s*` + `\s+` regexes survive trivial reformatting.
- migrate-line filter `"alembic" in ln and "upgrade head" in ln` excludes the comment line AND the `\`-split line. Keys assertions on the real migrate line.
- negative bare-`uv run alembic` guard works BECAUSE `--no-dev` sits between `uv run` and `alembic`.
- code-review hardening (669228a) added a 4th assertion: rollback must end in `exit 1` (fail-red) — locks the swallowed-failure invariant.

## VALIDATED LIVE (2026-06-15) — ADR-DEPLOY-01 closed
Merged `b4377889`; real Deploy to Production GREEN (3m21s). Droplet `alembic current` = `9fffb59ba45f (head)`, backend+worker+redis healthy, /health 200. PASS-on-inspection was confirmed by the real deploy — the migrate command that NEVER ran now runs cleanly. RE-REVIEW trigger: any future edit to the migrate retry/gate control flow or the COPY surface.
