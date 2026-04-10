# Test Coverage & Quality Audit — Phase 0

_Date: 2026-04-09 | Auditor: Claude Sonnet 4.6_

---

## Coverage Gap Analysis

| File | Coverage | Uncovered Functions / Branches | Priority |
|------|---------|-------------------------------|----------|
| `app/services/pipeline.py` | 24% | Everything below `download_video` (lines 162–385): the entire `run_cv_pipeline` body — all 11 pipeline steps, the `QualityGateRejection` raise path, storage deletion of source video (line 376–380), the local-file fallback branch (lines 186–188), and the `PipelineResult` constructor. No test for `download_video` at all. | **CRITICAL** |
| `app/workers/analysis_worker.py` | 70% | `_build_supabase_client` (lines 50–62) including the `ImportError`/exception branch; `_run_pipeline`'s re-fetch after pipeline (`analysis is None` guard at line 101–102); the `_generate_and_upload_pdf` function entirely (lines 203–265) — both the storage-upload path and the no-storage fallback; the `process_analysis` error-handler branch where `analysis is None` after re-fetch (lines 322–326). | **CRITICAL** |
| `app/api/deps.py` | 79% | `_get_supabase_url` when `SUPABASE_URL` not set (line 38); `_get_jwks` cache-hit fast-path (line 47) and the full JWKS fetch body (lines 50–55); JWKS-based ES256/RS256 success path (line 108 — tests only exercise HS256 fallback); `get_current_user` path where JWKS fails AND no `SUPABASE_JWT_SECRET` is set (line 128); missing `sub` or `email` in payload (line 131); `uuid.UUID(sub)` `ValueError` branch (lines 142–143). | **CRITICAL** |
| `app/repositories/user_profile.py` | 80% | Missing: `get_by_user_id` returning `None` path; `update` when row not found; any `upsert` / patch branch if present. Exact branch lines not available without running coverage, but 20% of 67 statements = ~13 lines untested. | **Important** |
| `app/services/coaching.py` | 84% | `_confidence_label` "Very Low" branch (score < 0.50, line 66); `_build_user_prompt` — the `except KeyError` threshold fallback branch (line 109) and the "Low"/"Very Low" confidence note insertion branch (lines 126–131); `_is_retryable` for `APIStatusError` with status_code==529 (line 146–148) and `APITimeoutError` (line 148); non-retryable non-auth error raise path (lines 287–294). | **Important** |
| `app/services/pdf.py` | 84% | `_build_rep_metrics_table` — the `int`/non-float value branch for cell rendering (line 91); `_build_plot_block` — the `OSError` exception path when a file exists but is unreadable (lines 110–120); `_build_coaching_strengths` with empty list (line 129); `_build_coaching_corrections` with empty list (line 165); `_build_sources_block` — the non-empty sources path (lines 172–173); `render_html` — `quality_gate_result` as a non-dict truthy value (lines 242–245). | **Important** |
| `app/services/admin.py` | 86% | ~14% of ~50 statements untested — likely the error/not-found branches in admin event creation and admin query paths. | **Nice-to-have** |

---

## Test Quality Issues

### No assertions / weak assertions

| Test | File | Issue |
|------|------|-------|
| `test_heartbeat_written_during_job` | `test_analysis_worker.py` lines 372–377 | The TTL assertion has a convoluted fallback that always passes — it only checks for `ex` kwarg presence but the fallback comment says "Accept either kwarg style or the value 1 (placeholder) — just require TTL > 0", meaning the check could pass with no actual TTL constraint. |
| `test_correct_reject_user_message` | `test_quality_gates.py` line 162 | Uses three OR-ed substrings (`"not clearly visible"`, `"good lighting"`, `"body is not"`) to assert the message — so a message containing any one of those three passes even if the other two are missing. This tests almost nothing about the actual message. |
| `test_missing_role_raises_403` in `TestGetAdminUser` | `test_auth.py` line 172 | The user dict has `"role": "viewer"` (not missing), yet the test is named `test_missing_role_raises_403`. The name is misleading; the actual intent (non-admin role raises 403) is already covered by `test_non_admin_raises_403`. |

### Tests that test implementation details over behavior

| Test | File | Issue |
|------|------|-------|
| `test_happy_path_status_transitions` | `test_analysis_worker.py` | Mocks out `_run_pipeline` (internal function) rather than testing the actual `process_analysis` → `_run_pipeline` integration. When `_run_pipeline` is mocked, the test is really just verifying the mock, not the status transition logic. The E2E version in `test_full_flow.py` is more meaningful. |
| `test_generate_pdf_passes_rendered_html_to_weasyprint` | `test_pdf.py` | Asserts `"bench" in html_arg` on the WeasyPrint HTML class argument — this checks the mock call args rather than any observable behavior of the function. |

