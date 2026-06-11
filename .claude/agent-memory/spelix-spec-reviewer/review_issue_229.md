---
name: review_issue_229
description: Spec review of issue #229 — IntegrityError catch on review_paper endpoint (FR-EXPV-03): PASS, 2026-06-10
metadata:
  type: project
---

## Reviewed: issue #229 (review IntegrityError, 2026-06-10) → PASS

FR-IDs: FR-EXPV-03. Commit 58a6bb5 on branch fix/issue-229-review-integrityerror.

**Requirements verified:**
1. Catch IntegrityError in review_paper → DONE (expert.py ~line 507)
2. Return 409 DUPLICATE_DOI in standard envelope → DONE (matches complete_paper_upload shape exactly)
3. db.rollback() called (discard poisoned tx) → DONE (expert.py line 513)
4. Row NOT deleted (no cleanup, unlike complete_paper_upload) → DONE (no delete call in except block)
5. db dependency injected via Depends(get_db) — same cached session as rag_repo → DONE
6. Test: IntegrityError → 409 DUPLICATE_DOI, rollback asserted_awaited_once, delete assert_not_awaited → DONE (test_admin_expert_routes.py TestExpertPaperReview)
7. No OVER-BUILT scope detected — only the minimal catch block + test added

**Patterns worth noting:**
- The test patches `app.api.v1.expert.RagDocumentRepository` at class level, not `_get_rag_repo`, matching the existing test class pattern.
- expert_app fixture's mock_db wires get_db override → rollback assertion is valid.
- IntegrityError import was already present on line 14 (from sqlalchemy.exc); no duplicate import added.
