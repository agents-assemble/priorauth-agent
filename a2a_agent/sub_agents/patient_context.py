"""Patient Context sub-agent — clinical-data retrieval specialist.

Week-1 scope: pass-through stub. The Agent instance is fully configured
(name, description, instruction per PLAN.md:233, model sourced from the same
env var as the root agent) but carries ``tools=[]`` — the MCP binding to
``fetch_patient_context`` lands in a follow-up PR once ``match_payer_criteria``
+ ``generate_pa_letter`` have stable ``shared/models.py`` contracts to
point at. Keeping this agent importable and trace-visible today means the
Week-2 diff is a ``tools=[...]`` swap, not a new-file PR.

See ``a2a_agent/sub_agents/__init__.py`` for the re-export surface consumed
by ``a2a_agent.agent.root_agent.sub_agents``.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from a2a_agent._model import _DEFAULT_MODEL

patient_context_agent = Agent(
    name="patient_context",
    model=os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL),
    description=(
        "Clinical data retrieval specialist for prior-authorization review. "
        "Fetches and normalizes patient context (diagnoses, conservative "
        "therapy trials, imaging history, red flags) from FHIR for a given "
        "patient and requested service."
    ),
    instruction=(
        "Clinical data retrieval specialist. Given a patient and requested "
        "service, fetch and return the normalized context exactly as your "
        "tool produces. No interpretation."
    ),
    tools=[],
)
