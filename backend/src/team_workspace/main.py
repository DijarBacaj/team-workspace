from fastapi import FastAPI

app = FastAPI(title="Team Workspace API")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
