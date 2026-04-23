"""Shared contracts between the MCP server and the A2A agent.

Any cross-service type lives here and only here. Never redefine these in
`mcp_server/` or `a2a_agent/` — always import from `shared.models`.
"""

from shared.models import (
    CriteriaResult,
    Decision,
    PALetter,
    PatientContext,
)

__all__ = [
    "CriteriaResult",
    "Decision",
    "PALetter",
    "PatientContext",
]
