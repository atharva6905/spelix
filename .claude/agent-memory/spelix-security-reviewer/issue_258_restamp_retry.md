---
name: issue_258_restamp_retry
description: PATCH metadata restamp-retry task + paper_points_filter helper, corpus-not-tenant RLS, server-derived restamp_failed → T2 PASS
metadata:
  type: project
---

# Issue #258 — restamp retry (T2 security gate → PASS, 2026-06-13)

Spec + quality reviewers already PASSed. Final T2 security gate: **PASS, no findings.**

- **AuthZ UNCHANGED**: PATCH `/papers/{doc_id}/metadata` still gated by `get_expert_reviewer_user` (expert.py:576). `_enqueue_restamp_retry` is internal-only (called inside the gated handler). New `restamp_paper_payload` worker task runs trusted (no user JWT), reads exactly one corpus row by id.
- **RLS**: no migration/RLS file in diff. Retry task uses worker `db_session_maker` (service role) + `RagDocumentRepository.get_by_id` (PK `select...where`, parameterized) of shared CORPUS data — NOT a user-data RLS bypass (corpus-not-tenant, per #221/#223/#225).
- **Injection-safe**: `paper_points_filter(paper_id)` (qdrant.py:58) → `MatchValue(str(paper_id))`, no interpolation; backfill SQL is a static `text(...)` literal, `paper_id=str(row.id)` is a DB-row value not user input; `sys.path` bootstrap = fixed `Path(__file__).parent.parent.parent`, not attacker-controlled.
- **Trust boundary**: `restamp_failed` is server-derived (expert.py:609-633: True on `qdrant is None` or `except Exception`), typed boolean, frontend read-only → client cannot spoof.
- **SaMD CLEAN**: only new user-facing string is "Saved — search index update pending retry" (React-escaped `<p role="status">`, ExpertPortalPage). `clinical_guideline` (expert.ts:98) is a pre-existing corpus-taxonomy enum, outside the diff.
- **Secrets**: none; backfill env-reads DATABASE_URL/QDRANT_URL/QDRANT_API_KEY. No `verify=False`.
- **Fail-safe**: enqueue failures swallowed as warning (mirrors `_maybe_enqueue_distillation`) so a committed-DB PATCH never 500s; worker RAISES on `qdrant is None` so streaq native retry/backoff (`max_tries=4`) fires rather than returning stale-forever.

Unchanged accepted-risk: #218/#223 "expert may edit any paper's metadata, no `uploaded_by` ownership check" class — no new ownership-sensitive path added; OK at single-partner private-beta scale. RE-FLAG only if expert role opens to multiple untrusted partners. See [[harness_governance_t1_t2_approval_gate]].
