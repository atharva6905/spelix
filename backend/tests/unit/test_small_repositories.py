"""Unit tests for BetaRequestRepository, ChatMessageRepository, and
AnalysisExpertReviewRepository — branch coverage uplift."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_scalars_db(rows: list) -> MagicMock:
    scalars_result = MagicMock()
    scalars_result.all.return_value = rows
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


def _make_scalar_db(value) -> MagicMock:
    execute_result = MagicMock()
    execute_result.scalar_one.return_value = value
    execute_result.scalar_one_or_none.return_value = value
    db = AsyncMock()
    db.execute.return_value = execute_result
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


# ===========================================================================
# BetaRequestRepository
# ===========================================================================


class TestBetaRequestRepository:
    @pytest.mark.asyncio
    async def test_create_returns_row(self):
        from app.repositories.beta_request import BetaRequestRepository

        db = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()

        created_row = SimpleNamespace(
            id=uuid.uuid4(), email="test@example.com", source="landing"
        )

        async def _refresh(obj):
            # Simulate refresh assigning id
            pass

        db.refresh = _refresh

        repo = BetaRequestRepository(db)

        # We can't easily intercept the BetaRequest constructor without patching
        # but we can verify add/flush/refresh were called
        with MagicMock() as _m:
            from unittest.mock import patch

            with patch(
                "app.repositories.beta_request.BetaRequest",
                return_value=created_row,
            ):
                result = await repo.create(
                    email="test@example.com", source="landing", consented=True
                )

        assert result is created_row
        db.add.assert_called_once_with(created_row)
        db.flush.assert_awaited_once()


# ===========================================================================
# ChatMessageRepository
# ===========================================================================


class TestChatMessageRepository:
    @pytest.mark.asyncio
    async def test_create_adds_and_returns_message(self):
        from app.repositories.chat_message import ChatMessageRepository

        msg = SimpleNamespace(id=uuid.uuid4(), analysis_id=uuid.uuid4())
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        repo = ChatMessageRepository(db)
        result = await repo.create(msg)

        db.add.assert_called_once_with(msg)
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once_with(msg)
        assert result is msg

    @pytest.mark.asyncio
    async def test_get_by_analysis_returns_messages(self):
        from app.repositories.chat_message import ChatMessageRepository

        analysis_id = uuid.uuid4()
        msg = SimpleNamespace(id=uuid.uuid4(), analysis_id=analysis_id)
        db = _make_scalars_db([msg])

        repo = ChatMessageRepository(db)
        result = await repo.get_by_analysis(analysis_id)

        assert result == [msg]
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_analysis_returns_empty_when_none(self):
        from app.repositories.chat_message import ChatMessageRepository

        db = _make_scalars_db([])
        repo = ChatMessageRepository(db)

        result = await repo.get_by_analysis(uuid.uuid4())

        assert result == []


# ===========================================================================
# AnalysisExpertReviewRepository
# ===========================================================================


class TestAnalysisExpertReviewRepository:
    @pytest.mark.asyncio
    async def test_create_adds_and_returns_review(self):
        from app.repositories.analysis_expert_review import (
            AnalysisExpertReviewRepository,
        )

        review = SimpleNamespace(id=uuid.uuid4(), analysis_id=uuid.uuid4())
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        repo = AnalysisExpertReviewRepository(db)
        result = await repo.create(review)

        db.add.assert_called_once_with(review)
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once_with(review)
        assert result is review

    @pytest.mark.asyncio
    async def test_list_by_analysis_returns_reviews(self):
        from app.repositories.analysis_expert_review import (
            AnalysisExpertReviewRepository,
        )

        analysis_id = uuid.uuid4()
        review = SimpleNamespace(id=uuid.uuid4(), analysis_id=analysis_id)
        db = _make_scalars_db([review])

        repo = AnalysisExpertReviewRepository(db)
        result = await repo.list_by_analysis(analysis_id)

        assert result == [review]

    @pytest.mark.asyncio
    async def test_list_by_annotator_returns_reviews(self):
        from app.repositories.analysis_expert_review import (
            AnalysisExpertReviewRepository,
        )

        annotator_id = uuid.uuid4()
        review = SimpleNamespace(id=uuid.uuid4(), annotator_id=annotator_id)
        db = _make_scalars_db([review])

        repo = AnalysisExpertReviewRepository(db)
        result = await repo.list_by_annotator(annotator_id, limit=50, offset=0)

        assert result == [review]

    @pytest.mark.asyncio
    async def test_count_by_analysis_returns_int(self):
        from app.repositories.analysis_expert_review import (
            AnalysisExpertReviewRepository,
        )

        db = _make_scalar_db(3)
        repo = AnalysisExpertReviewRepository(db)

        result = await repo.count_by_analysis(uuid.uuid4())

        assert result == 3

    @pytest.mark.asyncio
    async def test_latest_annotation_at_returns_datetime_or_none(self):
        from datetime import datetime, timezone

        from app.repositories.analysis_expert_review import (
            AnalysisExpertReviewRepository,
        )

        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db = _make_scalar_db(dt)

        repo = AnalysisExpertReviewRepository(db)
        result = await repo.latest_annotation_at(uuid.uuid4())

        assert result == dt

    @pytest.mark.asyncio
    async def test_latest_annotation_at_returns_none_when_no_annotations(self):
        from app.repositories.analysis_expert_review import (
            AnalysisExpertReviewRepository,
        )

        db = _make_scalar_db(None)
        repo = AnalysisExpertReviewRepository(db)

        result = await repo.latest_annotation_at(uuid.uuid4())

        assert result is None
