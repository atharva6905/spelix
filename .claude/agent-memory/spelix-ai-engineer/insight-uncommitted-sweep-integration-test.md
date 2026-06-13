---
name: insight-uncommitted-sweep-integration-test
description: Integration tests for unscoped table-wide DB mutations must run the mutation uncommitted and rollback, not commit it
metadata:
  type: feedback
---

When an integration test exercises a repo method that performs an UNSCOPED (table-wide,
no ID filter) destructive UPDATE against the shared Supabase DB — e.g.
`CoachBrainRepository.soft_delete_empty_unconfirmed()` (FR-BRAIN-16 consent cascade) —
do NOT commit the mutation. Committing it can persistently tombstone real production
rows that happen to match the predicate (active + empty `source_analysis_ids` +
`confirmation_count<3`), and a finally:-DELETE-by-test-IDs cleanup will NOT restore the
collateral rows.

**Why:** the repo cascade methods (`soft_delete_empty_unconfirmed`,
`remove_analysis_ids_for_user`) do NOT commit internally — the caller commits. So the
sweep only persists because the test commits it.

**How to apply** — the four-phase boundary structure:
1. Insert test rows, `flush()`, capture PKs into plain `uuid.UUID` vars, `commit()`
   (keeps the repo's commit-based harness convention for INSERTED rows; matches
   `test_beta_request_repository.py`).
2. Call the sweep method but do NOT commit — within the same open transaction the
   UPDATE is visible.
3. `db_session.expire_all()` then `select(...)` by captured IDs → verify post-sweep
   state in-session. Bulk UPDATE bypasses the identity map, so expire_all is mandatory.
4. `await db_session.rollback()` to discard the table-wide UPDATE. The committed
   inserts from step 1 survive (prior transaction).
5. finally: DELETE the captured IDs + commit (unchanged).

Gotchas: capture PKs into plain UUID vars BEFORE expire_all (avoid MissingGreenlet on
lazy `.id` load); after rollback use only the captured plain-UUID vars, never expired
ORM objects. Global-rowcount asserts on a shared DB are non-deterministic — use `>= 1`
and rely on per-row assertions for precise correctness; scoped UPDATEs (unique random
UUID filter) keep exact `== 1`. See [[insight-coach-brain-tombstone]].
