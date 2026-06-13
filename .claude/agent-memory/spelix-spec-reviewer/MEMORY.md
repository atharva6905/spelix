# spelix-spec-reviewer --- memory

- [Issue #219 review](review_issue_219.md) --- DOI upload form (FR-EXPV-02/05): PASS, 2026-06-09
- [Issue #237 review](review_issue_237.md) --- worktree-safe hooks (_lib.js, 5 hooks, smoke-test, settings): PASS, 2026-06-10
- [Issue #239 review](review_issue_239.md) --- Approval gate (ship-loop/governance/ADR): PASS after fix iteration 1, 2026-06-10
- [Issue #229 review](review_issue_229.md) --- IntegrityError catch on review_paper (FR-EXPV-03): PASS, 2026-06-10
- [Issue #230 review](review_issue_230.md) --- seed doi column fix (no-FR, seed script): PASS, 2026-06-10
- [Issue #232 review](review_issue_232.md) --- DoiLink extraction (3 sites, testid fallback, children/aria justified): PASS, 2026-06-11
- [Issue #234 review](review_issue_234.md) --- DOI optional for non-research-paper types (FR-EXPV-02, doc-type select): PASS, 2026-06-11
- [Issue #263 review](review_issue_263.md) --- Docling OCR PermissionError fix (bake models + writable artifacts path, no-FR): PASS, 2026-06-11
- [decisions.md cross-link rule](feedback_decisions_crosslink.md) --- superseded ADRs must have a back-reference added (both ways); flag CRITICAL if missing
- [Docling OCR fix pattern](docling_ocr_fix_pattern.md) — issue #263 fix: docling[rapidocr] extra pulls CPU onnxruntime; onnxruntime-gpu is NOT used
- [or-idiom safety for QualityTier](feedback_or_idiom_safety.md) — `x or default` is safe for quality_tier; empty string not a valid DB value (#267)
- [ChunkPayload construction](project_chunkpayload_construction.md) — constructed in exactly one place: ingestion.py _build_payloads (#267)
- [Retrieval read-side fallback](project_retrieval_fallback.md) — retrieval.py:246 defaults to L3_observational; ingestion write-side defaults to L4_guideline (intentional asymmetry) (#267)
- [Issue #260 review](review_issue_260.md) --- DUPLICATE_DOI 409 surfacing in ExpertPortalPage approve handler (FR-EXPV-06): PASS, 2026-06-12
- [Reject handler verification](feedback_reject_handler_verification.md) --- always grep all reviewPaper call sites before accepting implementer's claim that a reject handler doesn't exist
- [Issue #264 review](review_issue_264.md) --- seed review_status column + idempotency re-run (no-FR): PASS-WITH-NITS, 2026-06-12
