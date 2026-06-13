---
name: review_issue_264
description: Spec review of issue #264 — seed_research_papers.py review_status column + idempotency re-run: PASS-WITH-NITS, 2026-06-12
metadata:
  type: project
---

## Reviewed: issue #264 (seed review_status + idempotency, 2026-06-12) → PASS-WITH-NITS

Branch: fix/issue-264-seed-review-status. Commit a657499.

**Requirements verified:**

Fix 1 — review_status column:
1. _INSERT_SQL includes review_status column and :review_status bind param → DONE (seed_research_papers.py:865-867)
2. build_rag_document_row sets "review_status": "reviewed_approved" at top-level → DONE (line 937)
3. review_status also set in metadata JSONB (pre-existing from issue text) → DONE (line 934)
4. TestSeedDoiColumn extended: test_insert_sql_includes_review_status_column + test_row_review_status_is_reviewed_approved → DONE

Fix 2 — idempotency:
5. main() skips papers with non-null DOIs already in DB via SELECT before INSERT → DONE (lines 1024-1032)
6. doi=None papers always inserted (no dedup possible) → DONE (if paper.doi is not None guard)
7. Skipped titles logged → DONE (print f"  [skip] already exists: {paper.title[:60]}")
8. Script-header comment documenting re-run behavior → DONE (lines 16-22)

**doi_exists_live helper analysis:**
- Defined as a sync helper (takes sync session). main() duplicates the logic inline with await session.execute.
- doi_exists_live is exported and tested in isolation but NOT called by main(). This is a
  mild coherence issue (unused exported helper) but does NOT block correctness — main() has
  the correct logic directly.
- The _DOI_EXISTS_SQL comment says "uq_rag_documents_doi_live scope" but the SQL is a plain
  WHERE doi = :doi with no live/tombstone predicate. Since rag_documents has no soft-delete
  status column for rows (only review_status which is never 'tombstoned'), a plain equality
  check is functionally correct. A deprecated row would have review_status='deprecated' but
  the same doi value; the seed should skip on any matching DOI regardless. So the plain SELECT
  is adequate in practice.

**Tests:** Two new tests in TestSeedDoiColumn cover Fix 1 directly. Two new tests in
TestSeedIdempotency cover doi_exists_live helper True/False paths. main() idempotency path
is NOT tested end-to-end (would require an integration test hitting a real DB), but the
unit-level coverage of the building-block helper is acceptable for a seed script.

**Over-build check:** Only seed_research_papers.py and its test file changed. No models/
schemas/alembic touched. Scope-clean.

**Pyright pre-existing error:** quality_tier str vs QualityTier|None typing issue is
pre-existing; not introduced by this diff. Confirmed via or-idiom memory (#267).
