"""priorauth_agent — ADK agent definition.

Week 1 scope: root agent + three pass-through ADK sub-agents
(``patient_context`` / ``criteria_evaluator`` / ``pa_letter``) with
no MCP tools wired and no production routing logic. The sub-agents exist
today so ADK traces render the four-agent decomposition from PLAN.md
(§ "A2A Agent Orchestration") and so Week-2 work is a per-file tool-binding
diff instead of a new-module PR.

The ``before_model_callback=extract_fhir_context`` hook on the root remains
the A2A→session-state bridge for FHIR credentials sent by PO in message
metadata; sub-agents inherit session state via ADK's standard callback
plumbing, so adding MCP tools to a sub-agent in Week-2 does not require
re-plumbing the FHIR context.

Follow-up PRs:
- Person A: ``match_payer_criteria`` rule engine → binds to
  ``criteria_evaluator_agent.tools`` (and consumes ``PatientContext``
  produced by ``fetch_patient_context``).
- Person A: ``generate_pa_letter`` → binds to ``pa_letter_agent.tools``.
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
        "(CPT 72148). You orchestrate three sub-agents to (1) fetch the "
        "patient's clinical context from FHIR, (2) match it against the "
        "payer's published criteria, and (3) generate a signed PA letter "
        "or a needs-info checklist.\n\n"
        "Sub-agents available for transfer:\n"
        "  - `patient_context` — clinical-data retrieval from FHIR.\n"
        "  - `criteria_evaluator` — payer-criteria matching.\n"
        "  - `pa_letter` — letter / needs-info-checklist generation.\n"
        "Routing pass-through: when a clinician asks about a case, transfer "
        "to `patient_context` first; the sub-agent will return control once "
        "context is normalized. Then transfer to `criteria_evaluator`, then "
        "to `pa_letter`. None of the three sub-agents has tools wired yet "
        "(Week-1 scaffold); they will acknowledge and return to you until "
        "Week-2 PRs land the MCP bindings. Until then, respond to the "
        "clinician with:\n"
        "  1. A one-line acknowledgement of the patient/case.\n"
        "  2. Whether FHIR context was received. Look for a line in your "
        f"     input beginning with `{FHIR_CONTEXT_NOTE_PREFIX}`. "
        "     If present, confirm receipt and quote its `patient_id`. If "
        "     absent, say no FHIR context arrived with this message.\n"
        "  3. The next planned step (which sub-agent you would transfer to "
        "     once its tools are wired).\n"
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
