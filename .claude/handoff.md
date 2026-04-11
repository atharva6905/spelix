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

**Translation:** the backend is now successfully calling Supabase Storage, but Supabase itself rejects the JWT with `403 signature verification failed`. The async client fix worked. The remaining failure is a **production environment misconfiguration**:

**The `SUPABASE_SERVICE_ROLE_KEY` env var on the DigitalOcean droplet is wrong, stale, or doesn't match `SUPABASE_URL`.** Most likely: the service role key was rotated in the Supabase Dashboard and the droplet's env file was never updated. Or `SUPABASE_URL` points at a different Supabase project than the key was issued for.

### `/api/v1/insights/global` — FIXED on next deploy

PR #5 fixes this. The enriched exception envelope (PR #4) revealed the asyncpg `DataError` instantly. Will be 200 OK after PR #5 deploys.

### Other endpoints (unchanged)

- `GET /api/v1/profiles/me` — still 404 for users without a profile. Frontend already handles this silently (`ProfilePage.tsx:62-66`). MEDIUM priority, deferred to a follow-up. Not blocking.

## Blockers

### CRITICAL — User action required: rotate `SUPABASE_SERVICE_ROLE_KEY` on droplet

**This cannot be done from the Claude session — needs droplet shell access.**

Steps:
1. Open the Supabase Dashboard → **Project Settings → API**
2. Confirm the project URL matches what's in the droplet's `SUPABASE_URL` env var
3. Copy the current `service_role` secret (NOT the anon/publishable key)
4. SSH to the DO droplet
5. Update `/etc/spelix/api.env` (or wherever the env file lives) with the new `SUPABASE_SERVICE_ROLE_KEY`
6. Restart the FastAPI service: `sudo systemctl restart spelix-api` (or whatever the service name is — check Caddy/systemd config)
7. Verify with curl from a local terminal:
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
