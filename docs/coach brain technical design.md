# Coach Brain: technical design specification

**Coach Brain is architecturally viable as a second Qdrant collection with hybrid search, contextual embedding padding, a standalone LangGraph distillation graph, and explicit GDPR Article 9 consent.** The system requires two separate Qdrant collections (not namespacing), should defer ARQ→streaq migration until post-MVP, and must treat all form analysis data as special-category health data under GDPR. This document provides implementation-ready specifications across all areas, with evidence quality flagged throughout.

---

## 1. Technical architecture

### Qdrant: two separate collections, same cluster

Qdrant's own documentation states the rule plainly: **"You should only create multiple collections when your data is not homogenous or if users' vectors are created by different embedding models."** Scientific papers and 5–20-word coaching cues are fundamentally non-homogenous — different schemas, different payload structures, different update cadences, and potentially different HNSW tuning profiles. Two collections on a single cluster is the correct pattern.

The papers collection benefits from aggressive indexing thresholds and standard HNSW parameters (`m=16`, high `ef_construct`) for high-recall semantic search on long documents with infrequent writes. Coach Brain, with frequent writes from the distillation pipeline, benefits from more write-optimized configuration and lower indexing overhead. Qdrant does not support native namespaces (unlike Pinecone); multi-tenancy is implemented exclusively through payload-based partitioning with `is_tenant=true` keyword indexes. Two to three collections is well within safe limits — Qdrant warns against hundreds or thousands of collections, not single digits.

**Payload indexing for Coach Brain collection should include:**

- `entry_type` (keyword) — filter by cue, heuristic, compensation pattern
- `exercise` (keyword) — squat, bench_press, deadlift
- `phase` (keyword) — eccentric, concentric, lockout, setup
- `status` (keyword) — candidate, approved, rejected
- `created_at` (datetime, `is_principal=true`) — recency filtering
- `confirmation_count` (integer) — quality filtering

Create all payload indexes immediately after collection creation. Qdrant's HNSW graphs only benefit from additional filterable edges when generated after payload index creation. Cross-collection queries are not supported in a single Qdrant request (confirmed via GitHub issue #1322, marked `wontfix`); application-layer orchestration is required when the RetrieveTool needs results from both collections.

### ARQ → streaq: defer migration, prototype in branch

ARQ is confirmed maintenance-only. The README contains bold text: "In maintenance only mode," referencing issue #510. The repository at `python-arq/arq` has **85 open issues** accumulating without resolution and no planned v2. However, ARQ is not broken — it continues to work with current Python and Redis versions.

streaq (tastyware/streaq) is at **v6.2.1** with approximately 125 GitHub stars, 4–6 human contributors, and 51 releases. It is technically sophisticated — implementing Redis Streams, full ParamSpec typing, structured concurrency via anyio, and a built-in web UI. The PyPI classifier says "Production/Stable," but **no public evidence of large-scale production deployment exists**. The project has undergone 6 major versions in roughly one year, indicating significant API churn. The v6 release introduced breaking changes to structured concurrency, dependency injection, and CLI commands.

Migration requires rewriting all worker code: `WorkerSettings` class → `Worker()` instance, `functions` list → `@worker.task()` decorators, untyped `ctx: dict` → `WorkerDepends()` injection, `create_pool` + `enqueue_job('name', ...)` → direct `func.enqueue(...).start()`. There is **zero drop-in compatibility**.

**Recommendation:** Prototype migration of one non-critical worker (e.g., RAG document ingestion) in a feature branch. Do not migrate mid-sprint. Plan full migration for a natural break between milestones, ideally after streaq v6.x accumulates 2–3 more patch releases. **taskiq** (~1k stars, multiple brokers, native async, more contributors) is the safer alternative if streaq's single-maintainer risk is unacceptable.

### Distillation pipeline as LangGraph subgraph

The distillation pipeline should use **Pattern B: different state schemas, invoked inside a wrapper node** that transforms `CoachingState ↔ DistillationState`. This provides clean isolation while inheriting the parent graph's checkpointer for durable execution.

**DistillationState TypedDict:**

```python
class DistillationState(TypedDict):
    analysis_result: Dict[str, Any]        # completed form analysis
    eval_scores: EvalScores                # deepeval scores
    exercise_type: str                     # squat | bench_press | deadlift
    quality_gate_passed: bool              # set by quality gate
    distillation_decision: str             # create_entry | skip | refine
    coach_brain_entry: Optional[CoachBrainEntry]
    iterations: Annotated[int, operator.add]
    processing_log: Annotated[List[str], lambda l, r: (l or []) + (r or [])]
```

