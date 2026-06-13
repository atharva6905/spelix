# Shared ApiError migration (issue #283, PR #292) — security review notes

Repo-wide promotion of `ExpertApiError` → shared `ApiError`/`buildApiError` across every `@/api/*` module. Verdict: **PASS** (no CRITICAL/HIGH). Narrows the throw-shape attack surface (one audited unwrapper vs five hand-rolled spreads) without weakening any prior guarantee.

## Updated re-flag trigger (supersedes the expert-only #235 trigger; now covers the whole `@/api` surface)

The **curated-message-source invariant** is what makes general `.message` surfacing safe: `buildApiError` only ever reads a server-curated string into `.message` — never `str(exc)`, DB/constraint text, filesystem paths, or secrets. Re-review if ANY of:
- (a) a backend endpoint reachable from these modules starts interpolating `str(exc)` / DB text / filesystem paths / secrets into an HTTPException `message`;
- (b) a new Pydantic validator echoes raw user input into `msg`;
- (c) any `@/api/*` fetch helper wraps a caught exception body into `ApiError.message`;
- (d) any consumer moves a surfaced message into `dangerouslySetInnerHTML` or an href/attribute sink.

## Durable facts

- **`ApiError.detail` carries the full parsed body but is UNRENDERED** (grep-confirmed: `.detail` appears only in test assertions, never in a page/component). Re-flag if a future consumer renders `err.detail`.
- **`buildApiError` precedence preserves the pre-#283 `.message` value across all 5 migrated modules** (the `analyses.ts` top-level-`error` divergence is tested at `errors.test.ts`). detail-before-error ordering is unobservable in practice — backend envelope is `{error:{code,message,detail}}` (detail nested) or FastAPI `{detail:…}`, never both as top-level siblings.
- **Auth unchanged:** consumers key off numeric `err.status` (preserved verbatim); 401/403 flow through unchanged; no JWT/RLS code in the diff.
- **SaMD clean:** no `injury`/`diagnose`/`treat`/`medical` in any touched user-facing string; only pre-existing RAG taxonomy labels (`clinical_guideline` document-type) which classify the source, not the user. Refactor adds no new copy — only re-routes existing curated messages.
- Surfaced messages render as default-escaped React text children (`{uploadError}`, `{doiError}` via `FieldError`, etc.) — no injection sink.

Files: `frontend/src/api/errors.ts`, `expert.ts`, `analyses.ts`, `beta.ts`, `admin.ts`, `profiles.ts`, landing forms, expert pages.
