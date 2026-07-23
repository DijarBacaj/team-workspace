from fastapi import FastAPI
from team_workspace.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