**Minimal viable nodes:** `ingest_analysis` → `evaluate_quality` → conditional edge → `extract_wisdom` → `create_entry` → END, with a `refine_analysis` loop (max 3 iterations) and `log_and_exit` for failures. The quality gate uses `add_conditional_edges` with a routing function that checks `eval_scores["overall"] >= 0.85 AND eval_scores["correctness"] >= 0.8` for approval, `>= 0.6 AND iterations < 3` for refinement, and exits otherwise.

For production, the distillation should run **asynchronously** — the coaching graph's final node fires it via `asyncio.create_task` (MVP) or an external task queue (production) so it never blocks the user-facing coaching response. The LangGraph `Command` API enables combining state updates with routing in a single node when needed.

### Embedding strategy: Cohere embed-v4 with contextual padding and hybrid search

**Keep Cohere embed-v4** for Coach Brain. Consistency with the papers collection means shared API infrastructure and the same embedding space. The model's `input_type` parameter (`search_document` for indexing, `search_query` for retrieval) adds asymmetric encoding that helps when queries don't exactly match stored cue phrasing. No benchmarks exist specifically comparing embed-v4 on 5–20-word coaching text, but the model's BEIR performance (which uses short queries) and its training on noisy enterprise data suggest adequate handling of short input.

**The single highest-impact improvement is contextual padding at index time.** Instead of embedding the raw cue "drive knees out over toes during ascent," embed:

```
"Barbell back squat coaching cue for the concentric phase: drive knees out over toes during ascent"
```

Anthropic's Contextual Retrieval research demonstrated a **35% reduction** in top-20 retrieval failure rate from contextual prepending alone, and **49% reduction** when combined with BM25. This is a one-time cost at indexing, not at query time.

**Hybrid sparse+dense search is strongly recommended** for domain-specific coaching terminology. Qdrant's own research notes that "sparse vectors shine in domains where many rare keywords or specialized terms are present" — terms like "lockout," "valgus," "tempo," and "supinated grip" need exact keyword matching that BM25 provides alongside dense semantic search. Configure the Coach Brain collection with both dense vectors (Cohere embed-v4, 1536 dimensions) and sparse vectors (BM25 with server-side IDF via Qdrant's FastEmbed). Use **Reciprocal Rank Fusion (RRF)** to merge results. If retrieval quality remains insufficient on evaluation, **Cohere Rerank 4.0** as a post-retrieval step (retrieve top-20, rerank to top-5) provides additional precision.

### Cold-start fallback: graceful degradation with cosine thresholds

When Coach Brain has zero entries or returns no results above threshold, the RetrieveTool must degrade gracefully to papers-only RAG. The exact fallback logic:

```python
COACH_BRAIN_HIGH_CONFIDENCE = 0.82   # strong match, use as primary context
COACH_BRAIN_LOW_CONFIDENCE  = 0.65   # weak match, use as supplementary only
PAPERS_RAG_THRESHOLD        = 0.70   # standard papers collection threshold

async def retrieve_coaching_context(query: str, exercise: str) -> RetrievalResult:
    # Step 1: Query Coach Brain (skip if collection empty)
    brain_results = []
    if await coach_brain_has_entries():
        brain_results = await qdrant.query_points(
            collection_name="coach_brain",
            prefetch=[
                Prefetch(query=sparse_query, using="bm25", limit=20),
                Prefetch(query=dense_query, using="dense", limit=20),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            query_filter=Filter(must=[FieldCondition(key="exercise", match=exercise),
                                      FieldCondition(key="status", match="approved")]),
            limit=5,
            score_threshold=COACH_BRAIN_LOW_CONFIDENCE,
        )

    # Step 2: Always query papers RAG
    papers_results = await qdrant.query_points(
        collection_name="papers_rag", ..., score_threshold=PAPERS_RAG_THRESHOLD
    )

    # Step 3: Merge with priority logic
    if brain_results and brain_results[0].score >= COACH_BRAIN_HIGH_CONFIDENCE:
        return RetrievalResult(
            primary=brain_results[:3],
            supplementary=papers_results[:3],
            source="coach_brain_primary"
        )
    elif brain_results:
        return RetrievalResult(
            primary=papers_results[:3],
            supplementary=brain_results[:2],
            source="hybrid_brain_supplementary"
        )
    else:
        return RetrievalResult(
            primary=papers_results[:5],
            supplementary=[],
            source="papers_only_fallback"
        )
```

The coaching LLM prompt template should include a `{retrieval_source}` variable so the system prompt adjusts its framing — e.g., "Based on established coaching patterns" when Coach Brain is primary vs. "Based on sports science literature" when falling back to papers-only. **The 0.65/0.82 thresholds are starting points requiring calibration against labeled query-cue pairs once the seed corpus exists.** Track retrieval source distribution in production metrics to know when Coach Brain is contributing meaningfully.

