"""Sub-agent package for the prior-authorization root agent.

Exports the three ADK ``Agent`` instances that ``a2a_agent.agent.root_agent``
registers as ``sub_agents``. Each instance lives in its own module so Week-2
can land real MCP tool bindings, per-role prompt tuning, and handoff-logic
tweaks as per-file diffs instead of an ``agent.py`` churn-fest.

Week-1 invariants (pinned by ``tests/a2a_agent/test_sub_agents.py``):
- Exactly three sub-agents: ``patient_context``, ``criteria_evaluator``,
  ``pa_letter``.
- Each carries ``tools=[]`` — if a future PR accidentally wires an MCP tool
  onto a sub-agent before its own dedicated PR lands, the guardrail test
  fails loudly.
- Each shares the root agent's ``_DEFAULT_MODEL`` (single source of truth)
  and the same ``GEMINI_MODEL`` env override, so a capability-check escalation
  (bigger Gemini tier) flips all four agents in one env-var change.
"""

from __future__ import annotations

from a2a_agent.sub_agents.criteria_evaluator import criteria_evaluator_agent
from a2a_agent.sub_agents.pa_letter import pa_letter_agent
from a2a_agent.sub_agents.patient_context import patient_context_agent

__all__ = [
    "criteria_evaluator_agent",
    "pa_letter_agent",
    "patient_context_agent",
]
