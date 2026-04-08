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
    async with async_session() as session:
        yield session