### Tier 4 athlete memory: Postgres JSONB primary, Qdrant optional

Per-athlete episodic memory should use **Supabase Postgres JSONB as the primary store**. The dominant query patterns for athlete memory are relational: "show last 10 sessions," "effectiveness trend for cue X," "history by date." Postgres with Row-Level Security (RLS) provides battle-tested per-user data isolation — more mature than Qdrant's payload filtering for privacy-critical per-user data. ACID compliance gives transactional guarantees for writes, and joins with existing athlete profile tables are native.

If semantic search over athlete memories becomes a requirement (e.g., "find past sessions where the athlete struggled with knee cave"), add a third Qdrant collection (`athlete_memory`) with `athlete_id` indexed as `is_tenant=true` and `m=0` / `payload_m=16` to build per-tenant HNSW subgraphs. This is Phase 4 — defer until the need is validated.

**Schema for Postgres JSONB:**

```sql
CREATE TABLE athlete_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id UUID REFERENCES athletes(id),
    session_date TIMESTAMPTZ NOT NULL,
    exercise TEXT NOT NULL,
    cues_delivered JSONB,        -- [{cue_id, text, source}]
    cue_effectiveness JSONB,     -- [{cue_id, pre_score, post_score, delta}]
    form_scores JSONB,           -- {overall, depth, bar_path, ...}
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
-- RLS policy
ALTER TABLE athlete_memory ENABLE ROW LEVEL SECURITY;
CREATE POLICY athlete_own_data ON athlete_memory
    FOR ALL USING (athlete_id = auth.uid());
```

---

## 2. SRS change analysis

### New functional requirements

```
FR-BRAIN-01: Coach Brain collection management
Description: System shall maintain a second Qdrant vector collection ("coach_brain") 
  storing distilled coaching entries with hybrid dense+sparse vectors, separate from 
  the papers_rag collection.
Phase: 2  |  Priority: Must  |  Dependencies: Existing Qdrant infrastructure
---
FR-BRAIN-02: Coaching entry schema and validation
Description: Each Coach Brain entry shall contain: entry_id, entry_type 
  (cue|heuristic|compensation), exercise, phase, trigger_conditions (binned), 
  coaching_action, source_analysis_ids, confidence_score, confirmation_count, 
  status (candidate|approved|rejected), created_at, approved_at, approved_by.
Phase: 2  |  Priority: Must  |  Dependencies: FR-BRAIN-01
---
FR-BRAIN-03: Contextual embedding pipeline
Description: System shall prepend contextual metadata (exercise, phase, entry_type) 
  to raw coaching text before embedding with Cohere embed-v4 
  (input_type="search_document") for Coach Brain entries.
Phase: 2  |  Priority: Must  |  Dependencies: FR-BRAIN-01, existing Cohere integration
---
FR-BRAIN-04: Hybrid retrieval from Coach Brain
Description: RetrieveTool shall query Coach Brain using RRF fusion of dense 
  (Cohere embed-v4) and sparse (BM25) vectors, with payload filtering by exercise 
  and status=approved.
Phase: 2  |  Priority: Must  |  Dependencies: FR-BRAIN-01, FR-BRAIN-03
---
FR-BRAIN-05: Cold-start fallback logic
Description: When Coach Brain returns no results above similarity threshold (0.65), 
  RetrieveTool shall fall back to papers_rag collection results only, with adjusted 
  prompt framing.
Phase: 2  |  Priority: Must  |  Dependencies: FR-BRAIN-04
---
FR-BRAIN-06: Distillation pipeline (LangGraph subgraph)
Description: System shall run an async distillation subgraph after each completed 
  analysis + deepeval evaluation, extracting candidate coaching entries when eval 
  scores exceed quality thresholds (overall >= 0.85, correctness >= 0.8).
Phase: 3  |  Priority: Must  |  Dependencies: FR-BRAIN-02, existing deepeval pipeline
---
FR-BRAIN-07: Expert review queue
Description: System shall present candidate Coach Brain entries in an admin review 
  queue with promote/reject actions, displaying trigger conditions, coaching action, 
  source analysis context, and eval scores.
Phase: 3  |  Priority: Must  |  Dependencies: FR-BRAIN-06
---
FR-BRAIN-08: Confidence-based auto-triage
Description: System shall auto-approve entries with faithfulness >= 0.95 AND 
  confirmation_count >= 3, auto-reject entries with faithfulness < 0.60, and route 
  remaining entries to human review.
Phase: 3  |  Priority: Should  |  Dependencies: FR-BRAIN-07
---
FR-BRAIN-09: Seed corpus ingestion
Description: System shall support bulk ingestion of manually curated coaching entries 
  (minimum 20 entries covering common squat/bench/deadlift errors) with 
  status=approved bypassing the distillation pipeline.
Phase: 2  |  Priority: Must  |  Dependencies: FR-BRAIN-01, FR-BRAIN-02
---
FR-BRAIN-10: Privacy-preserving trigger conditions
Description: Trigger conditions shall use categorical bins (3-5 categories per 
  attribute) for body proportions rather than precise measurements, with minimum 
  group size enforcement (n >= 20) before surfacing patterns.
Phase: 2  |  Priority: Must  |  Dependencies: FR-BRAIN-02
---
FR-BRAIN-11: Explicit health data consent
Description: System shall implement a separate, granular consent interaction for 
  health data processing under GDPR Article 9(2)(a), distinct from general ToS 
  acceptance, with withdrawable consent tracked per user.
Phase: 2  |  Priority: Must  |  Dependencies: None (legal/UX)
---
FR-BRAIN-12: Per-athlete episodic memory
Description: System shall store per-athlete session history, cue delivery records, 
  and cue effectiveness scores in Postgres JSONB with RLS, queryable by athlete_id 
  and date range.
Phase: 4  |  Priority: Could  |  Dependencies: FR-BRAIN-04, existing Supabase setup
---
FR-BRAIN-13: Coach Brain retrieval metrics
Description: System shall log retrieval_source (coach_brain_primary, 
  hybrid_brain_supplementary, papers_only_fallback), similarity scores, and hit 
  counts per query for monitoring Coach Brain contribution over time.
Phase: 2  |  Priority: Should  |  Dependencies: FR-BRAIN-04
---
FR-BRAIN-14: CoVe verification for distilled entries
Description: Distillation pipeline shall apply Chain-of-Verification to candidate 
  entries, cross-checking coaching claims against papers_rag collection content 
  before promotion.
Phase: 3  |  Priority: Should  |  Dependencies: FR-BRAIN-06
---
FR-BRAIN-15: DPIA documentation
Description: System shall have a completed Data Protection Impact Assessment 
  covering Coach Brain processing before launch, addressing Article 35(7) 
  requirements.
Phase: 2  |  Priority: Must  |  Dependencies: FR-BRAIN-11 (legal)
```