### LLM / Anthropic API mock coverage

All coaching tests in `test_coaching.py` mock the `instructor` client correctly — no real Anthropic calls are made. The E2E test `test_full_flow.py` patches `anthropic` and `CoachingService` properly. **No real API calls in CI.** This is correct.

### Supabase mock coverage (frontend)

All frontend tests mock `@/lib/supabase` via `vi.mock("@/lib/supabase", ...)` — no real Supabase calls. All `@/api/analyses` and `@/api/insights` calls are mocked. This is correct.

### Video fixtures

`backend/tests/fixtures/` is **completely empty** — the directory exists but contains no `.mp4` files. The CLAUDE.md and backend CLAUDE.md both specify three video fixtures (squat, deadlift, bench, ~10s each, 720p) must be present. Without them, any test that exercises the real `extract_landmarks` / `run_quality_gates` on actual video cannot run. All current CV tests use synthetic numpy arrays as a workaround, but this means no integration-level test can verify the MediaPipe pipeline against real video data.

### Deprecation warning

`test_repositories.py` line 109 uses `datetime.utcnow()` which is deprecated in Python 3.12. Should be replaced with `datetime.now(timezone.utc)`.

---

## Missing Tests

| Category | What's Missing | Priority |
|----------|---------------|----------|
| **Pipeline orchestration** | `run_cv_pipeline` unit tests: happy path (mocked CV functions, asserts status transitions, DB writes), quality-gate-rejection path, storage-client-None path (local file fallback), and source-video storage deletion error handling (the `try/except` at line 376–380). No test file exists for `pipeline.py`. | **Critical** |
| **Worker: `_generate_and_upload_pdf`** | No test exercises this function in isolation — it is only patched away in existing worker tests. Need tests for: PDF generates and is uploaded when `storage_client` is not None; PDF written to local path when `storage_client` is None; exception from `PDFService.generate_pdf` is swallowed and logged (lines 264–265) without crashing the worker. | **Critical** |
| **Worker: `_build_supabase_client`** | No test covers: returns `None` when env vars missing; returns a client when both env vars set; returns `None` when `create_client` raises. | **Critical** |
| **deps.py — JWKS path** | Tests only exercise the HS256 fallback (using `SUPABASE_JWT_SECRET`). Missing: JWKS-based ES256 verification success path; JWKS fetch failure with no fallback secret (should raise 401); JWKS cache hit (second call within TTL reuses cache without HTTP); `_get_supabase_url` raising `RuntimeError` when `SUPABASE_URL` not set. | **Critical** |
| **deps.py — edge claim branches** | Missing `sub`-present-but-empty string branch; missing `email`-present-but-empty string branch; `uuid.UUID(sub)` raising `ValueError` for a non-UUID `sub`. | **Important** |
| **Quality gates: Phase 0 boundary values** | The framing gate tests cover too-small / too-large / normal, but there are no tests at the **exact** 30% and 80% boundary values (bounding box area exactly equals threshold). | **Important** |
| **Quality gates: FR-CVPL-06 through FR-CVPL-10** | FR-CVPL-06 (multi-person), FR-CVPL-07 (resolution), FR-CVPL-08 (lighting warning), FR-CVPL-09 (stability warning), FR-CVPL-10 (blur warning) are Phase 1/2/3 gates listed in the SRS but have no test stubs. These are clearly marked as Phase 1+ so absence is expected for Phase 0, but should be tracked. | **Nice-to-have** |
| **Confidence label boundaries (coaching module)** | `coaching.py` has its own private `_confidence_label` function that uses **different thresholds** (≥0.90=High, ≥0.70=Moderate, ≥0.50=Low) compared to `cv/confidence.py`'s `confidence_label` (≥0.80=High, ≥0.65=Moderate, ≥0.50=Low). The coaching-module version has no tests at all and no boundary tests. This threshold divergence is a **latent bug** — the prompt sent to Claude uses different labels than what appears on the results page. | **Critical** |
| **Rep detection: zero-rep case** | No test verifies that a flat (no movement) signal returns an empty list from `detect_reps`. | **Important** |
| **Rep detection: partial rep** | No test verifies that a signal that starts descending but never reaches depth is NOT counted. The hysteresis tests cover chatter at depth, but not an incomplete descent. | **Important** |
| **Status transitions: `queued → failed`** | `test_status_transitions.py` tests `test_queued_cannot_go_to_failed` (invalid) but there is no test for `processing → failed` or `coaching → failed` as **valid** transitions (both are in the SRS 5.2a table). The valid-path tests do include these via `test_processing_to_failed` and `test_coaching_to_failed`, so they are covered. _(No gap here — documented for completeness.)_ | — |
| **API endpoint: GET /analyses/{id}/status** | No unit test exercises this endpoint — neither 200 (status poll), 404, nor 401 cases. | **Important** |
| **API endpoint: GET /analyses/{id} (detail)** | No unit test for 200, 401, 403 (wrong user), 404. | **Important** |
| **Rate limiting: 10th request allowed** | `test_rate_limit.py` tests that the 11th is rejected but does NOT assert that the 10th succeeds (allowed boundary). | **Important** |
| **Account deletion cascades** | `test_account_deletion.py` tests service-level mocks. It does not verify that `RepMetric` and `CoachingResult` rows are deleted when an analysis is deleted (no cascade test via real DB or explicit mock verification of those repo calls). | **Important** |
| **PDF: `_build_plot_block` OSError path** | A file at a valid path that becomes unreadable (permission error) hits the `except OSError` branch in `_build_plot_block`. No test covers this. | **Nice-to-have** |
| **PDF: `quality_gate_result` as non-dict truthy** | `render_html` has a third branch (`else: qg_passed = bool(quality_gate_result)`) for non-dict values. No test hits this. | **Nice-to-have** |
| **PDF: `_build_sources_block` with sources** | The non-empty sources path (lines 172–173) is not covered — there is no test that passes a `sources` list to `render_html`. | **Nice-to-have** |
| **Coaching: 529 overload retry** | `_is_retryable` covers `APIStatusError` with `status_code==529` but no test simulates a 529 response — only 429 is tested via `anthropic.RateLimitError`. | **Important** |
| **Coaching: network timeout retry** | `APITimeoutError` / `TimeoutError` retry path is not tested. | **Important** |
| **Coaching: non-retryable 400 error** | The non-retryable, non-auth error path (lines 287–294) has no test. | **Important** |
| **Coaching: low/very-low confidence note in prompt** | `_build_user_prompt` inserts a caution note when confidence is "Low" or "Very Low". No test calls `_build_user_prompt` directly (it is a private function), and the integration tests do not check the constructed prompt content. | **Important** |

