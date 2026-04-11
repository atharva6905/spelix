# Session 12 Handoff — Storage Outage Layered Fix + Insights TZ Bug + Config Block

## Completed this session

| PR | Commit | Description |
|----|--------|-------------|
| **#3** | `94dd0fa` | `fix(api)`: wire Supabase client into `_make_storage_service` + initial `@app.exception_handler(Exception)` with CORS headers. Layer 1 of the dormant Phase 0 storage bug — replaced the `pass`-branch with `supabase.create_client(url, key)`. CI green, merged. E2E showed POST /analyses still 500'd → diagnosed Layer 2. |
| **#4** | `754393c` | `fix(api,worker)`: use `acreate_client` (async) — sync client breaks awaited storage methods. PR #3 used sync `create_client`; `StorageService.generate_signed_upload_url` does `await self._client.storage.from_(...).create_signed_upload_url(...)` which raises `TypeError: object dict can't be used in 'await' expression` on a sync client. Same dormant bug existed in `analysis_worker._build_supabase_client` and `cleanup._build_supabase_client` — never fired because no upload had ever succeeded. Module-level cache prevents creating a new client per request. Enriched the global exception handler to expose `detail.type` + `detail.message` so future bugs surface in the browser without server access. CI green, merged. |
| **#5** | `02fcc88` | `fix(insights,cleanup)`: strip tzinfo on cutoff datetimes — naive DB column. `analyses.created_at` is `TIMESTAMP WITHOUT TIME ZONE`; `InsightsService.global_insights` was passing a tz-aware `datetime.now(timezone.utc) - timedelta(days=30)` which asyncpg refuses. Same bug fixed in `cleanup.cleanup_expired_artifacts`. Discovered via the enriched exception envelope from PR #4 — root cause visible from the browser in one fetch. Regression test added. CI green, merged. |

## Test counts

- **Backend**: 943 passed, 8 skipped, 0 failures (was 895 pre-session)
- **Frontend**: 177 passed, 0 failures
- **CI**: green on all 3 PRs
- New tests added this session:
  - `test_storage_service.py::TestMakeStorageServiceFactory::test_returns_service_with_async_client_when_env_vars_set`
  - `test_storage_service.py::TestMakeStorageServiceFactory::test_returns_service_without_client_when_env_vars_missing`
  - `test_storage_service.py::TestMakeStorageServiceFactory::test_client_creation_failure_falls_back_to_none`
  - `test_storage_service.py::TestMakeStorageServiceFactory::test_client_is_cached_across_calls`
  - `test_global_exception_handler.py` — 4 tests (status, CORS header, detail.type+message, no traceback leak)
  - `test_analysis_worker.py::test_build_supabase_client_returns_async_client_when_env_set` (rewritten async)
  - `test_insights.py::test_cutoff_passed_to_repo_is_timezone_naive`

## E2E Verification Results

### POST /api/v1/analyses — STILL 500, but now a CONFIG bug not a code bug

After PR #4 merged + deployed, the production `POST /api/v1/analyses` response is now:

```json
{
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "An unexpected error occurred. Please try again.",
    "detail": {
      "type": "StorageApiError",
      "message": "{'statusCode': 403, 'error': Unauthorized, 'message': signature verification failed}"
    }
  }
}
```

**Translation:** the backend is now successfully calling Supabase Storage, but Supabase itself rejects the JWT with `403 signature verification failed`. The async client fix worked. The remaining failure is a **production environment misconfiguration — diagnosed end-of-session**:

**The `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_URL` on the droplet point to two DIFFERENT Supabase projects.** Decoded from the actual running container by user end-of-session:

- `SUPABASE_URL` host: `xvgwjpumswndke**xituxc**.supabase.co` (project Y)
- `SUPABASE_SERVICE_ROLE_KEY` JWT `ref` claim: `xvgwjpumswndke**ltuxc**` (project X)

The 14-char prefix `xvgwjpumswndke` is shared but everything from position 15 diverges. These are two distinct projects, almost certainly the result of an incomplete migration where some env vars were updated to project Y but `SUPABASE_SERVICE_ROLE_KEY` was forgotten and still references project X.

