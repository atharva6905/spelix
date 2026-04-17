"""Worker dependency builder for distillation.

Centralises construction of the heavyweight clients (Anthropic,
instructor, Cohere, Qdrant, BrainEmbeddingService) so task bodies can
stay thin.

Note on Qdrant: lifecycle_decision calls qdrant_client.search(...) which is
the raw AsyncQdrantClient API. QdrantClientWrapper only exposes query_points,
so we pass wrapper._client (the underlying AsyncQdrantClient) as qdrant_client.
CohereEmbedClient exposes embed_batch directly, so we pass the wrapper itself.
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

    # lifecycle_decision calls .search() — only available on the raw
    # AsyncQdrantClient, not on QdrantClientWrapper (which exposes query_points).
    qdrant_raw = qdrant_wrapper._client if qdrant_wrapper is not None else None

    return {
        "anthropic_client": anthropic_client,
        "instructor_client": instructor_client,
        "cohere_client": cohere_client,
        "qdrant_client": qdrant_raw,
        "brain_embedding_svc": brain_embedding,
        "db_session_maker": async_session,
    }
