"""End-to-end test of `fetch_patient_context`'s real-FHIR fan-out path.

Uses `httpx.MockTransport` (stdlib-included) to wire a fake FHIR server to
the same `httpx.AsyncClient` that production code uses, so the test exercises
the complete code path:

  `_fetch_from_fhir` → `FhirClient.read/search` → `httpx.AsyncClient.get`
                     → MockTransport → JSON dict → extractors + notes
                     → PatientContext

Three demo patients are encoded inline (structured FHIR + a base64-encoded
DocumentReference per patient pulled from `demo/clinical_notes/*.md`):

- `patient-a`: 47F happy path. 12 wks LBP + 8 PT visits + NSAID + muscle
  relaxant. Note explicitly denies all red flags. Expect APPROVE-shaped
  PatientContext: full therapy history, zero red-flag candidates from
  either ICD codes or note text.
- `patient-b`: 52M needs-info. NSAID OK, only 1 PT eval visit (incomplete
  course). Note reports no red flags. Expect needs-info-shaped (NSAID
  present, PT trial under-counted), zero red flags.
- `patient-c`: 61F red-flag fast-track. Active LBP + Z85.3 breast-ca
  history → `history_of_cancer` from ICD. Note presents textbook cauda
  equina → `cauda_equina_syndrome`, `saddle_anesthesia`,
  `bowel_bladder_dysfunction`, `acute_urinary_retention` from text.
  Combined set drives the red-flag fast-track decision the engine will
  make in Week 2.

Why we don't assert on the rule-engine *decision* here: the rule engine
ships in Week 2. These tests pin the *PatientContext shape* the engine
will receive — that's the cross-tool contract we're protecting.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from mcp_server.fhir.context import FhirContext
from mcp_server.tools.fetch_patient_context import _fetch_from_fhir

FHIR_BASE = "https://fhir.example.com/r4"
TOKEN = "fake-token-for-tests"  # test fixture, not a real secret

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_NOTES_DIR = REPO_ROOT / "demo" / "clinical_notes"


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


def _doc_ref(stem: str, *, when: str = "2026-04-15T14:32:00-07:00") -> dict[str, Any]:
    """Build a DocumentReference whose inline content is the demo `.md` file."""
    note_text = (DEMO_NOTES_DIR / f"{stem}.md").read_text(encoding="utf-8")
    return {
        "resourceType": "DocumentReference",
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "11506-3",
                    "display": "Progress note",
                }
            ]
        },
        "subject": {"reference": f"Patient/{stem.replace('_', '-')}"},
        "date": when,
        "content": [
            {
                "attachment": {
                    "contentType": "text/markdown",
                    "data": base64.b64encode(note_text.encode("utf-8")).decode("ascii"),
                }
            }
        ],
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
        (
            "DocumentReference",
            "patient=patient-a&type=http://loinc.org|11506-3",
        ): _bundle(_doc_ref("patient_a")),
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
        (
            "DocumentReference",
            "patient=patient-b&type=http://loinc.org|11506-3",
        ): _bundle(_doc_ref("patient_b")),
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
        (
            "DocumentReference",
            "patient=patient-c&type=http://loinc.org|11506-3",
        ): _bundle(_doc_ref("patient_c")),
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

    # Two active conditions extracted; no red flags from EITHER ICD codes
    # OR note text (Patient A's note explicitly denies them, and the
    # detector's negation/educational-marker logic suppresses the
    # "patient educated on red-flag symptoms (saddle numbness, ...)"
    # phrasing in the Plan section.
    assert {c.code for c in ctx.active_conditions} == {"M54.50", "M54.16"}
    assert ctx.red_flag_candidates == [], (
        "Patient A is the regression bound for the negation logic - "
        "any new pattern that fires here is a bug."
    )

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

    # Compressed excerpt populated from the DocumentReference. PR #4 review
    # follow-up #2: NSAID and muscle-relaxant trials must remain
    # distinguishable in the excerpt, not collapsed into one phrase.
    excerpt_lower = ctx.clinical_notes_excerpt.lower()
    assert "naproxen" in excerpt_lower
    assert "cyclobenzaprine" in excerpt_lower
    assert len(ctx.clinical_notes_excerpt) <= 3000


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
    assert ctx.red_flag_candidates == [], (
        "Patient B's note states 'No red flags' explicitly. Detector must "
        "emit zero from the text, and ICD codes alone (M54.50) carry none."
    )

    # Excerpt should still document the NSAID trial and the PT no-show
    # gap - both are needed for the LLM letter-writer to produce a
    # credible needs-info request that asks for completion of supervised PT.
    excerpt_lower = ctx.clinical_notes_excerpt.lower()
    assert "ibuprofen" in excerpt_lower
    assert "no-show" in excerpt_lower or "physical therapy" in excerpt_lower


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
        "the rule engine matches on this exact string. Sourced from Z85.3."
    )
    # Cauda-equina canonical labels are now sourced from the
    # DocumentReference text via `notes.detect_redflags_from_text`. The
    # combined set is what the rule engine uses to drive a red-flag fast-
    # track APPROVE in Week 2.
    cauda_labels = {
        "saddle_anesthesia",
        "bowel_bladder_dysfunction",
        "acute_urinary_retention",
        "cauda_equina_syndrome",
    }
    missing = cauda_labels - labels
    assert not missing, (
        f"Patient C should surface every cauda-equina canonical_label from "
        f"the note text. Missing: {missing}. All labels: {sorted(labels)}"
    )
    # Each note-derived candidate must carry source='clinical_note' so the
    # reasoning trace can distinguish it from ICD-derived candidates.
    note_sources = {c.source for c in ctx.red_flag_candidates if c.label in cauda_labels}
    assert note_sources == {"clinical_note"}

    assert ctx.coverage.payer_id == "aetna"

    # Excerpt populated and includes the textbook red-flag phrasing the
    # LLM letter-writer needs to author the urgent-banner section.
    excerpt_lower = ctx.clinical_notes_excerpt.lower()
    assert "cauda equina" in excerpt_lower
    assert "saddle anesthesia" in excerpt_lower
