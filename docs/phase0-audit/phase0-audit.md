# Phase 0 Audit Report — Consolidated

**Date**: 2026-04-09
**Baseline**: ruff clean, pyright 0 errors, tsc clean, 542 backend tests (90% cov), 94 frontend tests passing
**Sources**: audit-backend.md, audit-frontend.md, audit-tests.md, audit-infra.md

---

## CRITICAL — Must Fix Before Phase 1

These are SRS violations, broken functionality, or security issues that undermine Phase 0 correctness.

| # | Area | Finding | Location | SRS Ref |
|---|------|---------|----------|---------|
| C-1 | Frontend | **TUS upload entirely missing.** `UploadPage` calls `POST /analyses` but never uses the returned `upload_url`. No file bytes are transferred. `tus-js-client` is not installed. | `frontend/src/pages/UploadPage.tsx` | FR-UPLD-06, FR-UPLD-08 |
| C-2 | Frontend | **Wrong confidence thresholds in 3 files.** Code uses ≥0.8/0.6/0.4 but SRS specifies ≥0.80/0.65/0.50. Miscategorises Moderate→Low for 0.60–0.64 and Low→Very Low for 0.40–0.49. | `ResultsPage.tsx`, `HistoryPage.tsx`, `InsightsPanel.tsx` | FR-RESL-08, FR-CVPL-16 |
| C-3 | Frontend | **Three-tier disclaimer completely absent.** SRS requires: (a) fitness/not medical advice, (b) AI transparency, (c) assumption of risk. None rendered. | `ResultsPage.tsx` | FR-RESL-11 |
| C-4 | Frontend | **Summary card missing rep count and timestamp.** Only exercise/variant and confidence shown. | `ResultsPage.tsx` | FR-RESL-01a |
| C-5 | Frontend | **Appendix B status labels wrong.** `quality_gate_pending` → "Checking video quality…" (SRS: "Preparing to analyse…"), `quality_gate_rejected` → "Video quality check failed" (SRS: "Video could not be processed"). | `useAnalysisStatus.ts` | Appendix B |
| C-6 | Backend | **Status transition bypass.** `analysis.status = "failed"` set directly, bypassing `transition()` guard. Allows invalid transitions. | `analysis_worker.py:333` | Section 5.2a |
| C-7 | Backend | **Barbell detection not wired.** Pipeline calls `compute_bar_path_from_landmarks()` (wrist proxy) instead of actual `track_barbell()` + `compute_bar_path()` HoughCircles detection. Functions exist but are unused. | `services/pipeline.py` | FR-BDET-01/02/03 |
| C-8 | Backend | **Video duration validation missing.** No 40s default / 2min extended limit enforced anywhere. No FFprobe codec check. No storage quota check. | `analyses.py`, `pipeline.py` | FR-UPLD-02/03/05/13/14 |
| C-9 | Backend | **Coaching confidence thresholds diverge.** `_confidence_label()` in `coaching.py` uses 0.90/0.70/0.50; canonical `confidence_label()` in `confidence.py` uses 0.80/0.65/0.50. Prompt sent to Claude uses different labels than results page. | `services/coaching.py` vs `cv/confidence.py` | FR-SCOR-10 |
| C-10 | Tests | **`pipeline.py` is 24% covered.** The entire `run_cv_pipeline` function (lines 162–385) has zero tests. No test file exists. | `services/pipeline.py` | — |
| C-11 | Tests | **`tests/fixtures/` is empty.** No video fixtures exist. All CV tests use synthetic numpy arrays — no integration against real MediaPipe output. | `tests/fixtures/` | — |
| C-12 | Infra | **`.env.example` vs code naming mismatch.** `.env.example` declares `SUPABASE_SERVICE_ROLE_KEY` but all backend code reads `SUPABASE_SERVICE_KEY`. Service key silently `None` in prod if `.env.prod` follows example naming. | `.env.example`, `analyses.py`, `storage.py`, `cleanup.py`, `analysis_worker.py` | — |

