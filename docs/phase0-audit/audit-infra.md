# Infrastructure & Security Audit — Phase 0

**Date:** 2026-04-09  
**Auditor:** Claude (Sonnet 4.6 sub-agent)  
**Scope:** Dependencies, security, Dockerfile, CI pipeline, Alembic migrations, Docker Compose

---

## 1. Dependency Consistency

### 1.1 Backend — `backend/pyproject.toml`

All production dependencies use `>=` lower-bound pins with no upper bound (e.g. `>=1.18.4`). This is **not** pinned. Reproducible builds rely on `uv.lock` being committed (the pyproject.toml comments out `uv.lock` as optional). If `uv.lock` is present and committed, builds are reproducible; if not, they are floating.

| Package | Declared | Style | Issue |
|---------|----------|-------|-------|
| alembic | `>=1.18.4` | Lower-bound only | [MEDIUM] No upper bound — breaking changes possible |
| anthropic | `>=0.91.0` | Lower-bound only | [MEDIUM] No upper bound |
| arq | `>=0.27.0` | Lower-bound only | [MEDIUM] No upper bound |
| asyncpg | `>=0.31.0` | Lower-bound only | [MEDIUM] No upper bound |
| fastapi | `>=0.135.3` | Lower-bound only | [MEDIUM] No upper bound |
| httpx | `>=0.28.1` | Lower-bound only | [MEDIUM] No upper bound |
| instructor | `>=1.15.1` | Lower-bound only | [MEDIUM] No upper bound |
| matplotlib | `>=3.10.8` | Lower-bound only | [LOW] No upper bound |
| **mediapipe** | `>=0.10.33` | Lower-bound only | **[HIGH] Must be exact-pinned** — MediaPipe is notorious for silent landmark-ordering and API changes between patch releases; a floating mediapipe can silently corrupt CV output |
| numpy | `>=2.4.4` | Lower-bound only | [MEDIUM] NumPy 2.x has breaking API changes vs 1.x |
| opencv-python-headless | `>=4.13.0.92` | Lower-bound only | [LOW] No upper bound |
| pydantic | `>=2.12.5` | Lower-bound only | [MEDIUM] No upper bound |
| python-jose[cryptography] | `>=3.5.0` | Lower-bound only | [MEDIUM] No upper bound |
| python-multipart | `>=0.0.24` | Lower-bound only | [LOW] No upper bound |
| redis | `>=5.3.1` | Lower-bound only | [LOW] No upper bound |
| scipy | `>=1.17.1` | Lower-bound only | [LOW] No upper bound |
| slowapi | `>=0.1.9` | Lower-bound only | [LOW] No upper bound |
| sqlalchemy[asyncio] | `>=2.0.49` | Lower-bound only | [MEDIUM] Should be `>=2.0,<3` to prevent SQLAlchemy 3 breakage |
| supabase | `>=2.28.3` | Lower-bound only | [MEDIUM] No upper bound |
| uvicorn[standard] | `>=0.44.0` | Lower-bound only | [LOW] No upper bound |
| weasyprint | `>=68.1` | Lower-bound only | [LOW] No upper bound |

**Dev dependencies** (`[dependency-groups].dev`): same lower-bound-only pattern. Pyright, pytest, ruff, pytest-asyncio, pytest-cov — all unpinned upper bounds.

**Summary:** No dependency is exactly pinned in `pyproject.toml`. Reproducibility is entirely delegated to `uv.lock`. If `uv.lock` is committed and `uv sync --frozen` is used (as in the Dockerfile), builds are deterministic. The CI `uv sync` (without `--frozen`) is potentially non-deterministic if `uv.lock` is stale.

**Recommendation:** Pin mediapipe to an exact version (e.g. `mediapipe==0.10.33`). For sqlalchemy, add `<3` upper bound. Confirm `uv.lock` is committed.

---

### 1.2 Frontend — `frontend/package.json`

All dependencies use `^` (caret) semver ranges — no exact pins.

