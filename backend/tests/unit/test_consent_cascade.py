"""Tests for consent withdrawal cascade (P2-030, FR-BRAIN-16).

Tests the CoachBrainRepository cascade methods and the ARQ job function.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.coach_brain import CoachBrainRepository


# ---------------------------------------------------------------------------
# CoachBrainRepository.remove_analysis_ids_for_user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_analysis_ids_empty_list():
    """No-op when analysis_ids is empty."""
    db = AsyncMock()
    repo = CoachBrainRepository(db)
    result = await repo.remove_analysis_ids_for_user([])
    assert result == 0
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_remove_analysis_ids_updates_rows():
    """Calls array_remove for each analysis ID and sums rowcounts."""
    db = AsyncMock()
    mock_result_1 = MagicMock()
    mock_result_1.rowcount = 2
    mock_result_2 = MagicMock()
    mock_result_2.rowcount = 1
    db.execute.side_effect = [mock_result_1, mock_result_2]

    repo = CoachBrainRepository(db)
    aids = [uuid.uuid4(), uuid.uuid4()]
    result = await repo.remove_analysis_ids_for_user(aids)

    assert result == 3
    assert db.execute.call_count == 2


@pytest.mark.asyncio
async def test_remove_analysis_ids_zero_matches():
    """Returns 0 when no rows contain the given analysis IDs."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    db.execute.return_value = mock_result

    repo = CoachBrainRepository(db)
    result = await repo.remove_analysis_ids_for_user([uuid.uuid4()])
    assert result == 0


# ---------------------------------------------------------------------------
# CoachBrainRepository.soft_delete_empty_unconfirmed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_delete_returns_count():
    """Returns the number of rows soft-deleted."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 5
    db.execute.return_value = mock_result

    repo = CoachBrainRepository(db)
    result = await repo.soft_delete_empty_unconfirmed()
    assert result == 5


@pytest.mark.asyncio
async def test_soft_delete_zero_rows():
    """Returns 0 when no entries match the criteria."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    db.execute.return_value = mock_result

    repo = CoachBrainRepository(db)
    result = await repo.soft_delete_empty_unconfirmed()
    assert result == 0


# ---------------------------------------------------------------------------
# cascade_consent_withdrawal ARQ job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.workers.consent_cascade.CoachBrainRepository")
@patch("app.workers.consent_cascade.create_async_engine")
async def test_cascade_job_no_analyses(mock_engine_cls, mock_repo_cls):
    """No-op when user has no analyses."""
    from app.workers.consent_cascade import cascade_consent_withdrawal

    user_id = str(uuid.uuid4())

    # Mock engine + session
    mock_engine = AsyncMock()
    mock_engine_cls.return_value = mock_engine

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # Patch async_sessionmaker to return our mock session
    with patch("app.workers.consent_cascade.async_sessionmaker") as mock_sm:
        mock_sm.return_value = MagicMock(return_value=mock_session)

        result = await cascade_consent_withdrawal({}, user_id)

    assert result == {"removed": 0, "soft_deleted": 0, "candidates_updated": 0}
    mock_repo_cls.assert_not_called()


