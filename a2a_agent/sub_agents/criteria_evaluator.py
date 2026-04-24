"""Criteria Evaluator sub-agent — prior-authorization criteria evaluator.

Week-1 scope: pass-through stub. The production instruction (PLAN.md:234)
is preserved verbatim in ``_WEEK_2_INSTRUCTION`` below. The active
instruction is a Week-1 stub that explicitly forbids fabrication — same
defense-in-depth rationale as ``patient_context`` (see that module's
docstring for the full reasoning, anchored in the PR #9 confabulation
bug and PR #13 review).

Week-2 swap is two lines:

    instruction=_WEEK_2_INSTRUCTION
    tools=[match_payer_criteria]

See ``a2a_agent/sub_agents/__init__.py`` for the re-export surface consumed
by ``a2a_agent.agent.root_agent.sub_agents``.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from a2a_agent._model import _DEFAULT_MODEL

_WEEK_2_INSTRUCTION = (
    "Prior-authorization criteria evaluator. Given patient context and "
    "payer, invoke your tool and return the decision, met criteria, "
    "missing criteria, and red flags. Never fabricate evidence."
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

criteria_evaluator_agent = Agent(
    name="criteria_evaluator",
    model=os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL),
    description=(
        "Prior-authorization criteria evaluator. Decides whether the "
        "patient's documented context meets the payer's published medical-"
        "necessity criteria for the requested service, and surfaces any "
        "met/missing criteria and red-flag bypasses."
    ),
    instruction=_WEEK_1_STUB_INSTRUCTION,
    tools=[],
)
