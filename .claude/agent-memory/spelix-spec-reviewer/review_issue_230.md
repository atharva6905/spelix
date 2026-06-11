---
name: review_issue_230
description: Spec review of issue #230 — seed_research_papers.py doi column fix: PASS, 2026-06-10
metadata:
  type: project
---

## Reviewed: issue #230 (seed doi column, 2026-06-10) → PASS

Commit 6107afd on branch fix/issue-230-seed-doi-column.

**Requirements verified:**
1. _INSERT_SQL includes doi column and :doi binding → DONE (seed_research_papers.py ~line 855)
2. build_rag_document_row writes normalize_doi(paper.doi) → DONE; None branch explicit
3. validate_seed_dois() called at top of main() before DB work → DONE (line 924, before dry-run guard at 936)
4. Fail fast on malformed DOIs with entry name in error message → DONE
5. NULL only for entries that genuinely lack a DOI → DONE (None branch)
6. __import__("json") hack replaced with top-level import json → DONE
7. Actual INSERT uses text(_INSERT_SQL) + build_rag_document_row → DONE (lines 993-994)
8. --dry-run path still works (validate_seed_dois runs, then early return before DB) → DONE
9. 6 new tests in TestSeedDoiColumn → DONE (all 6 named tests present)

**No OVER-BUILT scope detected** — only seed script + test file touched.

**Pattern note:** validate_seed_dois is placed BEFORE the dry_run early-return, so --dry-run
also validates DOIs. This is correct behavior (fail-fast applies regardless of mode).