@pytest.mark.asyncio
@patch("app.workers.consent_cascade.CoachBrainRepository")
@patch("app.workers.consent_cascade.create_async_engine")
async def test_cascade_job_with_analyses(mock_engine_cls, mock_repo_cls):
    """Removes analysis IDs and soft-deletes empty entries."""
    from app.workers.consent_cascade import cascade_consent_withdrawal

    user_id = str(uuid.uuid4())
    analysis_ids = [uuid.uuid4(), uuid.uuid4()]

    mock_engine = AsyncMock()
    mock_engine_cls.return_value = mock_engine

    mock_session = AsyncMock()

    # First execute(): select(Analysis.id) -> analysis_ids
    mock_analysis_scalars = MagicMock()
    mock_analysis_scalars.all.return_value = analysis_ids
    mock_analysis_result = MagicMock()
    mock_analysis_result.scalars.return_value = mock_analysis_scalars

    # Second execute(): select(CoachBrainCandidate) -> no matching candidates
    mock_candidate_scalars = MagicMock()
    mock_candidate_scalars.all.return_value = []
    mock_candidate_result = MagicMock()
    mock_candidate_result.scalars.return_value = mock_candidate_scalars

    mock_session.execute.side_effect = [mock_analysis_result, mock_candidate_result]
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_repo = AsyncMock()
    mock_repo.remove_analysis_ids_for_user.return_value = 3
    mock_repo.soft_delete_empty_unconfirmed.return_value = 1
    mock_repo_cls.return_value = mock_repo

    with patch("app.workers.consent_cascade.async_sessionmaker") as mock_sm:
        mock_sm.return_value = MagicMock(return_value=mock_session)

        result = await cascade_consent_withdrawal({}, user_id)

    assert result == {"removed": 3, "soft_deleted": 1, "candidates_updated": 0}
    mock_repo.remove_analysis_ids_for_user.assert_awaited_once_with(analysis_ids)
    mock_repo.soft_delete_empty_unconfirmed.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Consent withdrawal endpoint enqueues cascade job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_withdraw_coach_brain_enqueues_cascade():
    """Withdrawing coach_brain_contribution consent enqueues streaq cascade job."""
    from app.api.v1.consent import withdraw_consent
    from app.workers.streaq_worker import cascade_consent_withdrawal as _cascade_task

    mock_repo = AsyncMock()
    mock_record = MagicMock()
    mock_record.id = uuid.uuid4()
    mock_record.consent_type = "coach_brain_contribution"
    mock_record.granted = False
    mock_record.granted_at = None
    mock_record.withdrawn_at = "2026-04-12T00:00:00"
    mock_record.consent_version = "1.0"
    mock_record.created_at = "2026-04-12T00:00:00"
    mock_repo.create.return_value = mock_record

    user = {"id": uuid.uuid4(), "email": "test@example.com"}
    body = MagicMock()
    body.consent_type = "coach_brain_contribution"

    mock_worker = MagicMock()

    with patch("app.api.v1.consent._get_streaq_worker", return_value=mock_worker):
        with patch.object(_cascade_task, "enqueue", new_callable=AsyncMock) as mock_enqueue:
            await withdraw_consent(body=body, user=user, repo=mock_repo)
            mock_enqueue.assert_awaited_once_with(str(user["id"]))


