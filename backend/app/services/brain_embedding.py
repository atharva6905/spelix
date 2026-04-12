"""BrainEmbeddingService — contextual embedding pipeline for Coach Brain entries.

Implements P2-024 (FR-BRAIN-03).

Encapsulates the two-step pipeline:
  1. Build a contextual text from the entry's exercise/phase/entry_type fields
     plus the raw content (ADR-BRAIN-02 format).
  2. Embed via Cohere embed-v4.0 (SEARCH_DOCUMENT) and upsert the resulting
     point to the ``coach_brain`` Qdrant collection.

The contextual text format is:
    "exercise:{ex} phase:{ph} type:{entry_type}\\n{content}"

When ``phase`` is ``None`` (allowed on ``CoachBrainEntryCreate``) the literal
string ``"general"`` is substituted so the prefix is always well-formed.

The ``CoachBrainPayload.content`` field stores the RAW content — not the
contextual text.  The contextual text is consumed only by Cohere and is
never persisted.
"""

from __future__ import annotations

from qdrant_client.models import PointStruct

from app.schemas.coach_brain import CoachBrainEntry, CoachBrainEntryCreate, CoachBrainPayload
from app.services.cohere_client import CohereEmbedClient, EmbedInputType
from app.services.qdrant import COLLECTION_COACH_BRAIN, QdrantClientWrapper


class BrainEmbeddingService:
    """Contextual embedding pipeline for Coach Brain entries (FR-BRAIN-03).

    Parameters
    ----------
    cohere_client:
        Configured ``CohereEmbedClient`` instance (embed-v4.0, 1024 dims).
    qdrant_client:
        Configured ``QdrantClientWrapper`` instance targeting the live cluster.
    """

    def __init__(
        self,
        cohere_client: CohereEmbedClient,
        qdrant_client: QdrantClientWrapper,
    ) -> None:
        self._cohere = cohere_client
        self._qdrant = qdrant_client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build_contextual_text(
        self, entry: CoachBrainEntry | CoachBrainEntryCreate
    ) -> str:
        """Prepend exercise/phase/type context before embedding.

        Format (ADR-BRAIN-02):
            "exercise:{exercise} phase:{phase} type:{entry_type}\\n{content}"

        When ``entry.phase`` is ``None`` the literal ``"general"`` is used so
        the prefix is always syntactically consistent and the embedding space
        captures the general nature of the entry.

        Parameters
        ----------
        entry:
            A full ``CoachBrainEntry`` or a ``CoachBrainEntryCreate`` (which
            allows ``phase=None``).

        Returns
        -------
        str
            Enriched text for embedding.  NOT for storage.
        """
        phase = entry.phase if entry.phase is not None else "general"
        return (
            f"exercise:{entry.exercise} phase:{phase} type:{entry.entry_type}\n"
            f"{entry.content}"
        )

    async def embed_and_upsert(self, entry: CoachBrainEntry) -> str:
        """Embed one Coach Brain entry and upsert to Qdrant.

        Steps:
        1. Build contextual text.
        2. Embed via Cohere (``input_type=SEARCH_DOCUMENT``).
        3. Build ``CoachBrainPayload`` from entry fields (raw content only).
        4. Create ``PointStruct`` with ``id=str(entry.id)``.
        5. Upsert to ``coach_brain`` collection.

        Parameters
        ----------
        entry:
            Full ``CoachBrainEntry`` with a server-assigned UUID.

        Returns
        -------
        str
            The Qdrant point ID (``str(entry.id)``).
        """
        contextual_text = self.build_contextual_text(entry)

        vectors = await self._cohere.embed_batch(
            [contextual_text],
            input_type=EmbedInputType.SEARCH_DOCUMENT,
        )
        vector = vectors[0]

        payload = CoachBrainPayload(
            id=str(entry.id),
            content=entry.content,
            exercise=entry.exercise,
            phase=entry.phase,
            entry_type=entry.entry_type,
            status=entry.status,
            confirmation_count=entry.confirmation_count,
            trigger_tags=entry.trigger_tags,
        )

        point = PointStruct(
            id=str(entry.id),
            vector=vector,
            payload=payload.model_dump(),
        )

        await self._qdrant.upsert_points(
            collection=COLLECTION_COACH_BRAIN,
            points=[point],
        )

        return str(entry.id)

    async def embed_and_upsert_batch(
        self, entries: list[CoachBrainEntry]
    ) -> list[str]:
        """Batch embed and upsert multiple Coach Brain entries.

        All contextual texts are assembled first and passed to a single
        ``embed_batch`` call (which handles the internal 96-chunk limit).
        All resulting points are upserted in one ``upsert_points`` call.

        Parameters
        ----------
        entries:
            List of ``CoachBrainEntry`` instances to index.

        Returns
        -------
        list[str]
            Qdrant point IDs in the same order as ``entries``.
        """
        contextual_texts = [self.build_contextual_text(e) for e in entries]

        vectors = await self._cohere.embed_batch(
            contextual_texts,
            input_type=EmbedInputType.SEARCH_DOCUMENT,
        )

        points: list[PointStruct] = []
        for entry, vector in zip(entries, vectors):
            payload = CoachBrainPayload(
                id=str(entry.id),
                content=entry.content,
                exercise=entry.exercise,
                phase=entry.phase,
                entry_type=entry.entry_type,
                status=entry.status,
                confirmation_count=entry.confirmation_count,
                trigger_tags=entry.trigger_tags,
            )
            points.append(
                PointStruct(
                    id=str(entry.id),
                    vector=vector,
                    payload=payload.model_dump(),
                )
            )

        await self._qdrant.upsert_points(
            collection=COLLECTION_COACH_BRAIN,
            points=points,
        )

        return [str(e.id) for e in entries]
