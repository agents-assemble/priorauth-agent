FROM python:3.11-slim AS base

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock .python-version ./
COPY shared/pyproject.toml shared/pyproject.toml
COPY mcp_server/pyproject.toml mcp_server/pyproject.toml
COPY a2a_agent/pyproject.toml a2a_agent/pyproject.toml

RUN uv sync --frozen --no-dev --package a2a_agent

COPY shared/ shared/
COPY a2a_agent/ a2a_agent/

EXPOSE 8001

CMD ["uv", "run", "--no-sync", "--package", "a2a_agent", \
     "uvicorn", "a2a_agent.app:a2a_app", \
     "--host", "0.0.0.0", "--port", "8001", "--log-level", "info"]
