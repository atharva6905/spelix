# Session 11 Handoff — E2E Verification Against spelix.app

## Completed this session

| Task | Commit / PR | Description |
|------|-------------|-------------|
| Fix CI push failures | `3f38894` (direct push; user had already pushed before branch-workflow rule existed) | Ruff E402/F841, pyright forward refs + Literal mismatches + matplotlib cmap + `CoachingResultRepository.get_by_analysis_id` → `get_by_analysis`, frontend TS2352 unknown cast, e2e `mock_cv_pipeline` returning `None` instead of `PipelineResult` |
| Add Checkpoint Workflow + Playwright MCP E2E rule | PR **#2** → `b9010a8` (merged, squash) | Root `CLAUDE.md` under 200 lines (185), `backend/CLAUDE.md` pointer + rationale, `frontend/CLAUDE.md` pointer + rationale, `.claude/commands/handoff.md` adds "E2E verification" standard section. CI green on PR, merged via `gh pr merge --squash --delete-branch`. Local main pulled the merge. |
| Live E2E verification of spelix.app via Playwright MCP | — | Walked upload flow to the POST request. **Upload is broken in production — see Findings below.** |

## Remaining

Phase 2 work is blocked until the production POST /analyses 500 is fixed (see E2E Findings #1). The workflow infrastructure is ready, but until the upload path works on prod, every new Phase 2 checkpoint will merge a non-verifiable feature.

## Test counts

- **Backend**: 896 passed, 2 skipped, 0 failures, 91% coverage (local)
- **Frontend**: 177 passed, 0 failures, tsc clean (local)
- **CI**: green on PR #2 and `3f38894` direct push (GitHub Actions run `24275400977` + `24275048709`)
- **Production deploy**: latest deploy `b9010a8` (PR #2 merge) completed in 49s on the DO droplet, ran `alembic upgrade head`

## E2E Verification — FAIL

**Environment**: https://spelix.app (prod), Playwright MCP browser, persistent-cookie session as `e2e-test@spelix.app` (user id `22b72971-132b-44d9-85c9-a8d9942932e5`), Chromium via MCP.

**Flow walked**: `/upload` (auto-redirect after login) → History → Profile → Upload → select `Squat` → select `High Bar` → attach `e2e/fixtures/squat-high-bar.mp4` (733.5 KB) → click `Upload Video`. Stopped at the POST because the request failed.

### CRITICAL — POST /api/v1/analyses returns 500 with no CORS headers → upload is broken in production

**What the browser sees:** `[ERROR] Access to fetch at 'https://api.spelix.app/api/v1/analyses' from origin 'https://www.spelix.app' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.` Frontend surfaces this as an inline alert "Failed to fetch (api.spelix.app)" — error handling in the UI is correct, but no upload can proceed. Screenshot: `e2e/screenshots/e2e-02-upload-cors-error.png`.

**What's actually happening:** I verified with `curl` that backend CORS is configured correctly — a preflight `OPTIONS /api/v1/analyses` with `Origin: https://www.spelix.app` returns 200 with `Access-Control-Allow-Origin: https://www.spelix.app`, `Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS`, and all required allow-headers. A `POST` with a fake Bearer token returns 401 with CORS headers intact. A `POST` with the **real Supabase JWT** returns:

```
HTTP/1.1 500 Internal Server Error
Alt-Svc: h3=":443"; ma=2592000
Content-Length: 21
Content-Type: text/plain; charset=utf-8
Server: uvicorn
Via: 1.1 Caddy

Internal Server Error
```

**No `Access-Control-Allow-Origin` header.** The body is literally `Internal Server Error` (21 bytes) — that's uvicorn's default 500 handler, not FastAPI's JSON error envelope. This means an **unhandled Python exception** escaped all of FastAPI's exception middleware chain AND CORSMiddleware, leaving uvicorn to generate the response from scratch without CORS. The browser then (correctly) reports "CORS policy block" because the response truly is missing the header — but the CORS error is a *symptom*, not the cause. The real bug is the unhandled exception.

**Root cause identified — Phase 0 dormant bug in `_make_storage_service`** at `backend/app/api/v1/analyses.py:48–66`:

```python
def _make_storage_service() -> StorageService:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if supabase_url and supabase_key:
        # We can't await here so we return a StorageService with no client;
        # the client is lazily created by the lifespan. For now, tests mock
        # the whole service, and production injects a ready client via a
        pass

    return StorageService()
```

The `if` branch is a literal `pass` — in production (where env vars are set) it STILL returns an empty `StorageService()` with `supabase_client=None`. The `POST /analyses` handler then calls `storage.generate_signed_upload_url(...)` → that function checks `if self._client is None:` and raises `RuntimeError("StorageService has no Supabase client. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.")`. That `RuntimeError` is not a `HTTPException`, so FastAPI's exception handler wraps it as a 500 — but apparently the error propagates far enough up the stack that CORSMiddleware doesn't wrap the response. Uvicorn emits the plain-text fallback. No CORS header. Browser blocks. User sees "CORS policy".

**Why this has been dormant**: every unit and integration test mocks `StorageService` via `dependency_overrides[_get_service]`. `test_analysis_api.py::_build_app` provides its own `_get_service` override. `test_full_flow.py` does similar. No test ever exercises the real `_make_storage_service` code path. The hole existed since Phase 0 B-009 and has survived every CI run.

**The worker already has the fix pattern** in `backend/app/workers/analysis_worker.py:50–62`:

```python
def _build_supabase_client() -> Any | None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        logger.warning("Failed to create Supabase client: %s", e)
        return None
```

**Concrete fix** (next session, Batch 1 / Phase 2 pre-flight):
1. Replace the `pass`-branch in `_make_storage_service` with a call to `supabase.create_client(url, key)` and pass the client to `StorageService(supabase_client=...)`.
2. Add an integration test that exercises the real `_get_service` against a mocked `supabase.create_client` to prove the code path runs without raising.
3. Wrap any non-HTTPException exceptions from the service layer in a global handler that ensures CORS headers are on 500 responses (FastAPI supports `@app.exception_handler(Exception)`). That way, future crashes at least show the real error instead of hiding behind a CORS red herring.
4. Add an end-to-end smoke test in CI that hits `POST /api/v1/analyses` against a real Supabase Storage bucket (using a CI-only service role key) — or, cheaper, a Playwright MCP post-deploy smoke check baked into the workflow.

### HIGH — `/api/v1/insights/global` also returns 500 without CORS

Browser console shows the same "CORS policy" error for `GET /api/v1/insights/global` on the History and Profile page loads (the History page fires it on mount; Profile inherits the cached fetch). The other insights endpoints (`/analyses?limit=50` list) return 200 with proper CORS. Without the raw curl I didn't fully root-cause this one, but the symptom pattern matches the storage-service bug: something in the `/insights/global` handler throws an unhandled exception that bypasses CORSMiddleware.

The UI handles the failure gracefully — the History page shows placeholder text "Insights coming soon — complete more sessions to unlock" regardless of whether the API succeeded or failed, so users don't see a broken UI. But the console error count climbs with every page load.

### MEDIUM — `GET /api/v1/profiles/me` returns 404 for authenticated users who haven't saved a profile yet

Profile page fires `GET /api/v1/profiles/me` on mount. For a user who has never saved a profile, the backend returns `404` (not `200 {}` or `204 No Content`). The frontend handles this gracefully (shows empty form, all fields blank) but a 404 in the console is a noisy signal that's easy to confuse with a real route-missing bug. Prefer returning `200` with an empty Pydantic object, or `204 No Content`, for "logged-in user has no profile yet".

### LOW / OBSERVATION — UI and auth work correctly

Positives from this run:
- Landing on `spelix.app` auto-redirects to `/upload` — session cookie persistence from the Playwright browse daemon works; I was logged in as `e2e-test@spelix.app` without any manual interaction.
- Upload form state is correct: `Exercise Variant` dropdown is `[disabled]` until `Exercise Type` is selected, `Upload Video` button is `[disabled]` until all three inputs are provided (type + variant + file). Both match FR-XDET-09.
- Filming Guidance text updates from the generic "Position your camera..." to the squat-specific "For squat: ..." copy when exercise type is selected.
- Frontend error handling: the `Failed to fetch (api.spelix.app)` alert surfaces the failure inline without breaking the form state. User can retry without a page refresh.
- History page renders "No analyses yet" + a "Upload your first video" CTA — correct empty-state.
- Profile page renders all 6 fields (height, weight, age, experience, arm span, femur length) — matches FR-PROF-06.
- Navigation: Spelix logo, Upload, History, Profile, Sign out — all links work.

Files captured this session:
- `e2e/screenshots/e2e-01-upload-initial.png` — clean initial upload state
- `e2e/screenshots/e2e-02-upload-cors-error.png` — post-click error state with inline alert
- `.playwright-mcp/console-2026-04-11T05-11-57-805Z.log` — all 7 console errors (gitignored)
- `.playwright-mcp/page-2026-04-11T05-*.yml` — 6 accessibility snapshots across the flow (gitignored)

## Blockers

1. **Production POST /api/v1/analyses is broken** — no user can upload a video on spelix.app. This is a **user-facing outage** that has been live for the entire existence of Phase 0 + Phase 1 (the bug predates Phase 1; every test mocked around it). Phase 2 work cannot proceed until this is fixed because the new Checkpoint Workflow requires E2E verification after every merge, and E2E verification cannot reach beyond the upload step.
2. **Exception handler gap** — whatever bug lands in a handler function (not a `HTTPException`) surfaces to users as "CORS policy" instead of the real error. This hides bugs behind a red herring and made today's root-cause investigation take longer than it should have. Fix #3 under the CRITICAL item addresses this.
3. **`/insights/global` 500** — same symptom pattern as #1, likely same class of dormant bug. Needs diagnosis in the same session that fixes #1.
4. **E2E gap in CI** — the bug was in code since Phase 0 B-009. 895 tests and 91% coverage missed it because every test mocked `_get_service`. The new Checkpoint Workflow's Playwright MCP verification step is the first thing that would have caught this. It caught it the moment we started using it.

## Next session start

```bash
# 1. Fix the three bugs
git checkout -b fix/prod-storage-client-and-cors

# backend/app/api/v1/analyses.py — replace pass with real client creation
# backend/app/main.py — add a global @app.exception_handler(Exception)
#                       that returns JSONResponse with CORS headers
# investigate /insights/global 500 (similar mechanism?)

# 2. Add integration test that exercises real _make_storage_service
#    with a mocked supabase.create_client

# 3. Local verification
cd backend && uv run ruff check . && uv run pyright app/ && uv run pytest tests/ -q
cd ../frontend && npx tsc --noEmit && npx vitest run

# 4. PR + CI + merge
git push -u origin fix/prod-storage-client-and-cors
gh pr create --title "fix(api): wire Supabase client into _make_storage_service" --body "..."
gh pr checks <#> --watch
gh pr merge <#> --squash --delete-branch

# 5. Wait for deploy, then E2E verify the upload flow end-to-end:
#    upload → status page → rep detection → scoring → coaching → results → PDF download
#    Use e2e/fixtures/squat-high-bar.mp4. Record findings in the next handoff.

# 6. Only then: Phase 2 planning (spelix-rag-engineer + spelix-corpus-curator,
#    migration 004 for rag_documents + expert_annotations, Qdrant cluster)
```
