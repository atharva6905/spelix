# Session 14 Handoff → Session 15: Phase 2 Batch 2 + Coach Brain + D-001

## Completed

| Task | Commits | PR | Description |
|------|---------|-----|-------------|
| D-002 | `9d8137f` (guard test, TDD red) + `404b982` (deletion, TDD green) | #15 | Dead `compute_rep_confidence` deleted from `cv/confidence.py`. Guard test `TestComputeRepConfidenceIsRemoved` prevents reintroduction. |
| D-003 | — | — | Closed — already covered by ADR-021. No new ADR needed. |
| P2-001 | `608e007` (migration + integration tests) + `d2eb0a0` (trigger fix + RLS helper fix) | #15 | Migration 004: `rag_documents`, `expert_annotations`, `coach_brain_entries`, `consent_records` + `retrieval_context` / `eval_scores` JSONB on `analyses` + RLS `user_own_data` on `consent_records`. Applied to live Supabase. |
| P2-002 | `d54f543` | #15 | `QdrantClientWrapper` (dual-collection 1024-dim cosine + BM25 sparse), shared RAG Pydantic types (`ChunkPayload`, `RetrievedContext`, `RetrievalResult`, `CitationBlock`), nightly `ping_qdrant_health` cron at 02:00 UTC. `scripts/provision_qdrant.py` one-shot. |
| P2-003 | `12b1e46` (test) + `eeec555` (impl) + `67c7df6` (config) | #15 | `CohereEmbedClient` — `embed-v4.0` + `rerank-v4.0-pro`, 96-batch chunking, `output_dimension=1024` mandatory + regression-test-asserted, `cohere.AsyncClientV2` v6.1.0 async-native. |
| Docs | `fc4c885` (backlog + 11 ADRs) + `7b4872a` (mark tasks done) | #15 | `backlog.md` Phase 2 section rewritten from kickoff brief. `decisions.md` gained ADR-P2-001, ADR-RAG-01..03, ADR-BRAIN-01..07. |
| CI fix | `d61f476` | #15 | `test_migration_004.py` refactored to `TEST_DATABASE_URL` + `@pytest.mark.integration` (self-skips in CI). `provision_qdrant.py` ruff F841 fixed. |

PR #15 squash-merged as `2503e07`. Deploy to Production succeeded. Orphan worktree branches pruned (7 deleted).

## Remaining

### Tech debt (no deps, can interleave)
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| D-001 | **open — dispatch failed** | ✅ | Instructor native streaming refactor. `spelix-coaching-engineer` bailed on FR-ID gate. Re-dispatch with `SRS_IDS: FR-AICP-07` in prompt header (first 5 lines). |
| D-004..D-010 | open | varies | Session 13 cleanup items. D-005 (720p fixture) still blocks D-008 (happy-path E2E). D-007 blocked on D-006. D-010 blocked on D-009. Others independent. |

### Phase 2 Batch 2 — Ingestion Pipeline (gate: P2-002 + P2-003 ✅)
| ID | Status | Deps met? |
|----|--------|-----------|
| P2-004 | open | ✅ — start here |
| P2-005 | open | blocked on P2-004 |
| P2-006 | open | blocked on P2-004 |
| P2-007 | open | blocked on P2-004 |

### Phase 2 Batch 3 — Hybrid Retrieval (gate: P2-004)
P2-008..P2-012 — all open, blocked on P2-004.

### Phase 2 Batch 4 — Four-Stage Prompt (gate: P2-010)
P2-013..P2-016 — all open, blocked on P2-010.

### Phase 2 Batch 5 — Citation & Safety
P2-017..P2-020 — all open, blocked on P2-013 or P2-014.

### Phase 2 Batch 6 — Frontend (gate: P2-013)
P2-021..P2-022 — all open, blocked on P2-013.

### Phase 2 Batch 7 — Coach Brain Foundation (gate: P2-002 ✅)
| ID | Status | Deps met? |
|----|--------|-----------|
| P2-023 | open | ✅ — start here (blocks P2-024..P2-028) |
| P2-024..P2-028 | open | blocked on P2-023 |
| P2-029 | open | P2-001 ✅ |
| P2-030 | open | blocked on P2-029 |
| P2-031 | open | no deps — **hard privacy gate** |

