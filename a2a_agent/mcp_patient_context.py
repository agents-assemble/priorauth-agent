"""MCP (FastMCP) streamable HTTP toolsets for A2A sub-agents (Week 2+).

When ``MCP_SERVER_URL`` is set (e.g. from ``.env``), :class:`McpToolset` connects
to our ``mcp_server`` streamable HTTP endpoint (``.../mcp``) and exposes the
selected tools to Gemini. ``patient_context`` uses ``fetch_patient_context``;
``criteria_evaluator`` uses ``evaluate_prior_auth``; ``pa_letter`` uses
``generate_pa_letter``.

``extract_fhir_context`` (``fhir_hook``) writes ``fhir_url`` and ``fhir_token``
into session state; :func:`_fhir_mcp_headers` injects the SHARP transport headers
(``x-fhir-server-url``, ``x-fhir-access-token``) for tools that call the PO
workspace FHIR server (e.g. ``fetch_patient_context``). The same header map is
sent for other tools too; the MCP server ignores headers it does not need.

Header names are duplicated from ``mcp_server.fhir.constants.py`` so
``a2a_agent`` does not take a hard dependency on the ``mcp_server`` package.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

logger = logging.getLogger(__name__)

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


def _streamable_http_mcp_url(url: str) -> str:
    """Return the JSON-RPC URL the MCP client must POST to.

    FastMCP registers streamable HTTP at ``/mcp`` by default (see
    ``mcp.server.fastmcp``). Callers often paste only the tunnel or host
    origin (``https://….trycloudflare.com``), which would otherwise 404.
    """
    raw = url.strip()
    if not raw:
        return raw
    base = raw.rstrip("/")
    if base.endswith("/mcp"):
        return base
    normalized = f"{base}/mcp"
    if normalized != raw.rstrip("/"):
        logger.info(
            "MCP_SERVER_URL normalized for streamable HTTP (append /mcp): %r -> %r",
            raw,
            normalized,
        )
    return normalized


def _streamable_mcp_toolsets(tool_filter: list[str]) -> list[McpToolset]:
    """One :class:`McpToolset` for ``tool_filter`` names, or empty if MCP is off."""
    url = (os.environ.get("MCP_SERVER_URL") or "").strip()
    if not url:
        return []
    url = _streamable_http_mcp_url(url)
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
    """Return the full-pipeline tool, patient-context lookup, and gap-fix."""
    return _streamable_mcp_toolsets(
        ["run_prior_auth", "fetch_patient_context", "generate_gap_fix_note"]
    )


def pa_letter_mcp_toolsets() -> list[McpToolset]:
    """Return tools the pa_letter sub-agent needs to be self-contained.

    ``pa_letter`` must gather its own inputs (PatientContext + CriteriaResult)
    because PO's taskId-reuse bug forces us to strip taskId on each turn,
    creating a fresh session with no conversation history from the criteria
    evaluation turn.
    """
    return _streamable_mcp_toolsets(
        [
            "fetch_patient_context",
            "match_payer_criteria",
            "generate_pa_letter",
        ]
    )
