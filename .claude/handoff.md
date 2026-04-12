# Session 16 Handoff → Session 17: Batch 4 complete — four-stage RAG pipeline wired

## Completed

| Task | Commit / PR | Description |
|------|-------------|-------------|
| P2-014 | `6970f53` PR #20 | CoveVerificationService — Haiku for claim extraction/verification, Sonnet for revision, max 2 iterations, never fails pipeline |
| P2-015 | `6970f53` PR #20 | FaithfulnessGateService — LLM-as-judge faithfulness gate (threshold 0.8), ADR-RAG-04 documents HHEM T5 substitution |
| P2-016 | `6970f53` PR #20 | Four-stage worker wiring: retrieval → coaching(contexts) → CoVe → faithfulness gate → enriched CoachingResult. SSE phase events. Analysis ORM columns. |
| ADR-RAG-04 | `6970f53` PR #20 | LLM-as-judge faithfulness instead of HHEM T5 due to 2GB RAM constraint |

## Remaining

### Phase 2 Batch 5 — Citation & Safety (gate: P2-013 ✅)
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| P2-017 | open | ✅ | Citation cross-reference validation |
| P2-018 | open | ✅ | Safety language post-filter |
| P2-019 | open | ✅ | Qdrant unavailable fallback (ungrounded coaching + disclaimer) |
| P2-020 | open | ✅ | Rerank timeout handling (3s cutoff, skip rerank) |

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

- **Backend**: 1198 passed / 19 skipped / 0 failures
- **Frontend**: 178 passed / 0 failures (unchanged — no frontend changes this session)
- **Coverage**: ~91% backend
- **Known failures**: none
- **Alembic head**: `004_phase2_rag_coach_brain` (applied)

## E2E verification

**Skipped** — P2-014/015/016 are backend service additions wired into the analysis worker, but the worker on the droplet does not have `QDRANT_URL` or `COHERE_API_KEY` env vars configured yet. The pipeline gracefully degrades (try/except around all retrieval/CoVe/FG blocks) so existing production behavior is unchanged. E2E verification will be meaningful once Qdrant+Cohere env vars are deployed to the droplet.

## Blockers

- **Qdrant/Cohere env vars not on droplet** — retrieval, CoVe, and faithfulness gate are all no-ops in production until `QDRANT_URL`, `QDRANT_API_KEY`, and `COHERE_API_KEY` are added to the droplet's Docker env. This should happen before Batch 5 merges or alongside it.

## Next session start

```bash
/status
```
Then continue with **Batch 5 (P2-017 through P2-020)** — Citation & Safety. All deps met. Consider deploying Qdrant/Cohere env vars to the droplet first so E2E verification becomes possible.