### Existing SRS requirements that change in scope

**RetrieveTool** (likely FR-RAG-XX): Currently assumes a single Qdrant collection. Must be extended to query two collections with priority logic and fallback. The tool's interface changes from `retrieve(query) → results` to `retrieve(query, exercise) → RetrievalResult{primary, supplementary, source}`.

**spelix-rag-engineer agent**: Currently scoped to papers collection only. Either expand scope to cover Coach Brain collection management, or split responsibilities (see agent definitions below). At minimum, the agent's system prompt and available tools must acknowledge two collections.

**ARQ worker architecture** (likely NFR-XX): Distillation pipeline adds a new async task type. If staying on ARQ, add `distill_coaching_entry` to the `functions` list in `WorkerSettings`. If migrating to streaq, add `@worker.task()` decorator.

**deepeval evaluation pipeline**: Currently evaluates coaching output quality. Must now also feed eval scores into the distillation pipeline as input. The evaluation step becomes a branching point — deliver results to user AND trigger distillation.

**Privacy Policy / ToS**: Must be updated with Article 13 information obligations for health data processing, automated decision-making disclosures, and explicit consent mechanism.

### New agent definitions

**Recommended: create `spelix-brain-engineer`, do NOT expand `spelix-rag-engineer`.** The two agents have different expertise domains and responsibilities:

| Agent | Responsibility |
|-------|---------------|
| `spelix-rag-engineer` | Papers collection management, document chunking, scientific literature ingestion, citation accuracy |
| `spelix-brain-engineer` | Coach Brain collection management, distillation pipeline, expert review queue, coaching entry quality, hybrid retrieval orchestration |
| `spelix-distillation-engineer` | **Not recommended as separate agent.** The distillation pipeline is a LangGraph subgraph, not a standalone agent. It is a component owned by `spelix-brain-engineer`. Creating a separate agent for a single pipeline adds unnecessary architectural complexity. |

### Phase assignment with dependency justification

**Phase 2 (Foundation):** FR-BRAIN-01 through -05, -09, -10, -11, -13, -15. Rationale: Collection infrastructure, seed corpus, retrieval integration, privacy consent, and DPIA must exist before any automated distillation. Phase 2 delivers a functional Coach Brain with manually seeded entries.

