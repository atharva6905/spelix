---
name: coaching-sex-aware-retrieval
description: Sex-aware retrieval/prompt threading (#225) — filter-merge pattern, cache boundary, and the worker-singleton orchestrator test harness
metadata:
  type: project
---

Reviewed issue #225 (sex-applicability hard filter on papers_rag + prompt line) 2026-06-10 → PASS, 1 non-blocking MEDIUM. Durable patterns for coaching/retrieval reviews:

**Qdrant filter-merge pattern (canonical):** `additional_filters: list | None` ANDed into `Filter.must` alongside the exercise `FieldCondition`. Faithful shape: `must_conditions: list = []`, append exercise cond if present, `extend(additional_filters)` if truthy, then `Filter(must=must_conditions)` only `if must_conditions`. Both `RetrievalService.dense_search` AND `SparseRetrievalService.sparse_search` must mirror this — the sparse/BM25 leg historically did NOT forward `additional_filters`, so any new payload filter touching only dense_search leaks opposite-class results through sparse. Grep both legs on every new retrieval filter.

**`additional_filters or None` idiom:** callers build local `list`, append, pass `local or None` (`[]`→`None`); downstream truthy-checks `if additional_filters:`. Consistent — don't flag `[]` vs `None` as long as both ends truthy-check.

**Cache boundary (FR-AICP-21/ADR-020):** per-user context (sex, body_stats, rep metrics) goes in `_build_user_prompt` (fresh per-turn user msg). `cache_control: ephemeral` applies ONLY to `_build_system_prompt` output (coaching.py ~583). Anything added to the user builder is outside the cached block by construction. Verify new per-user lines land in user builder, not system builder.

**Normalization single-point + defense-in-depth:** worker (`_run_coaching_imperative` + `_run_coaching_graph`) is the ONLY `prefer_not_to_say`/undisclosed→None site, via `if getattr(profile,'sex',None) in ("male","female")`. Yet tools.py, dual_collection, `_build_user_prompt` ALL re-check `in ("male","female")`. Intended defense-in-depth — not redundancy to flag.

**AgentState input-only PII field:** `lifter_sex` is INPUT only — never an `output_key`, so stays out of `agent_trace_json`/LangSmith (FR-EXPV-03). Confirm new PII-bearing AgentState fields aren't emitted as node outputs.

**Worker-test orchestrator harness (non-obvious, VALID):** `_setup_worker_test` patches `app.services.dual_collection.DualCollectionOrchestrator` with `return_value=mock_orchestrator` (singleton AsyncMock). Tests instantiate their OWN `DualCollectionOrchestrator(None,None)` inside the patch to grab the SAME mock, then assert `.retrieve.call_args.kwargs`. Looks suspicious but correct — patch makes every construction return the one mock. Not vacuous: uncalled mock → `.call_args` None → AttributeError, so passing means real invocation. Graph-path tests instead patch `app.agents.graph.run_coaching_graph` as AsyncMock and call `_run_coaching_graph` directly.

Minor (did not block): `_sex_conditions` helper copy-pasted across test_dual_collection.py + test_agents_tools.py. Fine for test isolation; MEDIUM if it spreads further.
