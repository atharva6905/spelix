# backlog.md — Phase 0 Task List

| ID | Title | Status | Phase | SRS IDs | Size | Deps | Notes |
|----|-------|--------|-------|---------|------|------|-------|
| B-001 | Project scaffold + Docker Compose | done | 0 | NFR-OPER-01, NFR-SECU-11, NFR-SECU-12 | M | — | Health endpoint, CORS, Redis |
| B-002 | SQLAlchemy models + migration 001 | done | 0 | Sec 7.2, 7.3 | L | B-001 | 4 tables, CHECK constraint, indexes |
| B-003 | Status transition guard | done | 0 | Sec 5.2a | S | B-002 | Pure function, TDD first |
| B-004 | Repository layer | done | 0 | Sec 5.1, NFR-MAIN-08 | M | B-002 | 4 repos, AsyncSession DI |
| B-005 | Supabase JWT auth dependency | done | 0 | FR-AUTH-02, FR-AUTH-08, NFR-SECU-05 | S | B-001 | get_current_user, admin check |
| B-006 | Supabase RLS policies | todo | 0 | FR-AUTH-06, NFR-SECU-01, NFR-SECU-06 | S | B-002 | Raw SQL in migration 002 |
| B-007 | Frontend auth + routes | todo | 0 | FR-AUTH-01, FR-AUTH-04, FR-AUTH-05 | M | B-001 | Login, signup, RequireAuth |
| B-008 | Profile API + onboarding page | todo | 0 | FR-PROF-01–05 | M | B-004, B-005 | Required + optional body stats |
| B-009 | Upload API (POST /analyses + /start) | todo | 0 | FR-UPLD-07, FR-UPLD-16, FR-UPLD-17 | L | B-004, B-005 | Signed URL, enqueue ARQ |
| B-010 | Rate limiting middleware | todo | 0 | NFR-SECU-10 | S | B-009 | slowapi + Redis, 10/user/day |
| B-011 | ARQ worker skeleton | todo | 0 | FR-UPLD-18, NFR-RELI-01–04, NFR-OPER-02 | M | B-003, B-004 | Heartbeat, idempotent, retry |
| B-012 | Quality gates | todo | 0 | FR-CVPL-03–11 | M | — | Body visibility, framing, warnings |
| B-013 | Upload page (frontend) | todo | 0 | FR-XDET-01–02, FR-XDET-05, FR-XDET-08–09, FR-UPLD-01–09 | L | B-007 | TUS upload, filming guidance |
| B-014 | Analysis status page (frontend) | todo | 0 | FR-RESL-13, NFR-RELI-06 | M | B-007 | Realtime sub, polling fallback |
| B-015 | MediaPipe pose extraction | todo | 0 | FR-CVPL-01, FR-CVPL-02, FR-CVPL-12–13 | M | B-001 | Exact config, sigmoid guard |
| B-016 | Savitzky-Golay + angle calc | todo | 0 | FR-CVPL-14 | S | — | Pure math functions |
| B-017 | Rep detection state machine | todo | 0 | FR-CVPL-15, FR-REPM-01, FR-REPM-05 | L | B-016 | Per-exercise thresholds, hysteresis |
| B-018 | Per-rep metric extraction | todo | 0 | FR-REPM-02–03, Sec 3.7 | XL | B-017 | 3 exercise analyzers, all metrics |
| B-019 | Phase 0 confidence scoring | todo | 0 | FR-CVPL-16, FR-RESL-08, FR-REPM-04 | S | — | Mean visibility, label mapping |
| B-020 | Barbell detection + tracking | todo | 0 | FR-BDET-01–07 | M | — | OpenCV contour, graceful null |
| B-021 | Annotated video + artifacts | todo | 0 | FR-CVPL-19, FR-UPLD-15, FR-XPRT-01 | L | B-018, B-020 | Skeleton overlay, plot, upload |
| B-022 | Wire CV pipeline in worker | todo | 0 | FR-UPLD-15, FR-UPLD-18 | L | B-011–B-021 | Full pipeline integration |
| B-023 | Phase 0 coaching service | todo | 0 | FR-RESL-03, Appendix D | M | — | Claude Sonnet, instructor, mock in tests |
| B-024 | Wire coaching in worker | todo | 0 | Status 5.2a | M | B-022, B-023 | processing→coaching→completed |
| B-025 | Thresholds config file | todo | 0 | FR-SCOR-00 | S | — | JSON file, named constants |
| B-026 | Results page (frontend) | todo | 0 | FR-RESL-01a–05, FR-RESL-08, FR-RESL-10–11, FR-SCOR-09–10 | XL | B-007 | Video, coaching, metrics, disclaimer |
| B-027 | Status poll endpoint | todo | 0 | FR-RESL-13 | S | B-004 | GET /analyses/{id}/status |
| B-028 | Analysis CRUD (delete/rename/tags) | todo | 0 | FR-UPLD-10–11, FR-XPRT-05 | M | B-004 | Cascade delete + Storage cleanup |
| B-029 | List + get analysis endpoints | todo | 0 | FR-HIST-01 | S | B-004 | Reverse chronological, user-filtered |
| B-030 | Summary metrics computation | todo | 0 | FR-HIST-04 | M | B-024 | Write summary_json after completion |
| B-031 | History insights endpoints | todo | 0 | FR-HIST-02–03 | M | B-030 | Rolling avg, personal best, global |
| B-032 | History page (frontend) | todo | 0 | FR-HIST-01–03, FR-HIST-06 | L | B-031 | List, insights, Recharts trends |
| B-033 | Admin API endpoints | todo | 0 | FR-ADMN-01–05 | M | B-005 | Admin role check, health panel |
| B-034 | Admin page (frontend) | todo | 0 | FR-ADMN-01–05 | M | B-033 | User mgmt, analysis log, health |
| B-035 | PDF report generation | todo | 0 | FR-XPRT-02–03 | L | B-024 | WeasyPrint, HTML template, background job |
| B-036 | CSV data export | todo | 0 | FR-XPRT-04, NFR-SECU-07 | S | B-004 | GDPR Article 20 |
| B-037 | Account deletion | todo | 0 | FR-AUTH-07, FR-XPRT-05, NFR-SECU-08 | M | B-004 | Full cascade purge |
| B-038 | Artifact cleanup cron | todo | 0 | FR-UPLD-15, FR-UPLD-19 | S | B-011 | Nightly, 7-day retention |
| B-039 | Error boundaries (frontend) | todo | 0 | NFR-USAB-09 | S | B-007 | Component-level recovery |
| B-040 | OpenAPI type generation | todo | 0 | NFR-MAIN-07 | S | B-029 | openapi-typescript |
| B-041 | E2E integration test | todo | 0 | NFR-MAIN-04 | L | all | Full flow with fixture video |
| B-042 | CI pipeline (GitHub Actions) | todo | 0 | NFR-MAIN-01, NFR-MAIN-05–06 | M | all | ruff, pyright, pytest, vitest, coverage |
