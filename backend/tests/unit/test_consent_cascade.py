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

    assert result == {"removed": 0, "soft_deleted": 0}
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
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = analysis_ids
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_repo = AsyncMock()
    mock_repo.remove_analysis_ids_for_user.return_value = 3
    mock_repo.soft_delete_empty_unconfirmed.return_value = 1
    mock_repo_cls.return_value = mock_repo

    with patch("app.workers.consent_cascade.async_sessionmaker") as mock_sm:
        mock_sm.return_value = MagicMock(return_value=mock_session)

        result = await cascade_consent_withdrawal({}, user_id)

    assert result == {"removed": 3, "soft_deleted": 1}
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
