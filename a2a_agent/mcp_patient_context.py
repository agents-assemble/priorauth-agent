"""MCP (FastMCP) toolset for the **patient_context** sub-agent (Week 2).

When ``MCP_SERVER_URL`` is set in the environment (e.g. from ``.env``), the
ADK ``McpToolset`` connects to our ``mcp_server`` streamable HTTP endpoint
(``.../mcp``) and exposes ``fetch_patient_context`` to Gemini.

``extract_fhir_context`` (``fhir_hook``) writes ``fhir_url`` and ``fhir_token``
into session state; :func:`_fhir_mcp_headers` injects the SHARP transport headers
(``x-fhir-server-url``, ``x-fhir-access-token``) so the MCP tool can call the
Prompt Opinion workspace FHIR server. Header names are duplicated from
``mcp_server/fhir/constants.py`` so ``a2a_agent`` does not take a hard dependency
on the MCP package.
"""

from __future__ import annotations

import os
from typing import Any

from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

# Must match mcp_server.fhir.constants (avoid importing mcp_server from a2a).
_FHIR_SERVER_URL_HEADER = "x-fhir-server-url"
_FHIR_ACCESS_TOKEN_HEADER = "x-fhir-access-token"


def _fhir_mcp_headers(readonly_context: Any) -> dict[str, str]:
    """Map ADK session state to MCP / SHARP request headers."""
    ro_state = getattr(readonly_context, "state", None)
    st = dict(readonly_context.state) if ro_state is not None else {}
    h: dict[str, str] = {}
    u = (st.get("fhir_url") or "").strip()
    t = (st.get("fhir_token") or "").strip()
    if u:
        h[_FHIR_SERVER_URL_HEADER] = u
    if t:
        h[_FHIR_ACCESS_TOKEN_HEADER] = t
    return h


def patient_context_mcp_toolsets() -> list[McpToolset]:
    """Return a singleton list of :class:`McpToolset` or empty if MCP is disabled."""
    url = (os.environ.get("MCP_SERVER_URL") or "").strip()
    if not url:
        return []

    return [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=url,
                timeout=60.0,
                sse_read_timeout=300.0,
            ),
            tool_filter=["fetch_patient_context"],
            header_provider=_fhir_mcp_headers,
        )
    ]
