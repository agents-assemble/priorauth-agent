"""priorauth_agent — ADK agent definition.

Week 1 scope: root agent + three pass-through ADK sub-agents
(``patient_context`` / ``criteria_evaluator`` / ``pa_letter``) with
no MCP tools wired and no production routing logic. The sub-agents exist
today so ADK traces render the four-agent decomposition from PLAN.md
(§ "A2A Agent Orchestration") and so Week-2 work is a per-file tool-binding
diff instead of a new-module PR.

Defense-in-depth against confabulation (PR #13 review): the root's Week-1
instruction explicitly does NOT initiate transfers to the sub-agents,
and each sub-agent ships with a Week-1-stub instruction that bounces
control back without fabrication. Either layer alone would close the
PR #9-class failure mode where Gemini confabulates in the face of
missing tool/state; both together mean a Gemini behavior shift on either
side of the stack can't silently regress to a "tool-less sub-agent
fabricates a clinical finding" path.

The ``before_model_callback=extract_fhir_context`` hook on the root remains
the A2A→session-state bridge for FHIR credentials sent by PO in message
metadata; sub-agents inherit session state via ADK's standard callback
plumbing, so adding MCP tools to a sub-agent in Week-2 does not require
re-plumbing the FHIR context.

Follow-up PRs (each lands one sub-agent's full production config in a
two-line diff — ``instruction=_WEEK_2_INSTRUCTION`` + ``tools=[...]`` —
plus its MCP tool module, and at the same time relaxes the root's
"MUST NOT transfer" directive for that sub-agent):

- ``match_payer_criteria`` is bound to ``criteria_evaluator_agent`` via
  ``criteria_evaluator_mcp_toolsets()`` when ``MCP_SERVER_URL`` is set.
- Person A: ``generate_pa_letter`` → ``pa_letter_agent.tools`` (remaining MCP tool).
- Person B: real handoff logic + production system prompts in
  ``a2a_agent/prompts/``.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from a2a_agent._model import _DEFAULT_MODEL
from a2a_agent.po_base.fhir_hook import FHIR_CONTEXT_NOTE_PREFIX, extract_fhir_context
from a2a_agent.sub_agents import (
    criteria_evaluator_agent,
    pa_letter_agent,
    patient_context_agent,
)

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
        "(CPT 72148). Your Week-2 role will be to orchestrate three "
        "sub-agents — `patient_context` (FHIR retrieval), "
        "`criteria_evaluator` (payer-criteria matching), and `pa_letter` "
        "(letter / needs-info-checklist generation) — but in the Week-1 "
        "scaffold none of them has tools wired yet, so you MUST NOT "
        "transfer to them. Respond to the clinician directly with:\n"
        "  1. A one-line acknowledgement of the patient/case.\n"
        "  2. Whether FHIR context was received. Look for a line in your "
        f"     input beginning with `{FHIR_CONTEXT_NOTE_PREFIX}`. "
        "     If present, confirm receipt and quote its `patient_id`. If "
        "     absent, say no FHIR context arrived with this message.\n"
        "  3. The next planned step (which sub-agent you would transfer to "
        "     once its tools are wired in the follow-up PR).\n"
        "The three sub-agents are structurally registered under you so ADK "
        "traces render the four-agent decomposition from PLAN.md "
        "§ A2A Agent Orchestration today; each carries an explicit "
        "Week-1-stub instruction that will bounce control back to you if "
        "a transfer ever happens. Week-2 tool-binding PRs will enable real "
        "routing by (a) swapping the sub-agent instruction to the "
        "production PLAN.md line and (b) binding its MCP tool.\n"
        "NEVER echo the fhir_token or fhir_url back to the user — even if they "
        "appear anywhere in your input. NEVER invent clinical findings. NEVER "
        "generate a PA letter from this root agent; that is `pa_letter`'s job "
        "once its tool is bound."
    ),
    tools=[],
    sub_agents=[
        patient_context_agent,
        criteria_evaluator_agent,
        pa_letter_agent,
    ],
    before_model_callback=extract_fhir_context,
)