---

## E2E Coverage

**File:** `backend/tests/e2e/test_full_flow.py`

### Coverage summary

| Step | Covered? | Notes |
|------|----------|-------|
| Auth (JWT validation) | Partial — mocked via `dependency_overrides` | No real JWT round-trip tested |
| Profile creation | Not tested | No profile endpoint is called in the E2E flow |
| Upload (POST /analyses → 201) | Yes | `test_create_and_list_analyses` |
| List analyses (GET /analyses → 200) | Yes | Same test |
| Start analysis (POST /analyses/{id}/start) | Not tested | No E2E test calls the `/start` endpoint |
| Quality gate → rejected | Yes | `test_worker_quality_gate_rejection` |
| Quality gate → processing | Yes | `test_worker_full_pipeline_flow` (mocked CV pipeline) |
| CV pipeline (real MediaPipe) | No — mocked | `run_cv_pipeline` is patched; no real pose extraction tested |
| Coaching (real Claude call) | No — mocked | `CoachingService` is patched with `AsyncMock` |
| PDF generation | No — `_generate_and_upload_pdf` is patched | |
| Summary metrics | Partial — `SummaryService` is mocked but `compute_and_store` is called | |
| Results (GET /analyses/{id}) | Not tested | No E2E test fetches the detail/results endpoint |
| History (GET /analyses) | Partial | Only listing is tested, not filtering/pagination |
| Status transitions order | Yes | `test_worker_full_pipeline_flow` asserts full sequence |

### Issues with the E2E test

1. **No real video processing.** `run_cv_pipeline` is always mocked. The E2E label is misleading — this is closer to a worker integration test with all external dependencies mocked. A true E2E test would use the video fixtures to exercise the real MediaPipe pipeline. This is blocked by the empty `tests/fixtures/` directory.

2. **`/start` endpoint not called.** The E2E test directly calls `process_analysis` without going through the API start endpoint. The flow `POST /analyses → POST /analyses/{id}/start → ARQ enqueue` is not end-to-end tested.

3. **Auth not round-tripped.** `get_current_user` is replaced with a plain dict override. No test verifies that a real JWT (even a test-signed one) flows through the auth stack into the worker context.

4. **Results endpoint absent.** After the worker completes, no test calls `GET /analyses/{id}` to verify the completed analysis is readable with coaching results, rep metrics, and artifact paths.

---

## Frontend Test Gaps

### Pages

