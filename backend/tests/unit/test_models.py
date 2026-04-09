"""Unit tests for SQLAlchemy models — validates fields, CHECK constraint, and indexes."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Analysis, CoachingResult, RepMetric, UserProfile, VALID_STATUSES


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh async session against Supabase for each test, with rollback."""
    import os

    raw_url = os.environ["DATABASE_URL"]
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(
        raw_url,
        connect_args={"statement_cache_size": 0},
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()

    await engine.dispose()


class TestAnalysisModel:
    """Tests for the Analysis model."""

    @pytest.mark.asyncio
    async def test_create_analysis_valid_status(self, db_session: AsyncSession):
        analysis = Analysis(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            status="queued",
            exercise_type="squat",
            exercise_variant="high_bar",
            retry_count=0,
            flagged_for_review=False,
            is_golden_dataset=False,
        )
        db_session.add(analysis)
        await db_session.flush()

        result = await db_session.get(Analysis, analysis.id)
        assert result is not None
        assert result.status == "queued"
        assert result.exercise_type == "squat"
        assert result.confidence_score is None
        assert result.form_score_safety is None
        assert result.summary_json is None
        assert result.tags is None

    @pytest.mark.asyncio
    async def test_all_valid_statuses_accepted(self, db_session: AsyncSession):
        for status in VALID_STATUSES:
            analysis = Analysis(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                status=status,
                exercise_type="squat",
                exercise_variant="high_bar",
            )
            db_session.add(analysis)
        await db_session.flush()

    @pytest.mark.asyncio
    async def test_invalid_status_rejected(self, db_session: AsyncSession):
        analysis = Analysis(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            status="invalid_status",
            exercise_type="squat",
            exercise_variant="high_bar",
        )
        db_session.add(analysis)
        with pytest.raises(Exception, match="ck_analyses_status"):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_jsonb_columns(self, db_session: AsyncSession):
        analysis = Analysis(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            status="queued",
            exercise_type="deadlift",
            exercise_variant="conventional",
            summary_json={"total_reps": 5, "avg_score": 0.85},
            quality_gate_result={"passed": True, "checks": []},
        )
        db_session.add(analysis)
        await db_session.flush()

        result = await db_session.get(Analysis, analysis.id)
        assert result.summary_json["total_reps"] == 5
        assert result.quality_gate_result["passed"] is True

    @pytest.mark.asyncio
    async def test_cascade_delete_rep_metrics(self, db_session: AsyncSession):
        analysis = Analysis(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            status="completed",
            exercise_type="bench_press",
            exercise_variant="flat",
        )
        db_session.add(analysis)
        await db_session.flush()

        rep = RepMetric(
            id=uuid.uuid4(),
            analysis_id=analysis.id,
            rep_index=1,
            start_frame=0,
            end_frame=30,
            confidence_score=0.92,
            metrics_json={"depth_angle": 85.0},
        )
        db_session.add(rep)
        await db_session.flush()

        await db_session.delete(analysis)
        await db_session.flush()

        result = await db_session.get(RepMetric, rep.id)
        assert result is None


class TestUserProfileModel:
    @pytest.mark.asyncio
    async def test_create_profile(self, db_session: AsyncSession):
        profile = UserProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            height_cm=180.0,
            weight_kg=85.0,
            age=25,
            experience_level="intermediate",
        )
        db_session.add(profile)
        await db_session.flush()

        result = await db_session.get(UserProfile, profile.id)
        assert result.height_cm == 180.0
        assert result.arm_span_cm is None


class TestCoachingResultModel:
    @pytest.mark.asyncio
    async def test_create_coaching_result(self, db_session: AsyncSession):
        analysis = Analysis(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            status="completed",
            exercise_type="squat",
            exercise_variant="low_bar",
        )
        db_session.add(analysis)
        await db_session.flush()

        coaching = CoachingResult(
            id=uuid.uuid4(),
            analysis_id=analysis.id,
            structured_output_json={"summary": "Good form", "issues": []},
            stream_complete=True,
            cove_verified=False,
        )
        db_session.add(coaching)
        await db_session.flush()

        result = await db_session.get(CoachingResult, coaching.id)
        assert result.structured_output_json["summary"] == "Good form"
        assert result.stream_complete is True


class TestIndexes:
    @pytest.mark.asyncio
    async def test_required_indexes_exist(self, db_session: AsyncSession):
        result = await db_session.execute(
            text("""
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename IN ('analyses', 'rep_metrics', 'coaching_results')
                ORDER BY indexname
            """)
        )
        index_names = {row[0] for row in result.fetchall()}
        assert "ix_analyses_user_created" in index_names
        assert "ix_rep_metrics_analysis" in index_names
        assert "ix_coaching_results_analysis" in index_names
