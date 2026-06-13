# Shared ApiError migration (issue #283, PR #292) — quality review notes

Follow-up to #235/#282. Promoted expert-only `ExpertApiError` → shared `frontend/src/api/errors.ts` (`ApiError` class + `isApiError` guard + `buildApiError(status, body)`). Verdict: **PASS (1 LOW)**.

## Durable facts

1. **Three frontend `@/api/*` error-throw idioms (census, post-#283):**
   - Shared `ApiError` via `buildApiError` — the 5 spread-throw modules (`beta`, `admin`, `profiles`, `analyses.createAnalysis`, `expert`).
   - `new Error(message) + .status` — `insights.ts`.
   - bare `new Error(message)` — `consent.ts`, and `analyses.ts` `startAnalysis`/`getAnalysisStatus`/`getAnalysisDetail`/`getChatHistory`.
   The LOW finding: fold the latter two idioms onto `buildApiError` for one error idiom repo-wide (future follow-up, out of #283 scope — those were never the spread shape and no consumer reads `.error.code` off them).

2. **`expert.ts` re-export shim is LOAD-BEARING, not dead code.** `ExpertApiError = ApiError` and `isExpertApiError = isApiError` aliases are imported by `frontend/src/api/__tests__/expert-upload.test.ts`. `instanceof ExpertApiError` still passes because it IS `ApiError`. Do not flag for removal.

3. **Legacy-dual-path collapse = correct, no coverage lost.** The deleted `ExpertPortalPage`/`ExpertPaperUploadPage` "legacy throw shape" tests asserted a production path that no longer exists (a legacy literal now fails `isApiError` and falls to the generic message). 2-DOI-tests→1 collapse: survivor still asserts the surfaced message AND that the generic fallback is NOT shown.

4. **Test-realism pattern to PREFER (resolves the #235 trap):** build error fixtures with the REAL `buildApiError` (local `apiErr()` helper), and do NOT re-declare the guard inside `vi.mock("@/api/...")`. The page then exercises the real `isApiError` instead of a mock that mirrors the guard and never tests it. The #235 trap was "mock mirrors guard, never tests real guard."

5. **#282-class consumer-census result (the load-bearing lesson):** every consumer of the 5 migrated functions reads only `.status`/`.message` or is a generic catch — NO unmigrated nested `.error.code` reader remained (the #282 regression was exactly an unmigrated `ExpertPortalPage.handleApprovePaper`). For ANY diff changing a shared throw/return shape, grep + audit every consumer, not just the diff's files.

Files: `frontend/src/api/errors.ts`, `expert.ts`, `insights.ts`, `consent.ts`, `analyses.ts`, `frontend/src/api/__tests__/errors.test.ts`.
