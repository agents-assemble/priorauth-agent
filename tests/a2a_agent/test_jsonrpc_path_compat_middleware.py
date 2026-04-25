"""Tests for ``JsonRpcPathCompatMiddleware`` (POST /mcp -> POST / on A2A)."""

from __future__ import annotations

from a2a_agent.po_base.middleware import JsonRpcPathCompatMiddleware
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


def test_post_mcp_is_rewritten_to_slash_for_routing() -> None:
    async def echo(request):
        return JSONResponse({"path": request.url.path})

    app = Starlette(routes=[Route("/", echo, methods=["POST"])])
    app.add_middleware(JsonRpcPathCompatMiddleware)

    with TestClient(app) as client:
        r = client.post("/mcp", json={"ok": True})
    assert r.status_code == 200
    assert r.json() == {"path": "/"}


def test_post_slash_unchanged() -> None:
    async def echo(request):
        return JSONResponse({"path": request.url.path})

    app = Starlette(routes=[Route("/", echo, methods=["POST"])])
    app.add_middleware(JsonRpcPathCompatMiddleware)

    with TestClient(app) as client:
        r = client.post("/", json={})
    assert r.status_code == 200
    assert r.json() == {"path": "/"}


def test_get_mcp_not_rewritten() -> None:
    async def mcp_get(request):
        return JSONResponse({"path": request.url.path})

    app = Starlette(routes=[Route("/mcp", mcp_get, methods=["GET"])])
    app.add_middleware(JsonRpcPathCompatMiddleware)

    with TestClient(app) as client:
        r = client.get("/mcp")
    assert r.status_code == 200
    assert r.json() == {"path": "/mcp"}
