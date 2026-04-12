# Spelix Phase 2 RAG knowledge layer: technical research brief

**Phase 2 of Spelix's coaching platform is architecturally sound but requires specific calibration decisions across retrieval fusion, verification latency, eval gating, and ingestion reliability.** The six areas investigated below reveal that Qdrant's native BM25 support (server-side since v1.15.2) eliminates application-layer sparse vector management, CoVe verification will add 6–13 seconds of latency per iteration requiring deliberate UX mitigation, and the dual RAGAS + TruLens eval gate is defensible but largely redundant. Evidence is strong for retrieval and eval patterns, moderate for CoVe in domain-specific RAG, and thin for exercise-science-specific benchmarks. Every recommendation below is grounded in documentation, benchmarks, or production case studies — gaps are flagged explicitly.

---

## Area 1: Qdrant hybrid retrieval is now simpler than the SRS assumes

### Sparse vectors are native and server-side

As of Qdrant 1.15.2 (2025), **BM25 conversion happens server-side** — IDF computation runs inside Qdrant when `Modifier.IDF` is set in the collection config. Sparse vectors use an inverted index with dot-product distance, requiring no size or distance metric specification. The supported sparse models include `Qdrant/bm25`, SPLADE (`prithivida/Splade_PP_en_v1`), BM42 (`Qdrant/bm42-all-minilm-l6-v2-attentions`), and miniCOIL (`Qdrant/minicoil-v1`). For a domain with specialized biomechanics terminology, Qdrant recommends **miniCOIL** for keyword retrieval with semantic awareness — it captures precise term overlap better than vanilla BM25.

The correct hybrid query pattern uses Qdrant's Universal Query API with `prefetch` for both dense and sparse retrievers, then fuses results server-side:

```python
results = client.query_points(
    collection_name="exercise_science",
    prefetch=[
        models.Prefetch(query=dense_embedding, using="dense", limit=20),
        models.Prefetch(
            query=models.SparseVector(indices=sparse.indices.tolist(),
                                      values=sparse.values.tolist()),
            using="bm25", limit=20),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=10,
    with_payload=True,
)
```

For self-hosted Qdrant with external Cohere embedding, generate dense vectors via the Cohere API and sparse vectors via FastEmbed locally (`Qdrant/bm25` model), then pass both to `query_points`. No application-layer fusion logic is needed.

### RRF is the correct default; HNSW is unnecessary at this scale

Qdrant natively supports two fusion strategies: **Reciprocal Rank Fusion (RRF)** and Distribution-Based Score Fusion (DBSF). RRF requires zero tuning (k=60 works across datasets), is score-agnostic (rank-based), and performs within 1–2% of a well-tuned weighted sum on BEIR benchmarks. Elastic's experiments confirm RRF's "remarkably stable" performance across models and datasets. For biomedical retrieval specifically, a 2025 clinical RAG evaluation of 250 vignettes found that **hybrid RRF pipelines delivered the highest relevance scores** (P@5 ≥ 0.68, nDCG@10 ≥ 0.67). Self-MedRAG (2025) validated RRF on PubMedQA/MedQA, noting that "fused retrieval using RRF provides broader coverage of clinically relevant evidence." No study has tested RRF specifically on exercise science corpora — biomedical is the closest proxy.

For **500–2,000 vectors at 1024 dimensions**, Qdrant explicitly recommends brute-force search over HNSW. The vector data occupies ~8 MB — well under the default `full_scan_threshold` of 10,000 KB. Exact search at this scale completes in under 5ms. If HNSW is configured for future-proofing, use `m=16, ef_construct=200, hnsw_ef=128`, but no quantization is needed and the parameters are essentially irrelevant at this corpus size.

### 512-token recursive chunking wins the benchmarks

The largest real-document chunking benchmark (FloTorch/Vecta, February 2026, 50 academic papers) found **recursive 512-token splitting achieved 69% accuracy** versus semantic chunking at 54%. Semantic chunking produced fragments averaging only 43 tokens — too small for meaningful retrieval. A separate clinical decision support study found adaptive section-aware chunking reached 87% accuracy on medical content, but this requires reliable section detection. The Vectara NAACL 2025 study (25 configs × 48 models) found chunking configuration had "as much or more influence on retrieval quality as the choice of embedding model."

The SRS specification of **500 tokens / 50-token overlap is well-calibrated**. The recommended enhancement: preprocess papers with section detection (Abstract/Methods/Results/Discussion) before chunking to prevent cross-section bleeding, then apply recursive character splitting within each section.