**Critical evidence chain showing project Y is canonical:**
- Login on spelix.app works → frontend's `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` (Vercel env) point to project Y, otherwise the user couldn't authenticate
- `get_current_user` in `backend/app/api/deps.py:62` validates the user JWT against JWKS fetched from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` — login succeeds, so backend `SUPABASE_URL` AND `SUPABASE_JWT_SECRET` are project Y
- Only `SUPABASE_SERVICE_ROLE_KEY` is mismatched (project X)

**MUST verify before fix: `DATABASE_URL`.** This contains a `postgres.<PROJECT_REF>` username portion that determines which Postgres database the backend reads/writes to. If `DATABASE_URL` points to project X (matches the bad key) instead of project Y (matches the URL), the backend has been silently writing data to the wrong database — there's no FK to `auth.users` so this fails silently. The history page rendering "No analyses yet" is consistent with EITHER project, since both could be empty for this user. Run on droplet:

```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
import os, urllib.parse
url = os.environ['DATABASE_URL']
parsed = urllib.parse.urlparse(url)
user = parsed.username or ''
ref = user.split('.', 1)[1] if '.' in user else '(no ref)'
print('DATABASE_URL ref:', ref)
print('SUPABASE_URL:    ', os.environ.get('SUPABASE_URL'))
"
```

Expected: `DATABASE_URL ref: xvgwjpumswndkexituxc` (matching SUPABASE_URL). If it shows `xvgwjpumswndkeltuxc` instead, **stop and figure out where real data lives** before any env change.

### `/api/v1/insights/global` — FIXED on next deploy

PR #5 fixes this. The enriched exception envelope (PR #4) revealed the asyncpg `DataError` instantly. Will be 200 OK after PR #5 deploys.

### Other endpoints (unchanged)

- `GET /api/v1/profiles/me` — still 404 for users without a profile. Frontend already handles this silently (`ProfilePage.tsx:62-66`). MEDIUM priority, deferred to a follow-up. Not blocking.

## Blockers

### CRITICAL — User action required: reconcile project refs across all 8 Supabase env vars

**This cannot be done from the Claude session — needs droplet shell access AND Vercel dashboard access.**

The droplet uses docker compose with `env_file: - .env.prod` (see `docker-compose.prod.yml`). The CI deploy job in `.github/workflows/ci.yml:154-177` runs `cd /home/deploy/spelix && docker compose -f docker-compose.prod.yml up -d --build` over SSH. Env vars are read at container START time from `/home/deploy/spelix/.env.prod`. The filename is correct — the local `.env` vs droplet `.env.prod` discrepancy is BY DESIGN (local dev runs natively without docker, prod runs via docker compose). Filename was investigated and ruled out as a cause.

**Every one of these 8 env vars must reference the SAME Supabase project ref:**

Backend (`/home/deploy/spelix/.env.prod`):
1. `SUPABASE_URL` — currently project Y (`xvgwjpumswndkexituxc`)
2. `SUPABASE_SERVICE_ROLE_KEY` — currently project X (`xvgwjpumswndkeltuxc`) ← **WRONG**
3. `SUPABASE_JWT_SECRET` — must be project Y's JWT secret (login works, so probably correct)
4. `SUPABASE_JWT_ISSUER` — optional override; if set, must be `https://<ref>.supabase.co/auth/v1`. Safer left unset (derived from `SUPABASE_URL` in `deps.py:30-39`)
5. `DATABASE_URL` — username portion `postgres.<ref>` must match. **MUST VERIFY** (see diagnostic command above)
6. `SUPABASE_STORAGE_BUCKET` — defaults to `videos`; bucket must exist in canonical project's Storage tab

Frontend (Vercel project env, NOT in repo):
7. `VITE_SUPABASE_URL` — must be project Y (login works, so already correct)
8. `VITE_SUPABASE_ANON_KEY` — JWT `ref` claim must match (login works, so already correct)

