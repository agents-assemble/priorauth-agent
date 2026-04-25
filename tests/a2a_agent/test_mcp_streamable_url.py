"""Unit tests for MCP streamable-HTTP URL normalization."""

from __future__ import annotations

from a2a_agent.mcp_patient_context import _streamable_http_mcp_url


def test_appends_mcp_when_missing() -> None:
    assert _streamable_http_mcp_url("https://example.trycloudflare.com") == (
        "https://example.trycloudflare.com/mcp"
    )
    assert _streamable_http_mcp_url("http://localhost:8000") == "http://localhost:8000/mcp"


def test_preserves_when_already_has_mcp() -> None:
    assert _streamable_http_mcp_url("http://localhost:8000/mcp") == "http://localhost:8000/mcp"
    assert _streamable_http_mcp_url("http://localhost:8000/mcp/") == "http://localhost:8000/mcp"


def test_empty_unchanged() -> None:
    assert _streamable_http_mcp_url("") == ""
    assert _streamable_http_mcp_url("   ") == ""
