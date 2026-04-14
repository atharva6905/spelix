# Session 27 Handoff → Session 28: Phase 2 gate passed, D-022 fixed, PDF+Qdrant+Realtime fixes deployed

## Completed

### Phase 2 Transition Gate — PASSED
- 33/33 Must requirements verified against SRS
- 1,443 backend tests / 225 frontend tests / 0 failures
- Migration 006 applied, migration 007 added (Realtime enablement)
- Full E2E smoke test passed on production

### Phase 3 Backlog Seeded
- 7 tasks (P3-001 through P3-007) covering 8 Must requirements
- **Deferred to post-Saturniq (mid-August 2026)** per STRATEGY.md

### Production Bug Fixes (4 PRs merged)

| PR | Commit | Description |
|----|--------|-------------|
| #37 | `b86d07e` | D-022 part 1: bind mount `./reports/templates:/app/reports/templates:ro` |
| #38 | `2fbec9f` | D-022 part 2: CWD-based fallback path in `pdf.py` (for Docker) |
| #39 | `6fde5e1+b7b6b1f` | Qdrant idempotent indexes + migration 007 (Realtime enablement) |

### Production Config Changes Captured in Code

**Migration 007** — captures the one-off SQL applied manually during debugging:
- `ALTER PUBLICATION supabase_realtime ADD TABLE public.analyses`
- `ALTER TABLE public.analyses REPLICA IDENTITY FULL`

**Qdrant** — both `exercise` and `status` keyword payload indexes now cover all 24 coach_brain seed points (applied via inline Python; code change makes future deploys self-healing).

### E2E Verification — PARTIAL

Full upload → results flow verified on spelix.app with `smoketest@spelix.app`:
- Upload + processing + scoring + coaching + annotated video + PDF download ✅ (analysis `5f04cca1`)
- **PDF Report download link CONFIRMED** (D-022 fix working)
- Realtime subscription connected (no "Connection lost" banner on fresh page load after publication fix)
- Full live status transitions via Realtime **NOT verified** due to droplet OOM during late-session test (see Known Issues)

## Known Issues

| ID | Status | Notes |
|----|--------|-------|
| **Droplet OOM** | new | 2GB droplet was unresponsive to SSH during late session 27 test (analysis `f3c1f2d5` stuck in `quality_gate_pending` for 11+ minutes). D-014 (2GB swap) already deployed in session 24 — may need larger droplet or worker memory profiling. |
| D-017 | pending | Replace AI-synthesized paper text with real PDFs via Docling |
| D-004..D-010 | open | Session 13 tech debt items |

## Test Counts
- **Backend**: 1,443 passed / 0 failures
- **Frontend**: 225 passed / 0 failures
- **CI**: All checks green on PRs #37, #38, #39

## Next Session Start

```bash
/status
# Priority: L2 beta polish before May 9 freeze
# 1. Verify Realtime E2E — upload a video, watch status transitions live (requires droplet to not be OOM)
# 2. Apply migration 007 to Supabase (alembic upgrade head) — currently ONLY the one-off SQL is in prod, migration file not yet executed
# 3. Investigate droplet memory pressure — consider 4GB upgrade or worker optimization
# 4. D-017 (real paper PDFs) if time permits
```

## Blockers

- **Migration 007 not yet applied** — must run `uv run alembic upgrade head` against Supabase. The one-off SQL already achieved the same state, so this is just to keep the alembic chain aligned.
- **Droplet memory** — blocks reliable Realtime E2E verification.
