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
    lands, this test fails loudly. That is intentional -- the per-tool PRs
    are where reviewers look for tool-binding regressions.
    """

    for sub in root_agent.sub_agents:
        assert isinstance(sub, LlmAgent), (
            f"sub-agent {sub.name!r} is not an LlmAgent: {type(sub).__name__}"
        )
        assert sub.tools == [], (
            f"sub-agent {sub.name!r} has unexpected tools wired: {sub.tools!r} "
            "-- Week-2 tool bindings must land in their own PRs, not here."
        )


def test_sub_agents_carry_week_1_stub_instruction() -> None:
    """Week-1 confabulation-safety guardrail (PR #13 review).

    A tool-less sub-agent carrying the production PLAN.md instruction
    (which directs Gemini to invoke its tool) invites the same class of
    confabulation bug PR #9 fixed on the root agent. Each sub-agent
    must ship with a Week-1-stub instruction that forbids fabrication
    until its Week-2 tool-binding PR lands.

    The Week-2 swap (``instruction=_WEEK_2_INSTRUCTION`` +
    ``tools=[...]``) makes BOTH the tool list non-empty AND the
    instruction sentinel absent in the same diff, so this test and
    ``test_sub_agents_have_no_tools_wired_yet`` fail together on a
    legitimate Week-2 promotion -- and a reviewer updating the pair of
    tests (or temporarily xfailing them) is the explicit sign-off that
    Week-2 tool binding has landed for that sub-agent.
    """

    sentinel = "Week-1 scaffold"
    for sub in root_agent.sub_agents:
        assert isinstance(sub, LlmAgent), (
            f"sub-agent {sub.name!r} is not an LlmAgent: {type(sub).__name__}"
        )
        # LlmAgent.instruction is typed str | Callable[..., str | Awaitable[str]];
        # Week-1 stubs are always literal strings, so narrow before substring check.
        instruction = sub.instruction
        assert isinstance(instruction, str), (
            f"sub-agent {sub.name!r} has a callable instruction "
            f"({type(instruction).__name__}); Week-1 stubs must be literal "
            "strings so the sentinel check below is meaningful."
        )
        assert sentinel in instruction, (
            f"sub-agent {sub.name!r} is missing the Week-1 stub sentinel "
            f"'{sentinel}'. Either the production PLAN.md instruction was "
            "promoted without also binding an MCP tool (see "
            "test_sub_agents_have_no_tools_wired_yet), or the stub was "
            "edited without updating this guardrail. See PR #13 review."
        )
