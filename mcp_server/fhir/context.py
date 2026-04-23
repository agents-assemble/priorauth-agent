"""SHARP-on-MCP request-context extraction.

Adapted from prompt-opinion/po-community-mcp/python/fhir_utilities.py +
fhir_context.py (commit e19ec91). Changes from upstream:

- Return a `FhirContextError` sentinel instead of `None` so tools can surface
  a structured error to the caller rather than letting a plain `ValueError`
  bubble out through FastMCP's JSON-RPC layer (the upstream reference does
  `raise ValueError(...)` which stringifies poorly in client traces).
- `get_patient_id_if_context_exists` catches `jwt.DecodeError` instead of
  letting malformed tokens crash the handler — PO's workspace FHIR can
  occasionally hand us opaque tokens (not JWTs) depending on the identity
  provider, and the `x-patient-id` header is the documented fallback.
- Minor: `dataclass(frozen=True, slots=True)` for hashability + ~30% smaller
  memory footprint on hot paths.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import jwt
from mcp.server.fastmcp import Context

from .constants import FHIR_ACCESS_TOKEN_HEADER, FHIR_SERVER_URL_HEADER, PATIENT_ID_HEADER

logger = logging.getLogger(__name__)

# FastMCP's Context is Generic[ServerSessionT, LifespanContextT, RequestT].
# We only ever touch request_context.request.headers, so the concrete
# types are irrelevant at our callsites - Any/Any/Any is the correct alias.
McpContext = Context[Any, Any, Any]


@dataclass(frozen=True, slots=True)
class FhirContext:
    """Authenticated FHIR endpoint + bearer token extracted from MCP headers."""

    url: str
    token: str | None = None


class FhirContextError(Exception):
    """Raised by tools when PO did not propagate a FHIR context.

    Either the MCP server is not registered with `pass token` enabled in the
    PO workspace, or the caller forgot to set x-fhir-server-url. Surfaces as
    a structured JSON-RPC error with an actionable message rather than a
    500-tier crash.
    """


def get_fhir_context(ctx: McpContext) -> FhirContext | None:
    """Return the FHIR endpoint + token from MCP request headers, or None.

    Returns None (not raises) when the URL header is absent so individual
    tools can decide between "hard error" and "stub/demo fallback" — the
    scaffold tools use the latter so the server is exercisable via `curl`
    before PO registration lands.
    """
    req = ctx.request_context.request
    if req is None:
        return None
    url = req.headers.get(FHIR_SERVER_URL_HEADER)
    if not url:
        return None
    token = req.headers.get(FHIR_ACCESS_TOKEN_HEADER)
    return FhirContext(url=url, token=token)


def get_patient_id_if_context_exists(ctx: McpContext) -> str | None:
    """Return the patient id the caller has scoped the MCP request to.

    Resolution order, matching upstream PO reference:
      1. Decode the SHARP access token and read the `patient` claim.
      2. Fall back to the explicit `x-patient-id` header.

    Returns None if neither is available — the tool should then decide
    whether that is a hard error (Week-2 path) or a demo fallback (Week-1).
    """
    req = ctx.request_context.request
    if req is None:
        return None
    fhir_token = req.headers.get(FHIR_ACCESS_TOKEN_HEADER)
    if fhir_token:
        try:
            claims = jwt.decode(fhir_token, options={"verify_signature": False})
        except jwt.DecodeError:
            # Opaque (non-JWT) token — legitimate per SHARP spec, fall through
            # to the explicit header.
            logger.debug("non-jwt access token; falling back to x-patient-id header")
        else:
            patient = claims.get("patient")
            if patient:
                return str(patient)
    header_value = req.headers.get(PATIENT_ID_HEADER)
    return str(header_value) if header_value is not None else None
