---
name: review_issue_234
description: Spec review of issue #234 — DOI optional for non-research-paper types (FR-EXPV-02): PASS, 2026-06-11
metadata:
  type: project
---

## Reviewed: issue #234 (DOI optional by document type, 2026-06-11) → PASS

Branch: feat/issue-234-doi-optional-types. Commits: a5594ce (backend) + 6236afb (frontend).

**Requirements verified:**

Backend schema:
1. `doi: str | None` with `default=None` + `min_length=1` on non-null values → DONE (rag_document.py:142)
2. `@model_validator(mode="after")` requiring doi for `document_type == "research_paper"` → DONE (rag_document.py:152-159)
3. Error message "A DOI is required for research papers." — test asserts substring "DOI is required for research papers" which is present → PASS
4. `normalize_doi` + 409/422 paths kept for non-null values via `if body.doi is not None:` guard → DONE (expert.py)
5. Tests: both validator arms — research_paper+null=422, non-research+null=201, non-research+valid_doi=normalized+deduped, non-research+malformed_doi=422, all 4 DOI-less types via parametrize → DONE

Frontend:
6. Document Type select added (JUSTIFIED: `document_type` was hardcoded `research_paper`; without the select, DOI-less types are unreachable) — not YAGNI
7. Select options match `DocumentTypeLiteral` exactly (5 values, same order) → DONE
8. DOI label shows `*` for research_paper, `(optional)` for others → DONE
9. Submit disabled: `form.document_type === "research_paper" && !form.doi.trim()` → DONE
10. In-handler guard conditional on `doiRequired = form.document_type === "research_paper"` → DONE
11. Payload: `...(form.doi.trim() ? { doi: form.doi.trim() } : {})` — omits doi when empty for any type; sends when non-empty for any type → DONE
12. `PaperUploadMetadata.doi` changed to `doi?: string` in expert.ts → DONE
13. Frontend tests: 8 cases covering options list, required marker, submit-enable/disable, payload (doi absent + doi present), type switch re-enables DOI req, in-handler guard bypass → DONE

Verify null-DOI no-ops:
- Pre-check: `get_live_by_doi` skipped when `doi is None` → tested (`assert_not_awaited` in test_textbook_without_doi_returns_201_and_skips_dedup)
- Complete-step race: `complete_paper_upload` code unchanged; partial index `WHERE doi IS NOT NULL` won't fire for null-DOI docs; task said "verify" (not "test"); code-level review confirms no-op; no dedicated test required

**No OVER-BUILT scope detected.** Document type select is a necessary enabler. No extra endpoints/components.

**Patterns noted:**
- `test_rag_document_schema_sex.py` passes `doi="10.1234/test"` with default `research_paper` type — still valid under new schema; no breakage.
- "verify … no-op" wording in task scope checklist = code-level review, not a test mandate, when the code path is untouched by the diff.
