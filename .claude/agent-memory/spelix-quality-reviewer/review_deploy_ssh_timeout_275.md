---
name: review-deploy-ssh-timeout-275
description: Deploy SSH command_timeout 30m fix (#275) — appleboy/ssh-action timeout shape, why 30m is sane, and the shared-budget rollback gap
metadata:
  type: project
---

# Deploy via SSH step — command_timeout / cold-rebuild / rollback (#275)

The CI `deploy` job (`.github/workflows/ci.yml`, job "Deploy to Production", lines ~154-183) is a SINGLE `appleboy/ssh-action@v1` step running an inline remote `script:` on `spelix-droplet`. There is NO `timeout-minutes` at job or step level → the GitHub-hosted runner default (6h) is the only outer ceiling, so the action's `command_timeout` is the ONLY effective ceiling on the remote script.

**Why:** #275 — `appleboy/ssh-action` `command_timeout` defaults to ~10m. A cold rebuild (lockfile change invalidates uv-sync layer → full rebuild incl. #263 docling model bake; `exporting layers` ~7min) overran 10m; the timeout fired before `docker compose up -d` ran, leaving prod on the old image while the checkout had already advanced. Fix `dec6644`: add `command_timeout: 30m`.

**How to apply (durable for future deploy-pipeline reviews):**
- 30m is the right magnitude: ~3x headroom over the observed >10m cold build, well under the 6h runner default, deploy step is serial/once-per-merge so a 30m hang-cost is acceptable. Do NOT flag 30m as too tight or absurd.
- SHARED-BUDGET ROLLBACK GAP (known, accepted — follow-up, NOT this PR's scope): `command_timeout` covers the ENTIRE remote script — primary `up -d --build`, alembic upgrade, the 6x10s=60s health loop, AND the failure-path rollback (`git checkout $PREVIOUS_SHA` + a SECOND `up -d --build`). A primary build eating most of the 30m before the health loop fails can leave too little budget for the rollback rebuild → prod left half-deployed. Mitigant: rollback rebuilds PREVIOUS SHA layers (usually cached → fast). Real fix if ever pursued: per-phase budgets / dedicated rollback timeout — open a follow-up issue, do NOT expand the timeout PR.
- Rollback path does NOT downgrade alembic migrations (script echoes a warning). Known/intentional.
- Related: [[insight-deploy-ci-false-negative]] (#211 — red Deploy step on lockfile-only merges can be a false negative; verify droplet SHA directly). #263 docling model bake is the layer that makes cold builds slow (disk-bake, not RAM).
- Provenance for `30m`: commit `dec6644` message is sufficient; an inline YAML comment is optional polish, not required.
