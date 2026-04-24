"""Criteria Evaluator sub-agent — prior-authorization criteria evaluator.

Week-1 scope: pass-through stub. The Agent instance is fully configured
(name, description, instruction per PLAN.md:234, model sourced from the same
env var as the root agent) but carries ``tools=[]`` — the MCP binding to
``match_payer_criteria`` lands after Person-A's Week-2 rule-engine PR.

See ``a2a_agent/sub_agents/__init__.py`` for the re-export surface consumed
by ``a2a_agent.agent.root_agent.sub_agents``.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from a2a_agent._model import _DEFAULT_MODEL

criteria_evaluator_agent = Agent(
    name="criteria_evaluator",
    model=os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL),
    description=(
        "Prior-authorization criteria evaluator. Decides whether the "
        "patient's documented context meets the payer's published medical-"
        "necessity criteria for the requested service, and surfaces any "
        "met/missing criteria and red-flag bypasses."
    ),
    instruction=(
        "Prior-authorization criteria evaluator. Given patient context and "
        "payer, invoke your tool and return the decision, met criteria, "
        "missing criteria, and red flags. Never fabricate evidence."
    ),
    tools=[],
)