### Cohere embed-v4 scientific benchmarks have gaps

Embed-v4 scores **67.71 on MTEB retrieval** and supports 128K-token context with Matryoshka dimensionality reduction, but Cohere explicitly states embed-v4 was "NOT optimized for BEIR" since the benchmark is "largely saturated." **No published head-to-head comparison exists between embed-v4 and PubMedBERT/BiomedBERT on scientific retrieval.** The hybrid dense+sparse approach mitigates any domain vocabulary gap: specialized terms like "valgus moment" or "glenohumeral internal rotation" are captured by the BM25 sparse channel even if the dense model's representation is imperfect.

⚠️ **Evidence gap**: No embed-v4 benchmarks on TREC-COVID, NFCorpus, or SciFact specifically. The competitive position against domain-specific models is inferred from general MTEB scores and the hybrid retrieval safety net.

---

## Area 2: CoVe adds 6–13 seconds and needs UX engineering

### Latency is estimated, not measured

**No published production latency benchmarks exist for CoVe.** The original Meta paper (Dhuliawala et al., ACL 2024 Findings) does not report wall-clock time. From architectural analysis: each CoVe iteration requires 3–5 sequential LLM calls (draft → plan verification questions → answer questions → revise). With Claude Sonnet's typical TTFT of 0.5–1.5s and generation at 30–60 tokens/second, one iteration costs approximately **6–13 seconds**. With `max_iterations=2`, worst case is 12–26 seconds before streaming begins. The `max_iterations=2` cap is reasonable — the original paper shows most quality gains come from a single verification pass, with diminishing returns beyond that.

Parallel verification question answering reduces latency from O(n) to O(depth), where n is the number of verification questions. With 3–5 verification questions answered in parallel, the verification step itself takes 1–3 seconds rather than 5–15 seconds sequentially.

### The "verifying" spinner pattern is production-validated

The Perplexity Pro Search case study directly validates the **spinner-then-stream** pattern: "users were more willing to wait for results if the product would display intermediate progress." The recommended SSE event protocol:

```
event: phase → {"step": "retrieving", "detail": "Searching knowledge base..."}
event: phase → {"step": "verifying", "detail": "Cross-checking 3 claims...", "iteration": 1}
event: token → {"content": "Based on "}  ← final verified response streams
event: done  → {"sources": [...], "verification_score": 0.92}
```

Streaming unverified content then replacing it is not recommended — it causes visual jarring and erodes trust. No production system was found using that pattern for verification specifically.

### CoVe effectiveness is strong for factual claims, moderate for domain-specific RAG

The original paper reports **77% reduction in hallucinated entities** on Wikidata and **+28% FACTSCORE improvement** on biography generation. CoV-RAG (He et al., EMNLP 2024 Findings) integrated verification into RAG and achieved **+3.7 points exact-match accuracy** on Vicuna-13b. MedTrust-RAG (2025) applied a similar verify-and-revise loop to biomedical QA and achieved +2.7% accuracy for LLaMA3.1-8B, with hallucination rates for faulty reasoning dropping from 57.9% to 43.0% on MedQA.

**No study applies CoVe specifically to exercise science or sports coaching.** The biomechanical coaching domain — where claims like "use 70–75% 1RM for sets of 8" are factual and verifiable against retrieved context — maps well to CoVe's strengths with atomic factual claims.

### Reranking before CoVe should reduce verification failures, but no empirical evidence exists

No published study tests the rerank → generate → verify pipeline. The reasoning is sound: Cohere Rerank at **0.90 Precision@5** (versus 0.74 without reranking) delivers substantially better source material to the LLM, producing fewer factual errors in the draft, which means fewer verification questions fail. This could effectively reduce most responses from 2 CoVe iterations to 1 — a ~50% latency improvement. The risk is over-filtering: aggressive reranking might remove safety-caveat documents that are less "relevant" but critical for the response. Mitigate with a generous prefetch (retrieve 20–30 → rerank to top 5).

⚠️ **Evidence gap**: The rerank + CoVe interaction is entirely analytical. No empirical data exists for this combination.

---

## Area 3: Inline numbered citations are the industry standard

### Perplexity-style [N] markers with a parallel sources array

Production RAG systems converge on **claim-level inline `[N]` markers** with a structured `sources` array. The LLM generates text like `"Excessive lumbar flexion increases disc herniation risk [1][2]"` and the backend returns a parallel array mapping each number to `{title, authors, year, doi, relevance_score, excerpt}`. This pattern is used by Perplexity, Google AI Mode, LlamaIndex CitationQueryEngine, and Vectara.

