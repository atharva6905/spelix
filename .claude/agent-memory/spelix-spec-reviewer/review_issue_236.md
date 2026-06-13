---
name: review-issue-236
description: Issue #236 expert upload hygiene (FieldError component, fillForm hoist, resetForm, complete-step 409 hint): PASS-WITH-NITS, 2026-06-12
metadata:
  type: project
---

Issue #236 — 4 hygiene items on ExpertPaperUploadPage + FieldError shared component.

**Verdict: PASS-WITH-NITS**

Key findings:

1. **Item 1 (FieldError, 4 sites)**: Fully implemented. All 4 inline sites replaced. fileError site gains role="alert" (the a11y gap). text-xs → text-sm normalization on UploadPage fileSizeError/durationError is acceptable per "normalize styling" in the task.

2. **Item 2 (fillForm hoist)**: Fully implemented. fillForm parameterized with {title?, doi?, file?} at module scope; resetApiMocks extracted; all 3 beforeEach blocks de-duped.

3. **Item 3 (resetForm)**: PARTIAL — the `resetForm()` function exists and includes `setDoiError(null)`, and is used by "Upload Another". However, `handleSubmit` submit-start does NOT call `resetForm()` — it does its own inline partial clear (lines 199–202). The inline clear DOES include `setDoiError(null)`, so the bug the requirement aimed to fix IS corrected. But the letter says "used by both". The semantics are incompatible (resetForm nulls selectedFile + resets form, which submit-start cannot do). MEDIUM nit, does not block merge.

4. **Item 4 (completing-409 hint)**: Fully correct. `failingPhase` local var correctly tracks phase (React state stale in async closure). Request-phase 409 tested explicitly. Upload-phase 409 not explicitly tested (MEDIUM gap — upload-phase 409 is covered by the same `failingPhase !== "completing"` guard).

5. **Over-build**: `apiErr.error?.message` broadening covers ALL non-DOI-duplicate errors (not just completing-409). No dedicated test for this path with a non-409 API error object. HIGH: untested scope expansion.

**Pattern**: when a requirement says "shared function used by both X and Y", verify call sites — implementer may use inline clears at one site and the shared function at the other (especially if the semantics differ).

**Why:** `resetForm()` semantically cannot be called at submit-start (would null selectedFile mid-submission). The literal requirement overstated what was achievable.

**Update (post-fixup, PR #281 merged `7fafe84`):** findings 3 & 5 were FIXED before merge. Item 3 → a shared `clearErrors()` helper (nulls the 3 error states) is now genuinely called by BOTH submit-start and `resetForm()` (commit `7279e53`). Item 5 over-build → a non-409 structured-error-surfacing test was added (`7279e53`); security review separately verified the broadened surfacing is non-leaking (see security `error_surfacing_allowlist.md` #236 extension). Item 4 upload-phase-409 gap → explicit negative test added (`d1890f7`). Net: shipped PASS, all spec MEDIUMs resolved in-loop.
