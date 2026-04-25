"""Tests for AGENT_PUBLIC_URL normalization in create_a2a_app."""

from __future__ import annotations

from a2a_agent.po_base.app_factory import _normalize_agent_card_public_url


def test_strip_trailing_mcp_suffix() -> None:
    assert (
        _normalize_agent_card_public_url("https://demo.ngrok-free.app/mcp")
        == "https://demo.ngrok-free.app"
    )


def test_strip_trailing_slash_then_mcp() -> None:
    assert (
        _normalize_agent_card_public_url("https://demo.ngrok-free.app/mcp/")
        == "https://demo.ngrok-free.app"
    )


def test_preserves_correct_agent_base() -> None:
    assert (
        _normalize_agent_card_public_url("https://demo.ngrok-free.app")
        == "https://demo.ngrok-free.app"
    )


def test_mcp_suffix_case_insensitive() -> None:
    assert (
        _normalize_agent_card_public_url("https://demo.ngrok-free.app/MCP")
        == "https://demo.ngrok-free.app"
    )
