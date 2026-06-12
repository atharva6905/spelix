# Error-surfacing allowlist pattern (expert pages) — safe backend-message display

(Persisted by the main agent on 2026-06-12 — the reviewer ran read-only in the PR #278 gate and asked for this to be recorded.)

**Pattern (APPROVED, do not flag):** frontend catch blocks may render a backend-provided `error.message` ONLY behind a doubly-gated allowlist — explicit `status` match AND explicit `error.code` match, with a hardcoded literal fallback via `??` and a static generic message in the else branch. Canonical instances:
- `ExpertPaperUploadPage.tsx` ~232-240: allows 409 DUPLICATE_DOI + 422 INVALID_DOI.
- `ExpertPortalPage.tsx` ~454-459 (PR #278): allows 409 DUPLICATE_DOI only (strictly narrower — review endpoint has no DOI-format validation path).

**Why safe:** no raw stack traces, DB errors, or arbitrary backend strings can reach the UI; every non-allowlisted error degrades to static generic copy. When reviewing future error-handling diffs, the question is "is the rendered message gated by an explicit code allowlist?" — blanket `setError(err.message)` is the info-disclosure failure mode to flag.

**ExpertPortalPage security baseline (as of PR #278):** client-side role gate at ~405-418 (`expert_reviewer`/`admin` via app_metadata/user_metadata) is defense-in-depth only; the authorization boundary is the backend expert API. No secrets, no injection surface (pure client React state). SaMD check: paper-corpus error copy ("A paper with this DOI already exists.") is corpus-management language, not user health copy.
