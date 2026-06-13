---
name: frontend-expert-api-error
description: Quality notes on frontend/src/api/expert.ts typed-error design (ExpertApiError, isExpertApiError guard, buildExpertApiError unwrap ladder) and its test coverage gaps — issue #235
metadata:
  type: project
---

`frontend/src/api/expert.ts` introduced a typed transport error (issue #235, commit a4fb494).

Design (sound, reviewed PASS):
- `ExpertApiError extends Error` with readonly status/code?/detail?. Real Error subclass so consumers get `instanceof Error`/`err.message`.
- `isExpertApiError` guard: instanceof first, then duck-types `name === "ExpertApiError" && typeof status === "number"` to survive transpile/realm boundaries.
- `buildExpertApiError(status, body)` unwrap ladder, never throws from the error path. Branch order: FastAPI `{detail:{error:{code,message}}}` -> plain detail object `{detail:{code,message}}` -> Pydantic array `detail:[{msg}]` -> string detail -> no-detail top-level `{code,message}` -> bare `Request failed (HTTP n).` fallback.

Why deferred (defensible): the 4th issue-#235 bullet (migrate beta.ts/admin.ts/profiles.ts/analyses.ts off hand-rolled `{status,...detail}` throws) was scoped out to keep blast radius on the expert-upload surface. analyses.ts:263 additionally diverges on spread precedence (`body.error ?? body.detail ?? body`) — touches the core user analysis path. Documented in the ExpertApiError JSDoc.

Test-coverage trap (NON-BLOCKING): unit tests in api/__tests__/expert-upload.test.ts cover FastAPI nested-error, Pydantic array, string detail, and empty/unparseable fallback — but NOT (a) the "plain detail object" branch `{detail:{code,message}}` with no nested `error`, nor (b) the "no-detail top-level `{code,message}`" branch. Both are live branches; a shape change there would pass silently. If this file is touched again, add those two cases.

Page catch dual-path (ExpertPaperUploadPage.tsx): the catch uses `isExpertApiError(err)` but ALSO keeps a `legacy = err as {status,error:{...}}` path. Transitional: page tests still throw bare object literals for DOI cases, so the legacy branch is exercised. Defensible now; once expertFetch is the only throw site and tests migrate to real ExpertApiError throws, delete the legacy branch to remove dual-shape confusion.

vi.mock test trap: page test must re-declare `isExpertApiError` inside the `vi.mock("@/api/expert", ...)` factory because vi.mock replaces the WHOLE module — the real guard is not importable. The mock mirrors the real duck-type. Correct, but means the page test never exercises the real guard's instanceof arm.

Error-phase render is correct (NOT a bug): in `uploadPhase === "error"` the submit button shows "Upload Paper" (no stale phase label) and stays DISABLED (`uploadPhase !== "idle"` is true) — user must click "Try again" -> idle to re-submit. Intentional anti-double-submit design. `retryFromError()` preserves form+file (distinct from `resetForm()` full wipe); `clearErrors()` is the shared single-source error reset.