**Phase 3 (Automation):** FR-BRAIN-06, -07, -08, -14. Rationale: Distillation pipeline depends on having a working collection (Phase 2) and a sufficient volume of completed analyses with eval scores to feed the pipeline. Expert review queue depends on distillation producing candidates.

**Phase 4 (Personalization):** FR-BRAIN-12. Rationale: Per-athlete memory depends on sufficient user base and validated coaching effectiveness signal from Coach Brain. This is the longest-horizon feature with the most privacy complexity.

### Architecture Decision Records

**ADR-BRAIN-01: Separate Qdrant collection for Coach Brain**
- Decision: Create a second named collection (`coach_brain`) on the existing Qdrant cluster rather than namespacing within `papers_rag`.
- Context: Collections have different schemas, update cadences, and HNSW tuning needs. Qdrant documentation explicitly recommends separate collections for non-homogenous data.
- Consequences: Application-layer orchestration needed for cross-collection queries. Two collections to monitor/backup. Modest additional resource overhead (acceptable at 2–3 collections).

**ADR-BRAIN-02: Contextual padding over raw embedding for short coaching text**
- Decision: Prepend structured metadata (exercise, phase, entry_type) to raw coaching cue text before embedding.
- Context: Anthropic's Contextual Retrieval research shows 35% retrieval failure reduction from contextual prepending. Short coaching cues (5–20 words) provide limited semantic signal for dense embeddings without context.
- Consequences: Embedding pipeline must construct padded text at index time. Template changes require re-embedding affected entries. Query-time embedding remains unchanged (asymmetric retrieval via `input_type`).

**ADR-BRAIN-03: Hybrid dense+sparse retrieval with RRF fusion**
- Decision: Use both Cohere embed-v4 dense vectors and BM25 sparse vectors in Coach Brain, merged via Reciprocal Rank Fusion.
- Context: Domain-specific coaching terminology (lockout, valgus, tempo) requires exact keyword matching that BM25 provides. Qdrant's own research confirms sparse vectors excel when rare specialized terms are present.
- Consequences: Each entry requires both dense and sparse vector computation at index time. Slightly higher storage and query latency. Significantly improved retrieval precision for domain-specific queries.

**ADR-BRAIN-04: Defer ARQ → streaq migration to post-MVP**
- Decision: Remain on ARQ for MVP; prototype streaq migration in a branch for one non-critical worker.
- Context: ARQ is maintenance-only but functional. streaq is technically strong but has ~125 stars, single maintainer, no proven production deployments, and 6 major versions in one year. Migration requires rewriting all worker code with zero drop-in compatibility.
- Consequences: Accept ARQ's 85 unresolved issues and lack of new features short-term. Avoid mid-project API churn risk. Re-evaluate after streaq v6.x stabilizes (target: 3–6 months post-MVP). taskiq is the fallback if streaq doesn't mature.

**ADR-BRAIN-05: GDPR Article 9 explicit consent for all form analysis data**
- Decision: Treat all barbell form analysis data (body proportions, movement quality, session history) as special-category health data under GDPR Article 9 and require explicit opt-in consent.
- Context: CJEU Grand Chamber (2022) interpreted health data broadly. Body proportion data "reveals information relating to physical health status" per Recital 35. Conservative compliance position protects against enforcement risk in EU markets.
- Consequences: Requires separate consent interaction in UX (cannot bundle with ToS). Users who decline health data consent cannot have their analyses contribute to Coach Brain aggregate patterns. Mandatory DPIA before launch. DPO appointment recommended.

**ADR-BRAIN-06: Postgres JSONB for per-athlete episodic memory (Phase 4)**
- Decision: Use Supabase Postgres JSONB with Row-Level Security for per-athlete session history, deferring a third Qdrant collection unless semantic search over memories is validated as a requirement.
- Context: Dominant query patterns are relational (recent sessions, effectiveness trends, date-range lookups). Postgres RLS is more mature than Qdrant payload filtering for privacy-critical per-user isolation. Supabase already deployed.
- Consequences: No semantic search over athlete memories without adding a third Qdrant collection later. Relational queries are faster and simpler. Schema changes require migrations rather than re-indexing.

**ADR-BRAIN-07: Distillation as LangGraph subgraph with async invocation**
- Decision: Implement distillation as a separate LangGraph `StateGraph` with its own `DistillationState`, invoked inside a wrapper node using Pattern B (state schema transformation), triggered asynchronously after coaching graph completion.
- Context: Distillation must not block user-facing coaching response. Clean state isolation enables independent testing. LangGraph's subgraph pattern inherits the parent's checkpointer.
- Consequences: Wrapper node handles `CoachingState ↔ DistillationState` transformation. Async invocation means distillation failures don't affect user experience but require separate monitoring. Background task reliability depends on task queue (ARQ/streaq).

