---
name: issue-294-apierror-unify
description: #294 final-gate PASS — analyses/insights/consent api throw sites migrated to buildApiError + additive fallbackMessage 3rd arg; no message widening, SaMD-clean
metadata:
  type: project
---

# Issue #294 (apierror-unify, T2 final security gate, 2026-06-13, commit d80cf5a) → PASS

Pure frontend refactor; closes the #283 follow-up so all `@/api/*` use ONE error idiom. 8 files (4 src + 4 test), +201/−33. No backend/schema/auth-logic/config.

**Why:** finishes migrating the remaining `new Error(message)` throw sites in `analyses.ts`/`insights.ts`/`consent.ts` onto the shared `buildApiError(status, body, fallbackMessage?)` / typed `ApiError` from `errors.ts` (#283 surface).
**How to apply:** this is a verified-safe re-route of curated messages, not new copy. Do NOT re-flag the general-surfacing concern for these three modules — it was checked here.

## What was verified
- **No message widening.** Pre-#294 the migrated sites already derived `.message` from `body.error?.message ?? body.detail` (confirmed by retained tests in `analyses.test.ts`: "Status unavailable", "Chat not found", etc.). `buildApiError`'s extra precedence cases (Pydantic array `msg`, string detail, plain `{code,message}`) read only server-CURATED fields — the #283 curated-message-source invariant ([[shared-apierror-283]]). Grep of `backend/app/api/**/{analyses,insights,consent}*.py` for `str(exc)`/`str(e)`/`message=f`/`detail=f`: ZERO matches → no raw exception / DB / stack / secret reaches `.message`.
- **`fallbackMessage` is additive** (optional 3rd arg, `?? `Request failed (HTTP N)``). Each migrated site passes its exact original fallback string ("Failed to fetch status/analysis/chat history", "Failed to send message", "Failed to start analysis", "Failed to fetch exercise/global insights", "Failed to fetch consent status", "Failed to grant/withdraw consent") → user-facing copy byte-for-byte preserved. A real body message still wins over the fallback (tested errors.test.ts L138-155).
- **Auth preconditions UNCHANGED.** `getAuthToken()` still `throw new Error("Not authenticated")` in all three modules (analyses.ts:235, insights.ts:37, consent.ts:62). `listAnalyses` deliberately KEEPS plain `new Error(message)` (analyses.ts:368-374) — not migrated, unchanged.
- **`.status`/`.detail` not leaked.** All consumers (`useAnalysisDetail`/`useChat`/`useConsent`) read `err instanceof Error ? err.message : ...`. `ApiError extends Error` → `instanceof Error` true, `.message` identical to old path. No consumer renders `.status`/`.detail`. `ApiError.detail` carries full body but stays UNRENDERED (grep-confirmed via #283).
- **SaMD-clean.** No `injury`/`safety score`/`diagnose`/`treat`/`clinical`/`medical` in any new/changed string. Refactor introduces zero new user-facing copy.
- **No injection sink.** Messages render as default-escaped React text children; no `dangerouslySetInnerHTML`, no new interpolation, no secrets.

## Re-flag triggers (inherit #283/#235 invariant)
Re-review if any analyses/insights/consent backend endpoint starts interpolating `str(exc)`/DB text/filesystem paths/secrets into an HTTPException `message`, OR any consumer moves a surfaced `.message` into `dangerouslySetInnerHTML`/href/attribute sink, OR a future `@/api/*` fetch helper wraps a caught exception body into `ApiError.message`.
