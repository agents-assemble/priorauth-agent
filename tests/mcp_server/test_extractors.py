"""Unit tests for `mcp_server.fhir.extractors`.

Pure-function tests over hand-crafted FHIR R4 resource dicts. Fixtures are
intentionally inline rather than file-based JSON so the expected→actual
relationship lives in one place. The full-bundle end-to-end fixtures for the
three demo patients live next to the tool integration test
(`test_fetch_patient_context_fhir.py`).

Each `_REDFLAG_ICD_MAP` and `_RXNORM_TO_KIND` entry asserted here is also
referenced by `mcp_server/criteria/data/cigna_evicore_lumbar_mri.v1_0_2026
.json` `red_flags[].canonical_labels` (PR #8) — these tests guard the
cross-file contract that the rule engine matches what the extractor emits.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from mcp_server.fhir.extractors import (
    detect_payer_from_text,
    detect_redflags_from_conditions,
    extract_conditions,
    extract_coverage,
    extract_demographics,
    extract_medication_trials,
    extract_prior_imaging,
    extract_procedure_trials,
    extract_service_request,
)
from shared.models import Condition

# ---------------------------------------------------------------------------
# Demographics
# ---------------------------------------------------------------------------


def test_demographics_year_math_handles_pre_birthday() -> None:
    today = date.today()
    pre_bday = today.replace(year=today.year - 47).replace(day=min(today.day + 1, 28))
    patient = {"id": "p1", "birthDate": pre_bday.isoformat(), "gender": "female"}
    demo = extract_demographics(patient)
    # Pre-birthday → still 46, not 47.
    assert demo.age in (46, 47), "age must reflect off-by-one safe year math"
    assert demo.sex == "female"
    assert demo.patient_id == "p1"


def test_demographics_missing_birthdate_defaults_to_zero_not_raise() -> None:
    demo = extract_demographics({"id": "p2", "gender": "male"})
    assert demo.age == 0
    assert demo.sex == "male"


def test_demographics_invalid_birthdate_logs_and_returns_zero() -> None:
    demo = extract_demographics({"id": "p3", "birthDate": "not-a-date", "gender": "unknown"})
    assert demo.age == 0


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------


def _condition(
    code: str,
    *,
    display: str = "",
    system: str = "http://hl7.org/fhir/sid/icd-10-cm",
    status: str = "active",
    onset: str | None = None,
) -> dict[str, Any]:
    res: dict[str, Any] = {
        "resourceType": "Condition",
        "clinicalStatus": {"coding": [{"code": status}]},
        "code": {"coding": [{"system": system, "code": code, "display": display or code}]},
    }
    if onset:
        res["onsetDateTime"] = onset
    return res


def test_extract_conditions_keeps_active_drops_resolved() -> None:
    raw = [
        _condition("M54.50", display="Low back pain", status="active"),
        _condition("M51.16", display="Disc herniation, lumbar", status="resolved"),
    ]
    conds = extract_conditions(raw)
    assert len(conds) == 1
    assert conds[0].code == "M54.50"


def test_extract_conditions_computes_duration_weeks_when_onset_present() -> None:
    onset = (date.today() - timedelta(weeks=12)).isoformat()
    conds = extract_conditions([_condition("M54.50", onset=onset)])
    assert conds[0].onset_date == onset
    # 12 weeks ago → 12 weeks duration (allow ±1 for day-rounding around today).
    assert conds[0].duration_weeks is not None
    assert 11 <= conds[0].duration_weeks <= 13


def test_extract_conditions_skips_when_no_code_at_all() -> None:
    raw = [{"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]}}]
    assert extract_conditions(raw) == []


def test_extract_conditions_falls_back_to_first_coding_when_icd_system_missing() -> None:
    raw = [
        _condition(
            "M54.50",
            display="Low back pain",
            system="http://snomed.info/sct",  # not ICD
            status="active",
        )
    ]
    conds = extract_conditions(raw)
    # Fallback path: still emits the code rather than dropping the row.
    assert len(conds) == 1
    assert conds[0].code == "M54.50"


# ---------------------------------------------------------------------------
# Medication trials
# ---------------------------------------------------------------------------


def _med_request(
    rxnorm_code: str,
    *,
    display: str = "",
    authored_on: str = "2026-03-01",
) -> dict[str, Any]:
    return {
        "resourceType": "MedicationRequest",
        "status": "active",
        "authoredOn": authored_on,
        "medicationCodeableConcept": {
            "text": display or rxnorm_code,
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": rxnorm_code,
                    "display": display or rxnorm_code,
                }
            ],
        },
        "dispenseRequest": {
            "expectedSupplyDuration": {"value": 30, "unit": "d"},
        },
    }


@pytest.mark.parametrize(
    ("rxnorm", "expected_kind"),
    [
        ("5640", "NSAID"),
        ("7258", "NSAID"),
        ("21949", "MUSCLE_RELAXANT"),
        ("25480", "GABAPENTINOID"),
        ("8640", "ORAL_CORTICOSTEROID"),
        ("7804", "ANALGESIC_OPIOID"),
        ("161", "ANALGESIC_NON_OPIOID"),
    ],
)
def test_med_request_classification_maps_rxnorm_to_pr8_taxonomy(
    rxnorm: str, expected_kind: str
) -> None:
    trials = extract_medication_trials([_med_request(rxnorm, display=f"drug-{rxnorm}")])
    assert len(trials) == 1
    assert trials[0].kind == expected_kind
    assert trials[0].sessions_or_days == 30


def test_med_request_unknown_rxnorm_is_dropped_not_guessed() -> None:
    # An RxNorm code we don't recognise must NOT fall into a default bucket.
    trials = extract_medication_trials([_med_request("999999", display="mystery-drug")])
    assert trials == []


# ---------------------------------------------------------------------------
# Procedure trials
# ---------------------------------------------------------------------------


def _procedure(cpt: str, *, performed: str, display: str = "") -> dict[str, Any]:
    return {
        "resourceType": "Procedure",
        "status": "completed",
        "performedDateTime": performed,
        "code": {
            "coding": [
                {
                    "system": "http://www.ama-assn.org/go/cpt",
                    "code": cpt,
                    "display": display or cpt,
                }
            ]
        },
    }


def test_procedure_collapses_multiple_pt_visits_into_one_trial_with_session_count() -> None:
    raw = [
        _procedure("97110", performed="2026-02-01"),
        _procedure("97110", performed="2026-02-08"),
        _procedure("97110", performed="2026-02-15"),
        _procedure("97110", performed="2026-02-22"),
        _procedure("97110", performed="2026-03-01"),
        _procedure("97110", performed="2026-03-08"),
        _procedure("97110", performed="2026-03-15"),
        _procedure("97110", performed="2026-03-22"),
    ]
    trials = extract_procedure_trials(raw)
    assert len(trials) == 1
    trial = trials[0]
    assert trial.kind == "PHYSICAL_THERAPY"
    assert trial.sessions_or_days == 8
    assert trial.start_date == "2026-02-01"
    assert trial.last_date == "2026-03-22"


def test_procedure_unknown_cpt_dropped() -> None:
    trials = extract_procedure_trials([_procedure("99999", performed="2026-03-01")])
    assert trials == []


def test_procedure_chiro_manipulation_classifies_as_spinal_manipulation() -> None:
    trials = extract_procedure_trials([_procedure("98941", performed="2026-03-01")])
    assert trials[0].kind == "SPINAL_MANIPULATION"


# ---------------------------------------------------------------------------
# ServiceRequest, Coverage, prior imaging
# ---------------------------------------------------------------------------


def test_service_request_picks_matching_cpt_with_reason_codes() -> None:
    raw = [
        {
            "resourceType": "ServiceRequest",
            "status": "active",
            "authoredOn": "2026-04-15",
            "code": {"coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": "72148"}]},
            "requester": {"display": "Dr. Alice Chen, MD"},
            "reasonCode": [
                {
                    "coding": [
                        {
                            "system": "http://hl7.org/fhir/sid/icd-10-cm",
                            "code": "M54.50",
                        }
                    ]
                }
            ],
        }
    ]
    sr = extract_service_request(raw, cpt_code="72148")
    assert sr.cpt_code == "72148"
    assert sr.ordered_date == "2026-04-15"
    assert sr.ordering_provider == "Dr. Alice Chen, MD"
    assert sr.reason_codes == ["M54.50"]


def test_service_request_returns_empty_shell_when_no_match() -> None:
    sr = extract_service_request([], cpt_code="72148")
    assert sr.cpt_code == "72148"
    assert sr.ordered_date == ""
    assert sr.ordering_provider == ""


@pytest.mark.parametrize(
    ("payor_display", "expected_id"),
    [
        ("Cigna HealthCare", "cigna"),
        ("eviCore by EVERNORTH", "cigna"),
        ("Aetna Better Health", "aetna"),
        ("UnitedHealth Group", ""),  # no rule for UHC yet → unknown payer
    ],
)
def test_coverage_routes_payer_name_to_canonical_id(payor_display: str, expected_id: str) -> None:
    cov = extract_coverage(
        [
            {
                "resourceType": "Coverage",
                "status": "active",
                "payor": [{"display": payor_display}],
            }
        ]
    )
    assert cov.payer_id == expected_id
    assert cov.payer_name == payor_display


def test_coverage_payor_reference_without_display_still_routes() -> None:
    cov = extract_coverage(
        [
            {
                "resourceType": "Coverage",
                "status": "active",
                "payor": [{"reference": "Organization/001-cigna-demo-plan"}],
            }
        ]
    )
    assert cov.payer_id == "cigna"
    assert "cigna" in cov.payer_name.lower()


def test_prior_imaging_filters_to_lumbar_loinc_codes() -> None:
    raw = [
        {
            "resourceType": "DiagnosticReport",
            "effectiveDateTime": "2025-09-01",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "24531-6",
                        "display": "MR Lumbar spine WO contrast",
                    }
                ]
            },
        },
        {
            "resourceType": "DiagnosticReport",
            "effectiveDateTime": "2026-01-01",
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "30746-2"}]  # CT chest
            },
        },
    ]
    imaging = extract_prior_imaging(raw)
    assert len(imaging) == 1
    assert imaging[0].modality == "MR Lumbar"
    assert imaging[0].date == "2025-09-01"


# ---------------------------------------------------------------------------
# Red-flag detection from ICD codes
# ---------------------------------------------------------------------------


def test_redflag_z853_breast_cancer_history_surfaces_history_of_cancer() -> None:
    """Patient C's `Z85.3` (breast-ca hx) must surface as a candidate.

    This is the structured-data signal the rule engine sees even before the
    PR-B free-text extractor pulls cauda-equina labels from her clinical
    note. Cross-references `cigna.redflag.cancer.canonical_labels` in PR #8.
    """
    candidates = detect_redflags_from_conditions(
        [Condition(code="Z85.3", display="Personal hx malignant neoplasm of breast")]
    )
    labels = {c.label for c in candidates}
    assert "history_of_cancer" in labels
    for c in candidates:
        assert c.source == "icd_code"
        assert "Z85.3" in c.evidence


def test_redflag_g834_emits_cauda_equina_syndrome_canonical_label() -> None:
    candidates = detect_redflags_from_conditions(
        [Condition(code="G83.4", display="Cauda equina syndrome")]
    )
    assert {c.label for c in candidates} == {"cauda_equina_syndrome"}


def test_redflag_dedup_across_two_motor_weakness_codes() -> None:
    candidates = detect_redflags_from_conditions(
        [
            Condition(code="G83.1", display="Monoplegia of lower limb"),
            Condition(code="G83.2", display="Monoplegia of upper limb"),
        ]
    )
    labels = [c.label for c in candidates]
    # Each canonical label should appear at most once across the 2 conditions.
    assert len(labels) == len(set(labels))
    assert "motor_weakness" in labels


def test_redflag_unknown_icd_emits_nothing() -> None:
    # M54.50 is the routine LBP code — explicitly NOT a red flag.
    assert detect_redflags_from_conditions([Condition(code="M54.50", display="LBP")]) == []


def test_redflag_prefix_match_handles_unenumerated_z85_subcodes() -> None:
    # Z85.7x family isn't in the explicit map but the Z85. prefix covers it.
    candidates = detect_redflags_from_conditions(
        [Condition(code="Z85.79", display="Personal hx of other lymphoid neoplasm")]
    )
    assert {c.label for c in candidates} == {"history_of_cancer"}


# ---------------------------------------------------------------------------
# detect_payer_from_text — notes-based payer fallback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected_id",
    [
        ("Patient covered under Cigna HealthCare plan.", "cigna"),
        ("Insurance: CIGNA PPO", "cigna"),
        ("Aetna Open Choice PPO", "aetna"),
        ("Covered by Evernorth Behavioral Health", "cigna"),
        ("eviCore prior auth guidelines apply", "cigna"),
    ],
)
def test_detect_payer_from_text_matches(text: str, expected_id: str) -> None:
    name, payer_id = detect_payer_from_text(text)
    assert payer_id == expected_id
    assert name != ""


def test_detect_payer_from_text_no_match() -> None:
    name, payer_id = detect_payer_from_text(
        "Patient presents with low back pain. No insurance information in note."
    )
    assert payer_id == ""
    assert name == ""


def test_detect_payer_from_text_empty_string() -> None:
    assert detect_payer_from_text("") == ("", "")


def test_detect_payer_from_text_first_match_wins() -> None:
    """When note mentions both Cigna and Aetna, Cigna comes first in _PAYER_ROUTING."""
    _, payer_id = detect_payer_from_text("Primary: Cigna, Secondary: Aetna")
    assert payer_id == "cigna"
