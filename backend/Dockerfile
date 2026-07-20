# syntax=docker/dockerfile:1.6
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS base

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

# Install lockfile & manifest first for layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code.
COPY app ./app
COPY main.py ./

# SQLite data lives on a mounted volume.
ENV DATABASE_URL=sqlite+aiosqlite:////app/data/workbench.db

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]