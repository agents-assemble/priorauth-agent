"""PA Letter sub-agent — prior-authorization letter writer.

Week-1 scope: pass-through stub. The Agent instance is fully configured
(name, description, instruction per PLAN.md:235, model sourced from the same
env var as the root agent) but carries ``tools=[]`` — the MCP binding to
``generate_pa_letter`` lands after Person-A's Week-2 letter-generator PR.

See ``a2a_agent/sub_agents/__init__.py`` for the re-export surface consumed
by ``a2a_agent.agent.root_agent.sub_agents``.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from a2a_agent._model import _DEFAULT_MODEL

pa_letter_agent = Agent(
    name="pa_letter",
    model=os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL),
    description=(
        "Prior-authorization letter writer. Produces a ready-to-submit PA "
        "letter when criteria are met, or a needs-info checklist when "
        "evidence is missing, or a red-flag fast-track letter when a red "
        "flag bypasses standard criteria."
    ),
    instruction=(
        "Prior-authorization writer. Given context and criteria result, "
        "produce the ready-to-submit PA letter (or needs-info checklist). "
        "Cite every claim against the context — no unsupported assertions."
    ),
    tools=[],
)
