"""PA Letter sub-agent — prior-authorization letter writer.

Without ``MCP_SERVER_URL`` this sub-agent is a pass-through stub
(``tools=[]`` + Week-1 stub instruction). The production line (PLAN.md:235)
is in ``_WEEK_2_INSTRUCTION``; with MCP, ``pa_letter_mcp_toolsets()`` binds
``generate_pa_letter``. Same anti-confabulation pattern as
``patient_context`` / ``criteria_evaluator`` (see those modules' docstrings).

Week-2 binding (MCP when ``MCP_SERVER_URL`` is set — see
``a2a_agent.mcp_patient_context.pa_letter_mcp_toolsets``):

    instruction=_WEEK_2_INSTRUCTION
    tools=pa_letter_mcp_toolsets()

See ``a2a_agent/sub_agents/__init__.py`` for the re-export surface consumed
by ``a2a_agent.agent.root_agent.sub_agents``.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from a2a_agent._model import _DEFAULT_MODEL
from a2a_agent.mcp_patient_context import pa_letter_mcp_toolsets
from a2a_agent.po_base.fhir_hook import extract_fhir_context

_WEEK_2_INSTRUCTION = (
    "You are a prior-authorization letter writer. You MUST use your tools — "
    "never draft a letter, checklist, or denial from memory.\n\n"
    "Step 1: Get the `patient_id` from the FHIR system note in your input "
    "(look for `[SYSTEM NOTE — FHIR context received`). If no system note, "
    "use any patient ID the user or orchestrator provided.\n\n"
    "Step 2: Call `fetch_patient_context` with the patient_id and "
    'service_code "72148" (or whatever CPT the user specified). Save the '
    "full JSON result — this is your **PatientContext**.\n\n"
    "Step 3: Call `match_payer_criteria` with:\n"
    "  - `patient_context_json`: the PatientContext JSON from Step 2\n"
    '  - `service_code`: "72148"\n'
    "Save the full JSON result — this is your **CriteriaResult**.\n\n"
    "Step 4: Call `generate_pa_letter` with:\n"
    "  - `patient_context_json`: the PatientContext JSON from Step 2\n"
    "  - `criteria_result_json`: the CriteriaResult JSON from Step 3\n"
    "  - `clinician_note` (optional): only non-clinical tone or logistics\n\n"
    "Step 5: Present the returned PALetter to the user (subject line, "
    "rendered body, checklist if needs_info, urgent banner if applicable).\n\n"
    "Rules:\n"
    "- ALWAYS call all three tools in sequence. Never skip any step.\n"
    "- Never fabricate clinical data or letter content.\n"
    "- If any tool returns an error, report the error — do not guess.\n"
    "- Never echo raw FHIR tokens or URLs."
)

_WEEK_1_STUB_INSTRUCTION = (
    "Week-1 scaffold — no tools are wired yet. If control transfers to "
    "you, respond with a single sentence ('pa_letter sub-agent received "
    "handoff; MCP tools bind in Week-2 PR') and return control to the "
    "root agent. Do NOT draft a prior-authorization letter, needs-info "
    "checklist, or any other clinical narrative under any circumstances "
    "until the Week-2 tool-binding PR activates the production "
    "instruction (PLAN.md line 235)."
)

_pa_mcp = pa_letter_mcp_toolsets()
pa_letter_agent = Agent(
    name="pa_letter",
    model=os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL),
    description=(
        "Prior-authorization letter writer. Produces a ready-to-submit PA "
        "letter when criteria are met, or a needs-info checklist when "
        "evidence is missing, or a red-flag fast-track letter when a red "
        "flag bypasses standard criteria."
    ),
    instruction=_WEEK_2_INSTRUCTION if _pa_mcp else _WEEK_1_STUB_INSTRUCTION,
    tools=_pa_mcp,
    before_model_callback=extract_fhir_context if _pa_mcp else None,
)
