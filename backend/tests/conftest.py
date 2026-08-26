import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from team_workspace.database import get_db_session
from team_workspace.main import create_app
from team_workspace.models import Base


@pytest.fixture
def test_app(tmp_path: Path) -> Iterator[FastAPI]:
    database_path = (tmp_path / "test.db").as_posix()
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        poolclass=NullPool,
    )
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    @event.listens_for(test_engine.sync_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def create_schema() -> None:
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_session() -> AsyncIterator[object]:
        async with test_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    asyncio.run(create_schema())
    application = create_app()
    application.dependency_overrides[get_db_session] = override_session
    yield application
    application.dependency_overrides.clear()
    asyncio.run(test_engine.dispose())


@pytest.fixture
def client(test_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(test_app) as test_client:
        yield test_client
