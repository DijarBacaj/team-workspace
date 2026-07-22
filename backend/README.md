# Team Workspace API

The backend API for the Team Workspace application.

## Run Locally

```powershell
uv sync
uv run uvicorn team_workspace.main:app --app-dir src --reload
```

## Run Quality Checks

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```