Anthropic's native Citations API (GA since January 2025) offers sentence-level attribution with `char_location` references, but **structured outputs cannot currently be combined with Citations** (returns 400 error) — a limitation if using Claude as the generation LLM with constrained JSON output.

For the SUMMARY / STRENGTHS / ISSUES / CORRECTION PLAN report structure, the recommended schema attaches `citation_ids` arrays at each level: per-sentence in SUMMARY, per-claim in STRENGTHS/ISSUES, and per-action in CORRECTION PLAN. Source metadata should include title, authors, year, journal, and DOI. Relevance scores should be used internally for quality gating but hidden from end users.

### Inline citations beat endnotes for trust in health content

Google AI Mode moved to inline citations specifically to improve trust in December 2025. The rationale: "inline citations let you instantly verify whether the answer comes from Mayo Clinic or an unvetted health blog without scrolling through a generic list of references." ShapeofAI pattern analysis recommends placing citations "where people expect them" — inline cues for sentence-level claims, panels/drawers for long-form exploration. Showing `"McGill, 2012"` inline is more trustworthy than just `[1]`.

⚠️ **Evidence gap**: No peer-reviewed UX study specifically compares citation formats in AI-generated fitness/coaching content. Recommendations extrapolate from health/medical AI citation UX research.

### Cohere Rerank 3.5 returns normalized [0, 1] relevance scores

The response object is straightforward: `{"results": [{"index": 3, "relevance_score": 0.999071}, ...]}`, sorted by score descending. Scores are normalized to **[0, 1]** and are query-dependent. Documents exceeding 4,093 tokens are auto-chunked, with the final score being the max across chunks.

Cohere's official threshold calibration method: assemble 30–50 representative queries from your domain, pair each with a borderline-relevant document, run all through rerank, and use the **mean score as your reference threshold**. For exercise science RAG, a starting threshold of **0.15–0.30** is recommended given high lexical overlap in the domain. Scores are not linearly proportional — a 0.91 document is not twice as relevant as a 0.45 document. Reranking adds **100–300ms** per call.

Note: **Cohere Rerank 4.0** was announced in two variants (Fast and Pro), with the Pro model optimized for "complex, reasoning-heavy, domain-specific retrieval" including healthcare. Consider upgrading from 3.5 when available.

---

## Area 4: The dual eval gate is defensible but largely redundant

### RAGAS faithfulness measures context consistency, not factual correctness

RAGAS faithfulness decomposes the generated answer into atomic claims via an LLM, then checks each claim against retrieved context (verdict: 1=supported, 0=not). The score equals `supported_claims / total_claims`. **Critical limitation: a response can score 1.0 but be factually wrong** if the retrieved context itself contains errors. The original RAGAS paper showed 95% agreement with human annotators on WikiEval, but domain-specific agreement rates are likely lower.

Known failure modes for scientific RAG include: subtle distortions passing verification ("approximately 50%" → "exactly 50%"), exclusivity errors (attributing a multi-author finding to one author), score instability from LLM-as-judge non-determinism, and a **14% gap between accuracy and context hit rate** found in the RAG-X 2025 study on medical QA. RAGAS assigns score 0 to "I don't know" responses even when refusing is correct behavior.

### TruLens groundedness differs in granularity, not in what it catches

TruLens groundedness (now maintained by Snowflake after acquiring TruEra in May 2024) uses mandatory chain-of-thought reasoning, **quotes specific passages** from context, and scores each claim on a 0–3 scale rather than binary. It produces better explainability — useful for the expert review queue — but fundamentally measures the same thing as RAGAS faithfulness: whether claims are grounded in retrieved context.

Running both is **defensible as a noise-reduction strategy** (dual-scoring reduces false positives from LLM-judge inconsistency) but not because they catch fundamentally different errors. A more efficient alternative: use RAGAS faithfulness as the primary gate and TruLens groundedness only as a secondary explanation generator for sub-threshold outputs entering the review queue. This halves LLM judge costs for passing responses.

The RAGAS alternative `FaithfulnesswithHHEM` uses Vectara's HHEM-2.1-Open (a T5 classifier) instead of an LLM judge, eliminating non-determinism and API costs for production scoring.

### Langfuse integration is straightforward but manual

