"""priorauth_agent — ADK agent definition.

Week 1 Platform Spike scope: single root agent, no MCP tools, no sub-agents.
Goal is to prove the PO registration + A2A round-trip works end-to-end with
a trivial Gemini-backed agent before we wire MCP tools or the 3 sub-agents.

The `before_model_callback=extract_fhir_context` hook is already attached so
FHIR creds sent by PO in A2A metadata land in session state. The spike agent
just acknowledges receipt — it does NOT query FHIR yet. Real FHIR access
happens via MCP tools once mcp_server/ is up (Person A, Week 1 end).

Follow-up PRs will add:
- 3 ADK sub-agents (patient_context, criteria_evaluator, pa_letter) with
  handoffs routed through this root agent
- MCP tool bindings via MCP_SERVER_URL so sub-agents call Kevin's tools
- A production system prompt in a2a_agent/prompts/root_v1.md
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from a2a_agent.po_base.fhir_hook import extract_fhir_context

# Model is read from env per AGENTS.md ("never hardcode the model name").
# Default: gemini-3.1-flash-lite-preview (PO Connectathon recommendation, preview tier).
# Fallback: gemini-2.5-flash-lite if preview access is revoked or rate-limited.
_DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"

root_agent = Agent(
    name="priorauth_agent",
    model=os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL),
    description=(
        "Prior authorization agent for lumbar MRI (CPT 72148). "
        "Evaluates payer criteria, identifies missing documentation, "
        "and generates ready-to-submit PA letters from FHIR patient data."
    ),
    instruction=(
        "You are a prior-authorization specialist for outpatient lumbar MRI "
        "(CPT 72148). You will eventually orchestrate three sub-agents to "
        "(1) fetch the patient's clinical context from FHIR, (2) match it "
        "against the payer's published criteria, and (3) generate a signed "
        "PA letter or a needs-info checklist.\n\n"
        "For this Week-1 Platform Spike you have NO tools wired yet. "
        "When a clinician asks about a case, respond with:\n"
        "  1. A one-line acknowledgement of the patient/case.\n"
        "  2. Whether FHIR context was received (check session state keys "
        "     `patient_id`, `fhir_url`, `fhir_token`).\n"
        "  3. The next planned step ('will call MCP tool fetch_patient_context "
        "     once available').\n"
        "Do NOT invent clinical findings. Do NOT generate a PA letter yet."
    ),
    tools=[],
    before_model_callback=extract_fhir_context,
)
