"""
Integration-style unit tests for the repository layer.

These tests require a real DATABASE_URL pointing at Supabase PgBouncer.
Each test runs inside a transaction that is rolled back at teardown —
leaving the DB clean after every run.

Run: cd backend && uv run pytest tests/unit/test_repositories.py -x -v
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models.analysis import Analysis
from app.models.coaching_result import CoachingResult
from app.models.rep_metric import RepMetric
from app.models.user_profile import UserProfile
from app.repositories.analysis import AnalysisRepository
from app.repositories.coaching_result import CoachingResultRepository
from app.repositories.rep_metric import RepMetricRepository
from app.repositories.user_profile import UserProfileRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session():
    raw_url = os.environ["DATABASE_URL"]
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(raw_url, connect_args={"statement_cache_size": 0})
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()
    await engine.dispose()


def _fake_user_id() -> UUID:
    """Return a random UUID that stands in for a Supabase auth.users id."""
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# AnalysisRepository tests
# ---------------------------------------------------------------------------


class TestAnalysisRepository:
    async def test_create_returns_persisted_analysis(self, db_session: AsyncSession):
        repo = AnalysisRepository(db_session)
        user_id = _fake_user_id()
        analysis = Analysis(
            user_id=user_id,
            status="queued",
            exercise_type="squat",
            exercise_variant="high_bar",
        )
        created = await repo.create(analysis)

        assert created.id is not None
        assert created.user_id == user_id
        assert created.status == "queued"

    async def test_get_by_id_returns_correct_row(self, db_session: AsyncSession):
        repo = AnalysisRepository(db_session)
        user_id = _fake_user_id()
        analysis = Analysis(
            user_id=user_id,
            status="queued",
            exercise_type="deadlift",
            exercise_variant="conventional",
        )
        created = await repo.create(analysis)

        fetched = await repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.exercise_type == "deadlift"

    async def test_get_by_id_returns_none_for_missing(self, db_session: AsyncSession):
        repo = AnalysisRepository(db_session)
        result = await repo.get_by_id(uuid.uuid4())
        assert result is None

    async def test_get_by_user_ordered_desc(self, db_session: AsyncSession):
        """Rows must come back ordered by created_at DESC."""
        repo = AnalysisRepository(db_session)
        user_id = _fake_user_id()

        # Use explicit naive UTC timestamps so ordering is deterministic even
        # within one transaction (server_default=now() returns the same value
        # for all rows in a single transaction). The column is TIMESTAMP
        # WITHOUT TIME ZONE so we pass naive datetimes.
        now = datetime.utcnow()
        a1 = Analysis(
            user_id=user_id,
            status="queued",
            exercise_type="squat",
            exercise_variant="high_bar",
            created_at=now - timedelta(seconds=10),
            updated_at=now - timedelta(seconds=10),
        )
        a2 = Analysis(
            user_id=user_id,
            status="completed",
            exercise_type="bench",
            exercise_variant="flat",
            created_at=now,
            updated_at=now,
        )
        created1 = await repo.create(a1)
        created2 = await repo.create(a2)

        rows = await repo.get_by_user(user_id)
        assert len(rows) == 2
        # Most recently created (a2) must be first
        ids = [r.id for r in rows]
        assert ids.index(created2.id) < ids.index(created1.id)

    async def test_get_by_user_respects_limit_offset(self, db_session: AsyncSession):
        repo = AnalysisRepository(db_session)
        user_id = _fake_user_id()

        for _ in range(3):
            a = Analysis(
                user_id=user_id,
                status="queued",
                exercise_type="squat",
                exercise_variant="high_bar",
            )
            await repo.create(a)

        page1 = await repo.get_by_user(user_id, limit=2, offset=0)
        page2 = await repo.get_by_user(user_id, limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 1

    async def test_update_status(self, db_session: AsyncSession):
        repo = AnalysisRepository(db_session)
        user_id = _fake_user_id()
        analysis = Analysis(
            user_id=user_id,
            status="queued",
            exercise_type="squat",
            exercise_variant="low_bar",
        )
        created = await repo.create(analysis)

        updated = await repo.update_status(created.id, "processing")
        assert updated.status == "processing"

    async def test_update(self, db_session: AsyncSession):
        repo = AnalysisRepository(db_session)
        user_id = _fake_user_id()
        analysis = Analysis(
            user_id=user_id,
            status="queued",
            exercise_type="squat",
            exercise_variant="high_bar",
        )
        created = await repo.create(analysis)
        created.error_message = "some error"
        updated = await repo.update(created)
        assert updated.error_message == "some error"

    async def test_delete_removes_row(self, db_session: AsyncSession):
        repo = AnalysisRepository(db_session)
        user_id = _fake_user_id()
        analysis = Analysis(
            user_id=user_id,
            status="queued",
            exercise_type="bench",
            exercise_variant="flat",
        )
        created = await repo.create(analysis)

        await repo.delete(created.id)
        fetched = await repo.get_by_id(created.id)
        assert fetched is None

    async def test_delete_nonexistent_is_noop(self, db_session: AsyncSession):
        repo = AnalysisRepository(db_session)
        # Must not raise
        await repo.delete(uuid.uuid4())


# ---------------------------------------------------------------------------
# UserProfileRepository tests
# ---------------------------------------------------------------------------


class TestUserProfileRepository:
    async def test_create_returns_persisted_profile(self, db_session: AsyncSession):
        repo = UserProfileRepository(db_session)
        user_id = _fake_user_id()
        profile = UserProfile(
            user_id=user_id,
            height_cm=180.0,
            weight_kg=80.0,
            age=25,
            experience_level="intermediate",
        )
        created = await repo.create(profile)

        assert created.id is not None
        assert created.user_id == user_id
        assert created.height_cm == 180.0

    async def test_get_by_user_id_returns_profile(self, db_session: AsyncSession):
        repo = UserProfileRepository(db_session)
        user_id = _fake_user_id()
        profile = UserProfile(user_id=user_id, height_cm=170.0, weight_kg=70.0)
        await repo.create(profile)

        fetched = await repo.get_by_user_id(user_id)
        assert fetched is not None
        assert fetched.user_id == user_id
        assert fetched.height_cm == 170.0

    async def test_get_by_user_id_returns_none_for_missing(
        self, db_session: AsyncSession
    ):
        repo = UserProfileRepository(db_session)
        result = await repo.get_by_user_id(uuid.uuid4())
        assert result is None

    async def test_update_persists_changes(self, db_session: AsyncSession):
        repo = UserProfileRepository(db_session)
        user_id = _fake_user_id()
        profile = UserProfile(user_id=user_id, height_cm=170.0)
        created = await repo.create(profile)

        created.weight_kg = 75.5
        updated = await repo.update(created)
        assert updated.weight_kg == 75.5


# ---------------------------------------------------------------------------
# RepMetricRepository tests
# ---------------------------------------------------------------------------


class TestRepMetricRepository:
    async def _make_analysis(
        self, db_session: AsyncSession, user_id: UUID | None = None
    ) -> Analysis:
        """Helper: insert a minimal Analysis row so FK constraint holds."""
        from app.repositories.analysis import AnalysisRepository

        a_repo = AnalysisRepository(db_session)
        a = Analysis(
            user_id=user_id or _fake_user_id(),
            status="processing",
            exercise_type="squat",
            exercise_variant="high_bar",
        )
        return await a_repo.create(a)

    async def test_create_batch_returns_all_metrics(self, db_session: AsyncSession):
        repo = RepMetricRepository(db_session)
        analysis = await self._make_analysis(db_session)

        metrics = [
            RepMetric(
                analysis_id=analysis.id,
                rep_index=i,
                start_frame=i * 30,
                end_frame=i * 30 + 29,
                confidence_score=0.9,
                metrics_json={"hip_angle": 90.0},
            )
            for i in range(3)
        ]
        created = await repo.create_batch(metrics)

        assert len(created) == 3
        assert all(m.id is not None for m in created)

    async def test_get_by_analysis_ordered_by_rep_index(
        self, db_session: AsyncSession
    ):
        repo = RepMetricRepository(db_session)
        analysis = await self._make_analysis(db_session)

        # Insert in reverse order to verify ordering is enforced by the query
        metrics = [
            RepMetric(
                analysis_id=analysis.id,
                rep_index=i,
                start_frame=i * 30,
                end_frame=i * 30 + 29,
                confidence_score=0.8,
            )
            for i in [2, 0, 1]
        ]
        await repo.create_batch(metrics)

        fetched = await repo.get_by_analysis(analysis.id)
        assert [m.rep_index for m in fetched] == [0, 1, 2]

    async def test_get_by_analysis_empty_for_unknown_id(
        self, db_session: AsyncSession
    ):
        repo = RepMetricRepository(db_session)
        result = await repo.get_by_analysis(uuid.uuid4())
        assert result == []


# ---------------------------------------------------------------------------
# CoachingResultRepository tests
# ---------------------------------------------------------------------------


class TestCoachingResultRepository:
    async def _make_analysis(self, db_session: AsyncSession) -> Analysis:
        from app.repositories.analysis import AnalysisRepository

        a_repo = AnalysisRepository(db_session)
        a = Analysis(
            user_id=_fake_user_id(),
            status="coaching",
            exercise_type="bench",
            exercise_variant="flat",
        )
        return await a_repo.create(a)

    async def test_create_returns_persisted_result(self, db_session: AsyncSession):
        repo = CoachingResultRepository(db_session)
        analysis = await self._make_analysis(db_session)

        coaching = CoachingResult(
            analysis_id=analysis.id,
            structured_output_json={"summary": "Good form overall."},
            stream_complete=True,
        )
        created = await repo.create(coaching)

        assert created.id is not None
        assert created.analysis_id == analysis.id
        assert created.structured_output_json == {"summary": "Good form overall."}

    async def test_get_by_analysis_returns_result(self, db_session: AsyncSession):
        repo = CoachingResultRepository(db_session)
        analysis = await self._make_analysis(db_session)

        coaching = CoachingResult(
            analysis_id=analysis.id,
            stream_complete=True,
        )
        created = await repo.create(coaching)

        fetched = await repo.get_by_analysis(analysis.id)
        assert fetched is not None
        assert fetched.id == created.id

    async def test_get_by_analysis_returns_none_for_missing(
        self, db_session: AsyncSession
    ):
        repo = CoachingResultRepository(db_session)
        result = await repo.get_by_analysis(uuid.uuid4())
        assert result is None