---

## 3. Privacy design

### Minimum viable privacy-preserving trigger_conditions

**Trigger conditions must use categorical bins derived from sports science literature, not from the user population distribution** (which would leak information about the user base). The binning schema:

| Attribute | Bins | Source of bin boundaries |
|-----------|------|------------------------|
| Height | short (<165cm), average (165–180cm), tall (>180cm) | Standard anthropometric categories |
| Build | light (<70kg), medium (70–90kg), heavy (>90kg) | Strength sport weight classes |
| Limb ratio | short, proportional, long | Relative to torso (standard somatotyping) |
| Mobility level | limited, average, above_average | Based on joint ROM thresholds from ACSM |
| Training age | novice (<1yr), intermediate (1–3yr), advanced (>3yr) | Standard periodization categories |

**K-anonymity enforcement:** Never surface a coaching pattern unless ≥20 users fall within the bin combination. With ~500 users and 5 quasi-identifiers at 3 categories each, the maximum possible groups are 3^5 = 243, yielding an average of ~2 users per group — far below k=20. **This means at early scale, most bin combinations will be suppressed.** Reduce quasi-identifiers to 2–3 (exercise + build + mobility_level) until the user base grows, which yields 3 × 3 × 3 = 27 groups and ~18 users per group at n=500 — borderline viable.

**Differential privacy is impractical below ~5,000 users.** The Laplace noise required for meaningful ε values (0.1–1.0) overwhelms signal in small subgroups. At n=500 with ε=1.0, noise standard deviation of ~1.41 on a subgroup count of 20 users introduces ~7% error; at ε=0.1, it renders small-group statistics useless. Defer formal DP to Phase 4 when user counts support it. Use pseudonymization + binning + minimum group sizes as the primary protection mechanism at early scale.

### GDPR Article 13 and Article 35 specifics

**Article 13 information obligations — the Privacy Policy must include:**

