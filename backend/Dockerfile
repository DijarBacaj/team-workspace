FROM python:3.13-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.12.6 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

COPY alembic.ini ./
COPY alembic ./alembic

RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "team_workspace.main:app", "--host", "0.0.0.0", "--port", "8000"]