| Page | Test File | Coverage Status |
|------|-----------|----------------|
| `HomePage.tsx` | **None** | **Not tested.** Contains Supabase auth check + redirect logic — no test exists for either the "logged in → redirect to /upload" or "logged out → show landing" paths. |
| `LoginPage.tsx` | `LoginPage.test.tsx` | Tested |
| `SignupPage.tsx` | `SignupPage.test.tsx` | Tested |
| `UploadPage.tsx` | `UploadPage.test.tsx` | Tested |
| `AnalysisStatusPage.tsx` | `AnalysisStatusPage.test.tsx` | Tested |
| `ResultsPage.tsx` | `ResultsPage.test.tsx` | Tested |
| `HistoryPage.tsx` | `HistoryPage.test.tsx` | Tested |
| `ProfilePage.tsx` | `ProfilePage.test.tsx` | Tested |
| `AdminPage.tsx` | `AdminPage.test.tsx` | Tested |

### Components

| Component | Test File | Coverage Status |
|-----------|-----------|----------------|
| `AppLayout.tsx` | **None** | **Not tested.** Navigation, layout structure, and any auth-conditional rendering in the layout are untested. |
| `ErrorBoundary.tsx` | `ErrorBoundary.test.tsx` | Tested |
| `RequireAuth.tsx` | `RequireAuth.test.tsx` | Tested |
| `InsightsPanel.tsx` | `HistoryPage.test.tsx` (indirect) | Tested via HistoryPage test |
| `TrendChart.tsx` | `HistoryPage.test.tsx` (indirect) | Tested via HistoryPage test |

### Hooks

| Hook | Test File | Coverage Status |
|------|-----------|----------------|
| `useAnalysisDetail.ts` | **None** | **Not tested.** This hook drives the entire ResultsPage data fetch — its loading/error/success states, refetch logic, and Supabase Realtime subscription should have dedicated tests. |
| `useAnalysisStatus.ts` | **None** | **Not tested.** Used by `AnalysisStatusPage` for polling/Realtime. The polling fallback behavior (10s interval when Realtime disconnects) and status transition reactions are not tested in isolation. |

### API module

| Module | Mocked In | Direct Tests |
|--------|-----------|--------------|
| `src/api/analyses.ts` | All page tests mock `@/api/analyses` | **No direct unit tests for the API client functions.** Error handling (401 → redirect, 429 → toast, 500 → error boundary) is not tested at the API layer. |
| `src/api/insights.ts` | `HistoryPage.test.tsx` | **No direct unit tests.** |

### Missing critical user flow tests

1. **Upload success flow end-to-end (frontend):** No test covers the complete upload path: file selected → form submitted → `createAnalysis` called → redirect to `/status/{id}`. The `UploadPage` test only verifies rendering and form state, not the actual submit handler result.

2. **Results page PDF download:** No test verifies the "Download PDF" link renders correctly when `pdf_path` is present vs. absent and that the 7-day expiry banner is shown.

3. **AnalysisStatusPage Realtime → polling fallback:** No test simulates Realtime disconnection and verifies the component falls back to REST polling.

4. **RequireAuth redirect:** The `RequireAuth` test should verify that unauthenticated users are redirected to `/login` — confirm this is covered (likely is, given the test file exists, but the hook tests are absent).

---

## Summary Scorecard

| Area | Status | Key Action |
|------|--------|-----------|
| `pipeline.py` coverage | 24% — RED | Write `test_pipeline.py` covering all 11 steps with mocked CV functions |
| `analysis_worker.py` coverage | 70% — YELLOW | Add tests for `_generate_and_upload_pdf`, `_build_supabase_client` exception path, analysis-disappeared guard |
| `deps.py` coverage | 79% — YELLOW | Add JWKS ES256 success path test; test JWKS-with-no-fallback; cache TTL hit |
| Confidence label divergence | **Latent bug** — CRITICAL | `coaching.py::_confidence_label` uses 0.70/0.50 thresholds; `cv/confidence.py::confidence_label` uses 0.65/0.50. These must be unified or the discrepancy documented and tested |
| Video fixtures | Empty — RED | Add at least one synthetic 5-second test video per exercise (can be generated with FFmpeg + a blank frame, or use numpy-to-video for CI) |
| `tests/fixtures/` | Empty | Add video files OR explicitly document synthetic-only policy |
| `datetime.utcnow()` deprecation | 1 instance in `test_repositories.py:109` | Replace with `datetime.now(timezone.utc)` |
| E2E: real pipeline path | Mocked throughout | Not a Phase 0 blocker but note gap |
| Frontend: `HomePage`, `AppLayout`, both hooks | No tests | Add tests for redirect logic and hook states |
| LLM calls in CI | Correctly mocked everywhere | No action needed |
| Supabase calls in frontend tests | Correctly mocked everywhere | No action needed |
