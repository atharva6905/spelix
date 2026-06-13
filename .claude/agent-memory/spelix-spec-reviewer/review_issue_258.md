---
name: review_issue_258
description: Spec review of issue #258 — restamp_failed flag + retry task on PATCH /expert/papers/{id}/metadata: PASS, 2026-06-13
metadata:
  type: project
---

## Reviewed: issue #258 (restamp retry + restamp_failed, 2026-06-13) → PASS

Branch: worktree-feat+issue-258-restamp-retry. 3 commits (7b721f7, 1a1e892, 709d39a).

**Requirements verified:**

REQ-1 — restamp_failed field on PATCH response:
- expert.py: `restamp_failed = False` initialized before try/except; set True in BOTH failure branches (qdrant is None @ line ~622; except Exception @ line ~632). Response dict includes `"restamp_failed": restamp_failed`. DONE.
- frontend/src/api/expert.ts: return type extended to `{ id, sex_applicability, restamp_failed: boolean }`. DONE.

REQ-2 — Frontend non-blocking warning, distinct from error banner:
- ExpertPortalPage.tsx: `restampPending: Set<string>` state added. handleSexApplicabilityChange reads `result.restamp_failed` and adds/removes paper id from the set. DB committed → select STILL updates to new value even on restamp failure. DONE.
- PapersTable renders `<p role="status" className="text-amber-600">Saved — search index update pending retry</p>` conditionally on `restampPending.has(paper.id)`. NOT the red error banner. DONE.
- Tests: shows warning when restamp_failed=true + select still updates; no warning when restamp_failed=false; select value assertion both cases. DONE.

REQ-3 — Retry task enqueued on both failure branches:
- expert.py: after try/except block, `if restamp_failed:` → `await _enqueue_restamp_retry(str(doc_id))` inside its own try/except (swallow-as-warning — enqueue failure must never 500 PATCH). DONE.
- streaq_worker.py: `@worker.task(timeout=120, max_tries=4) async def restamp_paper_payload(paper_id: str, ...)`. DONE.

REQ-4 — Retry re-reads DB (convergent, not stale payload):
- restamp_paper.py: reads `doc = await repo.get_by_id(doc_id)` inside async session; stamps `doc.sex_applicability` (current DB value). Never trusts a passed-in payload. DONE.

REQ-5 — Qdrant unavailability in retry task raises (so streaq backoff fires):
- restamp_paper.py: `if qdrant is None: raise RuntimeError(...)`. set_payload exceptions propagate naturally (no wrapper). DONE.
- Tested: test_restamp_raises_when_qdrant_unavailable. DONE.

REQ-6 — 200 always returned on restamp miss:
- PATCH returns 200 even if restamp_failed=True (DB write committed). The only 500 path would be a DB error, which is pre-existing. DONE.

REQ-7 — LOW/optional: paper_id filter extracted to shared helper:
- qdrant.py: `paper_points_filter(paper_id: str) -> Any` added (lines 58–74). Used by expert.py and restamp_paper.py. Backfill script noted in docstring. DONE.

**Key design checks passed:**
- Enqueue failure → swallowed as warning, never 500 PATCH (mirrors _maybe_enqueue_distillation pattern).
- Retry task set_payload exceptions propagate uncaught → streaq retries (correct).
- `not_found` returns cleanly (no raise), correct: paper deleted after enqueue = legitimate no-op.
- No stale payload passed to task; only paper_id passed.

**Minor gap noted (not a blocker):** test_restamp_paper_payload.py does not test the set_payload exception propagation path in the retry task. Behavior is correct by construction (no try/except around the call), but untested.

**Over-build check:** 9 changed files, all within scope: expert.py (PATCH endpoint), qdrant.py (shared helper), restamp_paper.py (new task body), streaq_worker.py (task registration), 4 test files, 2 frontend files. Agent-memory docs commit is expected harness output.
