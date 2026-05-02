"""Tests for Tool 2 — match_payer_criteria.

Three tiers:

Tier 1 — deterministic (no LLM, always runs in CI):
    Unit tests for the pure rule-engine helpers (_check_red_flags,
    _select_pathway, _check_service_applicable, _check_chart_mismatch, etc.).

Tier 1.5 — full tool, deterministic paths (no LLM call):
    Red-flag fast-track, wrong CPT, unknown payer, chart mismatch.

Tier 2 — LLM integration (@pytest.mark.llm, skipped in `make test-fast`):
    Full tool invocations against all 4 demo patients. Asserts on
    Decision enum + red_flag_fast_track + list non-emptiness, NOT
    exact string matching on reasoning_trace.
"""

from __future__ import annotations

import pytest
from mcp_server.criteria.loader import load_payer_criteria
from mcp_server.tools.match_payer_criteria import (
    _build_preliminary_findings,
    _check_chart_mismatch,
    _check_red_flags,
    _check_service_applicable,
    _estimate_therapy_duration_weeks,
    _select_pathway,
    match_payer_criteria,
)
from shared.models import (
    Condition,
    Coverage,
    Decision,
    Demographics,
    PatientContext,
    RedFlagCandidate,
    ServiceRequest,
    TherapyTrial,
)

# ---------------------------------------------------------------------------
# Shared fixtures — minimal PatientContext objects for the 3 demo patients
# ---------------------------------------------------------------------------


def _patient_a() -> PatientContext:
    """47F happy path: 12wk LBP + radiculopathy, 8 PT + NSAID + relaxant."""
    return PatientContext(
        demographics=Demographics(patient_id="patient-a", age=47, sex="female"),
        active_conditions=[
            Condition(code="M54.50", display="Low back pain", onset_date="2026-01-15"),
            Condition(
                code="M54.16",
                display="Radiculopathy, lumbar region",
                onset_date="2026-01-15",
            ),
        ],
        conservative_therapy_trials=[
            TherapyTrial(
                kind="NSAID",
                drug_or_procedure="ibuprofen 600 mg",
                start_date="2026-02-01",
                last_date="2026-03-22",
            ),
            TherapyTrial(
                kind="MUSCLE_RELAXANT",
                drug_or_procedure="cyclobenzaprine 10 mg",
                start_date="2026-02-01",
                last_date="2026-03-22",
            ),
            TherapyTrial(
                kind="PHYSICAL_THERAPY",
                drug_or_procedure="therapeutic exercises (CPT 97110)",
                start_date="2026-02-01",
                sessions_or_days=8,
                last_date="2026-03-22",
            ),
        ],
        service_request=ServiceRequest(
            cpt_code="72148",
            description="MRI Lumbar Spine without contrast",
            ordered_date="2026-04-15",
            ordering_provider="Dr. Alice Chen, MD",
            reason_codes=["M54.50"],
        ),
        coverage=Coverage(payer_id="cigna", payer_name="Cigna HealthCare"),
        clinical_notes_excerpt=(
            "47F with 12 weeks of mechanical low back pain and right lower "
            "extremity radiculopathy. Completed 8 sessions of PT over 7 weeks "
            "and a 6-week trial of ibuprofen 600mg TID + cyclobenzaprine 10mg "
            "QHS without resolution. No red flags — denies saddle numbness, "
            "bowel/bladder changes, progressive weakness, fever, weight loss."
        ),
    )


def _patient_b() -> PatientContext:
    """52M needs-info: NSAID only, 1 PT visit, incomplete course."""
    return PatientContext(
        demographics=Demographics(patient_id="patient-b", age=52, sex="male"),
        active_conditions=[
            Condition(code="M54.50", display="Low back pain", onset_date="2026-02-20"),
        ],
        conservative_therapy_trials=[
            TherapyTrial(
                kind="NSAID",
                drug_or_procedure="naproxen 500 mg",
                start_date="2026-03-01",
                last_date="2026-03-10",
            ),
            TherapyTrial(
                kind="PHYSICAL_THERAPY",
                drug_or_procedure="therapeutic exercises (CPT 97110)",
                start_date="2026-03-10",
                sessions_or_days=1,
                last_date="2026-03-10",
            ),
        ],
        service_request=ServiceRequest(
            cpt_code="72148",
            description="MRI Lumbar Spine without contrast",
            ordered_date="2026-04-15",
            ordering_provider="Dr. Alice Chen, MD",
            reason_codes=["M54.50"],
        ),
        coverage=Coverage(payer_id="cigna", payer_name="Cigna HealthCare"),
        clinical_notes_excerpt=(
            "52M with 10 weeks of low back pain. Started naproxen 500mg BID "
            "on 03/01. Had 1 PT intake evaluation on 03/10, then 3 no-shows. "
            "Patient reports substituting YouTube stretching videos at home. "
            "No red flags."
        ),
    )


