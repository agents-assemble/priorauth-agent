"""priorauth_agent — A2A application entry point.

Run locally:
    uv run uvicorn a2a_agent.app:a2a_app --host 0.0.0.0 --port 8001
Or via Makefile:
    make agent

Agent card (public, no auth):
    GET http://localhost:8001/.well-known/agent-card.json

All other endpoints require the X-API-Key header (set via AGENT_API_KEY in
your local .env). Prompt Opinion uses this key when calling us after registration.

For the Week-1 Platform Spike we advertised the FHIR scopes so PO could
exercise the FHIR-metadata flow end-to-end. When ``MCP_SERVER_URL`` is set, the
``patient_context`` sub-agent calls ``fetch_patient_context`` and
``criteria_evaluator`` calls ``match_payer_criteria`` (see
``a2a_agent/mcp_patient_context.py``). ``pa_letter`` binds ``generate_pa_letter``
when the MCP server exposes that tool (same ``MCP_SERVER_URL`` gate).
This lets us validate the full round-trip
(PO chat -> our agent card -> X-API-Key call -> FHIR-metadata extraction ->
Gemini -> response) as we wire the remaining tools and orchestrator
handoffs.
"""

from __future__ import annotations

import os

from a2a.types import AgentSkill
from shared.fhir_scopes import FHIR_SCOPES

from a2a_agent.agent import root_agent
from a2a_agent.po_base.app_factory import create_a2a_app

# Note: .env is loaded in a2a_agent/__init__.py — runs before this module's
# imports so po_base/middleware.py can read AGENT_API_KEY at its own import time.

_PO_BASE = os.environ.get("PO_PLATFORM_BASE_URL", "http://localhost:5139")
_AGENT_URL = os.environ.get(
    "AGENT_PUBLIC_URL",
    os.environ.get("BASE_URL", "http://localhost:8001"),
)

a2a_app = create_a2a_app(
    agent=root_agent,
    name="priorauth_agent",
    description=(
        "Prior authorization agent for lumbar MRI (CPT 72148). "
        "Evaluates payer criteria against a patient's FHIR context and generates "
        "a ready-to-submit PA letter (or a needs-info checklist)."
    ),
    url=_AGENT_URL,
    port=8001,
    fhir_extension_uri=f"{_PO_BASE}/schemas/a2a/v1/fhir-context",
    # Imported from shared/ — same tuple is advertised by the MCP server's
    # capability extension. PO workspace filters to the intersection of the
    # two lists, so keeping them in sync via import is load-bearing.
    fhir_scopes=list(FHIR_SCOPES),
    skills=[
        AgentSkill(
            id="prior-auth-lumbar-mri",
            name="prior-auth-lumbar-mri",
            description=(
                "End-to-end prior authorization for outpatient lumbar MRI "
                "(CPT 72148). Pulls patient context from FHIR, evaluates "
                "payer criteria, and returns either an approved PA letter "
                "or a needs-info checklist."
            ),
            tags=["prior-auth", "mri", "lumbar", "fhir", "cpt-72148"],
        ),
    ],
)
