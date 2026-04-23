"""SHARP-on-MCP header names.

Adapted verbatim from prompt-opinion/po-community-mcp/python/mcp_constants.py
(commit e19ec91). These header names are part of the PO platform contract —
the PO general agent sets them on every MCP request when our server is
registered with "pass token" enabled. Changing them here silently breaks the
round-trip, so they are isolated in one module and imported everywhere.

Spec reference: https://www.sharponmcp.com/ (v0.x draft as of 2026-04).
"""

from __future__ import annotations

FHIR_SERVER_URL_HEADER = "x-fhir-server-url"
FHIR_ACCESS_TOKEN_HEADER = "x-fhir-access-token"
PATIENT_ID_HEADER = "x-patient-id"
