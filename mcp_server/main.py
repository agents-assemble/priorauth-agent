"""Uvicorn ASGI entry point for the MCP server.

Run locally:
    make mcp
Or directly:
    uv run --package mcp_server uvicorn mcp_server.main:app \\
        --host 0.0.0.0 --port 8000 --log-level info --reload --env-file .env

The streamable-HTTP MCP endpoint is served at `/` (upstream convention). The
MCP capabilities blob - including our `ai.promptopinion/fhir-context`
extension - is reachable by any MCP client that completes the initialize
handshake. Quick sanity check: `make mcp-initialize` after `make mcp`.

CORS is wide-open locally so the PO workspace can call us from a browser
context during registration. Tighten before prod via MCP_ALLOWED_ORIGINS.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mcp_server.server import mcp


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan, title="priorauth-mcp")

_allowed = os.getenv("MCP_ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed.split(",")] if _allowed != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/", mcp.streamable_http_app())
