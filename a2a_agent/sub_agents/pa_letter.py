"""PA Letter sub-agent — prior-authorization letter writer.

Week-1 scope: pass-through stub. The production instruction (PLAN.md:235)
is preserved verbatim in ``_WEEK_2_INSTRUCTION`` below. The active
instruction is a Week-1 stub that explicitly forbids fabrication — same
defense-in-depth rationale as ``patient_context`` (see that module's
docstring for the full reasoning, anchored in the PR #9 confabulation
bug and PR #13 review). A letter-writing sub-agent fabricating under
missing-tool conditions is the worst-case variant of that class of bug:
an unsupported-by-chart PA letter is exactly the output the system must
never produce.

Week-2 swap is two lines:

    instruction=_WEEK_2_INSTRUCTION
    tools=[generate_pa_letter]

See ``a2a_agent/sub_agents/__init__.py`` for the re-export surface consumed
by ``a2a_agent.agent.root_agent.sub_agents``.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from a2a_agent._model import _DEFAULT_MODEL

_WEEK_2_INSTRUCTION = (
    "Prior-authorization writer. Given context and criteria result, "
    "produce the ready-to-submit PA letter (or needs-info checklist). "
    "Cite every claim against the context — no unsupported assertions."
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

pa_letter_agent = Agent(
    name="pa_letter",
    model=os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL),
    description=(
        "Prior-authorization letter writer. Produces a ready-to-submit PA "
        "letter when criteria are met, or a needs-info checklist when "
        "evidence is missing, or a red-flag fast-track letter when a red "
        "flag bypasses standard criteria."
    ),
    instruction=_WEEK_1_STUB_INSTRUCTION,
    tools=[],
)
