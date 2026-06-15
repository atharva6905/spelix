---
name: issue-311-deploy-migrate
description: Issue #311 (T2 CI deploy + Dockerfile) — prod migrate never ran (bare `uv run` synced dev deps into read-only venv + alembic.ini/alembic dir never COPYd). Fix bakes both into the image + uses `uv run --no-dev alembic -c /app/alembic.ini upgrade head` in a 5×retry MIGRATED-gate. Clean all 4 axes → PASS, 2026-06-15, commit 11b3e02.
metadata:
  type: project
---

# Issue #311 — deploy migrate command fix (T2 CI deploy + Dockerfile) → PASS

Commit 11b3e02 (+ hardening 669228a) on base 4c9cdf9. Fixes a prod migrate that NEVER ran: (1) bare `uv run` tried to sync DEV deps into the read-only `--no-dev` venv (PermissionError); (2) alembic.ini + alembic/ were never COPYd into the runtime image (alembic couldn't find script_location). Three files: backend/Dockerfile (+`COPY alembic.ini ./` + `COPY alembic/ ./alembic/`, after `COPY app/ ./app/`, BEFORE `USER spelix`), .github/workflows/ci.yml (migrate line → `uv run --no-dev alembic -c /app/alembic.ini upgrade head` wrapped in `for m in 1 2 3 4 5` retry + MIGRATED flag gate), backend/tests/unit/test_deploy_workflow.py (NEW string-assertion regression guards).

Clean on all four security axes:
- Secret exposure: none. secrets.DROPLET_IP + secrets.DEPLOY_SSH_KEY are with: inputs only, never in script:. Echoes carry only git SHA / $m / $i / $? / static strings. Baked alembic.ini has only inert placeholder `sqlalchemy.url = driver://user:pass@localhost/dbname`; env.py overrides from os.environ["DATABASE_URL"] at runtime — no real credential baked. .dockerignore excludes `.env*`/tests/scripts/.git but NOT alembic/ — new COPYs cannot drag in a secret-bearing file.
- Image content / supply chain: baked alembic/versions/** are the EXISTING already-on-prod migration tree (schema DDL only — RLS auth.uid()=user_id policies, indexes, CHECKs). Diff does NOT modify any migration. No embedded secret, no FK to auth.users, no destructive raw SQL. Spot-checked 002_rls_policies.py.
- Injection: only interpolations are deploy-controlled $PREVIOUS_SHA (quoted, git rev-parse HEAD) + literal loop tokens. Migrate exec is a static command. No PR/user input surface.
- Least privilege: COPYs land before USER spelix → root-owned, world-readable, read-only at runtime; alembic upgrade only reads them. Migrate runs via `docker compose exec -T backend` in the running container — no priv escalation.
- SaMD: N/A (CI YAML + Dockerfile + test; ROLLING BACK / Migration failed echoes are internal CI logs, not UI copy; no banned terms).

INCIDENT-CONTEXT (load-bearing): 5th deploy-script iteration (#275→#300→#299→#303→#305 PROD INCIDENT→reverted #306→#311). #305 broke prod via a migrate gate that FALSE-rolled-back on a post-`up -d` readiness race. #311 answers it: migrate now in a bounded `for m in 1..5` retry w/ sleep 10, rollback gated on MIGRATED flag not first non-zero exit. Success path still needs MIGRATED=1 AND the 6× health-loop curl before exit 0. Rollback (`git checkout "$PREVIOUS_SHA"` + rebuild + exit 1) intact, fails red (code-review added a test asserting the exit 1).

VALIDATED LIVE (2026-06-15): merged b4377889; real Deploy to Production GREEN (3m21s); droplet `alembic current` = `9fffb59ba45f (head)`, containers healthy, /health 200. ADR-DEPLOY-01 closed — PASS-on-inspection confirmed by the real deploy. RE-REVIEW trigger: any future edit to the migrate retry/gate control flow, the COPY surface, or routing of untrusted input into the script. Related: [[issue_303_migrate_rollback]], [[issue_300_ssh_action_pin]], [[issue_275_deploy_ssh_timeout]].
