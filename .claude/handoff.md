# Session 26 Handoff → Session 27: Phase 2 Batches 9-10 complete

## Completed

| Task | PR | SHA | Description |
|------|----|-----|-------------|
| P2-035 | #34 | `5e63cb2` | **Admin RAG corpus management** — Migration 006, RagDocument model, RagDocumentRepository, admin routes (list/delete/re-embed), RagCorpusPanel on AdminPage with filters + pagination |
| P2-036 | #34 | `5e63cb2` | **Admin expert reviewer queue** — list_flagged_analyses, get_expert_queue_stats, ExpertQueuePanel with stats summary |
| P2-037 | #34 | `5e63cb2` | **Admin Coach Brain management** — Extended CoachBrainRepository with CRUD, admin routes (list/create/update/delete), CoachBrainPanel with filters + approve/deprecate/delete |
| P2-038 | #34 | `5e63cb2` | **Expert portal route + role check** — get_expert_reviewer_user dep (admin + expert_reviewer), ExpertPortalPage.tsx, /expert route |
| P2-039 | #34 | `5e63cb2` | **Expert review queue** — GET /expert/queue with queue_type filter, ExpertService.get_review_queue, tab UI |
| P2-040 | #34 | `5e63cb2` | **Expert analysis detail** — Anonymized (no user_id), ExpertAnalysisDetailPage.tsx |
| P2-041 | #34 | `5e63cb2` | **Expert annotation submission** — POST /expert/analyses/{id}/annotations, AnalysisExpertReview model, annotation form |
| P2-042 | #34 | `5e63cb2` | **Expert paper upload** — POST /expert/papers, ExpertPaperUploadPage.tsx |
| P2-043 | #34 | `5e63cb2` | **Expert paper review** — PATCH /expert/papers/{id}/review with decision enum |
| P2-044 | #34 | `5e63cb2` | **Golden dataset labeling** — PATCH /expert/analyses/{id}/golden, is_golden_label on annotation form |
| — | #34 | `5e63cb2` | **ADR-040** (analysis_expert_reviews table naming), **ADR-041** (dual-role expert access) |

## Test counts

- **Backend**: 1367 passed / 19 skipped / 0 failures (+37 from session 25's 1330)
- **Frontend**: 225 passed / 0 failures (unchanged)
- **Lint**: ruff clean, tsc clean

## Migration

- **006_admin_expert_reviews** applied to Supabase. Adds promoted columns to rag_documents + new analysis_expert_reviews table.

## Remaining

### Phase 2 — Batch 11: Data Quality (deferred)
| ID | Status | Notes |
|----|--------|-------|
| D-017 | pending | Replace AI-synthesized paper text with real PDFs via Docling. Deferred until Phase 4 eval. |

### Tech debt (unchanged)
| ID | Status | Notes |
|----|--------|-------|
| D-004..D-010 | open | Session 13 tech debt items |

## Phase 2 Completion Status

All Phase 2 Must requirements are now implemented:
- Batches 1-8: completed in sessions 14-25
- Batch 9 (Admin UI): P2-035/036/037 done
- Batch 10 (Expert Portal): P2-038 through P2-044 done
- Batch 11 (D-017): deferred — not a Must requirement for Phase 2 gate

## Next session start

```bash
/status
# 1. Wait for PR #34 CI to go green, then merge:
#    gh pr merge 34 --squash --delete-branch && git checkout main && git pull
# 2. E2E verification on spelix.app:
#    - Login as admin → verify /admin shows corpus/brain/queue panels
#    - Verify /expert returns 403 for regular users
# 3. Run Phase 2 transition gate:
#    /phase — verify all Phase 2 Must requirements implemented
# 4. If gate passes, begin Phase 3 planning:
#    - Seed Phase 3 backlog from SRS Must filter
#    - Activate spelix-langgraph-engineer agent
```

## Blockers

None. PR #34 awaiting CI.
