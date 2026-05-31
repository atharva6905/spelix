# Coach Brain technical architecture: four decisions that shape the system

**Two separate Qdrant collections, deferred streaq migration, a standalone LangGraph distillation graph, and context-enriched embeddings with reranker-based score normalization** form the recommended architecture for Coach Brain. Each decision prioritizes operational isolation, production stability, and retrieval quality across fundamentally heterogeneous content types. Below is the detailed technical analysis for each area.

---

## 1a. Two Qdrant collections on one cluster beats every alternative

Qdrant's official docs state a clear principle: *"a single collection per embedding model with payload-based partitioning."* But they add an equally important caveat: *"Only create multiple collections when your data is not homogenous."* Papers RAG (long scientific prose, batch-ingested, rarely updated) and Coach Brain (5–20 word cues, structured JSON patterns, continuously updated via distillation) are textbook non-homogeneous data — despite sharing Cohere embed-v4 as the embedding model.

**The recommended pattern is two named collections (`papers_rag` and `coach_brain`) on a single self-hosted Qdrant cluster.** This is not the multi-tenancy anti-pattern Qdrant warns against (hundreds of tiny collections causing resource overhead). Two collections is well within operational norms, and the benefits are decisive:

**Update isolation** is the strongest argument. Coach Brain's continuous distillation pipeline triggers Qdrant's optimizer cycles — the merge optimizer consolidates small appendable segments, the vacuum optimizer cleans up updated records, and the indexing optimizer rebuilds HNSW graphs when segments exceed the threshold. In a shared collection, these optimizer cycles create lock contention that can briefly spike search latency for Papers RAG queries, even though the papers data hasn't changed. Separate collections give each data type its own independent optimizer pipeline with **zero cross-contamination**.

**Independent HNSW tuning** matters more than it appears. Papers RAG benefits from higher `ef_construct` values (e.g., 200) for more accurate search over dense academic text that changes rarely — the index build cost is amortized across long periods. Coach Brain needs lower `ef_construct` (e.g., 100) for faster index rebuilds during continuous updates. In a single collection, you're forced to choose one configuration or use Qdrant's `payload_m` per-partition HNSW, which adds complexity without clear benefit over simply having two collections.

**Operational clarity** rounds out the case. Separate snapshots allow independent backup and rebuild cycles. Collection-level monitoring reveals whether latency issues stem from papers search or Coach Brain search. And if the distillation pipeline introduces corrupted data, you can roll back `coach_brain` without touching `papers_rag`.

