---
name: coach-brain-integration-test
description: #216 integration test for consent-cascade tombstone — ORM identity map + expire_all() pattern, no-rollback harness
metadata:
  type: project
---

FR-BRAIN-16 integration test lives at `backend/tests/integration/test_coach_brain_consent_cascade.py` (commit f88f0c2).

## Key patterns established

**Harness convention — commit INSERTED rows, but NOT the sweep**: the integration harness has no savepoint-rollback fixture, so inserted test rows are committed and cleaned up via `DELETE` in `finally:` (same as `test_beta_request_repository.py`); UUID-prefixed `content` strings prevent collision on repeated runs. BUT the table-wide `soft_delete_empty_unconfirmed()` sweep itself must run **uncommitted and be rolled back** (it has no ID scope and could tombstone real rows) — see [[insight-uncommitted-sweep-integration-test]] for the four-phase boundary recipe (superseded the original "commit the sweep" approach in the `99c8ebe` hardening).

**expire_all() after bulk UPDATE**: `soft_delete_empty_unconfirmed()` and `remove_analysis_ids_for_user()` both issue raw-SQL or ORM-bulk UPDATEs that bypass the SQLAlchemy identity map. After these calls, the in-memory `CoachBrainEntry` objects still hold stale values. Without `session.expire_all()` before a re-SELECT, the query returns the cached object (stale), not the actual DB state.

**Capture PK before expire_all()**: After `session.expire_all()`, accessing any mapped attribute on an expired ORM object (even `entry.id`) triggers a synchronous lazy-load that raises `sqlalchemy.exc.MissingGreenlet` in async sessions. Solution: assign `entry_id = entry.id` into a plain Python variable BEFORE calling `expire_all()`, then use `entry_id` in subsequent WHERE clauses.

**Pyright pre-existing errors**: `sessionmaker(engine, class_=AsyncSession, ...)` produces 4 pyright errors (AsyncEngine/Session type mismatch) — same errors exist in `test_beta_request_repository.py`. This is an accepted pre-existing harness pattern; do NOT add `# type: ignore` to suppress them (sibling tests don't).

## CoachBrainEntry column map

- Python attribute `extra_metadata` → DB column `metadata` (explicit `mapped_column("metadata", ...)`)
- `source_analysis_ids`: `ARRAY(UUID(as_uuid=True))`, server_default=`{}`
- `status` CHECK: `seed | active | deprecated` only (no `rejected` — SRS says `deprecated` + `metadata.rejected_reason`)
- Tombstone reason string: `"source_consent_withdrawn"` (key `rejected_reason` in `extra_metadata` JSONB)
- `soft_delete_empty_unconfirmed()` predicate: `status='active' AND cardinality(source_analysis_ids)=0 AND confirmation_count<3`

**Why:** The original #203 bug was a row-selection bug only observable against real Postgres — the unit test only string-asserted rendered SQL. ADR-BRAIN-12 seed entries (source_analysis_ids=[], confirmation_count=1) must never be tombstoned.
