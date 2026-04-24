"""MCP (FastMCP) streamable HTTP toolsets for A2A sub-agents (Week 2+).

When ``MCP_SERVER_URL`` is set (e.g. from ``.env``), :class:`McpToolset` connects
to our ``mcp_server`` streamable HTTP endpoint (``.../mcp``) and exposes the
selected tools to Gemini. ``patient_context`` uses ``fetch_patient_context``;
``criteria_evaluator`` uses ``match_payer_criteria``.

``extract_fhir_context`` (``fhir_hook``) writes ``fhir_url`` and ``fhir_token``
into session state; :func:`_fhir_mcp_headers` injects the SHARP transport headers
(``x-fhir-server-url``, ``x-fhir-access-token``) for tools that call the PO
workspace FHIR server (e.g. ``fetch_patient_context``). The same header map is
sent for other tools too; the MCP server ignores headers it does not need.

Header names are duplicated from ``mcp_server/fhir/constants.py`` so
``a2a_agent`` does not take a hard dependency on the ``mcp_server`` package.
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


def _streamable_mcp_toolsets(tool_filter: list[str]) -> list[McpToolset]:
    """One :class:`McpToolset` for ``tool_filter`` names, or empty if MCP is off."""
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
            tool_filter=tool_filter,
            header_provider=_fhir_mcp_headers,
        )
    ]


def patient_context_mcp_toolsets() -> list[McpToolset]:
    """Return a singleton list of :class:`McpToolset` or empty if MCP is disabled."""
    return _streamable_mcp_toolsets(["fetch_patient_context"])


def criteria_evaluator_mcp_toolsets() -> list[McpToolset]:
    """Return fetch + match tools on the shared MCP server, or empty if off.

    ``fetch_patient_context`` is included alongside ``match_payer_criteria`` so
    the criteria sub-agent can run a self-contained sequence on PO
    (patient_id is in the FHIR system note) without depending on a fragile
    inter-sub-agent copy of a large JSON blob. ``patient_context`` is still
    the dedicated retrieval step in the multi-agent flow when the root
    orchestrates a longer trace.
    """
    return _streamable_mcp_toolsets(["fetch_patient_context", "match_payer_criteria"])
