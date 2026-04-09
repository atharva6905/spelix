# backlog.md — Phase 0 Hardening + Phase 1 Prep

Phase 0 core build complete (B-001 through B-042). Audit on 2026-04-09 found 67 issues.
Full audit: `docs/phase0-audit.md`. Detailed reports: `docs/audit-{backend,frontend,tests,infra}.md`.

## Completed (Phase 0 Core Build)

B-001–B-011, B-015–B-019, B-023–B-025, B-027–B-032, B-035–B-038, B-042 — all verified clean by audit.

Items B-012, B-013, B-020, B-022, B-026, B-033, B-034, B-039, B-040, B-041 had audit findings — reclassified as fix tasks below.

---

## Active Backlog — Audit Fixes

### CRITICAL — Must Fix Before Phase 1

| ID | Title | Status | Size | Deps | SRS IDs | Audit Ref | Files |
|----|-------|--------|------|------|---------|-----------|-------|
| B-043 | Unify confidence thresholds to SRS values | todo | S | — | FR-RESL-08, FR-CVPL-16, FR-SCOR-10 | C-2, C-9 | `coaching.py`, `ResultsPage.tsx`, `HistoryPage.tsx`, `InsightsPanel.tsx` |
| B-044 | Implement TUS upload flow in frontend | todo | L | — | FR-UPLD-06, FR-UPLD-08 | C-1 | `UploadPage.tsx`, `package.json` (add `tus-js-client`) |
| B-045 | Fix status transition bypass in worker error handler | todo | S | — | Sec 5.2a | C-6 | `analysis_worker.py:333` |
| B-046 | Align env var naming: SUPABASE_SERVICE_ROLE_KEY | todo | S | — | — | C-12 | `.env.example`, `analyses.py`, `storage.py`, `cleanup.py`, `analysis_worker.py` |
| B-047 | Add three-tier disclaimer to results page | todo | S | — | FR-RESL-11 | C-3 | `ResultsPage.tsx` |
| B-048 | Add rep count + timestamp to summary card | todo | S | — | FR-RESL-01a | C-4 | `ResultsPage.tsx` |
| B-049 | Fix Appendix B status label mapping | todo | S | — | Appendix B | C-5 | `useAnalysisStatus.ts` |
| B-050 | Add video duration validation (40s/2min) | todo | M | — | FR-UPLD-02/03/05 | C-8 | `pipeline.py` or `analysis_worker.py` |
| B-051 | Add FFprobe codec validation | todo | M | — | FR-UPLD-14 | C-8 | `pipeline.py` |
| B-052 | Wire actual barbell detection into pipeline | todo | M | — | FR-BDET-01/02/03 | C-7 | `pipeline.py` |
| B-053 | Write `test_pipeline.py` — pipeline orchestration tests | todo | L | — | — | C-10 | `tests/unit/test_pipeline.py` |
| B-054 | Add video test fixtures | todo | M | — | — | C-11 | `tests/fixtures/` |

### HIGH — Should Fix Before Phase 1

| ID | Title | Status | Size | Deps | SRS IDs | Audit Ref | Files |
|----|-------|--------|------|------|---------|-----------|-------|
| B-055 | Wrap all routes in ErrorBoundary | todo | S | — | NFR-USAB-09 | H-1 | `routes.tsx`, `App.tsx` |
| B-056 | Fix upload button disabled state (keyboard) | todo | S | — | FR-XDET-09 | H-2 | `UploadPage.tsx` |
| B-057 | Add sort control to rep metrics table | todo | S | — | FR-RESL-04 | H-3 | `ResultsPage.tsx` (RepMetricsTable) |
| B-058 | Add per-level confidence guidance text | todo | S | — | FR-RESL-08 | H-4 | `ResultsPage.tsx` |
| B-059 | Add annotated video MP4 download link | todo | S | — | FR-RESL-02, FR-XPRT-01 | H-5 | `ResultsPage.tsx` |
| B-060 | Fix admin health endpoint — inject Redis into AdminService | todo | S | — | FR-ADMN-05 | H-7 | `api/v1/admin.py`, `services/admin.py` |
| B-061 | Implement single-person quality gate | todo | M | — | FR-CVPL-06 | H-8 | `cv/quality_gates.py` |
| B-062 | Implement resolution quality gate (≥720p) | todo | S | — | FR-CVPL-07 | H-8 | `cv/quality_gates.py` |
| B-063 | Add occlusion detection warning | todo | M | — | FR-CVPL-17 | H-9 | `cv/quality_gates.py` or `cv/confidence.py` |
| B-064 | Add `.dockerignore` | todo | S | — | — | H-10 | `backend/.dockerignore` |
| B-065 | Add non-root user to Dockerfile | todo | S | — | — | H-11 | `backend/Dockerfile` |
| B-066 | Add `.env.local` + `.env.*` to `.gitignore` | todo | S | — | — | H-12 | `.gitignore` |
| B-067 | Test JWKS ES256 auth path | todo | M | — | — | H-13 | `tests/unit/test_auth.py` |
| B-068 | Test `_generate_and_upload_pdf` in isolation | todo | S | — | — | H-14 | `tests/unit/test_analysis_worker.py` |
| B-069 | Cover `analysis_worker.py` gaps (70%→90%) | todo | M | — | — | H-15 | `tests/unit/test_analysis_worker.py` |
| B-070 | Regenerate OpenAPI types from live backend | todo | M | B-044 | — | H-6 | `src/api/types.ts`, `package.json` (add `openapi-typescript` devDep) |

