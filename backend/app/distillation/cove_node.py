"""cove_verify node — calls BrainCoveService per non-NOOP candidate.

For each (candidate, decision) pair where decision != NOOP, run
BrainCoveService.verify_claim against the analysis's already-retrieved
papers_rag contexts. NOOP candidates are skipped with a placeholder
BrainCoveResult so downstream indexing stays aligned.

CoVe failures never block storage — they just mark the candidate
cove_verified=false, which Batch 3's review UI surfaces prominently.
"""

from __future__ import annotations

from typing import Any

from app.distillation.state import BrainCoveResult, DistillationState


async def cove_verify(
    state: DistillationState,
    *,
    cove_service: Any,
) -> dict[str, Any]:
    """Run single-claim CoVe for every non-NOOP candidate."""
    candidates = state.get("candidates") or []
    decisions = state.get("decisions") or []
    contexts = state.get("retrieved_papers_contexts") or []

    results: list[BrainCoveResult] = []
    for candidate, decision in zip(candidates, decisions, strict=True):
        if decision.decision == "NOOP":
            results.append(BrainCoveResult(verified=True, explanation="noop_skip", trace=[]))
            continue
        r = await cove_service.verify_claim(claim=candidate.content, contexts=contexts)
        results.append(r)

    return {"cove_results": results}