---

## HIGH — Should Fix Before Phase 1

Significant gaps, test holes, or security hardening issues.

| # | Area | Finding | Location | SRS Ref |
|---|------|---------|----------|---------|
| H-1 | Frontend | **ErrorBoundary never used.** Component exists but is imported nowhere. NFR-USAB-09 unimplemented. | All routes/pages | NFR-USAB-09 |
| H-2 | Frontend | **Upload button activatable via keyboard when disabled.** `aria-disabled=true` set but `disabled` HTML attribute not bound to selection state. | `UploadPage.tsx` | FR-XDET-09 |
| H-3 | Frontend | **Rep metrics table not sortable.** No sort control on any column header. | `ResultsPage.tsx` | FR-RESL-04 |
| H-4 | Frontend | **Per-category confidence guidance text incomplete.** High/Moderate have no guidance; Low/Very Low use generic text instead of SRS-specified distinct messages. | `ResultsPage.tsx` | FR-RESL-08 |
| H-5 | Frontend | **No annotated video MP4 download link.** Video plays inline but no download `<a>` element. | `ResultsPage.tsx` | FR-RESL-02, FR-XPRT-01 |
| H-6 | Frontend | **API types are empty stubs.** `api/types.ts` generated types are all `Record<string, never>`. All types hand-written with no contract enforcement. | `src/api/types.ts` | — |
| H-7 | Backend | **Admin health endpoint broken.** `AdminService` constructed without Redis client — `queue_depth` and `worker_heartbeat` always return 0/False. | `api/v1/admin.py` | FR-ADMN-05 |
| H-8 | Backend | **Missing Phase 0 quality gates.** FR-CVPL-06 (single-person) and FR-CVPL-07 (resolution ≥720p) marked "Must, Phase 0" in SRS but not implemented. | `cv/quality_gates.py` | FR-CVPL-06/07 |
| H-9 | Backend | **Occlusion warning missing.** No targeted "barbell occluded keypoints" warning generated. | `cv/` | FR-CVPL-17 |
| H-10 | Infra | **No `.dockerignore`.** `COPY . .` may bake `.env.prod` secrets into image layers. | `backend/Dockerfile` | — |
| H-11 | Infra | **Docker runs as root.** No `USER` directive in Dockerfile. | `backend/Dockerfile` | — |
| H-12 | Infra | **`.env.local` not in `.gitignore`.** Vite loads it automatically; secrets could be committed. | `.gitignore` | — |
| H-13 | Tests | **JWKS auth path never tested.** All auth tests use HS256 fallback. ES256/RS256 JWKS verification, cache hit, and no-fallback 401 paths uncovered. | `tests/unit/test_auth.py` | — |
| H-14 | Tests | **`_generate_and_upload_pdf` never tested in isolation.** Always patched away. Exception-swallow behavior untested. | `analysis_worker.py` | — |
| H-15 | Tests | **`analysis_worker.py` at 70% coverage.** `_build_supabase_client`, analysis-disappeared guard, and PDF upload path all uncovered. | `analysis_worker.py` | — |

---

## MEDIUM — Fix During Phase 1

Tech debt, minor inconsistencies, and hardening items.

