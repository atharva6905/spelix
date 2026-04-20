# Session 55 Handoff → Session 56: D-029 + D-031 shipped (PR #TBD)

**Context (session 55, 2026-04-20, L2 Sprint Day 14):** Shipped D-029 (SaMD column rename `injury_advice_accurate` → `movement_advice_accurate`) and D-031 (admin `review_status` Literal constraint + `uploading` exclusion). 4 commits on branch `fix/d029-d031-samd-rag-literal`.

## 1. Completed

### PR #TBD — D-029 + D-031

4 commits on branch `fix/d029-d031-samd-rag-literal`:

| Commit | Scope |
|---|---|
| `1ff5ecf` | D-031: `RagReviewStatusFilter` Literal type on `GET /admin/rag/documents`, `exclude_uploading` default in repo, 2 new tests |
| `96aaabb` | D-029: Migration 013 — `ALTER TABLE analysis_expert_reviews RENAME COLUMN injury_advice_accurate TO movement_advice_accurate` |
| `e975c94` | D-029: Backend rename across SQLAlchemy model, Pydantic schemas (AnnotationCreate + AnnotationResponse), service layer, test fixtures + 1 TDD guard test |
| `8f1cfc8` | D-029: Frontend rename across expert.ts interfaces + ExpertAnalysisDetailPage.tsx (11 occurrences) |

**Test delta**: 36 → 39 passed in `test_admin_expert_routes.py` (+3: D-031 422 test, D-031 exclude_uploading test, D-029 field-name guard). Frontend: all pass (no tests reference the renamed field).

## 2. Remaining open items

- D-030: Orphan `rag_documents` cleanup cron (pending)
- D-039: Re-run CoVe after admin content edit on approve (open)
- D-036: GPU offload for pose extraction (deferred post-beta)
- M-06: Phase 4 eval_scores.overall precedence check (pending)

## 3. Post-merge action required

- Apply migration 013 on prod: CI "Deploy to Production" handles this automatically via `alembic upgrade head` in the Docker entrypoint.
- E2E verification: this PR touches the expert portal annotation form. After deploy, navigate to an expert analysis detail page on prod and confirm the annotation form submits successfully with the new `movement_advice_accurate` field name.

## 4. Test counts

- Backend: 39 in `test_admin_expert_routes.py` (full suite ~1710+)
- Frontend: unchanged
- 0 failures
