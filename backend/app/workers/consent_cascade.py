"""ARQ job: consent withdrawal cascade (FR-BRAIN-16).

When a user withdraws coach_brain_contribution consent, this job:
1. Finds all analysis IDs owned by the user
2. Removes those IDs from source_analysis_ids in coach_brain_entries
3. Soft-deletes entries left empty with confirmation_count < 3
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import DATABASE_URL
from app.models.analysis import Analysis
from app.models.coach_brain_candidate import CoachBrainCandidate
from app.repositories.coach_brain import CoachBrainRepository

logger = logging.getLogger(__name__)


async def cascade_consent_withdrawal(ctx: dict, user_id: str) -> dict:
    """Remove a user's analysis contributions from Coach Brain entries.

    Called asynchronously via ARQ after consent withdrawal for
    'coach_brain_contribution' type.
    """
    uid = uuid.UUID(user_id)
    logger.info("Starting consent withdrawal cascade for user %s", uid)

    engine = create_async_engine(
        DATABASE_URL, echo=False, connect_args={"statement_cache_size": 0}
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as db:
            # Step 1: find all analysis IDs for this user
            result = await db.execute(
                select(Analysis.id).where(Analysis.user_id == uid)
            )
            analysis_ids = list(result.scalars().all())

            if not analysis_ids:
                logger.info("User %s has no analyses — cascade complete (no-op)", uid)
                return {"removed": 0, "soft_deleted": 0, "candidates_updated": 0}

            # Step 2: remove those IDs from coach_brain_entries
            repo = CoachBrainRepository(db)
            modified = await repo.remove_analysis_ids_for_user(analysis_ids)

            # Step 3: soft-delete entries left empty with low confirmation
            deleted = await repo.soft_delete_empty_unconfirmed()

            # Step 4 (FR-BRAIN-16): cascade to coach_brain_candidates
            cand_result = await db.execute(
                select(CoachBrainCandidate).where(
                    CoachBrainCandidate.source_analysis_ids.op("&&")(analysis_ids)
                )
            )
            cand_rows = cand_result.scalars().all()
            for row in cand_rows:
                remaining = [aid for aid in row.source_analysis_ids if aid not in analysis_ids]
                if not remaining:
                    row.review_status = "rejected"
                    row.rejected_reason = "source_consent_withdrawn"
                    row.source_analysis_ids = []
                else:
                    row.source_analysis_ids = remaining
            if cand_rows:
                await db.flush()

            await db.commit()

            logger.info(
                "Consent withdrawal cascade complete for user %s: "
                "%d entries modified, %d soft-deleted, %d candidates updated",
                uid,
                modified,
                deleted,
                len(cand_rows),
            )
            return {
                "removed": modified,
                "soft_deleted": deleted,
                "candidates_updated": len(cand_rows),
            }
    finally:
        await engine.dispose()
