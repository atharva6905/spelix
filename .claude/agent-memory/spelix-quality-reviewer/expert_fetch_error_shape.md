---
name: expert-fetch-error-shape
description: The exact shape of errors thrown by expertFetch in frontend/src/api/expert.ts — load-bearing for any apiErr cast in expert pages
metadata:
  type: project
---

`expertFetch<T>` (frontend/src/api/expert.ts) throws on `!resp.ok`:
`const err = { status: resp.status, ...(body.detail ?? body) }`

Implications for handlers casting the caught error:
- `apiErr.status` is always present (the HTTP status number).
- The rest is spread from `body.detail` if present, else the whole body.
- For `apiErr.error?.code` / `apiErr.error?.message` to resolve, the backend
  409/422 body must carry an `error: { code, message }` object (top level, or
  nested under `detail` as `{ error: {...} }`).

**Why:** when reviewing any expert-page handler that does
`(err as { status?; error?: {...} })`, the test mock and runtime check are only
valid if this thrown shape matches. Verified against the live, prod-shipped
ExpertPaperUploadPage handler using identical unpacking — contract is proven.

**How to apply:** don't flag an `as { status?; error? }` cast in an expert page
as risky for "unknown shape" — it is known and stable. Flag only if a handler
reads a field NOT produced by this spread.
Related: [[expert-api-error-pattern]].
