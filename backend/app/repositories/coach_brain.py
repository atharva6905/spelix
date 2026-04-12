"""Repository for coach_brain_entries table operations.

FR-BRAIN-16: consent withdrawal cascade — remove user's analysis IDs
from source_analysis_ids, soft-delete entries left empty with low confirmation.
"""

import uuid

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coach_brain_entry import CoachBrainEntry


class CoachBrainRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def remove_analysis_ids_for_user(self, analysis_ids: list[uuid.UUID]) -> int:
        """Remove the given analysis IDs from source_analysis_ids across all entries.

        Uses Postgres array_remove in a loop for each ID.
        Returns the number of entries that were modified.
        """
        if not analysis_ids:
            return 0

        modified = 0
        for aid in analysis_ids:
            result = await self._db.execute(
                text(
                    """
                    UPDATE coach_brain_entries
                    SET source_analysis_ids = array_remove(source_analysis_ids, :aid),
                        updated_at = now()
                    WHERE :aid = ANY(source_analysis_ids)
                    """
                ),
                {"aid": aid},
            )
            modified += result.rowcount
        return modified

    async def soft_delete_empty_unconfirmed(self) -> int:
        """Soft-delete entries where source_analysis_ids is empty AND confirmation_count < 3.

        Sets status='deprecated' (per DB CHECK constraint) and stores the
        rejection reason in metadata JSONB.
        FR-BRAIN-16: SRS specifies status='rejected' but the CHECK constraint
        only allows seed/active/deprecated. Using 'deprecated' with metadata
        to capture the reason.
        """
        result = await self._db.execute(
            update(CoachBrainEntry)
            .where(
                CoachBrainEntry.source_analysis_ids == {},
                CoachBrainEntry.confirmation_count < 3,
                CoachBrainEntry.status != "deprecated",
            )
            .values(
                status="deprecated",
                extra_metadata=text(
                    "metadata || '{\"rejected_reason\": \"source_consent_withdrawn\"}'::jsonb"
                ),
            )
        )
        return result.rowcount