Langfuse has a **documented first-party integration with RAGAS** but it is not native — you compute scores externally and push them via `langfuse.create_score()`. The pattern: trace your RAG pipeline normally, compute RAGAS scores on the trace's inputs/outputs, then call `create_score(name="faithfulness", value=score, trace_id=trace_id, data_type="NUMERIC")`. Langfuse supports annotation queues for routing sub-threshold traces to human reviewers, with score configs for standardized schemas.

For the eval gating pattern: compute both scores, check thresholds, tag the trace with `gate_status=PASSED|FAILED`, and enqueue failures. Production teams predominantly use a **flag → human review → graceful degradation** pattern: return a safe fallback response ("Our team is reviewing this analysis") while the expert reviews the flagged trace.

### deepeval vs RAGAS: use RAGAS for Langfuse, deepeval for CI/CD

DeepEval has more GitHub stars (**~12,700** vs ~7,000) and broader scope (agentic, safety, chatbot evaluation), but RAGAS has better Langfuse integration (first-party documented cookbook), stronger research credentials (EACL 2024 paper), and the HHEM option for cost-efficient production scoring. DeepEval's native platform is Confident AI, not Langfuse — integration is manual. DeepEval provides self-explaining scores with `reason` fields and has first-class pytest integration for CI/CD gates.

A practical pattern: **RAGAS for production runtime gating + Langfuse logging, deepeval for CI/CD test suites** with pytest. DeepEval can wrap RAGAS metrics via `RAGASFaithfulnessMetric`, so both ecosystems are interoperable.

---

## Area 5: ARQ idempotency is straightforward; PDF parsing is the hard part

### Deterministic chunk IDs make Qdrant upsert inherently idempotent

ARQ provides **at-least-once delivery** — jobs interrupted by worker shutdown are automatically requeued. The key insight: Qdrant upsert overwrites any point with an existing ID, so **re-running the entire embed+upsert pipeline for a paper is safe** as long as chunk IDs are deterministic. Generate IDs as `sha256(f"{paper_id}:chunk:{chunk_index}")` and upsert with `wait=True` for durability confirmation.

For embedding API rate limits, raise `arq.worker.Retry(defer=timedelta(seconds=2**job_try * 5))` for exponential backoff. For Qdrant unavailability, retry with linear backoff. Keep Qdrant upsert batches ≤100 points — a documented `qdrant-client` bug causes failures with larger parallel batches. After `max_tries` (default 5), write to a dead-letter queue in Redis for manual triage. Set custom `_job_id=f"embed:{paper_id}"` at enqueue time to prevent duplicate jobs for the same paper.

```python
async def idempotent_ingest(ctx, paper_id: str, chunks: list[str]):
    if await ctx['redis'].exists(f"ingestion:complete:{paper_id}"):
        return  # Already processed
    point_ids = [sha256(f"{paper_id}:chunk:{i}") for i in range(len(chunks))]
    embeddings = await embed_with_retry(chunks)  # 96-text batches
    for batch in batched(zip(point_ids, embeddings, chunks), 100):
        await qdrant.upsert(collection_name="papers", wait=True, points=[...])
    await ctx['redis'].set(f"ingestion:complete:{paper_id}", "1", ex=86400)
```

### Cohere embed-v4 caps at 96 texts per call, 2,000 inputs per minute

The maximum batch size is **96 texts** (or images, or mixed) per API call. The rate limit is **2,000 inputs/min** for both trial and production tiers, meaning ~20 API calls/min at full batch size. For 500-token chunks, each batch uses ~48K tokens — well within the 128K per-input limit. Inter-batch delay of ~2.9 seconds maintains rate compliance. For large-scale ingestion (100K+ documents), use the Embed Jobs API which handles batching server-side.

Dimension selection: **1024** provides the best quality/storage balance for this corpus size. At 2,000 chunks × 1024 dimensions × 4 bytes, total vector storage is ~8 MB — negligible.

### Docling is the recommended PDF parser; marker-pdf for equation-critical content

The 2025 PDF parsing landscape has a clear winner for general academic content: **Docling (IBM)** at 37K+ GitHub stars, MIT license, native LangChain/LlamaIndex integration, and the best table extraction (TableFormer AI model). It processes papers in ~28 seconds on M1 without GPU. IBM has used it to process 2.1M PDFs from Common Crawl.

For equation-heavy papers (LaTeX conversion), **marker-pdf** (~19K stars) uses Surya OCR + Texify for equation → LaTeX, but requires GPU (4GB VRAM), is 13× slower (~6 min/paper on M1), and has GPL licensing constraints (free under $2M revenue). As a fast fallback, **pymupdf4llm** (~1.2K stars) produces clean markdown in 0.14 seconds but has no equation support and known multi-column edge cases.