The query pattern at inference time requires two parallel API calls merged client-side, since Qdrant has **no cross-collection query API** (a feature request was labeled `wontfix` in GitHub Issue #1322). This is not a penalty — the LangGraph `RetrieveTool` fires both queries concurrently via `asyncio.gather`, and the Cohere reranker normalizes scores across the merged result set:

```python
async def query_both(query_vector: list[float], limit: int = 20):
    papers_task = client.query_points("papers_rag", query=query_vector, limit=limit)
    coach_task = client.query_points("coach_brain", query=query_vector, limit=limit)
    papers, coach = await asyncio.gather(papers_task, coach_task)
    return merge_and_rerank(papers, coach)
```

**Separate Qdrant clusters** are overkill — they add distinct endpoints, monitoring, and backup infrastructure for no meaningful isolation benefit beyond what two collections on one cluster already provide. Reserve that pattern for multi-region deployments or strict compliance boundaries.

---

## 1b. streaq is the right successor, but migration must wait for Phase 3

ARQ is confirmed in maintenance-only mode. The README now carries a banner pointing to Issue #510, and creator Samuel Colvin's ambitious Redis Streams roadmap (Issue #437, March 2024) was never executed. ARQ v0.27.0 (released February 2026) will continue receiving security patches but no new features. It works, but its trajectory is a slow sunset.

**streaq (tastyware/streaq) is the most credible successor** — a ground-up rewrite that implements the exact Redis Streams architecture ARQ envisioned but abandoned. It's classified as "Production/Stable" on PyPI, has 304 commits across 51 releases, and offers a **feature superset** of ARQ: cron jobs (`@worker.cron`), retries with exponential backoff, health checks, job results with TTL, plus new capabilities including task middleware, dependency injection modeled after FastAPI, priority queues, a built-in monitoring web UI, and benchmarked **5× throughput improvement** over ARQ.

However, **three risks make mid-Phase 2 migration inadvisable**:

The API is still settling rapidly. streaq went from v1 to v6 in under a year, with **significant breaking changes at each major version**. The v5→v6 jump restructured the concurrency model, introduced structured dependency injection, split the CLI, and raised the minimum Redis requirement to 7.0 (it uses `FCALL`). Another major version could land before Phase 3, forcing a re-migration.

The **bus factor is critical**. Graeme Holliday is essentially the sole maintainer, with only 3–4 minor contributors. If he steps away — exactly as happened with ARQ — the project stalls. By Q3 2026, more community adoption data will reveal whether this risk is materializing.

The **dependency on coredis** (rather than the standard `redis-py`) adds a layer of coupling. The v6 release was reportedly blocked waiting for anyio support in coredis, meaning streaq's release cadence is partially hostage to another single-maintainer library.

**Concrete migration plan:**

- **Now (Phase 2):** Pin `arq==0.27.0`. It works. Do nothing else in production.
- **Phase 2, low priority:** Create a proof-of-concept branch converting one worker (e.g., the heartbeat job) to streaq. Verify Redis 7.0+ compatibility with your DigitalOcean setup. Identify any blockers.
- **Phase 3 (Q3–Q4 2026):** Execute full migration. Budget one sprint (2 weeks) for the conversion plus integration testing. The actual code changes are moderate — roughly 2–4 days of implementation:
  - Replace `WorkerSettings` class with `Worker()` constructor
  - Convert `functions = [my_task]` to `@worker.task()` decorators
  - Refactor `on_startup`/`on_shutdown` into a `lifespan` async context manager
  - Update all `enqueue_job('task_name', ...)` call sites to `task.enqueue(...)` (type-safe)
  - Swap `Retry` → `StreaqRetry`, update cron syntax from `cron(fn, hour=9)` to `@worker.cron("0 9 * * *")`
- **Fallback:** If streaq shows signs of abandonment by Q3 2026, evaluate **Taskiq** or **SAQ** as alternatives.

The migration is not urgent. ARQ's maintenance mode means it will keep working with Python 3.12 and current Redis versions. The risk of *not* migrating is low in the 6-month timeframe; the risk of migrating prematurely into an unstable API is higher.

---

## 1c. A standalone distillation graph, not a subgraph, is the right LangGraph pattern

The distillation pipeline and the real-time coaching graph have **completely different lifecycles**: the coaching graph runs synchronously during a user session, while distillation runs asynchronously in a background ARQ worker after the session completes. There is no parent graph context at execution time, making the subgraph pattern architecturally inappropriate. LangGraph's own documentation recommends subgraphs for *"multi-agent systems"* and *"reusing node sets"* within a shared execution — neither applies here.

**The distillation pipeline should be an independently compiled `StateGraph`** invoked via `await distillation_graph.ainvoke(input_state)` inside the background worker. This gives independent testing, deployment, and state management with zero coupling to the coaching graph.

### State design uses three TypedDicts with Pydantic at boundaries

```python
class DistillationInput(TypedDict):
    session_id: str
    exercise_type: str
    completed_analysis: dict      # Full analysis payload
    eval_scores: dict             # deepeval/Langfuse scores

class DistillationOutput(TypedDict):
    coach_brain_entry: CoachBrainEntry | None
    status: Literal["stored", "rejected", "needs_review", "error"]
    rejection_reason: str | None

class DistillationState(TypedDict):
    # Input fields (set once)
    session_id: str
    exercise_type: str
    completed_analysis: dict
    eval_scores: dict
    # Extraction results
    effective_cues: list[EffectiveCue]
    compensation_patterns: list[CompensationPattern]
    movement_insights: list[str]
    # Quality gate results
    quality_passed: bool | None
    quality_details: dict
    needs_expert_review: bool
    rejection_reason: str | None
    # Final output
    coach_brain_entry: CoachBrainEntry | None
    status: Literal["stored", "rejected", "needs_review", "error"]
```

No `Annotated` reducers are needed — each field is written exactly once by a specific node, so default overwrite semantics are correct. `EffectiveCue`, `CompensationPattern`, and `CoachBrainEntry` are Pydantic models used for structured validation at graph boundaries, not as state schemas themselves.

### Five nodes with two conditional edges form the minimal viable graph

The graph topology is linear with two branch points:

```
START → extract_insights → validate_quality → [quality gate] → format_entry → store_entry → END
                                                    ↓ fail
                                                   END (rejected)
                                                    ↓ uncertain
                                               expert_review → [review gate] → format_entry / END
```

**`extract_insights`** calls Claude Sonnet with the completed analysis and eval scores, extracting effective cues, compensation patterns, and movement insights into structured Pydantic models. **`validate_quality`** runs four deterministic gates: minimum eval score threshold (≥0.6), content existence (at least one cue or pattern), cue consistency (all effectiveness scores ≥0.3), and sufficient data (≥3 reps). **`expert_review`** uses an LLM-based auto-reviewer for v1 (upgradable to LangGraph's `interrupt()` for human-in-the-loop when a checkpointer is added). **`format_entry`** builds the `CoachBrainEntry` including the enriched `embedding_text`. **`store_entry`** generates the Cohere embed-v4 embedding and upserts into Qdrant.

Quality gates live as **conditional edges** using `add_conditional_edges`, not inside nodes — this keeps routing logic pure and testable:

```python
def route_after_quality(state: DistillationState) -> Literal["format_entry", "expert_review", "__end__"]:
    if not state["quality_passed"]:
        return "expert_review" if state["needs_expert_review"] else "__end__"
    return "format_entry"
```

Clean early exit works by routing to `END` — the `status` and `rejection_reason` fields in state carry the exit metadata. The graph compiles with `StateGraph(DistillationState, input=DistillationInput, output=DistillationOutput)` to constrain the API surface.

### Worker integration is straightforward

LangGraph natively supports async nodes (`async def`), and `ainvoke()` runs the complete graph within the existing ARQ/streaq event loop. The coaching graph's final node simply enqueues a job with the analysis payload — the distillation graph is compiled once at module level and invoked independently per job.

---

## 1d. Context enrichment and reranking solve the heterogeneous embedding problem

Embedding 5-word coaching cues and 300-word scientific chunks with the same model creates an inherent asymmetry: longer documents produce richer embeddings with more semantic signal, making them disproportionately likely to appear in top-k results regardless of actual relevance. **The solution is a two-part strategy: enrich Coach Brain entries before embedding, then use Cohere's reranker to normalize relevance scores across both collections.**

### Cohere embed-v4 handles short text better than older models, but not well enough alone

Embed-v4 is trained to capture both **content quality and topic similarity** — not just keyword overlap. This quality-awareness partially helps short coaching cues, which pack high information density per token. The model also supports the `input_type` parameter (prepending special tokens to differentiate document vs. query roles), and both collections should use `input_type="search_document"` uniformly for indexing, with `input_type="search_query"` at query time.

However, a raw 3-word cue like "drive knees out" simply lacks the contextual tokens needed for precise vector space positioning. The model cannot infer that this cue addresses knee valgus during squat ascent, activates hip abductors, and is relevant to ACL load management — all context that a matching scientific paper chunk would contain.

### Context enrichment is the highest-impact intervention

**Wrap every Coach Brain entry with structured context before embedding.** Research on metadata-enriched embeddings (including "Utilizing Metadata for Better Retrieval-Augmented Generation," 2025) confirms that prefixing metadata significantly improves retrieval accuracy by increasing intra-document cohesion.

```python
def enrich_coaching_cue(cue: str, exercise: str, context: str, category: str) -> str:
    return (
        f"[Coaching cue | Exercise: {exercise} | Category: {category}]\n"
        f'Cue: "{cue}"\n'
        f"Context: {context}"
    )

# "drive knees out" becomes:
# [Coaching cue | Exercise: barbell back squat | Category: knee tracking]
# Cue: "drive knees out"
# Context: Addresses knee valgus during ascent. Activates hip abductors and external rotators.
```

This transforms a 3-word input into a ~30-word semantically rich document that embeds into the correct region of vector space. **Store both the raw text (for display) and the enriched text (what was actually embedded) in the Qdrant payload.** The enrichment function lives in the `format_entry` node of the distillation graph, which constructs the `embedding_text` field of `CoachBrainEntry`.

For structured compensation patterns and CV pipeline data, convert to descriptive text or YAML before embedding — Cohere's reranker natively handles semi-structured YAML and JSON formats.

### The reranker normalizes cross-collection scores

Even with enrichment, cosine similarity scores from two separate Qdrant collections are not directly comparable. The Cohere reranker (`rerank-v4.0-pro`) is a **cross-encoder** that processes each query-document pair through joint attention, producing calibrated relevance scores independent of document length or embedding density. This is the architectural solution to fair cross-collection ranking.

The inference pipeline should **over-retrieve then rerank**: pull top-20 from each collection via parallel Qdrant queries, merge the 40 candidates, pass all to the reranker with a `top_n=10` cutoff. The reranker's 32k-token context window easily handles both long paper chunks and enriched coaching cues in a single batch. Use the enriched text (not raw cue text) as the document input to the reranker for Coach Brain entries.

### Use Matryoshka embeddings at 1024 dimensions for both collections

Embed-v4 supports Matryoshka dimensionality at `[256, 512, 1024, 1536]`. **1024 dimensions** is the recommended sweet spot — roughly 95% of full-quality retrieval at 67% of the storage cost. Both collections must use identical dimensions to share the same vector space. For a platform at Spelix's scale (likely <100k total vectors across both collections in 2026), the storage savings are modest, but the reduced memory footprint directly improves Qdrant's HNSW search speed on a single DigitalOcean node.

---

## Conclusion

The four architectural decisions interlock cleanly. **Two Qdrant collections** provide the operational isolation that Coach Brain's continuous updates demand without sacrificing query performance — the parallel async query pattern is already required by the LangGraph `RetrieveTool`. **Deferring streaq migration** to Phase 3 avoids compounding infrastructure risk during active feature development while ARQ remains functional. The **standalone distillation graph** maintains a clean separation between real-time coaching and background knowledge extraction, with quality gates implemented as conditional edges for testability. And **context enrichment plus reranking** resolves the fundamental tension between short coaching cues and long scientific prose, making both content types compete fairly for relevance in the merged result set.

One cross-cutting insight emerges: the `format_entry` node in the distillation graph is where embedding quality is won or lost. The enrichment template — which maps raw cues to contextually rich text — directly determines whether Coach Brain entries surface alongside relevant papers at inference time. This node deserves disproportionate attention during implementation and should be validated empirically using deepeval against a curated set of coaching queries before the distillation pipeline goes live.