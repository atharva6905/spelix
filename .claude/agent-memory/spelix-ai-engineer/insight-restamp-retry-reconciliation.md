---
name: insight-restamp-retry-reconciliation
description: #258 — restamp retry queue for expert paper-metadata PATCH; re-read-from-DB convergent task, shared paper_points_filter, restamp_failed surfacing
metadata:
  type: project
---

Restamp retry queue (issue #258, FR-RAGK-05 ext., FR-AICP-12 ext.). T2.

**Problem:** PATCH /expert/papers/{id}/metadata commits `rag_documents.sex_applicability`
then best-effort restamps papers_rag Qdrant points via `set_payload`. On Qdrant None or
`set_payload` raising, the route returned 200 with the new value but the Qdrant payload
(the value the retrieval hard filter evaluates) stayed stale forever — a paper retagged
"female" kept being served to male lifters. T3 review-panel HIGH; human decision
2026-06-11 = flag + retry queue (not accept-log-as-signal).

**Design that shipped:**
- Retry task `restamp_paper_payload(ctx, paper_id)` in `app/workers/restamp_paper.py`,
  thin wrapper in `streaq_worker.py` (`@worker.task(timeout=120, max_tries=4)`). streaq's
  native retry/backoff (`max_tries`, default 3) covers the backoff requirement — do NOT
  hand-roll a sleep loop. The body RAISES `RuntimeError` when `get_qdrant_client()` is
  None so streaq retries; a silent return would leave the payload stale.
- **Re-read from DB, never trust a passed-in payload.** The task signature carries only
  `paper_id`; it loads `RagDocumentRepository.get_by_id` for the current value. This makes
  it idempotent AND convergent under concurrent edits (always stamps latest). Missing row
  → no-op clean (`status='not_found'`).
- Route sets `restamp_failed: bool` in the response dict (response is a plain dict, NOT a
  Pydantic model — no schema change). `_enqueue_restamp_retry(paper_id)` is its own
  module-level async fn (so tests patch `app.api.v1.expert._enqueue_restamp_retry`); the
  enqueue is wrapped in try/except so an enqueue miss never 500s the PATCH — mirror
  `_maybe_enqueue_distillation`'s swallow-as-warning.
- **Shared filter helper:** `paper_points_filter(paper_id) -> Filter` now lives in
  `app/services/qdrant.py` (hand-built in route + task + #222 backfill). Lazy-imports
  `qdrant_client.models` inside the fn (ADR-032 source-patch pattern friendly).
- Frontend: `updatePaperMetadata` return type extended with `restamp_failed: boolean`;
  `ExpertPortalPage` tracks a `restampPending: Set<string>` and renders a non-blocking
  amber `role="status"` line "Saved — search index update pending retry" per-paper —
  distinct from the red hard-error banner (which is only for an actual PATCH throw). On
  restamp_failed the select STILL updates (DB committed). String is SaMD-safe.

**TRAP — worktree frontend has NO node_modules.** A fresh /implement worktree ships the
backend `.venv` (uv) but NOT `frontend/node_modules`. `npx vitest`/`tsc` fail with
UNRESOLVED_IMPORT `@vitejs/plugin-react`. Run `npm ci` in `<worktree>/frontend` once
before any frontend gate. `npm ci` did not dirty tracked files (lockfile already in sync).

See [[insight-sex-aware-retrieval]] (the sex_applicability filter this reconciles)
[[insight-hybrid-rag-architecture]].