### MEDIUM — Fix During Phase 1

| ID | Title | Status | Size | Deps | SRS IDs | Audit Ref | Files |
|----|-------|--------|------|------|---------|-----------|-------|
| B-071 | Refactor InsightsService + AdminService to use repositories | todo | M | — | — | M-1 | `services/insights.py`, `services/admin.py` |
| B-072 | Use Literal types in AnalysisCreate schema | todo | S | — | — | M-2 | `schemas/analysis.py` |
| B-073 | Add `weight_kg` to AnalysisCreate schema | todo | S | — | FR-REPM-06 | M-4 | `schemas/analysis.py` |
| B-074 | Pin mediapipe to exact version | todo | S | — | — | M-6 | `pyproject.toml` |
| B-075 | Add JWT issuer validation | todo | S | — | — | M-7 | `api/deps.py` |
| B-076 | Add `.nvmrc` + `engines` field | todo | S | — | — | M-9 | `frontend/.nvmrc`, `frontend/package.json` |
| B-077 | CI: use `uv sync --frozen` | todo | S | — | — | M-10 | `.github/workflows/ci.yml` |
| B-078 | Pin `uv` Docker image tag | todo | S | — | — | M-11 | `backend/Dockerfile` |
| B-079 | Multi-stage Dockerfile | todo | M | B-064, B-065 | — | M-12 | `backend/Dockerfile` |
| B-080 | Add `.env.*` wildcard to `.gitignore` | todo | S | — | — | M-13 | `.gitignore` |
| B-081 | Fix TrendChart tooltip — show label not decimal | todo | S | — | FR-RESL-08 | M-14 | `TrendChart.tsx` |
| B-082 | Fix AdminPage raw status strings + invalid status | todo | S | — | Appendix B | M-15 | `AdminPage.tsx` |
| B-083 | Extract shared API_BASE constant | todo | S | — | — | M-16 | `src/api/*.ts`, `ResultsPage.tsx` |
| B-084 | Test coaching retry paths (529, timeout, 400) | todo | S | — | — | M-17 | `tests/unit/test_coaching.py` |
| B-085 | Test deps.py edge branches (empty sub/email, UUID) | todo | S | — | — | M-18 | `tests/unit/test_auth.py` |
| B-086 | Test rep detection zero-rep + partial rep | todo | S | — | — | M-19 | `tests/unit/test_rep_detection.py` |
| B-087 | Test GET /analyses/{id} and /status endpoints | todo | S | — | — | M-20 | `tests/unit/test_analysis_api.py` |
| B-088 | Test rate limit 10th-request boundary | todo | S | — | — | M-21 | `tests/unit/test_rate_limit.py` |
| B-089 | Test account deletion cascade (rep_metrics, coaching) | todo | S | — | — | M-22 | `tests/unit/test_account_deletion.py` |
| B-090 | Frontend tests: HomePage, AppLayout, hooks | todo | M | — | — | M-23 | `frontend/src/` |
| B-091 | Fix weak test assertions (heartbeat TTL, QG message) | todo | S | — | — | M-24, M-25 | `test_analysis_worker.py`, `test_quality_gates.py` |
| B-092 | Fix `datetime.utcnow()` deprecation | todo | S | — | — | M-26 | `test_repositories.py:109` |
| B-093 | Implement lighting + stability warning gates | todo | M | — | FR-CVPL-08/09 | M-3 | `cv/quality_gates.py` |

---

## Parallelization Guide

### Safe to run in parallel (non-overlapping file paths)

**Batch A — Frontend fixes (B-043f, B-047–B-049, B-055–B-059, B-081–B-083):**
All under `frontend/src/`. Can be split by page:
- Agent 1: `ResultsPage.tsx` fixes (B-047, B-048, B-057, B-058, B-059)
- Agent 2: `UploadPage.tsx` + status + routes (B-044, B-049, B-055, B-056)
- Agent 3: `TrendChart.tsx` + `AdminPage.tsx` + API constants (B-081, B-082, B-083)

**Batch B — Backend fixes (B-043b, B-045, B-046, B-050–B-052, B-060–B-063):**
- Agent 1: `cv/quality_gates.py` (B-061, B-062, B-063)
- Agent 2: `pipeline.py` + `analysis_worker.py` (B-045, B-050, B-051, B-052)
- Agent 3: `services/coaching.py` + `admin.py` + env var rename (B-043b, B-046, B-060)

**Batch C — Infra (B-064–B-066, B-074–B-078, B-080):**
All touch different files, safe to parallelize or batch as single agent.

**Batch D — Tests (B-053, B-067–B-069, B-084–B-092):**
All under `tests/`. Can be split by test file.

### Must be sequential
- B-044 (TUS upload) before B-070 (OpenAPI types) — types depend on working upload flow
- B-064 + B-065 before B-079 — multi-stage build depends on .dockerignore and non-root user
