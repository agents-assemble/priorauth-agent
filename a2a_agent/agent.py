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

import logging
import os
from typing import Any

from google.adk.agents import Agent
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from a2a_agent._model import _DEFAULT_MODEL
from a2a_agent.po_base.fhir_hook import FHIR_CONTEXT_NOTE_PREFIX, extract_fhir_context
from a2a_agent.sub_agents import (
    criteria_evaluator_agent,
    pa_letter_agent,
    patient_context_agent,
)

_logger = logging.getLogger(__name__)

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
    "You are a prior-authorization orchestrator for outpatient lumbar MRI "
    "(CPT 72148). You do NOT answer clinical questions yourself. Your ONLY "
    "job is to delegate to sub-agents by calling `transfer_to_agent`.\n\n"
    "When a prior-authorization request arrives with FHIR context (look for "
    f"a line beginning with `{FHIR_CONTEXT_NOTE_PREFIX}`), you MUST "
    "IMMEDIATELY call `transfer_to_agent` with agent_name "
    "`criteria_evaluator`. Do NOT generate any text before the transfer — "
    "just call the function. The `criteria_evaluator` sub-agent will fetch "
    "patient data and evaluate payer criteria on its own.\n\n"
    "Rules:\n"
    "- NEVER answer the clinical question yourself.\n"
    "- NEVER narrate what you plan to do — just transfer.\n"
    "- NEVER transfer to `pa_letter` (its tool is not wired yet).\n"
    "- NEVER echo fhir_token, fhir_url, or raw JWT text.\n"
    "- NEVER invent clinical findings, criteria decisions, or PA letters.\n"
    "- If no FHIR context is present, say so in one sentence and stop."
)

_root_instruction = _ROOT_MCP_ON if _mcp_patient and _mcp_criteria else _ROOT_WEEK1_OR_MCP_OFF

_MCP_ACTIVE = _mcp_patient and _mcp_criteria


def _deterministic_transfer(callback_context: Any, llm_request: Any) -> LlmResponse | None:
    """Skip the root LLM call entirely when MCP tools are active.

    When FHIR context is present, the root agent's only job is to call
    ``transfer_to_agent(criteria_evaluator)``. That is a fixed routing
    decision — burning a Gemini call for it wastes 1 of the 5-RPM
    free-tier budget. This callback short-circuits the LLM by returning
    a synthetic ``function_call`` response, saving ~20% of the per-
    request quota.

    Falls through to the LLM (returns None) when no FHIR context is
    found so the root can respond with a human-readable error.
    """
    extract_fhir_context(callback_context, llm_request)  # type: ignore[no-untyped-call]

    state = callback_context.state
    patient_id = (state.get("patient_id") or "").strip()

    if not patient_id:
        return None

    _logger.info("DETERMINISTIC_TRANSFER patient_id=%s → criteria_evaluator", patient_id)

    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=types.FunctionCall(
                        name="transfer_to_agent",
                        args={"agent_name": "criteria_evaluator"},
                    )
                )
            ],
        ),
        turn_complete=True,
    )


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
    before_model_callback=_deterministic_transfer if _MCP_ACTIVE else extract_fhir_context,
)
