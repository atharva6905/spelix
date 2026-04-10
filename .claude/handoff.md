# Phase 1 Handoff — Session 8

## Completed

| Task | Commit | Description |
|------|--------|-------------|
| Batch 1 cleanup | `936703c` | Removed redundant compute_rep_confidence from rep_detection |
| Batch 2A: Keyframe extraction | `97a3ee5` | FR-AICP-01 — RepKeyframes dataclass, extract_keyframes() via cv2 seek, pipeline Step 8b, 5 tests |
| Batch 2C: Schema + prompts | `455f439` | FR-AICP-03,04,05,06 — CoachingOutput extended (Citation, recommended_cues, etc.), priority enforcement, body_stats + keyframe_analysis_text in prompts, 10 new tests |
| Batch 2B: GPT-4o analysis | `c3ac6a2` | FR-AICP-02 — KeyframeAnalysisService with instructor+OpenAI, image cap at 18, openai dep added, 12 tests |
| Batch 2D: SSE + worker wiring | `af0407f` | FR-AICP-07,21 — generate_coaching_streaming() with Anthropic cache-control, SSE endpoint, Redis pub/sub, worker captures pipeline_result, GPT-4o keyframe analysis + body stats wired, 5 SSE tests + 2 worker tests updated |

## Test counts

- **Backend**: ~337 tests (335 passed, 2 skipped, 1 pre-existing failure in test_confidence_tiers)
- **Pre-existing failure**: `test_confidence_tiers.py::TestTier4::test_transition_multiplier` — Tier 4 assertion mismatch (0.6 vs 0.72), was noted in session 7 handoff as needing Docker/numpy
- **New tests added this session**: 5 (keyframes) + 10 (coaching schema/prompts) + 12 (GPT-4o analysis) + 5 (SSE) = 32 new tests

## Remaining

### Batch 3 — Parallel, Independent (NOT STARTED)
| SRS ID | Requirement | Deps |
|--------|-------------|------|
| FR-XPRT-02 (ext) | PDF report Phase 1 extension — dimension pills, Movement Quality warning | Batch 1 scoring (done) |
| FR-XDET-03/04/07 | Exercise auto-detect heuristic + GPT-4o fallback + confidence display | None |
| FR-PROF-06 | Body stats personalization in coaching context | None |

### Batch 4 — Test Coverage (NOT STARTED)
- Fix pre-existing test_confidence_tiers::TestTier4::test_transition_multiplier failure
- Integration tests for SSE endpoint (httpx AsyncClient)
- GPT-4o mock integration tests
- 95%+ coverage gate

## Architecture Notes

### SSE Flow (implemented)
```
Worker → run_cv_pipeline() → PipelineResult (with keyframes)
       → GPT-4o keyframe analysis (best-effort, logged on failure)
       → body stats fetch (best-effort)
       → status: coaching
       → generate_coaching_streaming() → Claude streaming API
           → publishes chunks to Redis "coaching:{analysis_id}"
           → publishes {"type":"done"} sentinel
           → instructor validation call → CoachingOutput
       → writes CoachingResult (stream_complete=True)
       → summary + PDF
       → status: completed

SSE Endpoint (GET /analyses/{id}/coaching/stream):
  → subscribe Redis BEFORE checking stream_complete (race prevention)
  → if stream_complete → send stored output as single event
  → otherwise → forward Redis pub/sub chunks as SSE events
  → done sentinel → fetch final from DB → send complete event
```

### Key design decisions
- Worker uses DEDICATED redis.asyncio client for pub/sub (not ARQ ctx["redis"])
- GPT-4o analysis is best-effort — failure logged, coaching proceeds without
- Body stats are best-effort — failure logged, coaching uses general population standards
- All new CoachingOutput fields are Optional with defaults — Phase 0 backward compat verified
- System prompt uses Anthropic cache-control: {"type": "ephemeral"}
- Streaming validation: two-call approach (stream raw text → instructor validation call)

## Blockers

- `OPENAI_API_KEY` needs to be added to `.env.example`, `docker-compose.dev.yml`, and production env
- Pre-existing test_confidence_tiers failure (Tier 4 transition multiplier)

## Next session start

```bash
# 1. Add OPENAI_API_KEY to env files
# 2. Fix test_confidence_tiers::TestTier4::test_transition_multiplier
# 3. Start Batch 3 (parallel: PDF extension, exercise auto-detect, body stats)
```