def _patient_c() -> PatientContext:
    """61F red-flag fast-track: breast-ca history + cauda equina symptoms."""
    return PatientContext(
        demographics=Demographics(patient_id="patient-c", age=61, sex="female"),
        active_conditions=[
            Condition(code="M54.50", display="Low back pain", onset_date="2026-04-01"),
            Condition(
                code="Z85.3",
                display="Personal hx malignant neoplasm of breast",
                onset_date="2019-03-01",
            ),
        ],
        conservative_therapy_trials=[],
        red_flag_candidates=[
            RedFlagCandidate(
                label="history_of_cancer",
                source="icd_code",
                evidence="Z85.3 Personal hx malignant neoplasm of breast",
            ),
            RedFlagCandidate(
                label="saddle_anesthesia",
                source="clinical_note",
                evidence="patient reports new saddle numbness",
            ),
            RedFlagCandidate(
                label="bowel_bladder_dysfunction",
                source="clinical_note",
                evidence="post-void residual 310 mL with overflow incontinence",
            ),
        ],
        service_request=ServiceRequest(
            cpt_code="72148",
            description="MRI Lumbar Spine without contrast",
            ordered_date="2026-04-15",
            ordering_provider="Dr. Alice Chen, MD",
            reason_codes=["M54.50"],
        ),
        coverage=Coverage(payer_id="aetna", payer_name="Aetna Better Health"),
        clinical_notes_excerpt=(
            "61F presenting to ED with acute onset bilateral lower extremity "
            "weakness, saddle numbness, and urinary retention (PVR 310 mL). "
            "History of ER+ breast cancer 7 years ago on anastrozole. "
            "Decreased rectal tone. Textbook cauda equina presentation."
        ),
    )


def _patient_d() -> PatientContext:
    """36F chart mismatch: pharyngitis + HTN, zero spine diagnoses."""
    return PatientContext(
        demographics=Demographics(patient_id="patient-d", age=36, sex="female"),
        active_conditions=[
            Condition(
                code="J02.9", display="Acute pharyngitis, unspecified", onset_date="2026-04-20"
            ),
            Condition(
                code="I10", display="Essential (primary) hypertension", onset_date="2024-01-15"
            ),
        ],
        conservative_therapy_trials=[],
        service_request=ServiceRequest(
            cpt_code="72148",
            description="MRI Lumbar Spine without contrast",
            ordered_date="2026-04-22",
            ordering_provider="Dr. James Kim, MD",
            reason_codes=["J02.9"],
        ),
        coverage=Coverage(payer_id="cigna", payer_name="Cigna HealthCare"),
        clinical_notes_excerpt="36F presents with sore throat x3 days. No back pain.",
    )


# ---------------------------------------------------------------------------
# Tier 1 — deterministic rule-engine unit tests
# ---------------------------------------------------------------------------

_CIGNA = load_payer_criteria("cigna")
_AETNA = load_payer_criteria("aetna")


class TestServiceApplicable:
    def test_cpt_72148_is_covered_by_cigna(self) -> None:
        assert _check_service_applicable(_CIGNA, "72148") is True

    def test_cpt_72148_is_covered_by_aetna(self) -> None:
        assert _check_service_applicable(_AETNA, "72148") is True

    def test_unknown_cpt_is_not_covered(self) -> None:
        assert _check_service_applicable(_CIGNA, "99999") is False


class TestRedFlags:
    def test_patient_c_triggers_fast_track_cigna(self) -> None:
        is_ft, reason, checks = _check_red_flags(_patient_c(), _CIGNA)
        assert is_ft is True
        assert reason is not None
        assert len(checks) >= 1
        matched_ids = {c.id for c in checks}
        assert "cigna.redflag.cancer" in matched_ids or "cigna.redflag.cauda_equina" in matched_ids

    def test_patient_c_triggers_fast_track_aetna(self) -> None:
        is_ft, reason, checks = _check_red_flags(_patient_c(), _AETNA)
        assert is_ft is True
        assert reason is not None
        assert len(checks) >= 1

    def test_patient_a_no_fast_track(self) -> None:
        is_ft, reason, checks = _check_red_flags(_patient_a(), _CIGNA)
        assert is_ft is False
        assert reason is None
        assert checks == []

    def test_patient_b_no_fast_track(self) -> None:
        is_ft, _reason, _checks = _check_red_flags(_patient_b(), _CIGNA)
        assert is_ft is False


