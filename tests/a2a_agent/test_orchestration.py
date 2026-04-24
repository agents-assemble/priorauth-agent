"""Orchestration contract tests (Week-2 prep, no ADK runtime required)."""

from __future__ import annotations

from a2a_agent.orchestration import (
    MCP_TOOL_BY_SUB_AGENT,
    ORCHESTRATOR_INSTRUCTION_V1,
    SUB_AGENT_HANDOFF_ORDER,
)
from shared.models import (
    Coverage,
    CriteriaResult,
    Decision,
    Demographics,
    PALetter,
    PatientContext,
    ServiceRequest,
)


def test_handoff_order_matches_plan_three_step_pipeline() -> None:
    assert SUB_AGENT_HANDOFF_ORDER == (
        "patient_context",
        "criteria_evaluator",
        "pa_letter",
    )


def test_mcp_tool_map_covers_each_sub_agent() -> None:
    for name in SUB_AGENT_HANDOFF_ORDER:
        assert name in MCP_TOOL_BY_SUB_AGENT
        assert MCP_TOOL_BY_SUB_AGENT[name]


def test_orchestrator_instruction_v1_is_substantive() -> None:
    assert len(ORCHESTRATOR_INSTRUCTION_V1) > 200
    assert "patient_context" in ORCHESTRATOR_INSTRUCTION_V1
    assert "criteria_evaluator" in ORCHESTRATOR_INSTRUCTION_V1
    assert "pa_letter" in ORCHESTRATOR_INSTRUCTION_V1


def _minimal_patient_context() -> PatientContext:
    return PatientContext(
        demographics=Demographics(patient_id="p1", age=47, sex="female"),
        service_request=ServiceRequest(
            cpt_code="72148",
            description="MRI lumbar spine without contrast",
            ordered_date="2026-04-01",
            ordering_provider="Dr. Smith",
        ),
        coverage=Coverage(payer_id="cigna", payer_name="Cigna Healthcare"),
    )


def _minimal_criteria_result() -> CriteriaResult:
    return CriteriaResult(
        decision=Decision.NEEDS_INFO,
        payer_id="cigna",
        service_cpt="72148",
        confidence=0.85,
        reasoning_trace="PT course not fully documented.",
        source_criteria_version="cigna_lumbar_mri.v1",
    )


def _minimal_pa_letter() -> PALetter:
    return PALetter(
        decision=Decision.NEEDS_INFO,
        patient_id="p1",
        payer_id="cigna",
        service_cpt="72148",
        subject_line="PA request — lumbar MRI",
        rendered_html="<p>Needs PT documentation.</p>",
        rendered_markdown="Needs PT documentation.",
        source_criteria_version="cigna_lumbar_mri.v1",
    )


def test_shared_models_minimal_round_trip_for_pipeline() -> None:
    """Guards Person B orchestration work against accidental contract drift."""

    pc = _minimal_patient_context()
    cr = _minimal_criteria_result()
    letter = _minimal_pa_letter()

    assert pc.demographics.patient_id == letter.patient_id
    assert cr.payer_id == letter.payer_id
    assert cr.service_cpt == letter.service_cpt
    assert cr.decision == letter.decision
