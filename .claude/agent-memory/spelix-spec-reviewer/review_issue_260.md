# Issue #260 review — DUPLICATE_DOI 409 surfacing in ExpertPortalPage (FR-EXPV-06)

**Verdict: PASS** (2026-06-12, PR #278, commit ff57b40)

- `handleApprovePaper` catch block now allowlists `status === 409 && error?.code === "DUPLICATE_DOI"` → `setError(error.message ?? fallback)`; else generic copy preserved.
- Issue text mentioned `handleRejectPaper` — verified imprecise: exactly ONE `reviewPaper` call site exists in the page (handleApprovePaper, "Approve & Ingest"). No reject handler. See [feedback_reject_handler_verification.md](feedback_reject_handler_verification.md).
- Test mocks `reviewPaper` rejecting with the post-expertFetch shape `{status, error:{code,message}}` and asserts both the specific message renders AND the generic copy does not — correct contract (matches quality reviewer's expertFetch shape memory).
- Scope minimal: 2 files, no over-build.
