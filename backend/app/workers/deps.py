"""Worker dependency builder for distillation.

Centralises construction of the heavyweight clients (Anthropic,
instructor, Cohere, Qdrant, BrainEmbeddingService) so task bodies can
stay thin. lifecycle_decision goes through QdrantClientWrapper.query_points
(ADR-DISTILL-07 / D-053), so the wrapper is passed directly — no raw-
client escape hatch.
"""

from __future__ import annotations

from typing import Any

import anthropic
import instructor

from app.db import async_session
from app.services.brain_embedding import BrainEmbeddingService
from app.services.cohere_client import get_cohere_client
from app.services.qdrant import get_qdrant_client


async def build_distillation_ctx() -> dict[str, Any]:
    """Build the non-session dependencies the distillation body expects."""
    anthropic_client = anthropic.AsyncAnthropic()
    instructor_client = instructor.from_anthropic(anthropic_client)

    cohere_client = get_cohere_client()
    qdrant_wrapper = await get_qdrant_client()

    brain_embedding = BrainEmbeddingService(
        cohere_client=cohere_client,
        qdrant_client=qdrant_wrapper,  # type: ignore[arg-type]
    )

    return {
        "anthropic_client": anthropic_client,
        "instructor_client": instructor_client,
        "cohere_client": cohere_client,
        "qdrant_client": qdrant_wrapper,
        "brain_embedding_svc": brain_embedding,
        "db_session_maker": async_session,
    }
