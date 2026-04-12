# Session 17 Handoff → Session 18: Batch 5 complete — citation validation, safety filter, Qdrant fallback, rerank timeout

## Completed

| Task | Commit / PR | Description |
|------|-------------|-------------|
| P2-017 | `b48c5c1` PR #21 | ValidateOutputTool — regex [N] extraction, cross-ref against CitationBlocks, populate Issue.citation_indices, flag invalid references. Wired before CoVe in worker. |
| P2-018 | `b48c5c1` PR #21 | SafetyFilter — replace prohibited "injury risk"/"injury prevention" phrases, inject medical screening disclaimer. Runs on all coaching outputs. |
| P2-019 | `b48c5c1` PR #21 | Qdrant unavailable fallback — degraded_mode flag on CoachingOutput, SSE "degraded" phase event, pipeline never fails on retrieval failure. |
| P2-020 | `b48c5c1` PR #21 | Rerank timeout — 3s asyncio.wait_for on Cohere rerank, fallback to RRF-fused scores. |
| Schema | `b48c5c1` PR #21 | Issue.citation_indices (list[int]), CoachingOutput.degraded_mode (bool) — backward compatible. |
| Lint fix | `7939a1e` PR #21 | Pre-existing ruff E402 in test_coaching_worker.py — mid-file import moved to top. |

## Remaining

### Phase 2 Batch 6 — Frontend (gate: P2-013 ✅)
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| P2-021 | open | ✅ | Citation rendering in results page |
| P2-022 | open | ✅ | Follow-up chat UI |

### Phase 2 Batch 7 — Coach Brain (partial done)
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| P2-025 | open | ✅ (P2-023 + P2-024 done) | Seed corpus ingestion (≥20 entries) |
| P2-026 | open | ✅ (P2-023 + P2-010 done) | Coach Brain hybrid retrieval + routing logic |
| P2-027 | open | blocked on P2-026 | Cold-start fallback |
| P2-029 | open | ✅ (P2-001 done) | Three-tier consent UI |
| P2-030 | open | blocked on P2-029 | Consent withdrawal cascade |
| P2-031 | open | no deps | DPIA — hard privacy gate |

### Phase 2 Batch 8 — Eval Logging (gate: P2-016 ✅)
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| P2-032 | open | ✅ (P2-016 done) | Per-analysis RAGAS/HHEM eval scores |
| P2-033 | open | ✅ (P2-016 done) | Retrieval metrics logging |
| P2-034 | open | ✅ (no deps) | Langfuse Cloud setup |

### Tech debt (no deps)
| ID | Status | Notes |
|----|--------|-------|
| D-004..D-010 | open | Session 13 cleanup items. D-005 (720p fixture) blocks D-008. |
| P2-007 | open | Corpus curation — seed research papers (data work, not code) |

## Test counts

- **Backend**: 1229 passed / 19 skipped / 0 failures (+31 new from Batch 5)
- **Frontend**: 178 passed / 0 failures (unchanged — no frontend changes this session)
- **Coverage**: ~91% backend
- **Known failures**: none
- **Alembic head**: `004_phase2_rag_coach_brain` (applied, no new migration this batch)

## E2E verification

**Pending** — PR #21 awaiting CI green + merge. After merge, restart droplet containers to pick up QDRANT_URL/QDRANT_API_KEY/COHERE_API_KEY env vars. Then run an analysis via spelix.app and verify:
1. Coaching output has `degraded_mode` field in structured_output_json
2. SSE stream includes `"degraded"` phase event when Qdrant is unreachable
3. No "injury risk" / "injury prevention" in any coaching text

## Blockers

None — Qdrant/Cohere env vars now on droplet. Containers need restart after merge.

## New files this session

- `backend/app/services/validate_output.py` — ValidateOutputTool
- `backend/app/services/safety_filter.py` — SafetyFilter
- `backend/tests/unit/test_validate_output.py` — 13 tests
- `backend/tests/unit/test_safety_filter.py` — 12 tests
- `backend/tests/unit/test_qdrant_fallback.py` — 3 tests

## Pipeline order (after Batch 5)

```
retrieval (with 3s rerank timeout P2-020)
  → coaching generation
  → degraded_mode stamp (P2-019)
  → citation validation (P2-017, before CoVe)
  → CoVe verification
  → safety filter (P2-018, after CoVe)
  → faithfulness gate
  → store
```

## Next session start

```bash
/status
```
Then continue with **Batch 6 (P2-021, P2-022)** — Frontend citation rendering + follow-up chat UI. All deps met.