| Package | Declared | Style | Issue |
|---------|----------|-------|-------|
| @supabase/supabase-js | `^2.102.1` | Caret | [LOW] Caret allows minor/patch; acceptable for library |
| react | `^19.2.4` | Caret | [LOW] Acceptable |
| react-dom | `^19.2.4` | Caret | [LOW] Acceptable |
| react-router | `^7.14.0` | Caret | [LOW] Acceptable |
| recharts | `^3.8.1` | Caret | [LOW] Acceptable |
| @vitejs/plugin-react | `^6.0.1` | Caret | [LOW] Acceptable |
| typescript | `~6.0.2` | Tilde (patch-only) | [LOW] More conservative — good |
| vite | `^8.0.4` | Caret | [LOW] Acceptable |
| vitest | `^4.1.3` | Caret | [LOW] Acceptable |
| tailwindcss | `^4.2.2` | Caret | [LOW] Acceptable |

**`package-lock.json`** is expected to exist (CI uses `npm ci`) which locks exact versions. If committed, the frontend is reproducibly locked despite `^` ranges in `package.json`. This is the npm standard pattern and is acceptable.

---

### 1.3 Version Enforcement

| Constraint | Location | Present? | Issue |
|---|---|---|---|
| Python 3.12 | `backend/.python-version` | YES — `3.12` | OK |
| Python 3.12 | `backend/pyproject.toml` | YES — `requires-python = ">=3.12"` | OK (no upper bound — acceptable) |
| Python 3.12 | `backend/Dockerfile` | YES — `FROM python:3.12-slim` | OK |
| Python 3.12 | CI `.github/workflows/ci.yml` | YES — `PYTHON_VERSION: "3.12"` | OK |
| Node version | `frontend/.nvmrc` | **MISSING** | [MEDIUM] No `.nvmrc` or `.node-version` in frontend — local dev uses whatever Node is active |
| Node version | `frontend/package.json engines` | **MISSING** | [MEDIUM] No `engines` field in `package.json` |
| Node version | CI | YES — `NODE_VERSION: "22"` | OK for CI, but inconsistency with local dev (CLAUDE.md says Node 20+, CI uses Node 22) |

**[MEDIUM]** CLAUDE.md states "Node 20+" but CI uses Node 22. Neither is wrong but the discrepancy can cause local/CI divergence.

---

### 1.4 Unused / Missing Dependency Cross-Check

**Backend — packages declared but import not found in `app/`:**

| Package | Imported in app/? | Notes |
|---------|-----------|-------|
| alembic | YES (alembic/env.py, migration files) | OK |
| anthropic | YES (app/services/coaching.py) | OK |
| arq | YES (app/workers/) | OK |
| asyncpg | YES (app/db.py via SQLAlchemy driver) | OK (implicit) |
| fastapi | YES | OK |
| httpx | YES (app/api/deps.py JWKS fetch) | OK |
| instructor | YES (app/services/coaching.py) | OK |
| matplotlib | YES (app/cv/artifact_generation.py) | OK |
| mediapipe | YES (app/cv/pose_extraction.py) | OK |
| numpy | YES (multiple CV files) | OK |
| opencv-python-headless | YES (cv2 imports in CV files) | OK |
| pydantic | YES | OK |
| python-jose[cryptography] | YES (app/api/deps.py) | OK |
| python-multipart | Implicit (FastAPI form handling) | OK |
| redis | YES (app/workers/settings.py) | OK |
| scipy | YES (app/cv/signal_processing.py) | OK |
| slowapi | YES (app/main.py, app/rate_limit.py) | OK |
| sqlalchemy[asyncio] | YES (app/db.py, models/) | OK |
| supabase | YES (app/services/storage.py, workers/) | OK |
| uvicorn[standard] | Runtime server | OK |
| weasyprint | YES (app/services/pdf.py) | OK |

No unused backend dependencies detected.

**Frontend — packages declared but import not found in `src/`:**

