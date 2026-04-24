"""Patient Context sub-agent — clinical-data retrieval specialist.

Week-1 scope: pass-through stub. The Agent instance is fully configured
(name, description, model sourced from the same env var as the root agent)
but carries ``tools=[]`` and ships with a **Week-1 stub instruction** that
explicitly forbids fabrication. The production instruction (PLAN.md:233)
is preserved verbatim in ``_WEEK_2_INSTRUCTION`` below so the Week-2
tool-binding PR is a two-line swap:

    instruction=_WEEK_2_INSTRUCTION
    tools=[fetch_patient_context]

Defense-in-depth rationale (PR #13 review): shipping the production
instruction with ``tools=[]`` creates a contradictory directive set — the
prompt tells Gemini to "fetch and return the normalized context exactly
as your tool produces" while no tool exists to invoke. If the root agent
ever routes here under such a configuration, Gemini's two reachable
failure modes are (a) confabulate a patient context (same class of bug
as PR #9's "FHIR context not received" confabulation) or (b) idle / loop
on "I cannot invoke my tool". The Week-1 stub closes both paths with an
explicit bounce-back instruction; the root agent's Week-1 instruction
also refrains from initiating transfers at all (belt + suspenders).

See ``a2a_agent/sub_agents/__init__.py`` for the re-export surface consumed
by ``a2a_agent.agent.root_agent.sub_agents``.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from a2a_agent._model import _DEFAULT_MODEL
from a2a_agent.mcp_patient_context import patient_context_mcp_toolsets

_WEEK_2_INSTRUCTION = (
    "Clinical data retrieval specialist. Given a patient and requested "
    "service, fetch and return the normalized context exactly as your "
    "tool produces. No interpretation."
)

_WEEK_1_STUB_INSTRUCTION = (
    "Week-1 scaffold — no tools are wired yet. If control transfers to "
    "you, respond with a single sentence ('patient_context sub-agent "
    "received handoff; MCP tools bind in Week-2 PR') and return control "
    "to the root agent. Do NOT attempt to fetch or fabricate patient "
    "context. The production instruction (PLAN.md line 233) activates "
    "in the Week-2 tool-binding PR."
)

_patient_mcp = patient_context_mcp_toolsets()
patient_context_agent = Agent(
    name="patient_context",
    model=os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL),
    description=(
        "Clinical data retrieval specialist for prior-authorization review. "
        "Fetches and normalizes patient context (diagnoses, conservative "
        "therapy trials, imaging history, red flags) from FHIR for a given "
        "patient and requested service."
    ),
    instruction=_WEEK_2_INSTRUCTION if _patient_mcp else _WEEK_1_STUB_INSTRUCTION,
    tools=_patient_mcp,
)
