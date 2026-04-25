"""MCP tool wrappers for A2A sub-agents (Week 2+).

When ``MCP_SERVER_URL`` is set, this module exposes MCP tools as plain
ADK ``FunctionTool``s by calling the MCP server via raw ``httpx``.
This bypasses both ``McpToolset`` and the MCP SDK's
``streamablehttp_client``, which have ``anyio`` cancel-scope
incompatibilities with uvicorn's asyncio event loop (ADK experimental
issue as of 2026-04).

The MCP Streamable HTTP protocol is JSON-RPC over HTTP with SSE
responses. For tool calls we just POST the JSON-RPC envelope and
parse the SSE ``event: message`` frame.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)

_FHIR_SERVER_URL_HEADER = "x-fhir-server-url"
_FHIR_ACCESS_TOKEN_HEADER = "x-fhir-access-token"

_MCP_URL = (os.environ.get("MCP_SERVER_URL") or "").strip()

_SSE_DATA_RE = re.compile(r"^data:\s*(.+)$", re.MULTILINE)
_HTTP_OK = 200


def _get_fhir_headers_from_context(tool_context: Any) -> dict[str, str]:
    """Extract FHIR headers from ADK tool context session state."""
    headers: dict[str, str] = {}
    try:
        state = tool_context.state
        fhir_url = (state.get("fhir_url") or "").strip()
        fhir_token = (state.get("fhir_token") or "").strip()
        if fhir_url:
            headers[_FHIR_SERVER_URL_HEADER] = fhir_url
        if fhir_token:
            headers[_FHIR_ACCESS_TOKEN_HEADER] = fhir_token
    except Exception:
        logger.warning("Could not extract FHIR headers from tool context")
    return headers


def _parse_sse_json(text: str) -> dict[str, Any] | None:
    """Extract the first JSON-RPC result from an SSE response body."""
    for m in _SSE_DATA_RE.finditer(text):
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
    return None


async def _call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    extra_headers: dict[str, str] | None = None,
) -> str:
    """Call an MCP tool via raw httpx (no MCP SDK, no anyio issues)."""
    if not _MCP_URL:
        return json.dumps({"error": "MCP_SERVER_URL not configured"})

    logger.info("MCP_CALL tool=%s url=%s", tool_name, _MCP_URL)

    hdrs = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        **(extra_headers or {}),
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            init_body = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "a2a-agent", "version": "1.0"},
                },
            }
            init_resp = await client.post(_MCP_URL, json=init_body, headers=hdrs)
            if init_resp.status_code != _HTTP_OK:
                logger.error("MCP init failed: %s %s", init_resp.status_code, init_resp.text[:200])
                return json.dumps({"error": f"MCP init failed: HTTP {init_resp.status_code}"})

            session_id = init_resp.headers.get("mcp-session-id", "")
            if session_id:
                hdrs["mcp-session-id"] = session_id

            notif_body = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            await client.post(_MCP_URL, json=notif_body, headers=hdrs)

            call_body = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
            call_resp = await client.post(_MCP_URL, json=call_body, headers=hdrs)
    except httpx.ConnectError as e:
        logger.error("MCP_CONNECT_FAILED tool=%s url=%s error=%s", tool_name, _MCP_URL, e)
        return json.dumps({"error": f"MCP connection failed: {e}"})
    except Exception as e:
        logger.error("MCP_UNEXPECTED_ERROR tool=%s error=%r", tool_name, e)
        return json.dumps({"error": f"MCP unexpected error: {type(e).__name__}: {e}"})

    if call_resp.status_code != _HTTP_OK:
        logger.error("MCP tool call failed: %s %s", call_resp.status_code, call_resp.text[:200])
        return json.dumps({"error": f"MCP call failed: HTTP {call_resp.status_code}"})

    parsed = _parse_sse_json(call_resp.text)
    if parsed is None:
        try:
            parsed = json.loads(call_resp.text)
        except json.JSONDecodeError:
            logger.error("MCP unparseable response: %s", call_resp.text[:500])
            return json.dumps({"error": "Could not parse MCP response"})

    result = parsed.get("result", {})
    content = result.get("content", [])
    is_error = result.get("isError", False)

    text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
    combined = "\n".join(text_parts)

    if is_error:
        logger.error("MCP_CALL_ERROR tool=%s error=%s", tool_name, combined[:200])
        return json.dumps({"error": combined})

    logger.info("MCP_CALL_OK tool=%s response_len=%d", tool_name, len(combined))
    return combined


async def _fetch_patient_context_wrapper(
    patient_id: str,
    service_code: str,
    tool_context: Any,
) -> str:
    """ADK FunctionTool wrapper for MCP fetch_patient_context."""
    headers = _get_fhir_headers_from_context(tool_context)
    return await _call_mcp_tool(
        "fetch_patient_context",
        {"patient_id": patient_id, "service_code": service_code},
        extra_headers=headers,
    )


async def _match_payer_criteria_wrapper(
    patient_context_json: str,
    payer_id: str,
    service_code: str,
    tool_context: Any,
) -> str:
    """ADK FunctionTool wrapper for MCP match_payer_criteria."""
    headers = _get_fhir_headers_from_context(tool_context)
    return await _call_mcp_tool(
        "match_payer_criteria",
        {
            "patient_context_json": patient_context_json,
            "payer_id": payer_id,
            "service_code": service_code,
        },
        extra_headers=headers,
    )


async def evaluate_prior_auth(
    patient_id: str,
    service_code: str,
    tool_context: Any,
) -> str:
    """ADK FunctionTool wrapper for MCP evaluate_prior_auth (combined).

    Function name must match what the criteria_evaluator instruction tells the
    LLM to call — ADK's FunctionTool derives tool.name from the function name.
    """
    headers = _get_fhir_headers_from_context(tool_context)
    return await _call_mcp_tool(
        "evaluate_prior_auth",
        {"patient_id": patient_id, "service_code": service_code},
        extra_headers=headers,
    )


def patient_context_mcp_tools() -> list[FunctionTool]:
    """Return ADK FunctionTools for the patient_context sub-agent."""
    if not _MCP_URL:
        return []
    return [FunctionTool(_fetch_patient_context_wrapper)]


def criteria_evaluator_mcp_tools() -> list[FunctionTool]:
    """Return ADK FunctionTools for the criteria_evaluator sub-agent.

    Uses the combined ``evaluate_prior_auth`` tool so the LLM makes one
    tool call instead of two sequential calls, reducing Gemini usage from
    5 to 3 calls per PO request (fits within the free-tier 5 RPM limit).
    """
    if not _MCP_URL:
        return []
    return [FunctionTool(evaluate_prior_auth)]


def patient_context_mcp_toolsets() -> list[FunctionTool]:
    """Alias for backward compat."""
    return patient_context_mcp_tools()


def criteria_evaluator_mcp_toolsets() -> list[FunctionTool]:
    """Alias for backward compat."""
    return criteria_evaluator_mcp_tools()
