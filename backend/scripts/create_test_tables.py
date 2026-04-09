"""Create test database tables using SQLAlchemy create_all.

Used in CI instead of Alembic because CI Postgres lacks the Supabase
auth schema required by migration 002 (RLS policies).
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend/ to sys.path so `app` package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine

from app.models.base import Base

# Import all models so they register with Base.metadata
from app.models import Analysis, CoachingResult, RepMetric, UserProfile  # noqa: F401


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Test tables created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
