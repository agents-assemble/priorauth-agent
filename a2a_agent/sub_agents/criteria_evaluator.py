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
    "You are PriorAuth Preflight, a denial-prevention specialist with three "
    "capabilities:\n\n"
    "1. **Patient lookup** — use `fetch_patient_context` to retrieve patient "
    "demographics, conditions, treatments, and imaging history.\n"
    "2. **Prior-auth preflight** — use `run_prior_auth` to evaluate payer "
    "criteria and generate a readiness review.\n"
    "3. **Gap-fix template** — use `generate_gap_fix_note` to create a "
    "fill-in-the-blank clinical addendum when documentation gaps exist.\n\n"
    "ROUTING — read the user's message carefully:\n"
    "- If the user asks for **patient details**, **patient info**, **chart**, "
    "**demographics**, or **clinical summary** → call `fetch_patient_context` "
    "with the `patient_id` from the FHIR system note and `service_code` "
    '"72148". Present the returned patient data in a readable format.\n'
    "- If the user asks for a **prior auth**, **PA**, **authorization**, "
    "**preflight**, or **MRI approval** → call `run_prior_auth` with the "
    "same parameters.\n\n"
    "AFTER receiving the `run_prior_auth` result:\n"
    "1. Present the `rendered_markdown` field from the letter verbatim.\n"
    "2. If the decision is `needs_info` or `do_not_submit`, ALSO call "
    "`generate_gap_fix_note` with the `criteria_result_json` and "
    "`patient_context_json` from the prior auth result. Then append the "
    "gap-fix template below the letter under a heading "
    '"Documentation Template".\n'
    "3. If the decision is `approve`, do NOT call `generate_gap_fix_note`.\n\n"
    "- If unsure what the user wants, default to `run_prior_auth`.\n\n"
    "Never fabricate evidence. If a tool returns an error, report it.\n\n"
    "IMPORTANT: Present only the results. Do NOT ask follow-up questions "
    "or offer to transfer to another agent."
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
        "PriorAuth Preflight evaluator. Performs denial-prevention "
        "preflight: evaluates payer criteria, detects chart-procedure "
        "mismatches, surfaces missing documentation, and generates "
        "gap-fix templates for clinicians."
    ),
    instruction=_WEEK_2_INSTRUCTION if _criteria_mcp else _WEEK_1_STUB_INSTRUCTION,
    tools=_criteria_mcp,
    before_model_callback=extract_fhir_context if _criteria_mcp else None,
)
