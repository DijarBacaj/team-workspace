from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from team_workspace.config import get_settings

settings = get_settings()


def build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


engine = build_engine(settings.database_url)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
