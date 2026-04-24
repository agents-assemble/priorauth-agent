"""Week-2 orchestration contract — priorauth pipeline (Person B).

This module is the **single place** for handoff order and MCP tool names while
Kevin wires ``match_payer_criteria`` / ``generate_pa_letter`` and Sanjit
promotes the ADK root + sub-agents from Week-1 stubs.

``root_agent`` uses a Week-1 or MCP-enabled instruction in ``a2a_agent.agent``
(see ``_root_instruction``) when tools are present; a future pass may point it
at ``ORCHESTRATOR_INSTRUCTION_V1`` and explicit transfer routing.
"""

from __future__ import annotations

# Sub-agent registration order on ``root_agent.sub_agents`` is arbitrary; this
# tuple is the **logical** pipeline order from PLAN.md (retrieve → evaluate → draft).
SUB_AGENT_HANDOFF_ORDER: tuple[str, ...] = (
    "patient_context",
    "criteria_evaluator",
    "pa_letter",
)

# MCP tool names (FastMCP) bound in Week-2 PRs — must match ``mcp_server`` registrations.
MCP_TOOL_BY_SUB_AGENT: dict[str, str] = {
    "patient_context": "fetch_patient_context",
    "criteria_evaluator": "match_payer_criteria",
    "pa_letter": "generate_pa_letter",
}

# Draft root instruction for the Week-2 orchestrator swap (see ``agent.py``).
ORCHESTRATOR_INSTRUCTION_V1 = (
    "You are the root orchestrator for prior authorization of outpatient "
    "lumbar MRI (CPT 72148) inside Prompt Opinion.\n\n"
    "Hard rules:\n"
    "- Never echo fhir_token, fhir_url, workspace URLs, or raw JWT text.\n"
    "- Never invent clinical facts, criteria outcomes, or PA letter content "
    "yourself—sub-agents own retrieval, evaluation, and drafting once their "
    "MCP tools are wired.\n"
    "- Enforce the pipeline order: patient_context → criteria_evaluator → "
    "pa_letter. Only skip a step if a prior step failed irrecoverably; say "
    "what failed, do not fabricate chart data.\n\n"
    "Handoffs:\n"
    "- When FHIR context is present (see the injected session note), transfer "
    "first to `patient_context` to obtain normalized PatientContext via MCP.\n"
    "- Then transfer to `criteria_evaluator` with that context for "
    "CriteriaResult.\n"
    "- Then transfer to `pa_letter` with PatientContext + CriteriaResult for "
    "the final PALetter (approval letter, needs-info checklist, or red-flag "
    "fast-track per tool output).\n"
)