**Fix steps once `DATABASE_URL` is verified to match `SUPABASE_URL` (project Y):**
1. Open Supabase Dashboard → Project Y → Project Settings → API → copy current `service_role` secret (NOT `anon`)
2. SSH to droplet, edit `/home/deploy/spelix/.env.prod`, update `SUPABASE_SERVICE_ROLE_KEY=` with the project Y service_role JWT
3. Watch out for: surrounding `"` quotes (compose env_file does NOT strip them — value becomes literally `"eyJ..."`), trailing CRLF (use `cat -A` to check), line continuations (compose doesn't support them — JWTs must be on a single line)
4. Bounce containers to force re-read of env file:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate backend worker
   ```
5. Verify the running container has the right key:
   ```bash
   docker compose -f docker-compose.prod.yml exec backend python -c "
   import os,base64,json
   k=os.environ['SUPABASE_SERVICE_ROLE_KEY']
   p=k.split('.')[1]; p+='='*(-len(p)%4)
   d=json.loads(base64.urlsafe_b64decode(p))
   print('role:',d.get('role'),'ref:',d.get('ref'))
   "
   ```
   Must show `role: service_role` and `ref: xvgwjpumswndkexituxc` (matching `SUPABASE_URL`)
6. Then re-test with curl:
   ```bash
   JWT=<a real Supabase user JWT — easiest: open spelix.app in a browser, devtools → Application → Local Storage → copy access_token>
   curl -X POST https://api.spelix.app/api/v1/analyses \
     -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json" \
     -d '{"exercise_type":"squat","exercise_variant":"high_bar","filename":"test.mp4","file_size_bytes":750000}'
   ```
   Expect `201 Created` with a JSON body containing `id`, `upload_url`, `status: "queued"`, `expires_at`. If still 403, the key is wrong or the project URL is wrong.
8. Once curl returns 201, re-run the Playwright E2E (next session) — first time the worker pipeline will reach end-to-end in production EVER. Watch for further dormant bugs surfacing via the enriched envelope.

### What's NOT blocked

- The codebase is clean and ready for Phase 2 RAG work as soon as #1 lands. Three layered bugs were fixed this session:
  - Storage factory client=None (PR #3)
  - Sync vs async Supabase client in upload endpoint AND both workers (PR #4)
  - asyncpg tz-aware vs tz-naive datetime in insights + cleanup (PR #5)
- The global exception handler is now a permanent diagnostic asset — any future production crash returns the actual exception type + message in the JSON envelope, so future debugging shouldn't require server-log access.

## Next session start

```bash
# 1. Confirm the droplet env fix landed
curl -X POST https://api.spelix.app/api/v1/analyses \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"exercise_type":"squat","exercise_variant":"high_bar","filename":"test.mp4","file_size_bytes":750000}'
# Expect 201

# 2. Re-run Playwright MCP E2E end-to-end on spelix.app:
#    upload → status (quality_gate_pending → processing → coaching → completed)
#    → results page → FormScoreCards → coaching output → PDF download
#    Use e2e/fixtures/squat-high-bar.mp4. First time the worker pipeline
#    will run end-to-end on real Supabase Storage — any further dormant
#    bugs (Anthropic API key, OpenAI key, ARQ Redis URL, threshold config
#    path, MediaPipe model download, WeasyPrint fonts) will surface here
#    and be visible via the enriched exception envelope.

# 3. Fix /profiles/me 404 polish if convenient (MEDIUM, deferred)

# 4. Phase 2 planning: RAG (Qdrant, Cohere), document ingestion,
#    citation-grounded coaching, CoVe verification, follow-up chat.
#    Activate spelix-rag-engineer and spelix-corpus-curator agents.
#    Migration 004 for rag_documents + expert_annotations.
```

## Key learnings to carry forward

1. **The enriched global exception handler is a force multiplier.** PR #5 was diagnosed in one browser fetch instead of requiring SSH to the droplet. Worth keeping permanently — the security cost of leaking `RuntimeError: ...` to authenticated users on a private app is much smaller than the operational cost of guessing.
2. **`supabase.create_client` (sync) vs `supabase.acreate_client` (async)** — different return types, different awaitability of storage methods. If you `await` a sync-client method you get `TypeError: dict can't be awaited`. The correct one for any code that awaits storage is `acreate_client`. Verified by `inspect.signature(supabase.create_client)` returning `Client`, `inspect.signature(supabase.acreate_client)` returning `AsyncClient`.
3. **Mocks hide bugs that real factories expose.** Every Spelix test that touched storage mocked at the `_get_service` dependency-override level, so the real factory path was never exercised in 943 tests. PR #3 added regression tests that exercise the real factory and patch at `supabase.create_client` / `supabase.acreate_client` instead. New rule: any singleton or factory that constructs an external client should have at least one test that exercises the real construction path with the third-party module patched at its source, not at the consumer.
4. **`analyses.created_at` is `TIMESTAMP WITHOUT TIME ZONE`** — any cutoff datetime compared to it must also be tz-naive. `datetime.now(timezone.utc).replace(tzinfo=None)` is the modern idiom (`datetime.utcnow()` is deprecated). This affects every query that filters on `created_at`. Check before adding any new time-window query.
5. **Bugs survive to production in layers.** What looked like one bug (POST /analyses returning 500 with no CORS headers) was actually three: (a) factory returning client=None, (b) sync vs async client mismatch, (c) tz-aware datetime in a separate endpoint that also returned 500 with no CORS headers. The enriched handler made layers 2 and 3 visible in minutes instead of hours.
