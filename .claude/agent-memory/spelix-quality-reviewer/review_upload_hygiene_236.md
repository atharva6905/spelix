---
name: review-upload-hygiene-236
description: Issue #236 expert upload hygiene review — async-closure phase tracking, vacuous-reset-test trap, shared FieldError; PASS-WITH-NITS 2026-06-13
metadata:
  type: project
---

Issue #236 (PR #281) — FieldError extraction + ExpertPaperUploadPage hygiene. Verdict: PASS-WITH-NITS (all nits later fixed). Durable heuristics:

1. **Stale-state-in-async-closure → local `let` reassigned before each phase transition** is the validated idiom for "which phase failed?" in a multi-`await` submit handler. The React state var (`uploadPhase`) is stale inside the catch of an async closure, so a local `let failingPhase` reassigned right before each `setUploadPhase(...)` is correct — do NOT flag it in favor of reading the (stale) state var. It cannot be wrong: e.g. `failingPhase === "completing"` is only reachable after the prior `await` resolved.

2. **Vacuous-reset-test trap:** a test asserting "error X is gone after reset" is VACUOUS if a normal path (e.g. submit-start `setXError(null)` / a shared `clearErrors()`) already nulled X before the reset runs — the assertion then passes whether or not the reset clears X. To prove a reset clears something, X must be present in the state the reset acts on, with no intervening clear. Special case: a "Upload Another" button only renders on the SUCCESS screen, where error state is never set — so its error-clearing is non-observable defense-in-depth and CANNOT be made non-vacuous via the UI. Fix = assert the OBSERVABLE reset instead (form returns to initial: inputs cleared, success screen gone, submit disabled). Note: a `<input type="file">` is uncontrolled — `resetForm` clears the React `selectedFile` state but not the native DOM `.files` list, so assert on the React-observable file-summary-line disappearing, not `fileInput.files.length`.

3. **Shared `FieldError`** (`frontend/src/components/FieldError.tsx`) now exists as the canonical inline field-error component (always `role="alert"`, `text-sm text-red-600`, className merge via `[base, className].filter(Boolean).join(" ")` — the local idiom; there is no `cn`/`clsx` util for this). Future expert/upload forms should use it, not re-introduce inline `<p className="... text-red-600">`. Adjacent to `DoiLink.tsx` (#232).

See [[expert_api_error_pattern]] and [[expert_fetch_error_shape]] for the surfacing/cast tradeoffs.
