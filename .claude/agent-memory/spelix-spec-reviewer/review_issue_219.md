---
name: review_issue_219
description: Spec review of issue #219 — DOI required field + DUPLICATE_DOI/INVALID_DOI inline error on ExpertPaperUploadPage
metadata:
  type: project
---

## Reviewed: issue #219 (DOI upload form, 2026-06-09) → PASS

FR-IDs: FR-EXPV-02, FR-EXPV-05. Commit 28e95f3 on branch feat/issue-219-doi-upload-form.

**What was implemented (all required):**
- `PaperUploadMetadata.doi` changed optional→required (`expert.ts:103`)
- `doiError` state added (`ExpertPaperUploadPage.tsx:91`)
- DOI label asterisk (`ExpertPaperUploadPage.tsx:307`)
- onChange handler clears `doiError` (`ExpertPaperUploadPage.tsx:314`)
- Inline `role="alert"` `<p>` adjacent to DOI input (`ExpertPaperUploadPage.tsx:322`)
- Submit disabled gains `|| !form.doi.trim()` (`ExpertPaperUploadPage.tsx:457`)
- Payload uses `doi: form.doi.trim()` (no `|| undefined`) (`ExpertPaperUploadPage.tsx:175`)
- Catch block handles 409 DUPLICATE_DOI / 422 INVALID_DOI → setDoiError + setUploadPhase("idle") + early return (`ExpertPaperUploadPage.tsx:202-210`)
- Generic fallback preserved (`ExpertPaperUploadPage.tsx:211-212`)
- All 5 required tests present and matching task names exactly
- Existing tests patched to supply `doi` (necessary for type change; not over-building)

**Patterns found:**
- The catch block uses a type-cast (`err as { status?: number; error?: {...} }`) — task spec did not require a type guard — this is the correct pattern given `expertFetch` throws a plain object, not an `Error` instance.
- `doiError` is NOT cleared when a new submit begins (only `uploadError` is cleared at `setUploadError(null)` on line 165). Task spec does not require clearing `doiError` on submit start — only onChange must clear it. This is a quality gap, not a spec gap.
- `gen-types` fallback: hand-written one-line `doi: string` change in `expert.ts` is explicitly permitted by the task when backend is unreachable.
