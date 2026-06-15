# spelix-quality-reviewer — memory

(Persisted by the main agent on 2026-06-10 — the reviewer ran read-only and asked for these to be recorded.)

## Reviewed: issue #239 / approval gate (T2 governance docs) (2026-06-10) → FAIL then re-review
- [Harness governance reviews](harness_governance_review.md) — outcome-enum drift is the dominant failure mode in ship-loop SKILL.md procedural diffs

## Reviewed: issue #237 / worktree-safe hooks (T2) (2026-06-10) → FAIL then re-review
- [Hooks worktree review (#237)](hooks_worktree_review.md) — smoke-test conflated cwd with git main checkout; polluted real handoff.md; fixture setup outside try/finally. Production `_lib.js` fix itself sound.

## Reviewed: issue #219 / DOI upload form (2026-06-10) → PASS (1 MEDIUM, fixed pre-merge)

- **expertFetch flattened-error-shape contract** (reusable for every expert-portal form review): backend raises `HTTPException(detail={"error": {"code","message","detail"}})` → FastAPI wraps as `{"detail": {...}}` → `expertFetch` (frontend/src/api/expert.ts ~164) throws `{ status, ...(body.detail ?? body) }`, i.e. components see `{ status, error: { code, message, detail } }`. Correct test mocks reject the api-function with this POST-expertFetch shape, never the raw fetch Response. When reviewing error handling in expert pages, verify the component reads `err.status` + `err.error?.code` — reading `err.detail.error` is a contract bug.
- **Stale field-error-state trap** (recurring React form pattern): a field-scoped error state (`doiError`-style) that is cleared only in that field's onChange goes stale when the user resubmits after editing a DIFFERENT field — the alert survives into the success state. Check every per-field error is also reset at submit start, alongside the page-level error reset. Found as MEDIUM on #219; fix is one line at the top of handleSubmit.
- Upload-phase state machine on ExpertPaperUploadPage: inputs are `disabled={uploadPhase !== "idle"}`, so any error path that should leave the form editable must set phase back to `"idle"` (not `"error"`) and early-return before the generic handler.

## Reviewed: issue #221 / sex-aware coaching contract (T2) (2026-06-10) → PASS (1 LOW)
- **Contract-task review heuristic (worked here)**: for "add field, keep N call-sites valid" tasks, the load-bearing checks are (a) every existing constructor still type-checks via field DEFAULTS, (b) no exact-key-set test breaks on schema growth, (c) `model_dump`-based serializers silently pick up the new field. Do NOT flag "field written but never read" on a contract task — reading/filtering is the next issue's scope.
- **ChunkPayload round-trip map**: ingest writes via `ingestion.py::_build_points` → `payload.model_dump()` into Qdrant (new fields auto-serialize, forward-compatible). Retrieval reads via `retrieval.py::dense_search` constructing field-by-field from `point.payload.get(...)` — new fields fall to defaults until a downstream issue adds the `.get()` lines.
- **CHECK-constraint test convention**: no precedent for DB-integration CHECK-violation tests (all `IntegrityError` usages are UNIQUE or mocked). Conventional bar for a new CHECK column = Pydantic-Literal accept/reject + column-metadata assertion. Residual LOW: nothing asserts the model `__table_args__` CHECK predicate matches the migration's.
- **Profile test factories build REAL ORM objects** (`_make_orm_profile`, `_make_profile`), not MagicMocks — adding a nullable column does NOT trigger the MagicMock+Pydantic-500 trap on the profile path (contrast analysis API/CRUD factories which do). No mock-factory follow-up needed for profile-schema growth.

## Reviewed: issue #223 / sex-applicability expert portal (2026-06-10) → PASS (2 MEDIUM, 1 LOW — non-blocking; MEDIUMs fixed in-loop)
- ADR-TXN-01 commit-before-side-effect pattern (validated good here): expert.py routes that mutate the row then touch an external store (Qdrant/Storage) must (1) check the repo's None-return and raise HTTPException BEFORE db.commit() — get_db rolls back on HTTPException and the repo method early-returns without flushing when the row is missing, so the 404 path leaks no state; (2) await db.commit() AFTER the None-check, BEFORE the external call. _get_rag_repo and the route's db both Depends(get_db) → FastAPI dependency caching gives the SAME session, so the route's explicit db.commit() flushes the repo's change. complete_paper documents this same pattern. Verify this exact ordering on every new expert mutate-then-restamp route.
- Best-effort external restamp = bare `except Exception` + logger.warning is the ACCEPTED pattern (issue #223): Qdrant set_payload failure is swallowed, request still 200s, ingestion re-stamps on next re-embed. Intentional, spec-scoped, test-covered. Do NOT flag broad except here. Route also guards `if qdrant is not None` (get_qdrant_client can return None when Qdrant disabled).
- Function-local `from qdrant_client import models as qdrant_models` is the dominant convention (7 call sites). Lazy import for optional dep. Never flag.
- MEDIUM — inline-select busy-state inconsistency: handleApprovePaper tracks `approving` to disable mid-request; new handleSexApplicabilityChange inline <select> had NO busy state during in-flight PATCH. Mirror the `approving`-style guard on inline mutating controls.
- MEDIUM — duplicated SEX_APPLICABILITY_OPTIONS copy-pasted into ExpertPaperUploadPage.tsx AND ExpertPortalPage.tsx. Existing QUALITY_TIER/STUDY_DESIGN options are page-local (no shared module), so page-local is the convention — but first option set shared across two pages → dedup to a shared module.
- LOW — Qdrant orchestration inline in the route; acceptable (sibling complete_paper does the same; single call site).
- Test quality strong: response is plain dict[str,Any] (no Pydantic model_validate over MagicMock → no vacuous pass), tests use real RagDocument via _make_doc, failure paths (404/422/403/qdrant-down) covered, frontend error test uses correct post-expertFetch reject shape (honors #219 contract).
- [Optional UserProfile field](review_profile_optional_field.md) — upsert overwrite-all both paths + MagicMock/Pydantic factory trap + type-guard hydration (#224 PASS)

## Reviewed: issue #225 / sex-aware retrieval (2026-06-10) → PASS (1 non-blocking MEDIUM)
See [coaching-sex-aware-retrieval](coaching_sex_aware_retrieval.md) — Qdrant filter-merge (dense+sparse), cache boundary, normalization defense-in-depth, worker-singleton orchestrator test harness.

## Reviewed: issue #234 / DOI optional by document type (FR-EXPV-02, T2) (2026-06-11) → PASS (0 findings)
- **Cross-field Pydantic invariant → `model_validator(mode="after")` is the correct idiom** (not `field_validator`, which can't see sibling fields). On RagDocumentUploadRequest: DOI `str|None` + `@model_validator` raising ValueError iff `document_type=="research_paper" and doi is None`. The validator handles ONLY the null case; empty-string/length is still caught by the field's `min_length=1`. Schemas package convention: beta_request/candidate_review use field_validator (single-field), this is the first model_validator — both are valid, pick by scope.
- **Optional-business-key endpoint pattern (reusable)**: when a previously-required unique key becomes conditional, the route guards the entire normalize→dedup block behind `if body.doi is not None:` and inits `normalized_doi: str|None = None` before it. Null DOI skips BOTH normalize_doi AND get_live_by_doi — correct because the partial unique index is scoped `WHERE doi IS NOT NULL`. Verify the dedup pre-check is asserted NOT-awaited (`get_live_by_doi.assert_not_awaited()`) on the null path, and STILL awaited+normalized on the optional-DOI-provided path.
- **Frontend payload-omission idiom**: `...(form.doi.trim() ? { doi: form.doi.trim() } : {})` spread-omit is the right way to send `undefined`/absent for an optional field — test it with `expect("doi" in payload).toBe(false)`, NOT `payload.doi === undefined` (key-presence is the real contract). Whitespace-only DOI → trim()→"" → omitted, so no separate whitespace test needed client-side.
- **request-schema TS literals are hand-maintained in expert.ts** (PaperUploadMetadata.doi made optional `doi?`, document_type inline cast union of all 5 DocumentTypeLiteral values). Mirrors existing study_design/quality_tier hand-unions — NOT a Supabase-types-regen violation (request schemas aren't generated). Confirmed DocumentTypeLiteral (backend) === DOCUMENT_TYPE_OPTIONS (frontend) === inline cast, same 5 values same order — no drift. The `research_paper` literal triplication (backend Literal + frontend options + cast) is accepted convention, not a maintainability finding.
- **DOI-required early-return does NOT set uploadPhase("error")** (unlike title/year guards) — intentional: leaves phase "idle" so disabled inputs stay editable for the fix. doiError reset both in the select onChange AND at submit-start → honors the #219 stale-field-error trap. No regression.
- Test depth excellent both sides: backend (textbook-no-doi 201+skip-dedup, textbook-with-doi normalized+deduped, malformed-doi-textbook 422, null-doi-research 422; create mock uses real side_effect returning the doc, asserts doc_arg.doi/.document_type — no MagicMock/Pydantic vacuous pass); frontend (select options+order, marker toggle, submit enable/disable, payload omission via `in`, optional-DOI-sent, switch-back-to-research re-disables, in-handler guard via direct form submit).

## Reviewed: issue #263 / Docling OCR writable artifacts_path (2026-06-11) → PASS (1 LOW non-blocking)
- [Docling OCR artifacts review](review_docling_ocr_artifacts.md) — read-only-venv lazy-download crash class; pre-bake + env-pointer fix; worker shares image ENV; model bake = disk not RAM; to_thread offload preserved

## Reviewed: issue #231 / upload ownership guard (FR-EXPV-02, T2) (2026-06-11) → PASS (1 MEDIUM non-blocking)
- [Upload ownership guard review](review_upload_ownership_guard.md) — inline-guard is the expert.py per-resource authz convention; guard ordering before destructive ops honored; predicate now triplicated (extract helper for future cancel/delete) = MEDIUM; sentinel-default factory refactor is non-weakening

## Reviewed: issue #260 / DUPLICATE_DOI 409 surfacing in ExpertPortalPage (T1->T2) (2026-06-12) -> PASS (1 MEDIUM, deferred to #235)
- [expertFetch error shape](expert_fetch_error_shape.md) - how expert.ts rejections unpack; what an apiErr cast can safely read
- [Expert API error handling pattern](expert_api_error_pattern.md) - canonical 409/422 surfacing pattern; cast vs typed-error tradeoff (issue #235)

## Reviewed: issue #236 / expert upload hygiene (FieldError, clearErrors, 409 hint, T2) (2026-06-13) -> PASS-WITH-NITS (all fixed in-loop)
- [Upload hygiene review (#236)](review_upload_hygiene_236.md) - async-closure phase tracking via local `let`; vacuous-reset-test trap (Upload-Another only renders on success screen → error-clearing is non-observable defense-in-depth, assert the observable form reset instead; uncontrolled file-input caveat); shared FieldError is now canonical

## Reviewed: issue #235 / typed ExpertApiError + recoverable upload error phase (T2) (2026-06-13) → PASS (3 non-blocking)
- [Expert API error patterns](frontend-expert-api-error.md) - expert.ts ExpertApiError/guard/unwrap-ladder design notes + test-coverage traps (issue #235)
- [Frontend gotcha checklist](frontend-gotcha-checklist.md) - fast pass/fail list for frontend diffs (imports, use-client, fetch, SaMD copy, supabase mock)
- **Blast-radius miss caught downstream:** quality-review (like spec) cleared only the changed files and MISSED that `expertFetch`'s new top-level-`code` throw shape regressed `ExpertPortalPage.handleApprovePaper` (DUPLICATE_DOI, FR-EXPV-06/#260) — it still read `apiErr.error?.code`. `/code-review`'s cross-file tracer caught it; fixed in d1b7c93 + regression test. LESSON: for a diff that changes a SHARED error/throw/return shape, audit ALL consumers of that function (grep the symbol), not just the diff's files — the "two untested branches" finding is minor next to an unmigrated sibling consumer.

## Reviewed: issue #258 / restamp retry task (T2) (2026-06-13) -> PASS (2 non-blocking MEDIUM observations)
- [Restamp retry review (#258)](review_restamp_retry_258.md) - streaq thin-wrapper pattern; session-closed-before-Qdrant ordering is correct+superior; paper_points_filter de-dups only 2 of 3 claimed sites (backfill script left behind); retry-task set_payload-raises path untested (inline path covered)

## Reviewed: issue #283 / shared ApiError + buildApiError across all api modules (T2) (2026-06-13) → PASS (1 LOW)
- [Shared ApiError #283](shared-apierror-283.md) - three @/api error idioms census; expert.ts re-export shim is load-bearing (expert-upload.test.ts); legacy-dual-path collapse = correct; test-realism pattern (real buildApiError fixtures + don't re-declare guard in vi.mock — resolves the #235 trap); #282 consumer-census clean

## Reviewed: issue #269 / Docling weight sha256 manifest (T2 deploy-infra) (2026-06-13) → PASS (1 MEDIUM + 1 LOW, BOTH fixed in-loop pre-merge, PR #290)
- [Docling checksum review](review_docling_checksum_269.md) — COPY/WORKDIR/cd path-resolution verified; static-guard test is right tool but a `\n`-split + `.+$` regex MISSES a trailing `\r` that still breaks the Linux `sha256sum -c` (the MEDIUM); fix = `.gitattributes eol=lf` pin + byte-level `test_manifest_has_no_carriage_returns`; sha256sum -c extra-file gap = LOW (documented in ADR); mirrors BlazePose Dockerfile line 74
- [ApiError unify #294](apierror-unify-294.md) — #283 LOW executed; fallbackMessage 3rd-arg; #235/#282 branch gaps now closed; listAnalyses sole straggler

## Reviewed: issue #275 / deploy SSH command_timeout 30m (T2 CI deploy) (2026-06-14) → PASS (1 non-blocking observation)
- [Deploy SSH timeout review (#275)](review_deploy_ssh_timeout_275.md) — 30m is sane (3x headroom, under 6h runner default, no job-level timeout-minutes); shared-budget rollback gap = follow-up, not this PR; provenance via commit msg sufficient

## Reviewed: issue #300 / pin appleboy/ssh-action to SHA (T2 CI) (2026-06-14) → PASS (0 blocking, follow-up observation)
- [SSH action pin review (#300)](review_ssh_action_pin_300.md) — @<sha> # vX.Y.Z mirrors trufflehog convention; tag==SHA so zero behavior change; partial-pin scope boundary is sound (pin secret-bearing action, defer first-party/setup-uv); command_timeout 30m untouched

## Reviewed: issue #299 / bound deploy build so rollback retains budget (T2 CI) (2026-06-14) → PASS (0 blocking, 2 pre-existing observations)
- [Deploy rollback budget #299](review_deploy_rollback_budget_299.md) — **appleboy/ssh-action runs WITHOUT set -e** (load-bearing for all deploy-script reviews); the `if timeout 1320` wrapper CAPTURES build status (doesn't suppress errexit); converts the old command_timeout session-kill into an in-script rollback w/ ~8m budget; OBS-1 (alembic-fail-doesn't-rollback, pre-existing) filed as #303 — **#303 attempt #305 REVERTED #306, OBS-1 still OPEN (needs-design)**

## Reviewed: issue #303 / roll back deploy on alembic migration failure (T2 CI) (2026-06-15) → PASS-on-inspection but **REVERTED — broke prod**
- [Deploy migrate rollback #303](review_deploy_migrate_rollback_303.md) — ⚠️ **#305 false-rolled-back on the happy path (migrate gate runs before backend ready, post-`up -d` readiness race) → REVERTED #306**. BIG LESSON: a NEW gate on a readiness-dependent command (migrate/exec/DB-connect) right after `up -d` false-fails; needs readiness-retry + real-deploy validation, not just inspection. errexit-OFF nest-a-gate heuristic still valid; OBS-1 still open

## Reviewed: issue #303 REDESIGN (Option 1, migrate retry loop) (2026-06-15) → PASS (0 findings, real-deploy validation still required)
- [Deploy migrate rollback #303](review_deploy_migrate_rollback_303.md) (see "REDESIGN" section) — 5×retry migrate loop w/ 10s sleeps + `MIGRATED` flag gating health loop FIXES the #305 readiness race (heuristic (d) now satisfied); 3 if/3 fi balanced; quoting clean; ~26m worst case < 30m. MUST validate on real deploy per ADR-DEPLOY-01 — inspection can't exercise post-`up -d` timing.
