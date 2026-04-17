"""lifecycle_decision — FR-BRAIN-17 cosine routing.

For each CandidateInsight, embed via Cohere (SEARCH_DOCUMENT), search
the Qdrant coach_brain collection filtered by exercise + status=active,
and decide:
  cosine > 0.92 → NOOP (knowledge already exists)
  0.75 <= cosine <= 0.92 → UPDATE (confirm existing entry)
  cosine < 0.75 → ADD (novel; route to review queue)

Empty Qdrant (cold start or no matches) → ADD with nearest_entry_id=None.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import models as qdrant_models

from app.distillation.state import (
    CandidateInsight,
    DistillationState,
    LifecycleDecision,
)
from app.schemas.coach_brain import CoachBrainEntryCreate
from app.services.cohere_client import EmbedInputType
from app.services.qdrant import COLLECTION_COACH_BRAIN

logger = logging.getLogger(__name__)

_NOOP_THRESHOLD = 0.92
_UPDATE_FLOOR = 0.75


def _build_proxy_entry(candidate: CandidateInsight) -> CoachBrainEntryCreate:
    """Build a throwaway CoachBrainEntryCreate purely to reuse BrainEmbeddingService.build_contextual_text."""
    return CoachBrainEntryCreate(
        content=candidate.content,
        exercise=candidate.exercise,
        phase=candidate.phase,
        entry_type=candidate.entry_type,
        trigger_tags=candidate.trigger_tags,
    )


async def lifecycle_decision(
    state: DistillationState,
    *,
    cohere_client: Any,
    qdrant_client: Any,
    brain_embedding_svc: Any,
) -> dict[str, Any]:
    """Route each candidate to ADD / UPDATE / NOOP via cosine similarity."""
    candidates: list[CandidateInsight] = state.get("candidates") or []
    if not candidates:
        return {"decisions": []}

    texts = [
        brain_embedding_svc.build_contextual_text(_build_proxy_entry(c))
        for c in candidates
    ]
    vectors = await cohere_client.embed_batch(
        texts, input_type=EmbedInputType.SEARCH_DOCUMENT
    )

    decisions: list[LifecycleDecision] = []
    for candidate, vector in zip(candidates, vectors, strict=True):
        exercise_filter = qdrant_models.FieldCondition(
            key="exercise",
            match=qdrant_models.MatchValue(value=candidate.exercise),
        )
        status_filter = qdrant_models.FieldCondition(
            key="status",
            match=qdrant_models.MatchValue(value="active"),
        )
        query_filter = qdrant_models.Filter(must=[exercise_filter, status_filter])

        try:
            hits = await qdrant_client.search(
                collection_name=COLLECTION_COACH_BRAIN,
                query_vector=vector,
                query_filter=query_filter,
                limit=1,
                with_payload=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "lifecycle_decision: qdrant search failed (%s) — treating as ADD",
                exc,
            )
            hits = []

        if not hits:
            decisions.append(LifecycleDecision(decision="ADD", nearest_entry_id=None, cosine_sim=0.0))
            continue

        top = hits[0]
        nearest_id = uuid.UUID(top.id) if isinstance(top.id, str) else top.id
        score = float(top.score)

        if score >= _NOOP_THRESHOLD:
            label = "NOOP"
        elif score >= _UPDATE_FLOOR:
            label = "UPDATE"
        else:
            label = "ADD"

        decisions.append(
            LifecycleDecision(decision=label, nearest_entry_id=nearest_id, cosine_sim=score)
        )

    return {"decisions": decisions}
