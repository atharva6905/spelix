# spelix-quality-reviewer — memory

(Persisted by the main agent on 2026-06-10 — the reviewer ran read-only and asked for these to be recorded.)

## Reviewed: issue #219 / DOI upload form (2026-06-10) → PASS (1 MEDIUM, fixed pre-merge)

- **expertFetch flattened-error-shape contract** (reusable for every expert-portal form review): backend raises `HTTPException(detail={"error": {"code","message","detail"}})` → FastAPI wraps as `{"detail": {...}}` → `expertFetch` (frontend/src/api/expert.ts ~164) throws `{ status, ...(body.detail ?? body) }`, i.e. components see `{ status, error: { code, message, detail } }`. Correct test mocks reject the api-function with this POST-expertFetch shape, never the raw fetch Response. When reviewing error handling in expert pages, verify the component reads `err.status` + `err.error?.code` — reading `err.detail.error` is a contract bug.
- **Stale field-error-state trap** (recurring React form pattern): a field-scoped error state (`doiError`-style) that is cleared only in that field's onChange goes stale when the user resubmits after editing a DIFFERENT field — the alert survives into the success state. Check every per-field error is also reset at submit start, alongside the page-level error reset. Found as MEDIUM on #219; fix is one line at the top of handleSubmit.
- Upload-phase state machine on ExpertPaperUploadPage: inputs are `disabled={uploadPhase !== "idle"}`, so any error path that should leave the form editable must set phase back to `"idle"` (not `"error"`) and early-return before the generic handler.
