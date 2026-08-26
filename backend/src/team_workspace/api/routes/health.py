from fastapi import APIRouter
from sqlalchemy import text

from team_workspace.dependencies import SessionDep
from team_workspace.errors import AppError

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/health/ready")
async def readiness_check(session: SessionDep) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(
            503,
            "database_unavailable",
            "The database is unavailable.",
        ) from exc
    return {"status": "ready", "database": "available"}