| # | Area | Finding | Location |
|---|------|---------|----------|
| M-1 | Backend | Repository pattern violated — `InsightsService` and `AdminService` take `AsyncSession` directly and run queries inline. | `services/insights.py`, `services/admin.py` |
| M-2 | Backend | `AnalysisCreate` schema uses raw `str` for exercise_type/variant instead of typed `Literal`. OpenAPI spec doesn't document allowed values. | `schemas/analysis.py` |
| M-3 | Backend | FR-CVPL-08 (lighting warning) and FR-CVPL-09 (stability warning) marked "Should, Phase 0" but not implemented. | `cv/quality_gates.py` |
| M-4 | Backend | `AnalysisCreate` missing `weight_kg` field — users cannot log weight at upload time. | `schemas/analysis.py` |
| M-5 | Backend | No re-analysis/override endpoint — exercise type/variant cannot be changed post-upload. | — |
| M-6 | Infra | `mediapipe` not exactly pinned (`>=0.10.33`). Floating version can silently corrupt CV output. | `pyproject.toml` |
| M-7 | Infra | JWT issuer not validated — tokens from different Supabase projects accepted if `aud=authenticated`. | `api/deps.py` |
| M-8 | Infra | `openapi-typescript` missing from `package.json` devDeps — `npm run generate-types` fails. | `frontend/package.json` |
| M-9 | Infra | No `.nvmrc`, no `engines` field. Node version unenforced locally. | `frontend/` |
| M-10 | Infra | CI `uv sync` without `--frozen` — can silently upgrade packages vs lockfile. | `.github/workflows/ci.yml` |
| M-11 | Infra | `uv` Docker layer pinned to `:latest` — unpinned supply chain dependency. | `backend/Dockerfile` |
| M-12 | Infra | Single-stage Dockerfile — test files, scripts, and `uv` binary ship in production image. | `backend/Dockerfile` |
| M-13 | Infra | No `.env.*` wildcard in `.gitignore`. | `.gitignore` |
| M-14 | Frontend | `TrendChart` tooltip shows raw decimal confidence (e.g. "0.72") — user-visible violation. | `TrendChart.tsx` |
| M-15 | Frontend | `AdminPage` renders raw status strings; includes invalid status `quality_gate_passed`. | `AdminPage.tsx` |
| M-16 | Frontend | `localhost:8000` fallback duplicated in 4 API files + 1 inline JSX. Should be a shared constant. | `src/api/*.ts`, `ResultsPage.tsx` |
| M-17 | Tests | Coaching retry paths untested: 529 overload, `APITimeoutError`, non-retryable 400. | `test_coaching.py` |
| M-18 | Tests | `deps.py` edge branches uncovered: empty `sub`/`email`, `uuid.UUID` ValueError. | `test_auth.py` |
| M-19 | Tests | Rep detection: zero-rep case and partial rep (incomplete descent) not tested. | `test_rep_detection.py` |
| M-20 | Tests | API endpoints `GET /analyses/{id}` and `GET /analyses/{id}/status` have no unit tests. | — |
| M-21 | Tests | Rate limiting: 10th request allowed not asserted (only 11th rejected). | `test_rate_limit.py` |
| M-22 | Tests | Account deletion cascade — no verification that `RepMetric`/`CoachingResult` rows are actually deleted. | `test_account_deletion.py` |
| M-23 | Tests | Frontend: `HomePage`, `AppLayout`, `useAnalysisDetail`, `useAnalysisStatus` have zero test coverage. | `frontend/src/` |
| M-24 | Tests | Weak assertion: `test_heartbeat_written_during_job` TTL check has fallback that trivially passes. | `test_analysis_worker.py` |
| M-25 | Tests | Weak assertion: `test_correct_reject_user_message` uses 3 OR-ed substrings — nearly any message passes. | `test_quality_gates.py` |
| M-26 | Tests | `datetime.utcnow()` deprecation warning in `test_repositories.py:109`. | `test_repositories.py` |

---

## LOW — Backlog

