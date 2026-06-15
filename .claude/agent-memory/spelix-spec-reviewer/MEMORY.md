# spelix-spec-reviewer --- memory

- [Issue #219 review](review_issue_219.md) --- DOI upload form (FR-EXPV-02/05): PASS, 2026-06-09
- [Issue #237 review](review_issue_237.md) --- worktree-safe hooks (_lib.js, 5 hooks, smoke-test, settings): PASS, 2026-06-10
- [Issue #239 review](review_issue_239.md) --- Approval gate (ship-loop/governance/ADR): PASS after fix iteration 1, 2026-06-10
- [Issue #229 review](review_issue_229.md) --- IntegrityError catch on review_paper (FR-EXPV-03): PASS, 2026-06-10
- [Issue #230 review](review_issue_230.md) --- seed doi column fix (no-FR, seed script): PASS, 2026-06-10
- [Issue #232 review](review_issue_232.md) --- DoiLink extraction (3 sites, testid fallback, children/aria justified): PASS, 2026-06-11
- [Issue #234 review](review_issue_234.md) --- DOI optional for non-research-paper types (FR-EXPV-02, doc-type select): PASS, 2026-06-11
- [Issue #263 review](review_issue_263.md) --- Docling OCR PermissionError fix (bake models + writable artifacts path, no-FR): PASS, 2026-06-11
- [Issue #269 review](review_issue_269.md) --- Docling weight checksum manifest (supply-chain integrity, no-FR, T2): PASS, 2026-06-13
- [decisions.md cross-link rule](feedback_decisions_crosslink.md) --- superseded ADRs must have a back-reference added (both ways); flag CRITICAL if missing
- [Docling OCR fix pattern](docling_ocr_fix_pattern.md) — issue #263 fix: docling[rapidocr] extra pulls CPU onnxruntime; onnxruntime-gpu is NOT used
- [or-idiom safety for QualityTier](feedback_or_idiom_safety.md) — `x or default` is safe for quality_tier; empty string not a valid DB value (#267)
- [ChunkPayload construction](project_chunkpayload_construction.md) — constructed in exactly one place: ingestion.py _build_payloads (#267)
- [Retrieval read-side fallback](project_retrieval_fallback.md) — retrieval.py:246 defaults to L3_observational; ingestion write-side defaults to L4_guideline (intentional asymmetry) (#267)
- [Issue #260 review](review_issue_260.md) --- DUPLICATE_DOI 409 surfacing in ExpertPortalPage approve handler (FR-EXPV-06): PASS, 2026-06-12
- [Reject handler verification](feedback_reject_handler_verification.md) --- always grep all reviewPaper call sites before accepting implementer's claim that a reject handler doesn't exist
- [Issue #264 review](review_issue_264.md) --- seed review_status column + idempotency re-run (no-FR): PASS-WITH-NITS, 2026-06-12
- [Issue #236 review](review_issue_236.md) --- expert upload hygiene (FieldError, fillForm hoist, resetForm, 409 hint): PASS-WITH-NITS, 2026-06-12
- [Typed API error pattern (issue #235)](pattern-typed-api-error-235.md) — ExpertApiError class + isExpertApiError guard; expert-only, beta/admin/profiles/analyses deferred w/ doc comment
- [Vi.mock guard re-declaration is acceptable](pattern-vimock-guard-redeclare.md) — page tests may re-declare a mocked guard if it duck-types the real contract; the transport test is the real pin
- **Shared-throw-shape changes regress un-migrated consumers (issue #235, PR #282):** spec-review of the CHANGED files alone PASSED but MISSED a sibling consumer — changing `expertFetch`'s throw to top-level `code`/`message` broke `ExpertPortalPage.handleApprovePaper` (still read `apiErr.error?.code`), regressing DUPLICATE_DOI (FR-EXPV-06, #260). Only `/code-review`'s cross-file tracer caught it (fixed d1b7c93). LESSON: when a diff changes a SHARED transport/throw/return shape, grep + verify EVERY consumer of that function, not just files in the diff — same discipline as [[feedback_reject_handler_verification]].
- [Issue #275 review](review_issue_275.md) --- deploy SSH `command_timeout: 30m` raise (T2 CI deploy step, no-FR; `command_timeout` ≠ connection `timeout`; optional step-split correctly omitted): PASS, 2026-06-14

- [Issue #300 review](review_issue_300.md) --- pin appleboy/ssh-action to SHA 0ff4204d (supply-chain, T2 CI; actions/* follow-up scoping acceptable): PASS, 2026-06-14
- [Issue #299 review](review_issue_299.md) --- bound deploy build with `timeout 1320` so rollback retains budget (T2 CI; all 3 control-flow paths traced; migrate only on build success; diff confined to script body): PASS, 2026-06-14
- [Issue #303 review](review_issue_303.md) --- nest alembic upgrade head in inner if-then (migrate-failure rollback gate, T2 CI; all 4 control-flow paths traced): PASS-on-inspection, 2026-06-15 — ⚠️ but **#305 broke prod (gate false-rolled-back on post-`up -d` backend-readiness race) → REVERTED #306**; #303 reopened needs-design. Spec-review traces control flow correctly but CANNOT catch prod-deploy timing — deploy-script changes need real-deploy validation.
