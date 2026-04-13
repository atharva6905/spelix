# Session 25 Handoff → Session 26: Seed corpus complete, Phase 2 admin/expert UI planned

## Completed

| Task | PR | Squash SHA | Description |
|------|----|------------|-------------|
| P2-025 | #33 | `f39e958` | **Seed Coach Brain corpus** — 24 entries (8/exercise) seeded to DB `coach_brain_entries` + Qdrant `coach_brain` collection. Covers squat (depth, knee cave, back rounding), bench (bar path, elbow flare, leg drive), deadlift (lumbar flexion, hip hinge, lockout). `status=seed`, `confirmation_count=1`, `source=seed_manual_validated`. `scripts/seed_coach_brain.py`. 20 validation tests. |
| P2-007 | #33 | `f39e958` | **Seed research papers corpus** — 34 papers (12 squat, 11 bench, 11 deadlift) seeded to DB `rag_documents` + Qdrant `papers_rag`. 36 chunks. Quality tier mix: L1 SR/MA, L2 RCT, L3 observational, L4 guideline. Real metadata, AI-synthesized text (ADR-039). `scripts/seed_research_papers.py`. 13 validation tests. |
| — | — | `b5ca6af` | **Backlog Batches 9-11 + ADR-039** — added P2-035..P2-044 (admin UI + expert reviewer portal), D-017 (replace AI-synthesized text with real PDFs). ADR-039 documents seed corpus strategy. |

## Remaining

### Phase 2 — Batch 9: Admin UI (pending)
| ID | Status | Deps | Notes |
|----|--------|------|-------|
| P2-035 | pending | P2-004 ✅ | Admin RAG corpus management page (FR-ADMN-06, FR-RAGK-08, FR-RAGK-09) |
| P2-036 | pending | P2-035 | Admin expert reviewer queue page (FR-ADMN-07) |
| P2-037 | pending | P2-035 | Admin Coach Brain management page (FR-ADMN-10) |

### Phase 2 — Batch 10: Expert Reviewer Portal (pending)
| ID | Status | Deps | Notes |
|----|--------|------|-------|
| P2-038 | pending | — | Expert Reviewer portal route + role check (FR-EXPV-01) |
| P2-039 | pending | P2-038 | Expert review queue (FR-EXPV-02) |
| P2-040 | pending | P2-039 | Expert review detail view (FR-EXPV-03) |
| P2-041 | pending | P2-040 | Expert annotation submission form (FR-EXPV-04) |
| P2-042 | pending | P2-038 | Expert paper upload (FR-EXPV-05) |
| P2-043 | pending | P2-042 | Expert paper review workflow (FR-EXPV-06) |
| P2-044 | pending | P2-041 | Golden dataset workflow (FR-EXPV-07) |

### Phase 2 — Batch 11: Data Quality (deferred)
| ID | Status | Deps | Notes |
|----|--------|------|-------|
| D-017 | pending | P2-007 ✅ | Replace AI-synthesized paper text with real full-text PDFs via Docling. Must complete before Phase 4 eval metrics are meaningful. |

### Tech debt (unchanged)
| ID | Status | Notes |
|----|--------|-------|
| D-004..D-010 | open | Session 13 tech debt items |
| — | open | `.env.example` needs Langfuse vars added |

## Test counts

- **Backend**: 1330 passed / 19 skipped / 0 failures (+33 from session 24's 1297)
- **Frontend**: 225 passed / 0 failures (unchanged)
- **CI**: All 6 checks green on PR #33

## E2E verification

Skipped — this session added seed data scripts and backlog/ADR documentation only. No user-facing features were changed. The scripts ran against live Supabase and Qdrant Cloud, and data was verified via SQL queries (24 coach_brain_entries rows, 34 rag_documents rows).

## Blockers

None. All code deps for Batches 9-10 are met. The admin/expert reviewer UI work is pure frontend+API route implementation.

## Next session start

```bash
/status
# 1. Decide: implement Batches 9-10 (admin/expert UI) OR run Phase 2 transition gate
#    to evaluate if admin/expert features can defer to Phase 3.
#    Key question: does the SRS allow Phase 2 → 3 transition without FR-EXPV-* and FR-ADMN-06/07/10?
#    Check: rg "Phase 2.*gate\|transition.*criteria" docs/SRS.md
# 2. If proceeding with Batches 9-10:
#    /plan — design admin API routes + frontend pages
#    Start with P2-035 (admin corpus management) as it unblocks P2-036 and P2-037
# 3. If deferring admin UI to Phase 3:
#    Run Phase 2 transition gate (/phase)
#    Seed Phase 3 backlog from SRS Must filter
```
