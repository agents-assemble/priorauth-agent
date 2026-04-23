---
description: Python style conventions for the whole repo
globs: ["**/*.py"]
alwaysApply: true
---

# Python style

- Target **Python 3.11**. Use `from __future__ import annotations` in every module so `|` union syntax works everywhere.
- Use `uv` for dependency management. Never run `pip install` directly.
- Format + lint with `ruff` (config in `pyproject.toml`). Type check with `mypy --strict` where feasible.
- Prefer `pydantic.BaseModel` over dataclasses for anything crossing a service boundary.
- Async-first for I/O (FastMCP tools, ADK agents, FHIR client). Use `httpx.AsyncClient`, not `requests`.
- No bare `except:` — always catch specific exception types.
- Docstrings: short, one-liner summary + optional longer paragraph. No type info in docstrings (types are on signatures).
- Prefer `pathlib.Path` over `os.path`.
- Tests live in `tests/` mirroring the package structure. Use `pytest` with `pytest-asyncio` for async tests.
- Golden-file tests for LLM-generated outputs use `tests/fixtures/` for inputs and `tests/golden/` for expected outputs.
- Do not import from `mcp_server.*` inside `a2a_agent/` or vice versa. They only share via `shared/`.
