# Team Workspace API

The Team Workspace backend is an asynchronous REST API built with Python 3.13,
FastAPI, Pydantic, SQLAlchemy 2, Alembic, and PostgreSQL.

## Requirements

- Python 3.13
- uv 0.11 or newer
- PostgreSQL 17, or Docker and Docker Compose

## Local Setup

```powershell
Copy-Item .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn team_workspace.main:app --reload
```

Change `JWT_SECRET_KEY` in `.env` before starting the application. In production,
the application rejects the documented placeholder secret.

## Database Migrations

Apply all migrations:

```powershell
uv run alembic upgrade head
```

Create a migration after changing SQLAlchemy models:

```powershell
uv run alembic revision --autogenerate -m "describe schema change"
```

Inspect generated migrations before applying or committing them.

## Seed Data

Set a development-only admin password, then run the idempotent seed command:

```powershell
$env:SEED_ADMIN_PASSWORD = "StrongDevelopmentPassword123"
uv run team-workspace-seed
```

The default seed email is `admin@example.com`. Override it with
`SEED_ADMIN_EMAIL`.

## API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Authenticate in Swagger with the access token returned by `/api/v1/auth/login`.

## Endpoint Summary

| Area | Endpoints |
| --- | --- |
| Health | `GET /health`, `GET /health/ready` |
| Authentication | register, login, refresh, logout |
| Users | current authenticated user |
| Organizations | CRUD and paginated membership management |
| Projects | CRUD, search, status filter, pagination, sorting |
| Tasks | CRUD, search, filters, pagination, sorting |
| Assignments | idempotent assign and unassign operations |
| Labels | organization label CRUD and task attachment |
| Comments | paginated CRUD with author/admin permissions |

All business endpoints use the `/api/v1` prefix.

## Role Matrix

| Capability | Owner | Admin | Member | Viewer |
| --- | :---: | :---: | :---: | :---: |
| Read organization data | Yes | Yes | Yes | Yes |
| Manage organization | Yes | Yes | No | No |
| Delete organization | Yes | No | No | No |
| Manage memberships | Yes | Yes | No | No |
| Assign owner role | Yes | No | No | No |
| Manage projects and labels | Yes | Yes | No | No |
| Manage tasks and comments | Yes | Yes | Yes | No |

The final owner cannot be demoted or removed.

## Error Contract

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request data is invalid.",
    "details": []
  },
  "request_id": "7fc1a8e1-2990-4f02-a58a-d00635d59c6e"
}
```

The API returns the request ID in both the response body and `X-Request-ID`
header. A caller may supply its own `X-Request-ID` for correlation.

## Quality Checks

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=team_workspace --cov-report=term-missing
uv run alembic upgrade head --sql
```

## Docker

From the repository root:

```powershell
$env:JWT_SECRET_KEY = "replace-with-at-least-32-random-characters"
docker compose up --build
```

Compose waits for PostgreSQL, applies migrations, starts the API, and checks the
readiness endpoint.
