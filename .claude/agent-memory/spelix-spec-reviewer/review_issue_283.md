---
name: review-issue-283
description: Issue #283 — shared ApiError migration (all 5 api modules, 3 named consumers, legacy dual-path collapse, 2 new helper branches): PASS, 2026-06-13
metadata:
  type: project
---

Issue #283 — promote ExpertApiError to shared ApiError in @/api/errors, migrate all api modules, collapse legacy dual-path in expert pages.

**Verdict: PASS** (2026-06-13, branch refactor+issue-283-shared-apierror, 4 commits, 17 files)

## Checklist verified

1. **Shared ApiError class + isApiError guard + buildApiError helper in @/api/errors**: DONE (frontend/src/api/errors.ts, new file)
2. **beta.ts:44 migrated**: DONE
3. **admin.ts:59 migrated**: DONE
4. **profiles.ts:52 migrated**: DONE
5. **profiles.ts:72 migrated**: DONE
6. **analyses.ts:263 migrated**: DONE
7. **Precedence alignment (analyses.ts body.error divergence)**: DONE — buildApiError branch (5) preserves top-level `{error:{code,message}}` before branch (6) top-level `{code,message}`, which matches pre-#283 `body.error ?? body.detail ?? body` for the case where `body.error` is an object
8. **EmailCaptureForm.tsx consumer migrated**: DONE — reads `isApiError(err) ? err.message : ""` instead of `err.error?.message`; behavior preserved because buildApiError branch (1) maps `{detail:{error:{code,message}}}` → `err.message = errObj.message`
9. **LandingEmailForm.tsx consumer migrated**: DONE — reads `isApiError(err) && err.status === 409`
10. **ExpertPaperUploadPage.tsx legacy dual-path collapsed**: DONE — removed `legacy` cast; now guarded path only
11. **ExpertPortalPage.tsx legacy dual-path collapsed**: DONE — removed `legacy` cast; now guarded path only
12. **DOI tests migrated to real typed error**: DONE in both expert pages (buildApiError via apiErr helper)
13. **New helper test branch (a): `{detail:{code,message}}` no nested error**: DONE (errors.test.ts)
14. **New helper test branch (b): top-level `{code,message}` no detail/error**: DONE (errors.test.ts)
15. **ExpertApiError/isExpertApiError aliases preserved**: DONE in expert.ts (const/type exports re-exporting from @/api/errors)

## Consumer scan (guardrail)
- UploadPage.tsx → reads only `err.message` (Error base property) — safe
- AdminPage.tsx → never reads error fields (console.error + static fallback string) — safe
- ProfilePage.tsx:76 → reads `err?.status` — safe (ApiError has status property)
- No inline mock guard re-declaration left in any page test (replaced by real buildApiError import from @/api/errors, which is NOT vi.mocked)

## Precedence trace for analyses.ts
Pre-#283: `{ status, ...(body.error ?? body.detail ?? body) }` — if `body.error` is an object, spreads it → thrown has `{ status, code, message }`.
Post-#283: buildApiError branch (1) checks `detail` first; if no detail, branch (5) checks `body.error`; if `body.error` is an object, returns `ApiError{status, code: errObj.code, message: errObj.message}`. Behavior preserved — consumer reads `err.message`.

## Over-build check
ExpertApiError/isExpertApiError re-exports added — these preserve the existing import surface so consumers don't need immediate update. Authorized by the guardrail requirement ("migrate ALL consumers"). No other over-build detected.

## pattern-typed-api-error-235.md status
All deferred items from #235 are now DONE. That memory file should be treated as CLOSED.
