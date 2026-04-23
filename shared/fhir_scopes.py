"""Canonical SMART-on-FHIR scope list for the lumbar-MRI PA agent.

Two places need to declare these scopes — the A2A agent card
(`a2a_agent/app.py`) and the MCP server's capability extension
(`mcp_server/server.py`). PO's workspace filters to the intersection of
both lists: a scope missing from either side is silently dropped from
the token, which surfaces much later as "why is Condition empty?" at
tool-call time. Keeping the list in `shared/` prevents that whole class
of drift.

If you need to add a scope:
1. Add it here.
2. Both consumers import from here, so no other edits needed.
3. Bump the agent-card version and re-register in the PO workspace so
   the new scope is actually requested.

Scope naming: we use the `.rs` (read + search) suffix consistently — no
tool in this agent writes to FHIR. If a future tool needs write, add
a separate `.w` scope rather than upgrading an existing one so the
least-privilege boundary is explicit.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

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
"""Tuple so it cannot be mutated at import time by either consumer."""
