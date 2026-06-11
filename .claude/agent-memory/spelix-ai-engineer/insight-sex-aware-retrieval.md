---
name: insight-sex-aware-retrieval
description: Sex-aware coaching pattern (#225) — papers-only sex filter, lifter_sex threading through both coaching paths, BM25 filter-leak fix, trace PII safety
metadata:
  type: project
---

Sex-aware coaching retrieval + prompt (issue #225, FR-AICP-05/09/12 ext.). Final task of the sex-aware series stacked on #221-#224.

**What it does:** when lifter sex is known ("male"/"female"), hard-filter papers_rag retrieval to `sex_applicability ∈ {sex, "both"}` via `MatchAny`, and append one line to the coaching prompt's Athlete Profile block: `Lifter sex: {sex} — apply evidence for {sex} lifters where it differs.` Unset/"prefer_not_to_say" → behavior identical to before (no filter, no line).

**Why:** sex-specific biomechanics evidence; avoid surfacing opposite-sex papers. coach_brain retrieval intentionally UNCHANGED (deferred to #226).
**How to apply:**
- Normalization happens ONCE in the worker: `lifter_sex = profile.sex if profile.sex in ("male","female") else None`. Everything downstream assumes pre-normalized ("male"/"female"/None only). Don't re-normalize in coaching/agents.
- Filter is applied at the orchestrator (`dual_collection.retrieve`) and agent tool (`tools.retrieve_papers`) via `additional_filters=[FieldCondition(key="sex_applicability", match=MatchAny(any=[sex,"both"]))]` — papers_rag leg ONLY.
- **BM25 leak trap:** `RetrievalService.hybrid_search` previously forwarded `additional_filters` to the dense leg only — sparse leg ignored it. Fixed by adding `additional_filters` param to `sparse_retrieval.sparse_search` (merged into `Filter.must` exactly like dense) AND forwarding it in `hybrid_search`'s gather branch. Without this, sex-filtered queries leak opposite-sex papers via BM25.
- `sex` is NOT added to `_USER_PROFILE_BODY_STATS_FIELDS` (analysis_worker.py) — the prompt line is the single representation; avoids double-stating inside body_stats JSON.
- Two coaching paths both need threading: imperative (`orchestrator.retrieve` + `generate_coaching_streaming`) and LangGraph agent (`run_coaching_graph` → `make_initial_state` → `AgentState["lifter_sex"]` → `tools.retrieve_papers` reads `state.get("lifter_sex")`, `tools.generate_correction_plan` passes it to coaching svc).

**PII / trace safety (FR-EXPV-03):** `lifter_sex` is an AgentState INPUT field only. The trace (`agent_trace_json`) records only `NodeEvent.output_keys` = keys a node *returns*; inputs never appear. `lifter_sex` is never returned as a node output, so it cannot leak into agent_trace_json or LangSmith. `run_config_for_analysis` metadata only carries analysis_id/user_id/mode — no profile fields. Verified clean.

See [[insight-hybrid-rag-architecture]] [[insight-langgraph-orchestration]].
