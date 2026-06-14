---
name: review_issue_294
description: Spec review of issue #294 — unify @/api/* error throws onto buildApiError (analyses.ts 4 sites, insights.ts 2 sites, consent.ts 3 sites): PASS, 2026-06-13
metadata:
  type: project
---

## Reviewed: issue #294 (ApiError unify, 2026-06-13) → PASS

Commit: d80cf5a. Branch: worktree-feat+issue-294-apierror-unify.

**Requirements vs diff:**

1. analyses.ts — startAnalysis: migrated to buildApiError(..., "Failed to start analysis"). DONE (analyses.ts:288).
2. analyses.ts — getAnalysisStatus: migrated to buildApiError(..., "Failed to fetch status"). DONE (analyses.ts:308).
3. analyses.ts — getAnalysisDetail: migrated to buildApiError(..., "Failed to fetch analysis"). DONE (analyses.ts:329).
4. analyses.ts — getChatHistory: migrated to buildApiError(..., "Failed to fetch chat history"). DONE (analyses.ts:409).
5. insights.ts — getExerciseInsights: migrated from hand-rolled `new Error(...) as Error & {status}` to buildApiError. .status preserved via ApiError.status. DONE.
6. insights.ts — getGlobalInsights: same migration. DONE.
7. consent.ts — getConsents/grantConsent/withdrawConsent: all 3 migrated from bare new Error. DONE.
8. "Not authenticated" precondition throws: ALL remain plain Error in getAuthToken() — analyses.ts:235, insights.ts:37, consent.ts:61. DONE.
9. asString private: not exported (errors.ts:45). DONE.
10. fallbackMessage third arg: JUSTIFIED (required to preserve per-surface user-facing strings; additive + backward-compatible).
11. Full test coverage startAnalysis/getAnalysisStatus: both covered in analyses.test.ts. DONE.

**Over-build:**
- sendChatMessage (analyses.ts) migrated even though NOT in explicit site list. Benign: consumer useChat.ts reads only err.message via instanceof Error pattern; ApiError extends Error; tests cover it. Flagged HIGH (YAGNI) but harmless.
- listAnalyses NOT migrated — still uses old new Error pattern (analyses.ts:370-376). Consistent with not being listed. NOT a finding.

**Behavior preservation:**
- Consumer hooks (useAnalysisDetail, useAnalysisStatus, useConsent, useChat) all read err.message via instanceof Error. ApiError extends Error. PASS.
- HistoryPage.tsx catches insights errors with bare `catch {}` — no .status read from thrown error. PASS.
- insights.ts pre-branch set err.status = resp.status; post-branch ApiError.status is the same value. PASS.

**Stale memory note:** pattern-typed-api-error-235.md claimed "ALL deferred items now complete" after #283 — inaccurate. analyses.ts still had 4 `new Error` sites; insights.ts and consent.ts were entirely unmigrated. #294 is the actual completion of those items.

**Related:** [[pattern-typed-api-error-235]]