class TestSelectPathway:
    def test_radiculopathy_selects_cigna_default(self) -> None:
        pw = _select_pathway(_patient_a(), _CIGNA)
        assert pw is not None
        assert pw.applies_when == "default"
        assert pw.weeks == 6

    def test_radiculopathy_selects_aetna_6wk(self) -> None:
        pw = _select_pathway(_patient_a(), _AETNA)
        assert pw is not None
        assert pw.applies_when == "has_radiculopathy"
        assert pw.weeks == 6

    def test_lbp_only_selects_cigna_default(self) -> None:
        pw = _select_pathway(_patient_b(), _CIGNA)
        assert pw is not None
        assert pw.applies_when == "default"
        assert pw.weeks == 6

    def test_lbp_only_no_aetna_pathway(self) -> None:
        pw = _select_pathway(_patient_b(), _AETNA)
        assert pw is None

    def test_spondylolisthesis_selects_aetna_4wk(self) -> None:
        ctx = _patient_b()
        ctx.active_conditions.append(
            Condition(code="M43.10", display="Spondylolisthesis", onset_date="2026-01-01")
        )
        pw = _select_pathway(ctx, _AETNA)
        assert pw is not None
        assert pw.applies_when == "has_spondylolisthesis_or_ddd"
        assert pw.weeks == 4


class TestTherapyDuration:
    def test_patient_a_duration_over_6_weeks(self) -> None:
        weeks = _estimate_therapy_duration_weeks(_patient_a())
        assert weeks >= 6.0

    def test_patient_b_duration_under_6_weeks(self) -> None:
        weeks = _estimate_therapy_duration_weeks(_patient_b())
        assert weeks < 6.0

    def test_no_therapy_returns_zero(self) -> None:
        ctx = _patient_c()
        assert _estimate_therapy_duration_weeks(ctx) == 0.0


class TestPreliminaryFindings:
    def test_returns_nonempty_string(self) -> None:
        pw = _select_pathway(_patient_a(), _CIGNA)
        text = _build_preliminary_findings(_patient_a(), _CIGNA, pw)
        assert isinstance(text, str)
        assert len(text) > 50

    def test_includes_payer_and_patient(self) -> None:
        pw = _select_pathway(_patient_a(), _CIGNA)
        text = _build_preliminary_findings(_patient_a(), _CIGNA, pw)
        assert "Cigna" in text or "cigna" in text
        assert "47" in text


# ---------------------------------------------------------------------------
# Tier 1.5 — full tool, deterministic paths (no LLM call)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patient_c_aetna_red_flag_fast_track() -> None:
    """Red-flag fast-track: deterministic, no Gemini call."""
    ctx = _patient_c()
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="aetna",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.decision == Decision.APPROVE
    assert result.red_flag_fast_track is True
    assert result.red_flag_reason is not None
    assert result.confidence == 1.0
    assert result.source_policy_url is not None


@pytest.mark.asyncio
async def test_wrong_cpt_denies() -> None:
    """Wrong CPT -> DENY, deterministic, no Gemini call."""
    ctx = _patient_a()
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="cigna",
        service_code="99999",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.decision == Decision.DENY
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_empty_payer_id_needs_info_no_tool_error() -> None:
    ctx = _patient_a()
    ctx = ctx.model_copy(
        update={"coverage": Coverage(payer_id="", payer_name="Prompt Opinion Demo Plan")}
    )
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.decision == Decision.NEEDS_INFO
    assert result.criteria_missing
    assert result.criteria_missing[0].id == "system.payer_not_mapped"
    assert result.source_policy_url is None


@pytest.mark.asyncio
async def test_unknown_payer_slug_needs_info() -> None:
    ctx = _patient_a()
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="humana",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.decision == Decision.NEEDS_INFO
    assert result.criteria_missing
    assert result.criteria_missing[0].id == "system.payer_not_mapped"


# ---------------------------------------------------------------------------
# Tier 2 — full tool integration tests (calls Gemini, @pytest.mark.llm)
# ---------------------------------------------------------------------------


class TestChartMismatch:
    """Tier 1 — _check_chart_mismatch deterministic tests."""

    def test_patient_d_triggers_mismatch(self) -> None:
        result = _check_chart_mismatch(_patient_d())
        assert result is not None
        assert result.decision == Decision.DO_NOT_SUBMIT
        assert result.criteria_missing[0].id == "system.chart_mismatch"

    def test_patient_a_no_mismatch(self) -> None:
        assert _check_chart_mismatch(_patient_a()) is None

    def test_patient_b_no_mismatch(self) -> None:
        assert _check_chart_mismatch(_patient_b()) is None

    def test_patient_c_no_mismatch(self) -> None:
        assert _check_chart_mismatch(_patient_c()) is None

    def test_empty_conditions_triggers_mismatch(self) -> None:
        ctx = _patient_d()
        ctx.active_conditions = []
        result = _check_chart_mismatch(ctx)
        assert result is not None
        assert result.decision == Decision.DO_NOT_SUBMIT

    def test_red_flags_bypass_mismatch(self) -> None:
        """Even with non-spine ICD codes, red-flag candidates prevent mismatch."""
        ctx = _patient_d()
        ctx.red_flag_candidates = [
            RedFlagCandidate(
                label="history_of_cancer",
                source="clinical_note",
                evidence="patient reports history of cancer",
            )
        ]
        assert _check_chart_mismatch(ctx) is None


