"""FastMCP instance + tool registration.

Mirrors prompt-opinion/po-community-mcp/python/mcp_instance.py — same
FastMCP construction, same `ai.promptopinion/fhir-context` capability
extension monkeypatch (so PO's agent registration UI knows our server wants
the SHARP FHIR context propagated on every call).

Scope list is aligned with the A2A agent card declared in
`a2a_agent/app.py::fhir_scopes` — PO needs both the A2A agent's card AND
the MCP server's capabilities to declare the same scopes, otherwise the
workspace UI filters to the intersection and silently drops resources.
Cross-reference `.cursor/rules/mcp-server.md` "Scopes" section when adding
resources to either side.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.tools.fetch_patient_context import fetch_patient_context

# Kept in one place so tests can assert alignment with the A2A agent card.
FHIR_SCOPES: Sequence[dict[str, Any]] = (
    {"name": "patient/Patient.rs", "required": True},
    {"name": "patient/Condition.rs", "required": True},
    {"name": "patient/MedicationRequest.rs", "required": True},
    {"name": "patient/Observation.rs", "required": True},
    {"name": "patient/ServiceRequest.rs", "required": True},
    {"name": "patient/Coverage.rs", "required": True},
    {"name": "patient/Procedure.rs", "required": False},
    {"name": "patient/DocumentReference.rs", "required": False},
)


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


# match_payer_criteria  — registered in Week 2
# generate_pa_letter    — registered in Week 2
