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

_QDRANT_4XX_STATUS_CODES = frozenset({401, 403, 404, 429})


def _is_qdrant_4xx(exc: BaseException) -> bool:
    """Return True if the exception is a Qdrant HTTP 4xx (auth/missing).

    D-054: 4xx indicates sustained operator-action-required failure
    (revoked API key, deleted collection, rate-limit ceiling) and should
    page. Transient network errors (ConnectionError, timeout) stay at
    WARNING per the surrounding caller.

    The qdrant-client surface exposes HTTP errors via UnexpectedResponse;
    its `status_code` attribute is an int. We match defensively: duck-type
    the attribute rather than `isinstance` on UnexpectedResponse, so the
    helper stays correct if qdrant-client moves the exception class.
    """
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and status_code in _QDRANT_4XX_STATUS_CODES:
        return True
    return False


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
    """Route each candidate to ADD / UPDATE / NOOP via cosine similarity.

    D-053 (ADR-DISTILL-07): uses QdrantClientWrapper.query_points — NOT
    AsyncQdrantClient.search (removed in qdrant-client 1.x). The wrapper's
    query_points returns a QueryResponse envelope; nearest hits live on
    response.points. A try/except is retained as a safety net against
    legitimate Qdrant outages (which would otherwise crash the distillation
    graph for every candidate in a batch).
    """
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
            response = await qdrant_client.query_points(
                COLLECTION_COACH_BRAIN,
                vector,
                query_filter=query_filter,
                limit=1,
                with_payload=False,
            )
            hits = list(response.points)
        except Exception as exc:  # noqa: BLE001
            # D-054: distinguish auth/availability (4xx) from transient
            # (network, timeout) failures. A sustained 401/403 — e.g.
            # Qdrant API-key rotation or revocation — would be
            # operationally invisible at WARNING level if ops pages on
            # ERROR-and-above. Surface 4xx loudly; keep the broad
            # ADD-fallback behaviour intact so distillation never
            # crashes on transient errors.
            if _is_qdrant_4xx(exc):
                # Security (auditor HIGH on PR #100): do NOT interpolate the
                # raw exception via %s — UnexpectedResponse.__str__ embeds the
                # response `content` body, which on a 401 can echo request
                # context (headers, fragments) that flow into log aggregators
                # like Langfuse/Datadog. Log only the type name and status code.
                logger.error(
                    "lifecycle_decision: qdrant query_points 4xx "
                    "status=%s type=%s — treating as ADD; investigate "
                    "auth / collection state",
                    getattr(exc, "status_code", "unknown"),
                    type(exc).__name__,
                )
            else:
                # Transient (ConnectionError, timeout, etc.): %s interpolation
                # is kept to preserve historical debugging signal, but we
                # suppress the raw exception on the 4xx path above as a
                # defensive measure.
                logger.warning(
                    "lifecycle_decision: qdrant query_points failed (%s) — treating as ADD",
                    exc,
                )
            hits = []

        if not hits:
            decisions.append(LifecycleDecision(decision="ADD", nearest_entry_id=None, cosine_sim=0.0))
            continue

        top = hits[0]
        nearest_id = uuid.UUID(top.id) if isinstance(top.id, str) else top.id
        score = float(top.score)

        # FR-BRAIN-17: strict "> 0.92" for NOOP — a cosine of exactly 0.92
        # must UPDATE (increment confirmation_count), not be silently skipped.
        if score > _NOOP_THRESHOLD:
            label = "NOOP"
        elif score >= _UPDATE_FLOOR:
            label = "UPDATE"
        else:
            label = "ADD"

        decisions.append(
            LifecycleDecision(decision=label, nearest_entry_id=nearest_id, cosine_sim=score)
        )

    return {"decisions": decisions}
