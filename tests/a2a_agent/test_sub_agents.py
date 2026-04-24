"""Week-1 guardrail tests for ``a2a_agent.sub_agents``.

Scope: pin the three structural invariants Week-2 PRs must not accidentally
violate. Integration tests for the handoff itself (and for real MCP tool
invocations once bound) live in the Week-2 orchestration PR, not here — the
value of these tests is catching "I added my tool list to the wrong agent"
or "I renamed a sub-agent and forgot to update the prompt router" at lint
time rather than at PO smoke-test time.
"""

from __future__ import annotations

from a2a_agent.agent import root_agent
from google.adk.agents import LlmAgent

_EXPECTED_SUB_AGENT_NAMES = {
    "patient_context",
    "criteria_evaluator",
    "pa_letter",
}


def test_root_agent_has_three_sub_agents() -> None:
    """PLAN.md § A2A Agent Orchestration: orchestrator + exactly three subs."""

    assert len(root_agent.sub_agents) == 3, (
        f"expected 3 sub-agents on root_agent, got {len(root_agent.sub_agents)}"
    )


def test_sub_agent_names_match_expected_set() -> None:
    """PLAN.md lines 233-235 name the three sub-agents explicitly.

    Pin the name strings here so a rename on either side of the PLAN.md
    contract requires both sides to move together.
    """

    observed = {sub.name for sub in root_agent.sub_agents}
    assert observed == _EXPECTED_SUB_AGENT_NAMES, (
        f"sub-agent name drift: expected {_EXPECTED_SUB_AGENT_NAMES}, got {observed}"
    )


def test_sub_agents_have_no_tools_wired_yet() -> None:
    """Week-1 guardrail: MCP bindings land in their own per-tool PRs.

    If a future Week-2 diff accidentally wires an MCP tool onto a sub-agent
    before its dedicated PR (``match_payer_criteria``, ``generate_pa_letter``)
    lands, this test fails loudly. That is intentional — the per-tool PRs
    are where reviewers look for tool-binding regressions.
    """

    for sub in root_agent.sub_agents:
        # All three sub-agents are LlmAgent instances (the ``Agent`` alias);
        # ``BaseAgent`` itself doesn't expose ``.tools``, so narrow first.
        assert isinstance(sub, LlmAgent), (
            f"sub-agent {sub.name!r} is not an LlmAgent: {type(sub).__name__}"
        )
        assert sub.tools == [], (
            f"sub-agent {sub.name!r} has unexpected tools wired: {sub.tools!r} "
            "-- Week-2 tool bindings must land in their own PRs, not here."
        )