class TestRedFlagEvidenceSnippets:
    """Tier 1 — verify source_document and snippet on red-flag checks."""

    def test_red_flag_checks_have_source_document(self) -> None:
        _, _, checks = _check_red_flags(_patient_c(), _AETNA)
        assert len(checks) >= 1
        for check in checks:
            assert check.source_document is not None
            assert "RedFlagCandidate/" in check.source_document

    def test_red_flag_checks_have_snippet(self) -> None:
        _, _, checks = _check_red_flags(_patient_c(), _CIGNA)
        assert len(checks) >= 1
        for check in checks:
            assert check.snippet is not None
            assert len(check.snippet) > 0


# ---------------------------------------------------------------------------
# Tier 1.5b — full tool, DO_NOT_SUBMIT path (no LLM call)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patient_d_chart_mismatch_do_not_submit() -> None:
    """Chart mismatch: 36F with pharyngitis + HTN -> DO_NOT_SUBMIT, no Gemini call."""
    ctx = _patient_d()
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="cigna",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.decision == Decision.DO_NOT_SUBMIT
    assert result.confidence == 1.0
    assert result.criteria_missing[0].id == "system.chart_mismatch"
    assert result.evaluated_at is not None
    assert result.evidence_sources_used


# ---------------------------------------------------------------------------
# Tier 1.5c — audit metadata on all deterministic paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_red_flag_fast_track_has_audit_metadata() -> None:
    ctx = _patient_c()
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="aetna",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.evaluated_at is not None
    assert result.policy_version_tag is not None
    assert "aetna" in result.policy_version_tag
    assert "Patient" in result.evidence_sources_used
    assert result.review_status == "pending_human_review"


@pytest.mark.asyncio
async def test_unknown_payer_has_audit_metadata() -> None:
    ctx = _patient_a()
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="humana",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.evaluated_at is not None
    assert result.evidence_sources_used


@pytest.mark.llm
@pytest.mark.asyncio
async def test_patient_a_cigna_approves() -> None:
    """Happy path: 47F, 12wk therapy, NSAID + relaxant + PT -> approve."""
    ctx = _patient_a()
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="cigna",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.decision == Decision.APPROVE
    assert result.red_flag_fast_track is False
    assert len(result.criteria_met) > 0
    assert result.source_policy_url is not None
    assert result.confidence >= 0.7


@pytest.mark.llm
@pytest.mark.asyncio
async def test_patient_b_cigna_needs_info() -> None:
    """Needs-info: 52M, NSAID only, 1 PT visit -> needs_info."""
    ctx = _patient_b()
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="cigna",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.decision == Decision.NEEDS_INFO
    assert result.red_flag_fast_track is False
    assert len(result.criteria_missing) > 0
    assert result.source_policy_url is not None


@pytest.mark.llm
@pytest.mark.asyncio
async def test_patient_a_aetna_approves_via_radiculopathy_pathway() -> None:
    """Patient A against Aetna: M54.16 -> radiculopathy pathway -> approve."""
    ctx = _patient_a()
    ctx.coverage = Coverage(payer_id="aetna", payer_name="Aetna")
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="aetna",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.decision == Decision.APPROVE
    assert result.red_flag_fast_track is False
    assert result.source_policy_url is not None


@pytest.mark.llm
@pytest.mark.asyncio
async def test_patient_b_still_needs_info_not_do_not_submit() -> None:
    """CRITICAL: Patient B has M54.50 (spine-related) — must be NEEDS_INFO, never DO_NOT_SUBMIT."""
    ctx = _patient_b()
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="cigna",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.decision == Decision.NEEDS_INFO, (
        f"Patient B routes to {result.decision.value!r} — must be needs_info. "
        "M54.50 is a spine code so chart-mismatch must NOT fire."
    )
    assert result.evaluated_at is not None
    assert result.policy_version_tag is not None
    assert result.review_status == "pending_human_review"


@pytest.mark.llm
@pytest.mark.asyncio
async def test_llm_path_populates_audit_metadata() -> None:
    """LLM path (Patient A approve) should have audit metadata stamped."""
    ctx = _patient_a()
    result = await match_payer_criteria(
        patient_context_json=ctx.model_dump_json(),
        payer_id="cigna",
        service_code="72148",
        ctx=None,  # type: ignore[arg-type]
    )
    assert result.decision == Decision.APPROVE
    assert result.evaluated_at is not None
    assert result.policy_version_tag is not None
    assert "cigna" in result.policy_version_tag
    assert len(result.evidence_sources_used) >= 4
    assert result.review_status == "pending_human_review"