1. Explicit identification that body proportion data, movement quality scores, and session history constitute health data processed under Article 9
2. Specific purposes listed separately: (a) individual coaching delivery, (b) aggregate pattern extraction for coaching improvement, (c) per-athlete session tracking
3. Legal basis mapping: Article 6(1)(b) contract performance for individual coaching + Article 9(2)(a) explicit consent for health data processing
4. Named recipients of health data (cloud infrastructure provider, embedding API provider)
5. Retention periods per data category — recommend 24 months for individual analyses, indefinite for anonymized aggregates
6. Automated decision-making disclosure under Article 22: the AI coaching system generates form assessments and exercise recommendations that may qualify as automated decisions with significant effects
7. Right to withdraw consent and consequences (analyses will continue but won't contribute to aggregate patterns)

**Article 35 DPIA is mandatory.** Coach Brain meets at least 5 of the WP29's 9 high-risk criteria: evaluation/scoring of movement quality, automated decision-making with significant effect (coaching recommendations), systematic monitoring (ongoing session tracking), sensitive health data under Article 9, and innovative use of AI/ML technology. The DPIA must be completed before processing begins and must include: systematic description of processing operations, necessity/proportionality assessment, risk assessment to data subjects' rights, and specific mitigation measures.

### Consent mechanism

**Explicit opt-in under Article 9(2)(a) is the only viable option.** "Legitimate interest" under Article 6(1)(f) is not listed in Article 9(2)'s closed list of exceptions for special-category data. You need both an Article 6 basis AND an Article 9 condition. The recommended consent flow:

1. **General service consent** at signup — Article 6(1)(b) contract performance for delivering the coaching service
2. **Separate explicit consent** for health data analysis — presented as a distinct interaction, not bundled with ToS, explaining what data is collected, how it's processed, and for what purposes
3. **Optional granular consent** for aggregate pattern extraction — "Allow your anonymized form patterns to improve coaching for all users?" This is legally required if the aggregate extraction purpose is distinct from individual coaching delivery

Consent must be documented, timestamped, specific to each purpose, freely given (the service should function without aggregate consent — only individual coaching delivery is essential), and withdrawable at any time via a user-accessible mechanism.

---

## 4. Expert gate design

### Admin UI minimum for 30-second review

The reviewer needs exactly this information, rendered in a single-screen card:

- **Coaching action text** (the actual cue, prominently displayed, 5–20 words)
- **Entry type** badge (cue / heuristic / compensation)
- **Exercise + phase** (e.g., "Squat → Concentric")
- **Trigger condition summary** (binned attributes as tags, e.g., "tall · heavy · limited mobility")
- **Source analysis link** (clickable to view the original video analysis that generated this entry)
- **deepeval scores** displayed as a mini scorecard: faithfulness, correctness, relevance, overall — color-coded green/yellow/red
- **CoVe verification result** (pass/fail with brief explanation)
- **Confirmation count** (how many independent analyses produced similar entries)
- **Similar existing entries** (top 2 most similar approved entries, to assess redundancy — retrieved via cosine similarity from Coach Brain itself)
- **Two action buttons:** Approve (green) and Reject (red), with an optional "Needs edit" action that opens an inline text editor for the coaching action

### Confidence-based auto-triage thresholds

```
AUTO-APPROVE (no human review needed):
  faithfulness     >= 0.95  AND
  correctness      >= 0.90  AND
  cove_verified    == true  AND
  confirmation_count >= 3

AUTO-REJECT (no human review needed):
  faithfulness     < 0.60   OR
  correctness      < 0.50   OR
  overall          < 0.55

ROUTE TO HUMAN (everything else):
  All entries not matching auto-approve or auto-reject criteria
  Priority ordering in queue: higher overall score → higher in queue
```

**Rationale for thresholds:** The auto-approve bar is deliberately high (faithfulness ≥0.95 plus 3 independent confirmations) to prevent low-quality entries from entering the knowledge base without review. The auto-reject bar captures entries where the LLM demonstrably hallucinated (low faithfulness) or generated incorrect coaching advice (low correctness). The human-review band captures the uncertain middle where judgment is needed. **These thresholds should be calibrated against a labeled validation set of 50+ manually reviewed entries once available.** Start conservative (route more to humans) and relax auto-approve thresholds as reviewer agreement patterns emerge.

### Handling cv_compensation entries

Entries with `entry_type=compensation` (e.g., "excessive forward lean compensating for limited ankle dorsiflexion") require **biomechanics expertise, not just coaching expertise.** These entries involve causal chains between joint limitations and movement pattern adaptations.

**Triage logic for compensation entries:**

- Flag compensation entries with a `requires_technical_review` tag in the review queue
- Route to reviewers with a `biomechanics_qualified` flag on their admin account
- If no biomechanics-qualified reviewer is available, hold in queue with a 7-day SLA rather than auto-approving
- Compensation entries should have a **higher auto-approve threshold**: require `confirmation_count >= 5` (vs. 3 for cues) because the causal reasoning is more complex and error-prone
- Consider requiring two independent reviewer approvals for compensation entries (dual sign-off)

---

## 5. Minimum viable corpus

### 20 highest-priority seed entries

```
# SQUAT (8 entries)

1. entry_type: cue | exercise: squat | phase: descent
   trigger: knee_valgus_detected
   action: "Push knees out over pinky toes throughout the descent"

2. entry_type: cue | exercise: squat | phase: concentric  
   trigger: good_morning_squat_pattern
   action: "Drive your back into the bar — chest up first, then extend hips"

3. entry_type: heuristic | exercise: squat | phase: setup
   trigger: high_bar_position AND tall_lifter
   action: "Widen stance to shoulder-width-plus-one-fist; angle toes 30-45°"

4. entry_type: compensation | exercise: squat | phase: descent
   trigger: excessive_forward_lean AND limited_ankle_dorsiflexion
   action: "Elevate heels with wedge or squat shoes to reduce forward lean compensation"

5. entry_type: cue | exercise: squat | phase: concentric
   trigger: hip_shift_detected
   action: "Drive both feet equally — think 'spread the floor' on the way up"

6. entry_type: heuristic | exercise: squat | phase: descent
   trigger: depth_above_parallel
   action: "Pause at bottom position for 1-count to build confidence at depth"

7. entry_type: cue | exercise: squat | phase: setup
   trigger: bar_position_unstable
   action: "Squeeze shoulder blades together and pull elbows under the bar"

8. entry_type: compensation | exercise: squat | phase: concentric
   trigger: butt_wink AND short_torso_long_femur
   action: "Widen stance and reduce depth target to just-below-parallel to manage pelvic tuck"

# BENCH PRESS (6 entries)

9. entry_type: cue | exercise: bench_press | phase: descent
   trigger: elbow_flare_excessive
   action: "Tuck elbows to 45° — think 'bend the bar into a U'"

10. entry_type: cue | exercise: bench_press | phase: concentric
    trigger: bar_path_drifts_toward_face
    action: "Press back toward the rack — bar should travel in a J-curve, not straight up"

11. entry_type: heuristic | exercise: bench_press | phase: setup
    trigger: no_arch_detected
    action: "Plant feet flat, squeeze glutes, and drive chest toward ceiling to set arch"

12. entry_type: compensation | exercise: bench_press | phase: concentric
    trigger: one_arm_leads AND shoulder_imbalance_detected
    action: "Add 2-3 sets of single-arm dumbbell press on weaker side per week"

13. entry_type: cue | exercise: bench_press | phase: lockout
    trigger: sticking_point_mid_range
    action: "Accelerate through the sticking point — drive as fast as possible off the chest"

14. entry_type: cue | exercise: bench_press | phase: setup
    trigger: grip_width_suboptimal
    action: "Set grip so forearms are vertical when bar touches chest"

# DEADLIFT (6 entries)

15. entry_type: cue | exercise: deadlift | phase: concentric
    trigger: back_rounding_detected
    action: "Push the floor away with your legs — don't think 'pull,' think 'leg press'"

16. entry_type: cue | exercise: deadlift | phase: lockout
    trigger: soft_lockout
    action: "Squeeze glutes hard at the top — lock hips, don't hyperextend the back"

17. entry_type: heuristic | exercise: deadlift | phase: setup
    trigger: long_arms_short_torso
    action: "Conventional stance likely suits your proportions — bar over mid-foot, shoulders over bar"

18. entry_type: compensation | exercise: deadlift | phase: concentric
    trigger: hips_rise_first AND weak_quadriceps
    action: "Hips and shoulders should rise together — add front squats to strengthen quads"

19. entry_type: cue | exercise: deadlift | phase: setup
    trigger: bar_too_far_from_shins
    action: "Start with bar over mid-foot — should be 1 inch from shins at setup"

20. entry_type: cue | exercise: deadlift | phase: concentric
    trigger: grip_failure_before_legs
    action: "Switch to mixed grip or hook grip — grip should not be the limiting factor"
```

### Minimum corpus size for meaningful contribution

**No published hard thresholds exist from Mem0, Duolingo Birdbrain, or directly analogous systems.** Mem0 focuses on architectural efficiency (26% accuracy improvement over OpenAI memory) but publishes no minimum entry counts. Birdbrain processes 1.25 billion exercises daily at scale but does not publish cold-start thresholds; it ramped through 2020 before deployment, suggesting months of data accumulation.

From general RAG and expert system patterns, the estimated thresholds for Coach Brain:

- **20 entries (seed corpus):** Enough for Coach Brain to contribute non-trivially to ~40–60% of common-case queries across all three lifts. This is the "better than nothing" threshold that justifies the infrastructure investment.
- **50–100 entries:** Coverage extends to most common error patterns with exercise × phase × trigger granularity. The system starts consistently outperforming papers-only RAG for coaching-specific queries. **This is the target for Phase 2 launch.**
- **500+ entries:** Long-tail coverage of body-type-specific patterns, compensation chains, and multi-cue sequences. The system handles edge cases that static knowledge cannot.
- **2,000+ entries with outcome data:** Enables confidence in which cues actually work (not just which cues are plausible), because confirmation counts from real analyses provide empirical signal. **This is where Coach Brain's confirmation-count signal becomes meaningfully reliable.**

**Evidence quality flag:** These thresholds are analytical estimates based on coverage analysis (3 exercises × ~15 common errors × 3–5 body types = 135–225 unique patterns needed for comprehensive coverage), not empirical measurements from comparable systems. The 50–100 entry target for Phase 2 launch is a pragmatic bet — track retrieval hit rate and source distribution metrics (FR-BRAIN-13) to validate empirically.

### Seeding strategy recommendation

**LLM-assisted with expert validation** is the optimal approach. Pure manual creation by certified coaches is accurate but slow and expensive. Pure LLM generation risks hallucinated biomechanics. The hybrid approach:

1. **Claude generates candidate entries** from a structured prompt that includes exercise descriptions, common error taxonomies (from NSCA and ACSM literature), and the Coach Brain schema. Generate 50–100 candidates.
2. **Certified strength coach reviews each entry** for biomechanical accuracy, coaching appropriateness, and trigger condition validity. Estimate 2–3 minutes per entry = 2.5–5 hours total for 50–100 entries.
3. **Entries that fail review** get annotated with the reason and become training signal for improving the generation prompt.
4. Approved entries enter Coach Brain with `status=approved` and `source=seed_manual_validated`.

**Do not extract from existing analyses** for the seed corpus. At launch there are too few analyses to identify reliable patterns, and the distillation pipeline (Phase 3) is not yet built. Existing analyses will feed the automated distillation pipeline once it is operational.

