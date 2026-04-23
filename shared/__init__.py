"""Shared contracts between the MCP server and the A2A agent.

Any cross-service type lives here and only here. Never redefine these in
`mcp_server/` or `a2a_agent/` — always import from `shared.models`.
"""

from shared.fhir_scopes import FHIR_SCOPES
from shared.models import (
    CriteriaResult,
    Decision,
    PALetter,
    PatientContext,
)

__all__ = [
    "FHIR_SCOPES",
    "CriteriaResult",
    "Decision",
    "PALetter",
    "PatientContext",
]
