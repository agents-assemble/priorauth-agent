"""End-to-end test of `fetch_patient_context`'s real-FHIR fan-out path.

Uses `httpx.MockTransport` (stdlib-included) to wire a fake FHIR server to
the same `httpx.AsyncClient` that production code uses, so the test exercises
the complete code path:

  `_fetch_from_fhir` → `FhirClient.read/search` → `httpx.AsyncClient.get`
                     → MockTransport → JSON dict → extractors → PatientContext

Three demo patients are encoded inline:

- `patient-a`: 47F happy path. 12 wks LBP + 8 PT visits + NSAID + muscle
  relaxant. Expect APPROVE-shaped PatientContext (full therapy history,
  zero red-flag candidates).
- `patient-b`: 52M needs-info. NSAID OK, only 1 PT eval visit (incomplete
  course). Expect needs-info-shaped (NSAID present, PT trial under-counted).
- `patient-c`: 61F red-flag fast-track. Active LBP + Z85.3 breast-ca
  history. Expect history_of_cancer red-flag candidate from ICD alone.
  (Cauda-equina note-text candidates ship in PR-B.)

Why we don't assert on the rule-engine *decision* here: the rule engine
ships in Week 2. These tests pin the *PatientContext shape* the engine
will receive — that's the cross-tool contract we're protecting.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from mcp_server.fhir.context import FhirContext
from mcp_server.tools.fetch_patient_context import _fetch_from_fhir

FHIR_BASE = "https://fhir.example.com/r4"
TOKEN = "fake-token-for-tests"  # test fixture, not a real secret


# ---------------------------------------------------------------------------
# FHIR resource fixtures (small, hand-authored — one per demo patient)
# ---------------------------------------------------------------------------


def _bundle(*resources: dict[str, Any]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": r} for r in resources],
        "link": [],
    }


def _patient(pid: str, *, birth: str, gender: str) -> dict[str, Any]:
    return {"resourceType": "Patient", "id": pid, "birthDate": birth, "gender": gender}


def _cond(code: str, display: str, onset: str, status: str = "active") -> dict[str, Any]:
    return {
        "resourceType": "Condition",
        "clinicalStatus": {"coding": [{"code": status}]},
        "code": {
            "coding": [
                {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": code, "display": display}
            ]
        },
        "onsetDateTime": onset,
    }


def _med(rxnorm: str, display: str, authored: str) -> dict[str, Any]:
    return {
        "resourceType": "MedicationRequest",
        "status": "active",
        "authoredOn": authored,
        "medicationCodeableConcept": {
            "text": display,
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": rxnorm,
                    "display": display,
                }
            ],
        },
        "dispenseRequest": {"expectedSupplyDuration": {"value": 30, "unit": "d"}},
    }


def _proc(cpt: str, performed: str, display: str = "") -> dict[str, Any]:
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


def _service_request(cpt: str = "72148") -> dict[str, Any]:
    return {
        "resourceType": "ServiceRequest",
        "status": "active",
        "authoredOn": "2026-04-15",
        "code": {"coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": cpt}]},
        "requester": {"display": "Dr. Alice Chen, MD"},
        "reasonCode": [
            {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "M54.50"}]}
        ],
    }


def _coverage(payer_display: str) -> dict[str, Any]:
    return {
        "resourceType": "Coverage",
        "status": "active",
        "payor": [{"display": payer_display}],
    }


# Per-patient FHIR fixtures keyed by Patient.id. Each entry maps the (path,
# query-string-collapsed-to-params) to the JSON dict the mock returns.
_FIXTURES: dict[str, dict[tuple[str, str], dict[str, Any]]] = {
    "patient-a": {
        ("Patient/patient-a", ""): _patient("patient-a", birth="1979-05-12", gender="female"),
        ("Condition", "patient=patient-a"): _bundle(
            _cond("M54.50", "Low back pain", "2026-01-15"),
            _cond("M54.16", "Radiculopathy, lumbar region", "2026-01-15"),
        ),
        ("MedicationRequest", "patient=patient-a"): _bundle(
            _med("5640", "ibuprofen 600 mg", "2026-02-01"),
            _med("21949", "cyclobenzaprine 10 mg", "2026-02-01"),
        ),
        ("Procedure", "patient=patient-a"): _bundle(
            *(_proc("97110", performed=f"2026-02-{day:02d}") for day in (1, 8, 15, 22)),
            *(_proc("97110", performed=f"2026-03-{day:02d}") for day in (1, 8, 15, 22)),
        ),
        ("ServiceRequest", "code=72148&patient=patient-a"): _bundle(_service_request()),
        ("Coverage", "patient=patient-a"): _bundle(_coverage("Cigna HealthCare")),
        ("DiagnosticReport", "patient=patient-a"): _bundle(),
    },
    "patient-b": {
        ("Patient/patient-b", ""): _patient("patient-b", birth="1973-09-04", gender="male"),
        ("Condition", "patient=patient-b"): _bundle(
            _cond("M54.50", "Low back pain", "2026-02-20"),
        ),
        ("MedicationRequest", "patient=patient-b"): _bundle(
            _med("7258", "naproxen 500 mg", "2026-03-01"),
        ),
        ("Procedure", "patient=patient-b"): _bundle(
            # Only 1 PT visit — incomplete course. Documents the
            # needs-info shape the rule engine will see.
            _proc("97110", performed="2026-03-10"),
        ),
        ("ServiceRequest", "code=72148&patient=patient-b"): _bundle(_service_request()),
        ("Coverage", "patient=patient-b"): _bundle(_coverage("Cigna HealthCare")),
        ("DiagnosticReport", "patient=patient-b"): _bundle(),
    },
    "patient-c": {
        ("Patient/patient-c", ""): _patient("patient-c", birth="1965-03-22", gender="female"),
        ("Condition", "patient=patient-c"): _bundle(
            _cond("M54.50", "Low back pain", "2026-04-01"),
            # Personal-hx breast cancer — Z85.3 → red-flag history_of_cancer.
            _cond(
                "Z85.3",
                "Personal hx malignant neoplasm of breast",
                "2019-03-01",
            ),
        ),
        ("MedicationRequest", "patient=patient-c"): _bundle(),
        ("Procedure", "patient=patient-c"): _bundle(),
        ("ServiceRequest", "code=72148&patient=patient-c"): _bundle(_service_request()),
        ("Coverage", "patient=patient-c"): _bundle(_coverage("Aetna Better Health")),
        ("DiagnosticReport", "patient=patient-c"): _bundle(),
    },
}


def _make_handler(patient_id: str) -> Callable[[httpx.Request], httpx.Response]:
    """Build an httpx.MockTransport handler that serves the fixtures for one patient."""
    fixtures = _FIXTURES[patient_id]

    def handler(request: httpx.Request) -> httpx.Response:
        url = urlparse(str(request.url))
        # Path is `/r4/<resource>...` — strip the configured base path.
        path = url.path.removeprefix("/r4/")
        query_pairs = sorted(parse_qs(url.query).items())
        query = "&".join(f"{k}={','.join(v)}" for k, v in query_pairs)
        body = fixtures.get((path, query))
        if body is None:
            return httpx.Response(404, json={"resourceType": "OperationOutcome"})
        # Authorization header must be propagated for every call — guard.
        assert request.headers.get("Authorization") == f"Bearer {TOKEN}"
        return httpx.Response(200, json=body)

    return handler


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patient_a_happy_path_full_therapy_history_no_redflags() -> None:
    transport = httpx.MockTransport(_make_handler("patient-a"))
    async with httpx.AsyncClient(transport=transport) as http:
        ctx = await _fetch_from_fhir(
            fhir_ctx=FhirContext(url=FHIR_BASE, token=TOKEN),
            patient_id="patient-a",
            service_code="72148",
            http=http,
        )

    assert ctx.demographics.patient_id == "patient-a"
    assert ctx.demographics.sex == "female"
    assert ctx.demographics.age >= 46  # birth 1979 → ~46-47 today

    # Two active conditions extracted, no red flags from ICD codes alone.
    assert {c.code for c in ctx.active_conditions} == {"M54.50", "M54.16"}
    assert ctx.red_flag_candidates == []

    # Therapy: 1 NSAID + 1 muscle-relaxant from meds, 1 PT trial collapsed
    # from 8 procedure rows.
    kinds = sorted(t.kind for t in ctx.conservative_therapy_trials)
    assert kinds == ["MUSCLE_RELAXANT", "NSAID", "PHYSICAL_THERAPY"]
    pt = next(t for t in ctx.conservative_therapy_trials if t.kind == "PHYSICAL_THERAPY")
    assert pt.sessions_or_days == 8
    assert pt.start_date == "2026-02-01"
    assert pt.last_date == "2026-03-22"

    assert ctx.service_request.cpt_code == "72148"
    assert ctx.service_request.ordering_provider == "Dr. Alice Chen, MD"
    assert ctx.coverage.payer_id == "cigna"


@pytest.mark.asyncio
async def test_patient_b_needs_info_pt_undercounted_no_redflags() -> None:
    transport = httpx.MockTransport(_make_handler("patient-b"))
    async with httpx.AsyncClient(transport=transport) as http:
        ctx = await _fetch_from_fhir(
            fhir_ctx=FhirContext(url=FHIR_BASE, token=TOKEN),
            patient_id="patient-b",
            service_code="72148",
            http=http,
        )

    pt_trials = [t for t in ctx.conservative_therapy_trials if t.kind == "PHYSICAL_THERAPY"]
    assert len(pt_trials) == 1
    assert pt_trials[0].sessions_or_days == 1, (
        "Patient B has only 1 PT visit recorded — rule engine relies on "
        "this exact session count to drive a needs-info decision."
    )
    nsaid_trials = [t for t in ctx.conservative_therapy_trials if t.kind == "NSAID"]
    assert len(nsaid_trials) == 1
    assert ctx.red_flag_candidates == []


@pytest.mark.asyncio
async def test_patient_c_breast_ca_history_surfaces_history_of_cancer_red_flag() -> None:
    transport = httpx.MockTransport(_make_handler("patient-c"))
    async with httpx.AsyncClient(transport=transport) as http:
        ctx = await _fetch_from_fhir(
            fhir_ctx=FhirContext(url=FHIR_BASE, token=TOKEN),
            patient_id="patient-c",
            service_code="72148",
            http=http,
        )

    labels = {c.label for c in ctx.red_flag_candidates}
    assert "history_of_cancer" in labels, (
        "PR #8 cigna.redflag.cancer.canonical_labels lists 'history_of_cancer'; "
        "the rule engine matches on this exact string."
    )
    # Cauda-equina labels (saddle_anesthesia / bowel_bladder_dysfunction /
    # acute_urinary_retention) come from her clinical-note text — those land
    # in PR-B alongside the DocumentReference extractor.
    assert "saddle_anesthesia" not in labels
    assert ctx.coverage.payer_id == "aetna"
