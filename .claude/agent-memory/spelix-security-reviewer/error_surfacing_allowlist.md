# Error-surfacing allowlist pattern (expert pages) — safe backend-message display

(Persisted by the main agent on 2026-06-12 — the reviewer ran read-only in the PR #278 gate and asked for this to be recorded.)

**Pattern (APPROVED, do not flag):** frontend catch blocks may render a backend-provided `error.message` ONLY behind a doubly-gated allowlist — explicit `status` match AND explicit `error.code` match, with a hardcoded literal fallback via `??` and a static generic message in the else branch. Canonical instances:
- `ExpertPaperUploadPage.tsx` ~232-240: allows 409 DUPLICATE_DOI + 422 INVALID_DOI.
- `ExpertPortalPage.tsx` ~454-459 (PR #278): allows 409 DUPLICATE_DOI only (strictly narrower — review endpoint has no DOI-format validation path).

**Why safe:** no raw stack traces, DB errors, or arbitrary backend strings can reach the UI; every non-allowlisted error degrades to static generic copy. When reviewing future error-handling diffs, the question is "is the rendered message gated by an explicit code allowlist?" — blanket `setError(err.message)` is the info-disclosure failure mode to flag.

**ExpertPortalPage security baseline (as of PR #278):** client-side role gate at ~405-418 (`expert_reviewer`/`admin` via app_metadata/user_metadata) is defense-in-depth only; the authorization boundary is the backend expert API. No secrets, no injection surface (pure client React state). SaMD check: paper-corpus error copy ("A paper with this DOI already exists.") is corpus-management language, not user health copy.

## #236 extension (PR #281, 2026-06-13) — GENERAL surfacing approved as a vetted exception

ExpertPaperUploadPage's submit catch (PR #281) broadened from the strict status+code allowlist to a **general** render: `apiErr.error?.message ?? (err instanceof Error ? err.message : "Upload failed")` — i.e. it surfaces the backend `error.message` for ALL upload errors, not just allowlisted code matches. This is APPROVED (PASS) and must NOT be flagged as the "blanket setError(err.message)" failure mode, because it was verified safe by construction:
- `expertFetch` throws a **plain object** (`{status, ...body.detail}`), NOT an `Error`. So the `err instanceof Error` fallback NEVER fires for HTTP errors — only for hardcoded `throw new Error(...)` literals in `expert.ts` ("Not authenticated", "upload failed: HTTP {status}", "upload failed: network error", "upload aborted"). Zero interpolated exception strings.
- Structured `error.message` comes only from the three expert upload endpoints' hand-written HTTPException envelopes (`backend/app/api/v1/expert.py`): curated literals / validator messages / `review_status` enum interpolation. No `str(exc)`, no DB/constraint text, no stack, no secret, no internal UUID (the #218 paper-id UUID lives only in `detail`, never rendered).

So general surfacing is safe ONLY while BOTH halves hold. **Re-flag trigger for future diffs:** (a) any NEW `expert.ts` throw site that wraps a caught exception or response body in `new Error(...)` (would make `err.message` leak), OR (b) any NEW expert-endpoint HTTPException whose `.message` interpolates `str(exc)`/DB text. Either breaks the guarantee and the general surfacing must be re-narrowed to the status+code allowlist.
