---
name: pattern-typed-api-error-235
description: Issue #235 introduced ExpertApiError + guard (expert-only); #283 promoted to shared ApiError in @/api/errors — ALL deferred items now complete
metadata:
  type: project
---

Issue #235 (T1, expert API error surfacing) added `ExpertApiError extends Error`
({status, code?, message, detail?}) thrown by `expertFetch` for all non-ok responses,
plus exported `isExpertApiError` guard. `buildExpertApiError` unwraps FastAPI
`{detail:{error:{code,message}}}`, Pydantic array detail (code undefined, msg synthesized),
string detail, and plain-object fallback.

**Why:** PR #233 finding #1 -- hand-rolled `{status, ...detail}` object-literal throws hid
drift from both tsc and vitest. The fix pins the real thrown shape with a real Error subclass.

**Issue #283 (2026-06-13) completed all deferred items:**
- `ExpertApiError`/`buildExpertApiError` promoted to `ApiError`/`buildApiError`/`isApiError`
  in `frontend/src/api/errors.ts` (shared module)
- All 5 api modules migrated: beta.ts, admin.ts, profiles.ts (2 sites), analyses.ts
- `analyses.ts` spread divergence (`body.error ?? body.detail ?? body`) preserved via
  buildApiError branch (5) — top-level `{error:{code,message}}` maps to `err.message`
- `EmailCaptureForm.tsx`, `LandingEmailForm.tsx` consumer reads updated
- ExpertPaperUploadPage.tsx + ExpertPortalPage.tsx legacy dual-path collapsed
- DOI tests migrated from object literals to real `ApiError` via `buildApiError`
- `ExpertApiError`/`isExpertApiError` re-exported as aliases from `@/api/errors` (backward compat)

**Current state (post-#283):** `@/api/errors` is the authoritative shared module.
ExpertApiError is an alias for ApiError. All api modules use buildApiError.
All named consumer pages are migrated. No legacy dual-paths remain.

**How to apply:** If a future task adds a new api module, it should import `buildApiError`
from `@/api/errors` and throw `buildApiError(resp.status, body)` — not a hand-rolled literal.
If a page catch needs to inspect error fields, it should use `isApiError(err)` from
`@/api/errors`.