| # | Area | Finding | Location |
|---|------|---------|----------|
| L-1 | Frontend | 7-day banner text is a paraphrase; SRS specifies verbatim wording. | `ResultsPage.tsx` |
| L-2 | Frontend | `as any` cast in `AdminPage.tsx` unnecessary; inconsistent with `AppLayout.tsx`. | `AdminPage.tsx` |
| L-3 | Backend | `REDIS_URL` has localhost fallback — silent failure mode in production if env var missing. | `workers/settings.py` |
| L-4 | Backend | FR-AUTH-03: no defensive `email_confirmed_at` check at FastAPI layer. | `api/deps.py` |
| L-5 | Infra | `@testing-library/dom` in `dependencies` instead of `devDependencies`. | `frontend/package.json` |
| L-6 | Infra | `VERCEL_PREVIEW_ORIGIN` accepts arbitrary origin with no validation. | `main.py` |
| L-7 | Infra | Broad `except Exception` on JWKS path swallows fetch failures silently. | `api/deps.py` |
| L-8 | Infra | Redis has no password (acceptable for loopback-only). | `docker-compose.prod.yml` |
| L-9 | Infra | `analyses.updated_at` has no Postgres `BEFORE UPDATE` trigger. | migration 001 |
| L-10 | Infra | GitHub Actions `appleboy/ssh-action@v1` pinned to major tag, not SHA. | `ci.yml` |
| L-11 | Infra | RLS subquery policies may be slow at scale (acceptable Phase 0). | migration 002 |
| L-12 | Backend | Annotated video font uses `cv2.FONT_HERSHEY_SIMPLEX` (not Arial TTF) — closest OpenCV equivalent. | `cv/video_annotator.py` |
| L-13 | Backend | Experience level values stored lowercase vs SRS title-case — style mismatch only. | `schemas/profile.py` |
| L-14 | Tests | E2E test is a worker integration test — `run_cv_pipeline`, `CoachingService`, and PDF are all mocked. Not a true end-to-end. | `test_full_flow.py` |

---

## Positive Findings

The codebase is fundamentally solid. Key strengths:

- **MediaPipe config**: exact match to SRS (model_complexity=2, static_image_mode=True, num_threads=1, sigmoid applied)
- **Quality gates P0-01/P0-02**: predicates match SRS exactly (landmarks, thresholds, frame count)
- **Rep detection thresholds**: all exercise/variant angles and hysteresis values match SRS
- **Confidence computation**: correct landmark sets per exercise type, sigmoid applied
- **Status machine**: well-implemented with idempotency guard, covers all 7 valid states
- **ARQ settings**: exact match (queue_name, job_timeout=300, max_jobs=1, keep_result=0)
- **All CV operations**: properly wrapped in `run_in_executor`
- **DB connection**: PgBouncer pooler with `statement_cache_size=0`
- **CORS**: correctly blocks wildcard; prod-only origins
- **Rate limiting**: per-user (JWT sub), not per-IP
- **Security**: no hardcoded secrets, no forbidden language, zero TODO/FIXME
- **Backend type safety**: pyright clean, all `type: ignore` comments justified
- **Frontend type safety**: tsc clean, only 2 `as any` casts (both justified)
- **Test mocking**: all LLM/Anthropic and Supabase calls properly mocked in CI

---

## Statistics

| Metric | Value |
|--------|-------|
| Total findings | 67 |
| Critical | 12 |
| High | 15 |
| Medium | 26 |
| Low | 14 |
| Backend unit tests | 542 passing |
| Backend coverage | 90% |
| Frontend tests | 94 passing |
| Lowest coverage file | `pipeline.py` (24%) |

---

## Recommended Fix Order

1. **C-9 + C-2**: Unify confidence thresholds everywhere (backend coaching + frontend 3 files) → single source of truth
2. **C-1**: Install `tus-js-client`, implement TUS upload flow in UploadPage
3. **C-6**: Replace direct status assignment with `transition()` call
4. **C-12**: Align env var naming (`SUPABASE_SERVICE_ROLE_KEY` everywhere)
5. **C-3 + C-4 + C-5**: Frontend SRS text fixes (disclaimer, summary card, status labels)
6. **C-8**: Add video duration validation (40s/2min) and FFprobe check
7. **C-7**: Wire actual barbell detection into pipeline
8. **H-1 + H-2 + H-3 + H-4 + H-5**: Frontend component fixes (ErrorBoundary, button, sort, guidance, download)
9. **H-10 + H-11 + H-12**: Infra hardening (.dockerignore, non-root user, .gitignore)
10. **C-10 + C-11 + H-13–H-15**: Test coverage gaps
