"""Criteria Evaluator sub-agent — prior-authorization criteria evaluator.

Without ``MCP_SERVER_URL`` this sub-agent is a pass-through stub
(``tools=[]`` + Week-1 stub instruction). The production line (PLAN.md:234) is
in ``_WEEK_2_INSTRUCTION``; with MCP, ``criteria_evaluator_mcp_toolsets()`` binds
``evaluate_prior_auth``. Same anti-confabulation pattern as
``patient_context`` (see its docstring, PR #9 / PR #13).

Week-2 binding (MCP when ``MCP_SERVER_URL`` is set — see
``a2a_agent.mcp_patient_context.criteria_evaluator_mcp_toolsets``):

    instruction=_WEEK_2_INSTRUCTION
    tools=criteria_evaluator_mcp_toolsets()  # combined fetch + match; see module doc

See ``a2a_agent/sub_agents/__init__.py`` for the re-export surface consumed
by ``a2a_agent.agent.root_agent.sub_agents``.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from a2a_agent._model import _DEFAULT_MODEL
from a2a_agent.mcp_patient_context import criteria_evaluator_mcp_toolsets
from a2a_agent.po_base.fhir_hook import extract_fhir_context

_WEEK_2_INSTRUCTION = (
    "Prior-authorization evaluator and letter writer. You MUST use your MCP "
    "tool and never answer from memory. Call `run_prior_auth` with `patient_id` "
    "from the FHIR system note (or the user message if explicitly provided) "
    'and `service_code` "72148" unless the user specified a different CPT.\n\n'
    "Present the result in this order:\n"
    "1. Decision (approve / needs_info / deny) and confidence\n"
    "2. Criteria met and criteria missing with evidence\n"
    "3. Reasoning trace\n"
    "4. If a letter was generated, present its subject line and the rendered "
    "markdown body verbatim\n"
    "5. If decision is needs_info, present the needs-info checklist\n\n"
    "Never fabricate evidence. If the tool returns an error, report the error "
    "rather than guessing.\n\n"
    "IMPORTANT: Present only the results. Do NOT ask the user follow-up "
    "questions or offer to transfer to another agent. Just present the "
    "findings and stop."
)

_WEEK_1_STUB_INSTRUCTION = (
    "Week-1 scaffold — no tools are wired yet. If control transfers to "
    "you, respond with a single sentence ('criteria_evaluator sub-agent "
    "received handoff; MCP tools bind in Week-2 PR') and return control "
    "to the root agent. Do NOT attempt to evaluate criteria or fabricate "
    "a decision, met/missing criteria, or red flags. The production "
    "instruction (PLAN.md line 234) activates in the Week-2 tool-binding "
    "PR."
)

_criteria_mcp = criteria_evaluator_mcp_toolsets()
criteria_evaluator_agent = Agent(
    name="criteria_evaluator",
    model=os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL),
    description=(
        "Prior-authorization criteria evaluator. Decides whether the "
        "patient's documented context meets the payer's published medical-"
        "necessity criteria for the requested service, and surfaces any "
        "met/missing criteria and red-flag bypasses."
    ),
    instruction=_WEEK_2_INSTRUCTION if _criteria_mcp else _WEEK_1_STUB_INSTRUCTION,
    tools=_criteria_mcp,
    before_model_callback=extract_fhir_context if _criteria_mcp else None,
)