### Phase 2 Batch 8 — Eval Logging (gate: P2-016)
P2-032..P2-034 — all open, blocked on P2-016 (except P2-034 Langfuse Cloud which has no deps).

## Test counts

- **Backend local**: 1012 passed / 8 skipped (with `TEST_DATABASE_URL` set for migration integration tests)
- **Backend CI**: 995 passed / 25 skipped (17 migration integration tests skip since `TEST_DATABASE_URL` unset)
- **Frontend**: 178 passed / 0 failures / tsc clean (unchanged from session 13 — no frontend changes this session)
- **Coverage**: 91% backend (unchanged — migration integration tests don't contribute to coverage)
- **Known failures**: none
- **Alembic head**: `004_phase2_rag_coach_brain` (applied to live Supabase)

## E2E verification

PR #15 was schema-only + infrastructure (new tables, new services not yet wired into pipeline, dep adds). No user-facing behavior change. Playwright MCP smoke check after deploy:

- **Navigate**: `https://spelix.app` → redirected to `/upload`, page rendered with full form (exercise type, variant, video file, upload button).
- **Console errors**: 0
- **Failed network requests (4xx/5xx)**: 0
- **Verdict**: PASS — production unaffected by Phase 2 infrastructure additions.

Full flow walk-through (login → upload → status → results → PDF) deferred — no pipeline or coaching code changed; would exercise the same Phase 1 paths already verified in session 13.

## Blockers

1. **Qdrant Cloud collections not yet provisioned**. `scripts/provision_qdrant.py` exists but hasn't been run against the live cluster. Must run BEFORE any Batch 2 ingestion work (`P2-004`). Requires `QDRANT_URL` + `QDRANT_API_KEY` in `backend/.env` (already confirmed present).

2. **P2-001 column-name drift from kickoff-brief spec**. The migration landed with different names than the spec draft. All downstream code (Batches 2–8) must reference:
   - `analyses.retrieval_context` (not `retrieved_sources_json`)
   - `analyses.eval_scores` (not `eval_scores_json`)
   - `expert_annotations` = chunk-level Qdrant mirror (`document_id`, `chunk_index`, `chunk_text`, `embedding_model`, `qdrant_point_id`, `citation_metadata`) — NOT reviewer/action/notes
   - `coach_brain_entries.content` (not `coaching_action`)
   - `coach_brain_entries.status` CHECK: `seed|active|deprecated` (not `pending|approved|rejected`)
   - `consent_records.consent_type` CHECK: `coach_brain_contribution|health_data_processing|analytics` (not `tier_1_service|tier_2_health_data|tier_3_aggregate`)

   This is documented in `backlog.md` P2-001 done-row and `memory/session_state.md`. Agent dispatch prompts for Batch 2+ MUST include these column names explicitly or agents will write code against the stale spec.

3. **Agent dispatch FR-ID lesson**. `spelix-migration`, `spelix-tdd`, `spelix-coaching-engineer` all refuse unless the dispatch prompt has explicit `SRS_IDS: FR-XXXX-NN` in the first 5 lines. Backlog-row references are NOT sufficient. `spelix-rag-engineer` is inconsistent (accepted P2-003, refused P2-002). Safest template: always frontload `SRS_IDS:` as a prompt header field.

## Next session start

```bash
# 1. Load environment state
/status

# 2. Provision Qdrant Cloud (one-shot, first time only)
cd backend && uv run python scripts/provision_qdrant.py

# 3. Re-dispatch D-001 (instructor native streaming refactor)
#    Use spelix-coaching-engineer with SRS_IDS: FR-AICP-07 in prompt header

# 4. Activate Phase 2 Batch 2 + Batch 7 in parallel:
#    /team phase2-rag  — starting at P2-004 (ingestion pipeline)
#    /team phase2-brain — starting at P2-023 (Coach Brain schema-first)
#    Both gates met: P2-002 + P2-003 merged.
```