| Package | Imported in src/? | Notes |
|---------|-----------|-------|
| @supabase/supabase-js | YES (src/lib/supabase.ts, 23 files) | OK |
| react / react-dom | YES | OK |
| react-router | YES (src/routes.tsx, src/App.tsx) | OK |
| recharts | YES (src/components/TrendChart.tsx) | OK |
| @vitejs/plugin-react | YES (vite.config.ts) | OK |
| @tailwindcss/vite | YES (vite.config.ts) | OK |
| tailwindcss | YES (CSS imports) | OK |
| typescript / vite / vitest | Dev tooling | OK |
| @testing-library/* | YES (test files) | OK |
| @testing-library/dom | Transitive dep of @testing-library/react | [LOW] Listed as direct dep in `dependencies` (not `devDependencies`) — should be `devDependencies` |
| openapi-typescript | Used by `generate-types` script | Not in package.json — [MEDIUM] the `npm run generate-types` script calls `openapi-typescript` but the package is not declared in package.json |

**[MEDIUM]** `openapi-typescript` is called in `package.json` scripts (`generate-types`) but is not declared as a dependency or devDependency. Running `npm run generate-types` will fail on a clean install.

**[LOW]** `@testing-library/dom` is listed under `dependencies` instead of `devDependencies`. It is a test-only package and should not be in the production bundle.

---

## 2. Security Findings

### 2.1 `.gitignore` Coverage

| Pattern | In .gitignore? | Notes |
|---------|---------------|-------|
| `.env` | YES (line 147) | OK |
| `.env.prod` | YES (line 148) | OK |
| `.env.local` | **MISSING** | [HIGH] `.env.local` is a common Vite/Vercel convention for local secrets; it is not listed in .gitignore |
| `.envrc` | YES (line 149) | OK |
| `.env.*` wildcard | **MISSING** | [MEDIUM] No wildcard catch — `.env.staging`, `.env.test`, etc. could be accidentally committed |

**[HIGH]** `.env.local` is a first-class Vite convention (Vite loads `.env.local` automatically) and is not in the gitignore. A developer adding local secrets to `.env.local` would commit them inadvertently.

**Recommendation:** Add `.env.local` and `.env.*` (with exceptions for `.env.example`) to `.gitignore`.

---

### 2.2 `.env.example` Review

**File:** `C:/Users/athar/projects/spelix/.env.example`

All values are placeholders (`xxxxx`, `eyJ...`, `sk-ant-...`, `super-secret-jwt-token-...`). No real secrets present. Format is correct.

**[LOW]** The `SUPABASE_ANON_KEY` placeholder `eyJ...` looks like a real JWT prefix — consider using a clearer placeholder like `<your-supabase-anon-key>` to make it unambiguous.

---

### 2.3 `SUPABASE_SERVICE_ROLE_KEY` in Frontend

Grep of `frontend/src/` for `SUPABASE_SERVICE_ROLE_KEY`: **no matches found**. The frontend correctly uses only `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.

The backend uses `SUPABASE_SERVICE_KEY` (note: not `SUPABASE_SERVICE_ROLE_KEY` — the env var name differs from the `.env.example` key name).

**[MEDIUM]** Naming inconsistency: `.env.example` declares `SUPABASE_SERVICE_ROLE_KEY` but the backend code reads `SUPABASE_SERVICE_KEY` (found in `analyses.py`, `analysis_worker.py`, `storage.py`, `cleanup.py`). In production, if `.env.prod` follows the `.env.example` naming (`SUPABASE_SERVICE_ROLE_KEY`), the backend will silently receive `None` for the service key and Storage operations will fail. This is a **runtime correctness bug** with a security dimension (silent auth downgrade).

**Recommendation:** Align env var name to one canonical form in both `.env.example` and all code. Use `SUPABASE_SERVICE_ROLE_KEY` to match Supabase documentation convention.

---

### 2.4 CORS Configuration

**File:** `backend/app/main.py`

Production allowed origins are exactly `["https://spelix.app", "https://www.spelix.app"]`. Development origins (`localhost:5173`, `localhost:3000`) are added only when `SPELIX_ENV=development`. A `VERCEL_PREVIEW_ORIGIN` escape hatch allows a single additional origin via env var.

**[LOW]** The `VERCEL_PREVIEW_ORIGIN` escape hatch allows a single arbitrary origin string to be added at runtime. If this env var were set on the production droplet (accidentally or via a compromised deploy pipeline), it would expand CORS to an attacker-controlled origin. Consider restricting this to a validated `*.vercel.app` pattern, or removing it entirely and handling preview deployments another way.

Otherwise CORS is correctly configured: no wildcard, credentials allowed, explicit methods, TUS-specific headers present.

---

### 2.5 JWT Validation (`backend/app/api/deps.py`)

| Check | Status | Notes |
|-------|--------|-------|
| Expiration (`exp`) verified | YES | `python-jose` verifies `exp` by default |
| Audience (`aud`) verified | YES | `audience=_JWT_AUDIENCE` = `"authenticated"` |
| Issuer (`iss`) verified | **MISSING** | [MEDIUM] No `issuer=` parameter passed to `jwt.decode()` — any valid Supabase-signed token from a different project could pass validation if it has `aud=authenticated` |
| Signature verified | YES | ES256/RS256 via JWKS, HS256 fallback via secret |
| Algorithm whitelist | YES | `["ES256", "RS256"]` for JWKS, `["HS256"]` for fallback |
| Token extraction | YES | Standard Bearer extraction |
| JWKS cache TTL | YES | 60-minute cache with monotonic clock |

**[MEDIUM]** Missing issuer validation. `jwt.decode()` should include `issuer=f"{supabase_url}/auth/v1"` to prevent tokens from a different Supabase project being accepted. Supabase JWTs set `iss` to the project URL.

**[LOW]** The broad `except Exception` on the JWKS path (line 114) silently swallows all errors including network failures — if JWKS fetch fails and `SUPABASE_JWT_SECRET` is also unset, the user gets a 401 with no logged root cause. Add specific logging for JWKS fetch failures before the fallback.

---

### 2.6 Rate Limiting

**File:** `backend/app/rate_limit.py`

Rate limiting is per authenticated user (extracts JWT `sub` claim from Authorization header), falling back to remote IP on auth failure. Uses Redis as storage backend in production (`REDIS_URL` env var), in-memory in tests (`memory://`).

This is correctly implemented per-user, not per-IP. No issues found.

**[LOW]** The JWT is decoded without signature verification in the rate limiter's `_get_user_key` function (by design — full verification happens in `get_current_user`). The comment acknowledges this. The risk is that a crafted `sub` claim in an unsigned token could spoof a different user's rate limit bucket, allowing an attacker to exhaust another user's 10/day quota. However, since the request still requires a valid signed JWT to proceed (verified by `get_current_user`), the practical impact is low — an attacker would need a valid token anyway.

---

### 2.7 Redis Binding

**File:** `docker-compose.prod.yml`

```yaml
redis:
  ports:
    - "127.0.0.1:6379:6379"
```

Redis is correctly bound to `127.0.0.1` (loopback only) in production. Not exposed to the public network. No authentication configured on Redis (no `requirepass`), but since it's loopback-only this is acceptable for a single-tenant droplet.

**[LOW]** Redis has no password (`requirepass`). If the droplet is ever compromised or another service runs on the same host, Redis is immediately accessible. Consider adding `--requirepass` via a `command:` override and setting `REDIS_URL=redis://:password@localhost:6379/0`.

---

### 2.8 Hardcoded Secrets Search

Searched `backend/app/` for patterns matching hardcoded API keys, JWT secrets, and passwords. No real secrets found. The CI workflow file (`ci.yml`) contains:

```yaml
SUPABASE_JWT_SECRET: "test-jwt-secret-for-ci-only"
```

This is a test-only value, clearly labeled, and not a real Supabase secret. Acceptable.

No hardcoded secrets detected in source code.

---

## 3. Dockerfile Review

**File:** `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim AS base
```

| Check | Status | Notes |
|-------|--------|-------|
| Base image | `python:3.12-slim` | OK — matches Python version constraint |
| Multi-stage build | **NO** | [MEDIUM] Single stage only — dev tool `uv` binary is included, but `uv sync --no-dev` is used so dev packages are excluded from the layer. Still, a multi-stage build would allow stripping uv itself from the final image |
| Dev dependencies excluded | Partially — `uv sync --frozen --no-dev` | OK — dev packages not installed, but test files and scripts are still COPY'd into the image |
| `.dockerignore` | **MISSING** | [HIGH] No `.dockerignore` found in the project. Without it, `COPY . .` copies everything including `.env` files, `tests/`, `__pycache__/`, `.git/`, `uv.lock`, etc. into the image |
| `libgl1` (not `libgl1-mesa-glx`) | YES | OK — matches Debian trixie+ requirement per CLAUDE.md |
| opencv-python-headless | YES (in pyproject.toml) | OK |
| CMD uses `--no-dev` | YES — `uv run --no-dev uvicorn ...` | OK |
| Non-root user | **MISSING** | [HIGH] Container runs as root. No `USER` directive. If a container escape occurs, the attacker gains root on the container filesystem |
| Port exposed | `EXPOSE 8000` | OK |
| `/tmp/spelix` created | YES | OK — needed for video processing |

**[HIGH]** No `.dockerignore`. The `COPY . .` in the Dockerfile will copy any `.env.prod` or `.env` file if it exists in the build context. In a CI/CD scenario where the `.env.prod` is present on the droplet during `docker compose build`, secrets could be baked into the image layer.

**[HIGH]** Container runs as root. Standard hardening requires adding a non-root user:
```dockerfile
RUN adduser --disabled-password --gecos "" appuser
USER appuser
```

**[MEDIUM]** Single-stage build — all of `tests/`, `scripts/`, and the `uv` binary ship in the production image. A multi-stage build would produce a smaller, cleaner production artifact.

**[MEDIUM]** `uv` is installed via `COPY --from=ghcr.io/astral-sh/uv:latest` — the `latest` tag is not pinned. A future `uv` release could change behavior. Pin to a specific version digest or tag (e.g. `ghcr.io/astral-sh/uv:0.6.x`).

---

## 4. CI Pipeline

**File:** `.github/workflows/ci.yml`

| Check | Status | Notes |
|-------|--------|-------|
| Ruff lint | YES — `uv run ruff check .` | OK |
| Pyright type check | YES — `uv run pyright app/` | OK (source-only, not tests) |
| pytest | YES — with `--cov-fail-under=90` | OK |
| vitest | YES — `npx vitest run --coverage --reporter=verbose` | OK |
| TypeScript check (`tsc --noEmit`) | YES | OK |
| Secret scanning | YES — TruffleHog (`--only-verified`) | OK |
| Deploy depends on all test jobs | YES — `needs: [backend-lint, backend-test, frontend-lint, frontend-test, secret-scan]` | OK |
| Deploy only on `main` push | YES — `if: github.ref == 'refs/heads/main' && github.event_name == 'push'` | OK |
| PR check runs | YES — trigger on `pull_request` too | OK |

**[MEDIUM]** Frontend lint job runs `tsc --noEmit` but does **not** run `eslint` or any linter. There is no ESLint config in the project — this is a deliberate omission, but means style/lint issues in TypeScript are only caught by `tsc` strict mode. Acceptable if intentional.

**[MEDIUM]** CI `backend-test` job runs `uv sync` (without `--frozen`). If `uv.lock` is stale, this silently upgrades packages. Should be `uv sync --frozen` to match the Dockerfile behavior.

**[LOW]** TruffleHog runs with `--only-verified` — unverified secrets (e.g. rotated keys still in git history) are not flagged. Consider adding `--since-commit HEAD~1` for PR checks and a full history scan on main.

**[LOW]** CI uses `NODE_VERSION: "22"` at the workflow level, but this is not enforced locally (no `.nvmrc`). Recommend adding `frontend/.nvmrc` with `22`.

**[LOW]** The deploy step runs `docker compose ... up -d --build` then immediately `alembic upgrade head` via `exec -T`. If the build takes longer than the `sleep 5` before the health check, the health check may pass before migrations complete. The `sleep 5` is fragile — Alembic is called before the sleep, so this is likely fine in practice, but the ordering could be clearer.

**[LOW]** `appleboy/ssh-action@v1` is pinned to a major version tag, not a SHA digest. Supply-chain best practice is to pin Actions to full SHA (`appleboy/ssh-action@abc123...`).

---

## 5. Alembic Migrations

**Files:** `backend/alembic/versions/901e432196c4_001_initial_schema.py`, `backend/alembic/versions/002_rls_policies.py`

### 5.1 Migration 001 — Initial Schema

**Status CHECK constraint:**
```python
sa.CheckConstraint(
    "status IN ('queued','quality_gate_pending','quality_gate_rejected','processing','coaching','completed','failed')",
    name='ck_analyses_status'
)
```

SRS Section 5.2a defines 7 valid status values per the worker status transition sequence documented in backend/CLAUDE.md: `queued → quality_gate_pending → (quality_gate_rejected | processing) → coaching → completed`, plus `failed`.

Count of values in CHECK constraint: **7** (`queued`, `quality_gate_pending`, `quality_gate_rejected`, `processing`, `coaching`, `completed`, `failed`). This matches the 7-value requirement exactly. OK.

**Required indexes (SRS Section 7.3):**

| Index | Required | Present | Notes |
|-------|----------|---------|-------|
| `ix_analyses_user_created ON analyses (user_id, created_at DESC)` | YES | YES — line 54 | OK |
| `ix_rep_metrics_analysis ON rep_metrics (analysis_id)` | YES | YES — line 94 | OK |
| `ix_coaching_results_analysis ON coaching_results (analysis_id)` | YES | YES — line 82 | OK |

All three SRS-required indexes are present.

**`downgrade()` function:** Present and complete — drops all indexes and tables in correct reverse dependency order (rep_metrics → coaching_results → user_profiles → analyses). OK.

**JSONB columns:** All JSONB columns (`summary_json`, `quality_gate_result`, `structured_output_json`, `retrieved_sources_json`, `agent_trace_json`, `metrics_json`) correctly use `postgresql.JSONB(astext_type=sa.Text())`. OK.

**Non-nullable columns (SRS 7.3):** `id`, `user_id`, `status`, `exercise_type`, `exercise_variant`, `retry_count`, `flagged_for_review`, `is_golden_dataset`, `created_at`, `updated_at` — all present and `nullable=False`. OK.

**[LOW]** `analyses.updated_at` uses `server_default=sa.text('now()')` but has no `onupdate` trigger. SQLAlchemy ORM `onupdate` is not set either (this is an asyncio context, so ORM events are the mechanism). If rows are updated via raw SQL (e.g. Alembic data migrations, direct Supabase dashboard edits), `updated_at` will not auto-update. A Postgres trigger (`BEFORE UPDATE` trigger calling `now()`) would be more robust. This is a common oversight.

---

### 5.2 Migration 002 — RLS Policies

**`downgrade()` function:** Present and complete — drops all policies in reverse order and disables RLS on all four tables. OK.

**Policy completeness:** All four tables (`analyses`, `user_profiles`, `rep_metrics`, `coaching_results`) have SELECT, INSERT, UPDATE, and DELETE policies. Indirect ownership via subquery for `rep_metrics` and `coaching_results` is correct.

**[MEDIUM]** The RLS policies for `rep_metrics` and `coaching_results` use correlated subqueries (`analysis_id IN (SELECT id FROM analyses WHERE user_id = auth.uid())`). At high row counts this can be slow. A `JOIN` or a policy using an `EXISTS` clause with an index hint would perform better. Acceptable at Phase 0 scale but worth noting for Phase 1+.

---

## 6. Docker Compose

### 6.1 Production — `docker-compose.prod.yml`

| Check | Status | Notes |
|-------|--------|-------|
| Redis bound to 127.0.0.1 | YES — `"127.0.0.1:6379:6379"` | OK |
| Backend bound to 127.0.0.1 | YES — `"127.0.0.1:8000:8000"` | OK — Caddy proxies externally |
| Env vars via env_file | YES — `.env.prod` | OK |
| Redis health check | YES | OK |
| Backend health check | YES — `/health` endpoint | OK |
| Worker has no exposed port | YES — no `ports:` on worker | OK |
| Restart policy | YES — `unless-stopped` on all | OK |
| Redis volume persistent | YES — `redis-data:/data` | OK |
| Worker shares same image as backend | YES — same `build:` context | OK — saves image build time |

**[MEDIUM]** The `worker` service and `backend` service use the same Dockerfile with no `command:` override distinction beyond the worker's explicit `command:`. Both services receive the same `env_file: .env.prod`. This means the `SPELIX_ENV` variable (used for CORS) is shared — if the worker ever starts the FastAPI app (e.g. during a misconfiguration), it would use the same origin settings. Low risk but worth noting.

**[LOW]** No `REDIS_URL` explicit env var in the compose file — it's sourced from `.env.prod`. If `.env.prod` is missing `REDIS_URL`, both backend and worker silently fall back to `redis://localhost:6379` (the default in `workers/settings.py`). This would work by coincidence on the same droplet but is fragile.

**[LOW]** No development `docker-compose.yml` found at the root. CLAUDE.md documents `docker compose up -d` for dev, implying one exists or is expected. It may be present but was inaccessible during this audit (read permission denied for some root-level files). If absent, local dev relies solely on running services individually.

---

## Summary: Prioritised Findings

### [CRITICAL]
_None found._

### [HIGH]
| # | Finding | File |
|---|---------|------|
| H-1 | No `.dockerignore` — `COPY . .` may bake secrets into image layers | `backend/Dockerfile` |
| H-2 | Container runs as root — no `USER` directive in Dockerfile | `backend/Dockerfile` |
| H-3 | `.env.local` not in `.gitignore` — Vite loads it automatically, devs may store secrets there | `.gitignore` |

### [MEDIUM]
| # | Finding | File |
|---|---------|------|
| M-1 | `mediapipe` not exactly pinned — floating version can silently corrupt CV output | `backend/pyproject.toml` |
| M-2 | `SUPABASE_SERVICE_ROLE_KEY` (`.env.example`) vs `SUPABASE_SERVICE_KEY` (all backend code) naming mismatch — service key silently `None` in prod if `.env.prod` uses example naming | `backend/app/api/v1/analyses.py`, `workers/`, `services/storage.py` |
| M-3 | JWT issuer not validated — tokens from other Supabase projects accepted | `backend/app/api/deps.py` |
| M-4 | `openapi-typescript` missing from `package.json` — `npm run generate-types` fails on clean install | `frontend/package.json` |
| M-5 | No `.nvmrc` in frontend and `package.json` has no `engines` field — Node version unenforced locally (CLAUDE.md says 20+, CI uses 22) | `frontend/` |
| M-6 | CI uses `uv sync` without `--frozen` — can silently upgrade packages vs lockfile | `.github/workflows/ci.yml` |
| M-7 | `uv` Docker layer pinned to `:latest` — unpinned supply chain dep | `backend/Dockerfile` |
| M-8 | Single-stage Dockerfile — test files, scripts, and uv binary ship in production image | `backend/Dockerfile` |
| M-9 | No wildcard `.env.*` catch in `.gitignore` | `.gitignore` |

### [LOW]
| # | Finding | File |
|---|---------|------|
| L-1 | `@testing-library/dom` listed in `dependencies` instead of `devDependencies` | `frontend/package.json` |
| L-2 | `VERCEL_PREVIEW_ORIGIN` escape hatch accepts arbitrary origin string with no validation | `backend/app/main.py` |
| L-3 | Broad `except Exception` on JWKS path swallows JWKS fetch failures silently | `backend/app/api/deps.py` |
| L-4 | Rate limiter reads JWT `sub` without signature verification (by design, acknowledged in code) | `backend/app/rate_limit.py` |
| L-5 | Redis has no password — acceptable for loopback-only but adds risk if droplet is compromised | `docker-compose.prod.yml` |
| L-6 | `analyses.updated_at` has no Postgres `BEFORE UPDATE` trigger — only tracks creation time unless ORM always updates it | `backend/alembic/versions/901e432196c4_001_initial_schema.py` |
| L-7 | TruffleHog uses `--only-verified` — rotated/unverified secrets not flagged | `.github/workflows/ci.yml` |
| L-8 | GitHub Actions `appleboy/ssh-action@v1` pinned to major tag, not SHA digest | `.github/workflows/ci.yml` |
| L-9 | CI deploy health check `sleep 5` is fragile timing assumption | `.github/workflows/ci.yml` |
| L-10 | `.env.example` placeholder values (`eyJ...`) look like real JWT prefixes | `.env.example` |
| L-11 | RLS subquery policies on `rep_metrics`/`coaching_results` may be slow at scale | `backend/alembic/versions/002_rls_policies.py` |

---

## Recommended Immediate Actions (Before Phase 1)

1. **[H-1] Add `.dockerignore`** to `backend/` excluding `.env*`, `tests/`, `__pycache__/`, `.git/`, `*.pyc`.
2. **[H-2] Add non-root user** to `backend/Dockerfile` (`adduser appuser`, `USER appuser`).
3. **[H-3] Add `.env.local` to `.gitignore`** and add `.env.*` wildcard with `!.env.example` exception.
4. **[M-2] Fix env var naming** — align all backend code and `.env.example` to `SUPABASE_SERVICE_ROLE_KEY`.
5. **[M-1] Pin mediapipe** to exact version in `pyproject.toml` (e.g. `mediapipe==0.10.33`).
6. **[M-3] Add issuer validation** to JWT decode: `issuer=f"{supabase_url}/auth/v1"`.
7. **[M-4] Add `openapi-typescript`** to `frontend/package.json` devDependencies.
8. **[M-5] Add `frontend/.nvmrc`** with `22` and add `"engines": {"node": ">=22"}` to `package.json`.
9. **[M-6] Change CI `uv sync` to `uv sync --frozen`** in `backend-test` job.
