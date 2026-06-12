---
name: expert-api-error-pattern
description: Canonical pattern for surfacing backend 409/422 error messages in expert pages, and the accepted interim cast vs typed-error tradeoff
metadata:
  type: project
---

Canonical error-surfacing pattern in expert pages (ExpertPaperUploadPage,
ExpertPortalPage):

    const apiErr = err as { status?: number; error?: { code?: string; message?: string } };
    if (apiErr.status === 409 && apiErr.error?.code === "DUPLICATE_DOI") {
      setError(apiErr.error?.message ?? "A paper with this DOI already exists.");
    } else {
      setError("Generic fallback. Please try again.");
    }

**Why / accepted tradeoffs:**
- The inline `as { status?; error? }` cast is accepted interim state, not a
  finding. A typed `ExpertApiError` refactor is tracked in issue #235 and is
  queued. Do NOT demand that refactor in unrelated PRs.
- The fallback string ("A paper with this DOI already exists.") is duplicated
  across the two pages. MEDIUM maintainability note at most (a shared constant
  would dedupe) — not a blocker; strings are identical and the backend message
  is the primary display path (the literal is only a `??` fallback).

**How to apply:** pass a new expert-page error handler if it mirrors this
pattern exactly. Reading apiErr.status / apiErr.error?.* is safe per
[[expert-fetch-error-shape]]. T1->T2 escalation for "adds a user-facing fallback
string" is the correct governance call.
