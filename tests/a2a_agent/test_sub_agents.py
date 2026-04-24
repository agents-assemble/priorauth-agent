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
from google.adk.tools.mcp_tool import McpToolset

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
    """Week-1 guardrail: only ``patient_context`` may attach MCP; others stay empty in CI.

    In production dev, ``patient_context`` can carry a :class:`McpToolset` for
    ``fetch_patient_context`` when ``MCP_SERVER_URL`` is set. Pytest forces
    ``A2A_TESTING_NO_MCP`` so the default is still all-empty here.

    ``criteria_evaluator`` and ``pa_letter`` must not gain tools until their
    Week-2 MCP tool PRs land.
    """

    for sub in root_agent.sub_agents:
        assert isinstance(sub, LlmAgent), (
            f"sub-agent {sub.name!r} is not an LlmAgent: {type(sub).__name__}"
        )
        if sub.name == "patient_context":
            if not sub.tools:
                continue
            assert len(sub.tools) == 1, (
                f"patient_context must use a single McpToolset, got {sub.tools!r}"
            )
            assert isinstance(sub.tools[0], McpToolset), (
                f"expected McpToolset on patient_context, got {type(sub.tools[0])!r}"
            )
            continue
        assert sub.tools == [], (
            f"sub-agent {sub.name!r} has unexpected tools wired: {sub.tools!r} "
            "-- only patient_context is wired in Week-2 / fetch_patient_context first."
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
        if sub.name == "patient_context" and sub.tools:
            assert sentinel not in instruction, (
                "patient_context with MCP must use production instruction, not Week-1 stub"
            )
            assert "Clinical data retrieval specialist" in instruction
        else:
            assert sentinel in instruction, (
                f"sub-agent {sub.name!r} is missing the Week-1 stub sentinel "
                f"'{sentinel}'. Either the production PLAN.md instruction was "
                "promoted without also binding an MCP tool (see "
                "test_sub_agents_have_no_tools_wired_yet), or the stub was "
                "edited without updating this guardrail. See PR #13 review."
            )
