"""FastMCP instance + tool registration.

Mirrors prompt-opinion/po-community-mcp/python/mcp_instance.py — same
FastMCP construction, same `ai.promptopinion/fhir-context` capability
extension monkeypatch (so PO's agent registration UI knows our server wants
the SHARP FHIR context propagated on every call).

Scope list is imported from `shared.fhir_scopes.FHIR_SCOPES` — the same
tuple is advertised by the A2A agent card (`a2a_agent/app.py`). PO's
workspace filters to the intersection of the two declarations, so drift
would silently drop resources from every tool call.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from shared.fhir_scopes import FHIR_SCOPES

from mcp_server.tools.fetch_patient_context import fetch_patient_context
from mcp_server.tools.match_payer_criteria import match_payer_criteria


def _patch_capabilities(mcp: FastMCP) -> None:
    """Advertise the PO fhir-context extension via MCP server capabilities.

    FastMCP 1.9 does not expose a native extensions hook, so we wrap
    `get_capabilities` to inject the custom `ai.promptopinion/fhir-context`
    key. Upstream does the same — revisit on the next mcp bump if the
    framework grows a first-class API (https://github.com/modelcontextprotocol/python-sdk).
    """
    original = mcp._mcp_server.get_capabilities

    def patched(notification_options: Any, experimental_capabilities: Any) -> Any:
        caps = original(notification_options, experimental_capabilities)
        # Pydantic's model_extra is None unless the model was constructed with
        # extras; initialize __pydantic_extra__ directly (model_extra is a
        # property that reads it) so we can safely index into it.
        if caps.model_extra is None:
            caps.__pydantic_extra__ = {}
        assert caps.model_extra is not None  # narrowing for mypy
        caps.model_extra["extensions"] = {
            "ai.promptopinion/fhir-context": {"scopes": list(FHIR_SCOPES)},
        }
        return caps

    mcp._mcp_server.get_capabilities = patched  # type: ignore[method-assign]


mcp: FastMCP = FastMCP("priorauth_mcp", stateless_http=True, host="0.0.0.0")
_patch_capabilities(mcp)


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------

mcp.tool(
    name="fetch_patient_context",
    description=(
        "Build a normalized PatientContext (demographics + active conditions + "
        "conservative-therapy trials + prior imaging + red-flag candidates + "
        "service request + coverage) for a given patient + CPT code, pulling "
        "from the PO workspace FHIR server via the propagated SHARP token."
    ),
)(fetch_patient_context)


mcp.tool(
    name="match_payer_criteria",
    description=(
        "Evaluate a PatientContext against a payer's medical-necessity criteria "
        "for the requested CPT code. Returns a CriteriaResult with decision "
        "(approve / needs_info / deny), met and missing criteria with evidence, "
        "and a reasoning trace. Red-flag cases are fast-tracked deterministically; "
        "all other cases use a Gemini reasoning pass over the clinical context."
    ),
)(match_payer_criteria)


# generate_pa_letter    — registered in Week 2
