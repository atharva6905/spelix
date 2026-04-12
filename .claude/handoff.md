# Session 15 Handoff → Session 16: Phase 2 Batches 2–4 landed, Batch 4 remainder + Batch 5–7 carry forward

## Completed

| Task | Commit / PR | Description |
|------|-------------|-------------|
| D-001 | `42f54cd` PR #16 | Instructor native streaming via `create_partial` — eliminates 2nd LLM call (ADR-021 resolved) |
| P2-004 | `42f54cd` PR #16 | IngestionService: text → 500-token section-aware chunking → Cohere embed → Qdrant upsert. Idempotent SHA-256 point IDs. |
| P2-005 | `42f54cd` PR #16 | Delivered inside P2-004: recursive 500-token chunking, 50-token overlap, section-aware |
| P2-006 | `42f54cd` PR #16 | Delivered inside P2-004: metadata-as-payload on every Qdrant point |
| P2-023 | `42f54cd` PR #16 | CoachBrainEntry/Create/Update/Payload Pydantic v2 schemas. Aligned with migration 004 (trigger_tags=list[str], entry_type=cue/correction/principle/drill) |
| P2-008 | `720c97d` PR #17 | RetrievalService.dense_search — Cohere search_query embed → Qdrant cosine |
| P2-009 | `720c97d` PR #17 | SparseRetrievalService.sparse_search — client-side mmh3 tokenization, server-side BM25+IDF |
| P2-024 | `720c97d` PR #17 | BrainEmbeddingService — contextual text prefix before embedding, batch upsert to coach_brain |
| P2-010 | `c176951` PR #18 | hybrid_search — concurrent dense+sparse, RRF fusion (k=60), Cohere Rerank 4.0 |
| P2-028 | `c176951` PR #18 | TriggerPrivacyService — categorical bins, MIN_GROUP_SIZE=20, never raw measurements |
| P2-011 | `698714d` PR #19 | exercise_filter param on dense/sparse/hybrid search via Qdrant FieldCondition |
| P2-012 | `698714d` PR #19 | RetrievalGuard.check — min 3 docs threshold, coaching_unavailable sentinel |
| P2-013 | `698714d` PR #19 | Cite-then-generate prompt: numbered [1]..[N] citations, cite-by-number instruction |
| Qdrant | — | Cloud provisioned: papers_rag + coach_brain (1024-dim cosine + BM25 sparse) |
| STRATEGY.md | `37db4dd` | L2 beta launch plan committed |

## Remaining

### Phase 2 Batch 4 — Four-Stage Prompt (gate: P2-013 ✅)
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| P2-014 | open | ✅ | Stage 2 — CoVe verification loop |
| P2-015 | open | ✅ | Stage 3 — hallucination guard (HHEM score threshold) |
| P2-016 | open | ✅ | Stage 4 — four-stage prompt wiring in worker |

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

### Phase 2 Batch 8 — Eval Logging (gate: P2-016)
| ID | Status | Deps met? | Notes |
|----|--------|-----------|-------|
| P2-032 | open | blocked on P2-016 | Per-analysis RAGAS/HHEM eval scores |
| P2-033 | open | blocked on P2-016 | Retrieval metrics logging |
| P2-034 | open | ✅ (no deps) | Langfuse Cloud setup |

### Tech debt (no deps)
| ID | Status | Notes |
|----|--------|-------|
| D-004..D-010 | open | Session 13 cleanup items. D-005 (720p fixture) blocks D-008. |
| P2-007 | open | Corpus curation — seed research papers (data work, not code) |

## Test counts

- **Backend**: 1176 passed / 19 skipped / 0 failures
- **Frontend**: 178 passed / 0 failures (unchanged — no frontend changes this session)
- **Coverage**: ~91% backend (unchanged — new services not yet wired into pipeline)
- **Known failures**: none
- **Alembic head**: `004_phase2_rag_coach_brain` (applied to live Supabase)

## E2E verification

**Skipped** — all 4 PRs are backend service/schema additions not yet wired into the analysis pipeline. No user-facing behavior change on spelix.app. Same rationale as session 14 PR #15.

Full flow walk-through deferred until P2-016 (four-stage prompt wiring) lands and the RAG pipeline is connected to the worker.

## Blockers

1. **Local commits ahead of origin/main**: `37db4dd` (STRATEGY.md) and `04cd9ff` (backlog updates) are committed locally but not pushed — hook blocks direct push to main. Include them in the next PR branch or push via a docs-only PR.

2. **P2-009 sparse retrieval needs ingest-side sparse vectors**: The `SparseRetrievalService` uses mmh3 client-side tokenization for queries, but `IngestionService` (P2-004) currently only stores dense vectors. The ingest pipeline needs to be extended to also compute and store BM25 sparse vectors using the same `_VOCAB_SIZE = 2**17` hash scheme. Without this, sparse retrieval returns empty results against real data. This is a known gap — not a code bug, just incomplete wiring.

3. **Qdrant API key exposed in session output**: The JWT-format API key appeared in provision script output during the env var swap debugging. Rotate the key if the session transcript is shared outside the project.

## Next session start

```bash
# 1. Load environment state
/status

# 2. Push pending local commits (STRATEGY.md, backlog updates)
#    Option A: create a docs-only PR
#    Option B: include in next feature PR

# 3. Update backlog.md — mark P2-008..P2-013, P2-028 as done with PR SHAs

# 4. Dispatch Phase 2 Batch 4 remainder (all gates met):
#    P2-014 (CoVe verification loop)
#    P2-015 (hallucination guard)
#    P2-016 (four-stage prompt wiring in worker)
#    These three can run in parallel — no shared files.

# 5. In parallel with Batch 4, dispatch:
#    P2-025 (seed corpus ingestion — ≥20 entries)
#    P2-026 (Coach Brain hybrid retrieval + routing)
#    P2-019 (Qdrant unavailable fallback)

# 6. Fix P2-009 ingest-side sparse vector gap before testing retrieval E2E
```