@pytest.mark.asyncio
async def test_withdraw_coach_brain_does_not_crash_when_streaq_import_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: if the lazy `from app.workers.streaq_worker import worker`
    inside `_get_streaq_worker` raises, the factory returns None and the
    handler silently skips the enqueue — the HTTP request still succeeds.

    Matches the Task 6 pattern in test_streaq_enqueuer.py.
    """
    from app.api.v1 import consent as consent_mod

    consent_mod._streaq_worker_cache = None
    consent_mod._streaq_worker_cache_initialized = False
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

    import sys

    class _BrokenModule:
        def __getattr__(self, name: str) -> object:
            raise ImportError(f"simulated failure on {name}")

    monkeypatch.setitem(sys.modules, "app.workers.streaq_worker", _BrokenModule())

    w = await consent_mod._get_streaq_worker()
    assert w is None
    assert consent_mod._streaq_worker_cache_initialized is True


@pytest.mark.asyncio
async def test_withdraw_analytics_does_not_enqueue():
    """Withdrawing analytics consent does NOT enqueue cascade job."""
    from app.api.v1.consent import withdraw_consent

    mock_repo = AsyncMock()
    mock_record = MagicMock()
    mock_record.id = uuid.uuid4()
    mock_record.consent_type = "analytics"
    mock_record.granted = False
    mock_record.granted_at = None
    mock_record.withdrawn_at = "2026-04-12T00:00:00"
    mock_record.consent_version = "1.0"
    mock_record.created_at = "2026-04-12T00:00:00"
    mock_repo.create.return_value = mock_record

    user = {"id": uuid.uuid4(), "email": "test@example.com"}
    body = MagicMock()
    body.consent_type = "analytics"

    with patch("app.api.v1.consent._get_streaq_worker") as mock_get_worker:
        await withdraw_consent(body=body, user=user, repo=mock_repo)
        mock_get_worker.assert_not_called()


# ---------------------------------------------------------------------------
# FR-BRAIN-16 — coach_brain_candidates cascade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.workers.consent_cascade.CoachBrainRepository")
@patch("app.workers.consent_cascade.create_async_engine")
async def test_cascade_removes_analysis_id_from_candidates(mock_engine_cls, mock_repo_cls):
    """Cascade removes withdrawing user's analysis IDs from coach_brain_candidates.

    Mixed candidate retains the other analysis_id; solo candidate is
    soft-deleted (review_status='rejected', rejected_reason='source_consent_withdrawn').
    """
    from app.workers.consent_cascade import cascade_consent_withdrawal

    user_id = str(uuid.uuid4())
    withdrawing_aid = uuid.uuid4()
    other_aid = uuid.uuid4()

    # Solo candidate — only the withdrawing user's analysis_id
    solo_candidate = MagicMock()
    solo_candidate.source_analysis_ids = [withdrawing_aid]
    solo_candidate.review_status = "pending"
    solo_candidate.rejected_reason = None

    # Mixed candidate — withdrawing user's + another user's analysis_id
    mixed_candidate = MagicMock()
    mixed_candidate.source_analysis_ids = [withdrawing_aid, other_aid]
    mixed_candidate.review_status = "pending"
    mixed_candidate.rejected_reason = None

    mock_engine = AsyncMock()
    mock_engine_cls.return_value = mock_engine

    # First execute call returns analysis IDs; second returns candidates
    mock_analysis_scalars = MagicMock()
    mock_analysis_scalars.all.return_value = [withdrawing_aid]
    mock_analysis_result = MagicMock()
    mock_analysis_result.scalars.return_value = mock_analysis_scalars

    mock_candidate_scalars = MagicMock()
    mock_candidate_scalars.all.return_value = [solo_candidate, mixed_candidate]
    mock_candidate_result = MagicMock()
    mock_candidate_result.scalars.return_value = mock_candidate_scalars

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [
        mock_analysis_result,   # select(Analysis.id) query
        mock_candidate_result,  # select(CoachBrainCandidate) query
    ]
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_repo = AsyncMock()
    mock_repo.remove_analysis_ids_for_user.return_value = 1
    mock_repo.soft_delete_empty_unconfirmed.return_value = 0
    mock_repo_cls.return_value = mock_repo

    with patch("app.workers.consent_cascade.async_sessionmaker") as mock_sm:
        mock_sm.return_value = MagicMock(return_value=mock_session)

        result = await cascade_consent_withdrawal({}, user_id)

    # Solo candidate must be soft-deleted
    assert solo_candidate.review_status == "rejected"
    assert solo_candidate.rejected_reason == "source_consent_withdrawn"
    assert solo_candidate.source_analysis_ids == []

    # Mixed candidate must retain the other analysis_id only
    assert mixed_candidate.source_analysis_ids == [other_aid]
    assert mixed_candidate.review_status == "pending"  # unchanged

    # Return value still reports the coach_brain_entries counts
    assert result["removed"] == 1


@pytest.mark.asyncio
@patch("app.workers.consent_cascade.CoachBrainRepository")
@patch("app.workers.consent_cascade.create_async_engine")
async def test_cascade_candidates_no_overlap(mock_engine_cls, mock_repo_cls):
    """When no candidates overlap the withdrawing user's analyses, nothing is mutated."""
    from app.workers.consent_cascade import cascade_consent_withdrawal

    user_id = str(uuid.uuid4())
    withdrawing_aid = uuid.uuid4()

    mock_engine = AsyncMock()
    mock_engine_cls.return_value = mock_engine

    mock_analysis_scalars = MagicMock()
    mock_analysis_scalars.all.return_value = [withdrawing_aid]
    mock_analysis_result = MagicMock()
    mock_analysis_result.scalars.return_value = mock_analysis_scalars

    mock_candidate_scalars = MagicMock()
    mock_candidate_scalars.all.return_value = []  # no overlap
    mock_candidate_result = MagicMock()
    mock_candidate_result.scalars.return_value = mock_candidate_scalars

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [
        mock_analysis_result,
        mock_candidate_result,
    ]
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_repo = AsyncMock()
    mock_repo.remove_analysis_ids_for_user.return_value = 0
    mock_repo.soft_delete_empty_unconfirmed.return_value = 0
    mock_repo_cls.return_value = mock_repo

    with patch("app.workers.consent_cascade.async_sessionmaker") as mock_sm:
        mock_sm.return_value = MagicMock(return_value=mock_session)

        result = await cascade_consent_withdrawal({}, user_id)

    assert result == {"removed": 0, "soft_deleted": 0, "candidates_updated": 0}
