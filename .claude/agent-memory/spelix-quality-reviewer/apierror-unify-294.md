---
name: apierror-unify-294
description: Quality review of issue #294 — folding remaining new Error() throw sites in analyses/insights/consent onto shared buildApiError, with the additive fallbackMessage 3rd arg. PASS.
metadata:
  type: project
---

# ApiError unification (issue #294, follow-up to #283) — quality review PASS (1 LOW)

#294 executed the exact LOW finding from my #283 review ([[shared-apierror-283]]): folded the bare `new Error(message)` idioms in analyses.ts (startAnalysis, getAnalysisStatus, getAnalysisDetail, getChatHistory, sendChatMessage) + both insights fetchers + all 3 consent fns onto shared `buildApiError`. 88 tests green across the 4 affected files.

## Durable facts

1. **`fallbackMessage` 3rd-arg design is correct and minimal.** `buildApiError(status, body, fallbackMessage?)` — additive, backward-compatible (no-arg callers keep generic `Request failed (HTTP N).`). Fallback consumed only when body yields no usable message; a real body message still wins. Right call vs each caller fabricating a synthetic `{detail:"..."}` body (that would pollute `.detail` + lose real backend detail). `asString` stays private. Precedence unchanged from #283.

2. **#235/#282 branch-coverage gaps now CLOSED in errors.test.ts.** Prior memory ([[frontend-expert-api-error]], [[shared-apierror-283]]) flagged "plain detail object `{detail:{code,message}}` no nested error" + "no-detail top-level `{code,message}`" as untested live branches. #294 adds both explicitly. Do not re-flag.

3. **Cross-consumer audit clean (#282-class check).** Every consumer reads only `.message` via `err instanceof Error ? err.message`: useAnalysisDetail.ts (~39), HistoryPage.tsx (~224 — listAnalyses, NOT migrated but compatible), useAnalysisStatus.ts (both getAnalysisStatus sites just `console.error(err)`). `ApiError extends Error` → instanceof true, message preserved → zero regression. No consumer read `.error.code`/`.detail` off these throws.

4. **`listAnalyses` is the sole remaining `new Error(message)` API throw** (analyses.ts ~368-374), intentionally out of #294 scope. Precedence `body.error?.message ?? body.detail` differs subtly from buildApiError. Only straggler vs "one idiom" goal — documented residual LOW. Trivial future follow-up; not blocking.

5. **Test-depth template (MET):** each migrated site asserts `rejects.toSatisfy((e) => isApiError(e) && e.status === N && e.message === "<exact>")` — typed class + status + exact message, not "something throws". Fallback strings asserted verbatim. Real `isApiError` imported (not vi.mock mirror) → exercises real guard, resolves #235 mock-mirror trap.

6. **ExpertThresholdsPage.test.tsx flake claim verified:** ExpertThresholdsPage.tsx imports only `@/api/expert` (unchanged), ThresholdFlagModal, supabase, react-router — NONE of analyses/insights/consent/errors. Suite-fail-in-full-run / pass-in-isolation is a load-order flake unrelated to this diff.

Files: `frontend/src/api/{errors,analyses,insights,consent}.ts` + their `__tests__/*.test.ts`.
