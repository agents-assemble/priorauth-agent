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

When ``MCP_SERVER_URL`` is set, ``patient_context`` and
``criteria_evaluator`` have MCP toolsets; the root instruction below
allows handoffs to those two. ``pa_letter`` is still unbound until
``generate_pa_letter`` is wired.

``criteria_evaluator`` can ``fetch_patient_context`` and
``match_payer_criteria`` in sequence so a full criteria decision
works on Prompt Opinion without fragile JSON shuffles between
sub-agents. Remaining work: ``generate_pa_letter`` and production
``a2a_agent/prompts/`` tuning.
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

# Week-1: no MCP — root must not delegate to sub-agents (they are stubs).
# With MCP: patient_context + criteria_evaluator are live; pa_letter waits.
_mcp_patient = bool(patient_context_agent.tools)
_mcp_criteria = bool(criteria_evaluator_agent.tools)
_ROOT_WEEK1_OR_MCP_OFF = (
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
)

_ROOT_MCP_ON = (
    "You are a prior-authorization specialist for outpatient lumbar MRI "
    "(CPT 72148). The sub-agents `patient_context` and `criteria_evaluator` "
    "are wired to the MCP server. You MAY transfer to them in order: first "
    "`patient_context` to fetch normalized patient context, then "
    "`criteria_evaluator` to evaluate payer criteria (or transfer directly "
    "to `criteria_evaluator` if only a criteria decision is needed; it can "
    "call fetch then match on its own). The `pa_letter` sub-agent has no MCP "
    "tool yet — do NOT transfer to `pa_letter` until that tool is wired; "
    "acknowledge a letter request with a one-line deferral. "
    "In every turn: (1) confirm FHIR using the system note: look for a line "
    f"beginning with `{FHIR_CONTEXT_NOTE_PREFIX}` and confirm `patient_id` "
    "if present. (2) Summarize the user's request. (3) Delegate or report "
    "per above. "
    "NEVER echo the fhir_token or fhir_url. NEVER invent clinical details "
    "or a PA body from this root agent; letters stay the future `pa_letter` "
    "responsibility."
)

_root_instruction = _ROOT_MCP_ON if _mcp_patient and _mcp_criteria else _ROOT_WEEK1_OR_MCP_OFF

root_agent = Agent(
    name="priorauth_agent",
    model=os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL),
    description=(
        "Prior authorization agent for lumbar MRI (CPT 72148). "
        "Evaluates payer criteria, identifies missing documentation, "
        "and generates ready-to-submit PA letters from FHIR patient data."
    ),
    instruction=_root_instruction,
    tools=[],
    sub_agents=[
        patient_context_agent,
        criteria_evaluator_agent,
        pa_letter_agent,
    ],
    before_model_callback=extract_fhir_context,
)
