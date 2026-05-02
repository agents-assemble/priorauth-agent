FROM python:3.11-slim AS base

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock .python-version ./
COPY shared/pyproject.toml shared/pyproject.toml
COPY mcp_server/pyproject.toml mcp_server/pyproject.toml
COPY a2a_agent/pyproject.toml a2a_agent/pyproject.toml

RUN uv sync --frozen --no-dev --package mcp_server

COPY shared/ shared/
COPY mcp_server/ mcp_server/

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "--package", "mcp_server", \
     "uvicorn", "mcp_server.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
