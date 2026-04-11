import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_raw_url = os.environ["DATABASE_URL"]
DATABASE_URL = (
    _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if _raw_url.startswith("postgresql://")
    else _raw_url
)

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields a SQLAlchemy ``AsyncSession``.

    Commits the session on successful handler completion and rolls back
    on any exception (including ``HTTPException``). The commit is the
    crucial bit — without it, ``AsyncSession``'s ``autocommit=False``
    default rolls back the implicit transaction when the session closes,
    so every flushed write disappears. That bug took down the entire
    Spelix backend's data persistence from Phase 0 onward and was only
    surfaced when ``POST /api/v1/analyses`` returned 201 with a UUID and
    the immediately following ``POST /api/v1/analyses/{id}/start``
    returned 404 because the row was rolled back between requests.

    Regression coverage:
    ``tests/unit/test_db_session.py::TestGetDbCommit``.
    """
    async with async_session() as session:
        try:
            yield session  # type: ignore[misc]
            await session.commit()
        except Exception:
            await session.rollback()
            raise