The recommended approach: use Docling as default, with marker-pdf as an optional high-quality path for equation-critical papers. PDFBench found that parser accuracy on academic papers is 40–60% across all tools — **no single parser fully solves scientific PDF extraction**, making manual spot-checking of ingested content important.

⚠️ **Evidence gap**: No head-to-head benchmark exists for equation extraction quality across all five libraries on the same corpus.

---

## Area 6: LangGraph migration should wrap existing nodes, not rewrite them

### The migration pattern is incremental: nodes first, conditional edges second, agency last

LangGraph reached v1.0 GA in late 2025 with 400+ companies in production (Uber, LinkedIn, Klarna, Replit). The validated migration strategy has three phases: first, wrap each existing linear pipeline step (retrieve, verify, compare, generate) as a LangGraph node connected by simple edges — this reproduces the current ARQ behavior exactly. Second, add conditional edges for retry loops (re-retrieve on low relevance, re-verify on claim failures) and streaming. Third, introduce full agentic behavior where the LLM decides tool selection order.

The mental model shift: "In LangChain, you think in sequences. In LangGraph, you think in states and transitions — what state is my agent in, what conditions determine where it goes next, and what happens when something fails?"

### Multi-collection tool design uses separate @tool functions with descriptive docstrings

The official Qdrant + LangGraph tutorial demonstrates the exact pattern needed. Define separate `@tool` functions per collection — `retrieve_papers` for scientific evidence and `retrieve_coach_brain` for coaching methodology. The LLM selects which tool to call based on docstring descriptions, which serve as the routing mechanism. For deterministic flows (Phase 3's initial implementation), use conditional edges rather than tool-calling to enforce the retrieve → verify → compare → generate sequence.

The graph topology for the coaching agent:

- **retrieve_context** → queries both Qdrant collections
- **grade_documents** (conditional edge) → routes to verify_claims or rewrite_query based on relevance grading
- **rewrite_query** → loops back to retrieve_context (max 2 retries via `iteration_count`)
- **verify_claims** → implements CoVe (extract claims, generate verification Qs, verify against context)
- **compare_history** → personalizes against user's past sessions
- **generate_coaching** → streams final response via SSE

### Production guardrails are non-negotiable

The default `recursion_limit=25` throws a hard `GraphRecursionError` that crashes the application — it must be caught or reduced. Known failure modes include infinite loops (LLM calls same tool repeatedly), state bloat (messages accumulate across loop iterations, exceeding context windows), and checkpointer failures (in-memory state lost on restart). Required guardrails:

- **`recursion_limit=15`** in config, with `iteration_count` in state for graceful exit before the hard limit
- **`asyncio.wait_for(graph.ainvoke(...), timeout=60.0)`** as a hard timeout wrapper
- **PostgresSaver** (not InMemorySaver) for production checkpointing with connection pooling
- **State compression**: count tokens before LLM calls, summarize older messages when approaching budget
- **Duplicate tool call detection**: cache recent tool+args combinations, inject override message if repeated

For SSE streaming through FastAPI, combine LangGraph's `stream_mode=["custom", "updates", "messages"]`: `custom` for progress events via `get_stream_writer()`, `updates` for node completion tracking, `messages` for token-level streaming of the final coaching response. The critical nginx header `X-Accel-Buffering: no` must be set to prevent response buffering.

---

## Conclusion

The Spelix Phase 2 architecture is well-designed. Three calibration decisions stand out as highest-impact. First, **switch from application-layer BM25 to Qdrant's native server-side BM25** with RRF fusion — this simplifies the codebase and eliminates a failure surface. Second, **the dual eval gate (RAGAS + TruLens) should be restructured**: use RAGAS faithfulness with HHEM for cost-efficient production gating and reserve TruLens groundedness for generating explanations in the expert review queue only, rather than running both on every request. Third, **CoVe's 6–13 second verification delay is the primary UX risk** — invest in the spinner-then-stream pattern with structured SSE phase events, and track what percentage of responses actually require iteration 2 after reranking. If reranking reduces the iteration-2 rate below 10%, consider making `max_iterations=1` the default with an async background verification pass for quality monitoring.

The weakest evidence areas are embed-v4's performance on scientific subsets (no domain-specific benchmarks published), CoVe's effectiveness specifically for exercise science (extrapolated from medical RAG), and the rerank + CoVe latency interaction (purely analytical). These should be validated with internal A/B testing during Phase 2 rollout rather than treated as established facts.