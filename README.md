# Team Workspace

Team Workspace is a full-stack portfolio project for managing organizations,
members, projects, and tasks. The repository currently contains the production-ready
FastAPI backend; the React client is the next planned milestone.

## Backend Features

- Registration and login with Argon2 password hashing
- Short-lived JWT access tokens and rotating, revocable refresh tokens
- Organizations, memberships, and owner/admin/member/viewer authorization
- Projects and tasks with assignments, labels, and comments
- Pagination, filtering, searching, and sorting
- PostgreSQL constraints, indexes, and Alembic migrations
- Consistent validation and error responses with request IDs
- OpenAPI 3.1 and Swagger UI
- Seed data, Docker Compose, and GitHub Actions
- Unit and integration tests with coverage reporting

## Quick Start with Docker

```powershell
$env:JWT_SECRET_KEY = "replace-with-at-least-32-random-characters"
docker compose up --build
```

The API is available at `http://localhost:8000`, Swagger UI at
`http://localhost:8000/docs`, and readiness status at
`http://localhost:8000/health/ready`.

## Repository Structure

```text
team-workspace/
├── .github/workflows/backend-ci.yml
├── backend/
│   ├── alembic/
│   ├── src/team_workspace/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── docs/
├── docker-compose.yml
└── README.md
```

## Documentation

- [Backend development guide](backend/README.md)
- [Architecture](docs/architecture.md)
- [Database model](docs/database.md)
- [Security considerations](docs/security.md)
- [Architecture decision record](docs/decisions/0001-modular-monolith.md)
- [Performance](docs/performance.md)

## Quality Gate

Every backend change must pass:

```powershell
cd backend
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=team_workspace --cov-report=term-missing
```

## Project Status

The backend API is feature-complete for the first project milestone. The frontend
dashboard remains intentionally separate from this API milestone.
