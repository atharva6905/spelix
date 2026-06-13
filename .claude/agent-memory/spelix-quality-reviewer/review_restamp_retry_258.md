---
name: review-restamp-retry-258
description: Quality review of issue #258 restamp-retry — streaq task wiring pattern, session-then-Qdrant ordering, helper de-dup drift, swallow-enqueue precedent
metadata:
  type: project
---

# Issue #258 — restamp retry task (T2, PASS, 2 non-blocking observations)

PATCH /expert/papers/{id}/metadata now: surfaces `restamp_failed: bool`, enqueues
`restamp_paper_payload(paper_id)` streaq task on either failure branch (Qdrant None OR
set_payload raised), swallows enqueue failures as warning (mirrors
`_maybe_enqueue_distillation`), extracts `paper_points_filter()` helper into qdrant.py,
adds non-blocking amber frontend warning.

Why review PASSed clean on architecture:
- streaq task is a textbook thin-wrapper: @worker.task(timeout=120, max_tries=4) in
  streaq_worker.py -> lazy-imports body from new restamp_paper.py -> _adapt_ctx(context).
  Matches ingest_paper exactly. WorkerDepends() default param correct.
- Session-then-Qdrant ordering is CORRECT and superior (spec note #2 resolved):
  body opens `async with session_maker() as session`, reads doc.sex_applicability into
  a LOCAL scalar, exits the session block, THEN calls Qdrant. Returns the pooled PgBouncer
  conn before the slow network set_payload. No lazy-load-after-close hazard — scalar attr
  read happens inside the block. Mirrors paper_ingestion.py async with maker().
- Re-read-from-DB (not pass-in payload) = idempotent + convergent under concurrent edits.
  Missing-row -> clean no-op return. Qdrant-None -> RAISE so streaq backoff kicks in.
- set_payload is an async client call (NOT CPU-bound) -> no run_in_executor needed. No
  event-loop block. 4GB budget irrelevant (no frame buffers).
- PATCH response stays dict[str, Any] (no Pydantic model_validate over a MagicMock) ->
  restamp_failed bool assertions are real behavioral checks, not vacuous.

Two non-blocking observations (recorded, not gating):
1. MEDIUM (maintainability) — paper_points_filter docstring claims de-dup of "3+ places
   (... the #222 backfill)" but only 2 sites migrated (expert.py PATCH + restamp task). The
   #222 backfill scripts/oneoff/backfill_papers_payload_sex_exercise.py:94 STILL hand-builds
   the identical Filter and was left behind. Drift risk + inaccurate docstring. One-off
   script so low urgency — fix is either migrate the script or amend the docstring.
2. MEDIUM (test depth) — test_restamp_paper_payload.py covers happy/missing-row/Qdrant-None
   but NOT set_payload raising AFTER Qdrant is reachable (transient error). Correct-by-
   construction (unguarded await propagates -> streaq retries), but worth one
   set_payload=AsyncMock(side_effect=...)+pytest.raises assertion. The EXPERT-API side DOES
   test set_payload-raises (inline path covered) — only the retry-task path lacks it.

Reusable heuristics confirmed:
- swallow-enqueue-as-warning is canonical for "DB committed, side-effect enqueue must not
  500" — _maybe_enqueue_distillation is the cited precedent. Do NOT flag the bare except.
- _enqueue_restamp_retry lazy-imports the task wrapper to break api.v1 -> worker -> api.v1
  cycle. Never flag.
- Frontend: per-paper Set<string> restampPending, amber role="status" text (distinct from
  red error banner). Tests assert select STILL updates + warning shows + red banner absent;
  clean-save asserts no warning. Both transitions covered.

## Re-review of ca185d6 (both MEDIUMs resolved) -> PASS, 0 findings
- Finding #1 RESOLVED via preferred path: backfill script now imports + uses paper_points_filter (genuinely 3 live sites: expert PATCH, restamp task, #222 backfill). Dropped unused FieldCondition/Filter/MatchValue imports. Docstring rewritten to name the 3 real sites - no longer inaccurate.
- Finding #2 RESOLVED: test_restamp_propagates_set_payload_error added - Qdrant reachable, set_payload AsyncMock side_effect=RuntimeError, asserts pytest.raises(match=...) + set_payload.assert_awaited_once(). Locks the streaq-backoff contract on the retry-task path (the inline PATCH path was already covered).
- Latent bug they self-caught + fixed (verified correct): migrating the one-off backfill script to import app.* made it depend on app package, but it had no sys.path bootstrap (previously imported only installed pkgs). Added _BACKEND_DIR = Path(__file__).parent.parent.parent + sys.path.insert + # noqa: E402 on all post-insert imports. VERIFIED: script lives at backend/scripts/oneoff/, so .parent.parent.parent = oneoff->scripts->backend = correct dir where app/ lives. Bootstrap is byte-identical to sibling reembed_coach_brain_seeds.py (same scripts/oneoff/ depth -> same arithmetic). noqa:E402 correctly applied to every import after the sys.path mutation. No new regression.
