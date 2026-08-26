import asyncio

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from team_workspace.database import engine

EXPECTED_TABLES = {
    "alembic_version",
    "comments",
    "labels",
    "memberships",
    "organizations",
    "projects",
    "refresh_tokens",
    "task_assignees",
    "task_labels",
    "tasks",
    "users",
}


def table_names(connection: Connection) -> set[str]:
    return set(inspect(connection).get_table_names())


async def check_database() -> None:
    async with engine.connect() as connection:
        if await connection.scalar(text("SELECT 1")) != 1:
            raise RuntimeError("Database connectivity check failed.")
        existing_tables = await connection.run_sync(table_names)
    await engine.dispose()

    missing_tables = EXPECTED_TABLES - existing_tables
    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise RuntimeError(f"Database schema is missing tables: {missing}")
    print("Database connectivity and schema checks passed.")


if __name__ == "__main__":
    asyncio.run(check_database())
