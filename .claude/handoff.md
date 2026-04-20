# Session 56 Handoff → Session 57: D-039 + D-030 shipped

**Context (session 56, 2026-04-20, L2 Sprint Day 14):** Shipped D-039 (CoVe re-run on admin content edit) and D-030 (orphan rag_documents cleanup cron). Both backend-only, no migrations, no frontend changes.

## 1. Completed

### PR #105 — D-039: CoVe re-run on admin content edit during approve
Merge commit `596b77b`. 5 commits on branch `feat/d039-cove-rerun-on-approve-edit`:

| Commit | Scope |
|---|---|
| `b509ae1` | TDD red: 5 failing tests for CoVe re-run behavior |
| `186c434` | `_rerun_cove_for_edited_content` method + `approve` flow update |
| `24aec8d` | Wire `BrainCoveService` + `RetrievalService` into `_get_review_service` |
| `e574060` | Pyright fix: add assertions for optional service fields |
| `0210a81` | Docs: D-039 closed in backlog + ADR-COVE-RERUN-01 |

Backend: +5 tests (19 total in `test_candidate_review_service.py`). Ruff + pyright clean. CI 6/6 green.

### PR #106 — D-030: Nightly orphan `rag_documents` cleanup cron
Merge commit `befba80`. 4 commits on branch `feat/d030-orphan-rag-cleanup`:

| Commit | Scope |
|---|---|
| `86d9fa6` | TDD: 6 tests for orphan cleanup |
| `0226e55` | `cleanup_orphan_papers.py` — query stale uploading rows, delete Storage + DB |
| `abdd6a2` | Register `cleanup_orphan_papers_cron` at 04:00 UTC in `streaq_worker.py` |
| `1e4db53` | Backlog close |

Backend: +6 tests. Cron runs at 04:00 UTC (distinct from artifact cleanup 03:00, Qdrant keepalive 02:00). CI 6/6 green.

## 2. Remaining open items

- **L2 gate blocker**: Invite 3-5 trusted test users through end-to-end flow
- Landing V2-01: "Four Dimensions" section (pending)
- Landing V2-02: "Roadmap" section (pending)
- M-06: Phase 4 eval_scores.overall precedence check (pending, Phase 4 scope)
- D-056: Working vs non-working rep distinction (open post-L2)

## 3. L2 Sprint Gate Status (May 3)

| Gate | Status |
|------|--------|
| Landing page V1 live | done |
| Expert paper upload live | done |
| ARQ → streaq migration | done |
| Phase 3 agent on prod | done |
| Distillation StateGraph operational | done |
| Coach Brain review queue | done |
| Reasoning sidebar | done |
| 3-5 trusted test users | **NOT YET** |
| No CRITICAL prod bugs | verified — D-039 + D-030 were the last open items |

## 4. Test counts

- Backend: ~1720+ (1710 baseline + 5 D-039 + 6 D-030)
- Frontend: ~333 (unchanged)
- 0 failures
