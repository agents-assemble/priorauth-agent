"""Golden-file tests on the three `demo/patients/*.json` FHIR bundles.

These fixtures are imported into the Prompt Opinion workspace (see
`demo/patients/README.md`) and are the reproducible substrate for the whole
PA pipeline. The tests here load each bundle and run its resources through
the structured extractors in `mcp_server.fhir.extractors`, then pin:

- Demographics shape (age / sex / id)
- Active-condition ICD set
- Therapy-trial kinds and session counts
- `ServiceRequest` CPT + requester + reason codes
- `Coverage` → `payer_id` routing
- ICD-derived red-flag candidates (none for A/B; `history_of_cancer` for C)

Free-text extraction is **not** covered here — those cases live in
`tests/mcp_server/test_notes.py` and the end-to-end
`tests/mcp_server/test_fetch_patient_context_fhir.py`.

If you edit a bundle, update the matching assertion here in the same PR.
If you want to tighten an assertion (e.g. pin an exact medication display
string), do it here rather than pushing the check down into extractor
tests — those are unit tests of the extractor function, these are contract
tests of the demo fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp_server.fhir.extractors import (
    detect_redflags_from_conditions,
    extract_conditions,
    extract_coverage,
    extract_demographics,
    extract_medication_trials,
    extract_prior_imaging,
    extract_procedure_trials,
    extract_service_request,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLES_DIR = REPO_ROOT / "demo" / "patients"


# ---------------------------------------------------------------------------
# Bundle loader + resource selector
# ---------------------------------------------------------------------------


def _load(stem: str) -> dict[str, Any]:
    """Load a bundle by filename stem (e.g. 'patient_a')."""
    path = BUNDLES_DIR / f"{stem}.json"
    parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def _resources(bundle: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    """Return every `entry[].resource` of the given `resourceType`."""
    out: list[dict[str, Any]] = []
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        if res.get("resourceType") == resource_type:
            out.append(res)
    return out


def _first(bundle: dict[str, Any], resource_type: str) -> dict[str, Any]:
    resources = _resources(bundle, resource_type)
    assert resources, f"bundle is missing a {resource_type} resource"
    return resources[0]


# ---------------------------------------------------------------------------
# Bundle structural sanity (cheap guard — catches typos before extractor runs)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stem", ["patient_a", "patient_b", "patient_c"])
def test_bundle_is_well_formed_transaction(stem: str) -> None:
    bundle = _load(stem)
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "transaction", (
        "All demo bundles are transactions so a single POST to the FHIR root "
        "imports them atomically. A switch to 'collection' or 'searchset' is a "
        "breaking change for the import path documented in demo/README.md."
    )
    entries = bundle.get("entry", [])
    assert entries, "bundle has no entries"
    # Every entry must carry both a resource (for the server to apply) and a
    # request (so the server knows how to apply it). If either is missing,
    # a real FHIR server rejects the whole transaction atomically.
    for i, entry in enumerate(entries):
        assert "resource" in entry, f"entry[{i}] missing 'resource'"
        assert "request" in entry, f"entry[{i}] missing 'request'"
        req = entry["request"]
        # Bundles use POST (create) rather than PUT (updateCreate) because
        # the Prompt Opinion workspace FHIR — and strict FHIR servers more
        # generally — have updateCreate disabled. The server assigns the
        # logical id on create; intra-bundle references are rewritten
        # server-side via fullUrl matching, so our demo-patient-a style
        # references remain stable within one transaction.
        assert req.get("method") == "POST", (
            f"entry[{i}] uses method={req.get('method')!r}; all demo bundle "
            "entries use POST so the transaction imports into FHIR servers "
            "with updateCreate disabled (the PO workspace default)."
        )


# ---------------------------------------------------------------------------
# Patient A — happy path
# ---------------------------------------------------------------------------


def test_patient_a_bundle_happy_path_full_therapy_history_no_redflags() -> None:
    bundle = _load("patient_a")

    demographics = extract_demographics(_first(bundle, "Patient"))
    assert demographics.patient_id == "demo-patient-a"
    assert demographics.sex == "female"
    assert demographics.age == 47, (
        "Patient A's DOB 1978-11-03 is tuned to yield exactly 47 at the "
        "2026-04-15 encounter AND at test-run time. If this fails and the "
        "year is 2027+, bump the DOB rather than relaxing the assertion."
    )

    conditions = extract_conditions(_resources(bundle, "Condition"))
    assert {c.code for c in conditions} == {"M54.50", "M54.16"}, (
        "Patient A's note codes LBP (M54.50) and lumbar radiculopathy (M54.16). "
        "Drift from this set breaks the happy-path demo."
    )

    med_trials = extract_medication_trials(_resources(bundle, "MedicationRequest"))
    by_kind = sorted(t.kind for t in med_trials)
    assert by_kind == ["MUSCLE_RELAXANT", "NSAID"]
    nsaid = next(t for t in med_trials if t.kind == "NSAID")
    assert "naproxen" in nsaid.drug_or_procedure.lower()
    assert nsaid.start_date == "2026-02-15"
    assert nsaid.last_date == "2026-03-29"
    relaxant = next(t for t in med_trials if t.kind == "MUSCLE_RELAXANT")
    assert "cyclobenzaprine" in relaxant.drug_or_procedure.lower()

    proc_trials = extract_procedure_trials(_resources(bundle, "Procedure"))
    pt_trials = [t for t in proc_trials if t.kind == "PHYSICAL_THERAPY"]
    assert len(pt_trials) == 1, (
        "8 individual CPT 97110 procedures must collapse into one PHYSICAL_"
        "THERAPY trial — that's the cross-extractor contract documented in "
        "extract_procedure_trials."
    )
    assert pt_trials[0].sessions_or_days == 8
    assert pt_trials[0].start_date == "2026-02-10"
    assert pt_trials[0].last_date == "2026-03-28"

    sr = extract_service_request(_resources(bundle, "ServiceRequest"), cpt_code="72148")
    assert sr.cpt_code == "72148"
    assert sr.ordered_date == "2026-04-15"
    assert "Chen" in sr.ordering_provider
    assert sorted(sr.reason_codes) == ["M54.16", "M54.50"]

    cov = extract_coverage(_resources(bundle, "Coverage"))
    assert cov.payer_id == "cigna"
    assert "Cigna" in cov.payer_name

    # Zero red flags from ICD codes — M54.50 / M54.16 are not in _REDFLAG_ICD_MAP
    # and not in any prefix entry. Keeping this empty is the happy-path's whole
    # contract with the rule engine.
    redflags = detect_redflags_from_conditions(conditions)
    assert redflags == [], f"Patient A must emit zero ICD red flags, got {redflags}"

    # No DiagnosticReport resources in the bundle → empty prior imaging. Pinned
    # here so a future reviewer who adds a chest CT (for realistic noise) gets
    # a loud failure pointing them at this comment — Patient A's story requires
    # no prior lumbar imaging on file.
    prior_imaging = extract_prior_imaging(_resources(bundle, "DiagnosticReport"))
    assert prior_imaging == []


# ---------------------------------------------------------------------------
# Patient B — needs-info
# ---------------------------------------------------------------------------


def test_patient_b_bundle_nsaid_only_single_pt_visit_no_redflags() -> None:
    bundle = _load("patient_b")

    demographics = extract_demographics(_first(bundle, "Patient"))
    assert demographics.patient_id == "demo-patient-b"
    assert demographics.sex == "male"
    assert demographics.age == 52

    conditions = extract_conditions(_resources(bundle, "Condition"))
    assert {c.code for c in conditions} == {"M54.50"}, (
        "Patient B's note codes LBP only (no radiculopathy). A second code "
        "sliding in would change the needs-info narrative."
    )

    med_trials = extract_medication_trials(_resources(bundle, "MedicationRequest"))
    nsaid_trials = [t for t in med_trials if t.kind == "NSAID"]
    assert len(nsaid_trials) == 1
    assert "ibuprofen" in nsaid_trials[0].drug_or_procedure.lower()
    # No muscle relaxant, no gabapentinoid, no opioid — this is the gap the
    # rule engine will hold against Patient B in Week 2.
    non_nsaid = [t for t in med_trials if t.kind != "NSAID"]
    assert non_nsaid == []

    proc_trials = extract_procedure_trials(_resources(bundle, "Procedure"))
    pt_trials = [t for t in proc_trials if t.kind == "PHYSICAL_THERAPY"]
    assert len(pt_trials) == 1
    assert pt_trials[0].sessions_or_days == 1, (
        "Patient B has exactly one PT visit (the intake — the three follow-ups "
        "were no-shows). The rule engine uses this exact count to fire the "
        "'incomplete PT course' needs-info reason."
    )

    sr = extract_service_request(_resources(bundle, "ServiceRequest"), cpt_code="72148")
    assert sr.cpt_code == "72148"
    assert "Rivera" in sr.ordering_provider
    assert sr.reason_codes == ["M54.50"]

    cov = extract_coverage(_resources(bundle, "Coverage"))
    assert cov.payer_id == "cigna"

    # No ICD red flags — M54.50 alone. Same guard as Patient A.
    redflags = detect_redflags_from_conditions(conditions)
    assert redflags == [], f"Patient B must emit zero ICD red flags, got {redflags}"


# ---------------------------------------------------------------------------
# Patient C — red-flag fast-track
# ---------------------------------------------------------------------------


def test_patient_c_bundle_hx_cancer_surfaces_history_of_cancer_redflag() -> None:
    bundle = _load("patient_c")

    demographics = extract_demographics(_first(bundle, "Patient"))
    assert demographics.patient_id == "demo-patient-c"
    assert demographics.sex == "female"
    assert demographics.age == 61

    conditions = extract_conditions(_resources(bundle, "Condition"))
    codes = {c.code for c in conditions}
    assert codes == {"M54.51", "Z85.3", "R32", "R33.9"}, (
        "Patient C codes: M54.51 (vertebrogenic LBP), Z85.3 (hx breast ca), "
        "R32 (urinary incontinence), R33.9 (urinary retention). G83.4 is "
        "deliberately omitted — see demo/patients/README.md 'Why G83.4 is "
        "not in Patient C's bundle' for the demo-narrative reasoning."
    )

    # No medication trials (OTC acetaminophen/ibuprofen is self-reported in the
    # note, not a prescribed MedicationRequest).
    med_trials = extract_medication_trials(_resources(bundle, "MedicationRequest"))
    assert med_trials == []

    # No procedure trials (no PT was attempted — the presentation was too
    # acute). Rule engine in Week 2 won't need any trial evidence because the
    # red-flag fast-track short-circuits conservative-therapy checks.
    proc_trials = extract_procedure_trials(_resources(bundle, "Procedure"))
    assert proc_trials == []

    sr = extract_service_request(_resources(bundle, "ServiceRequest"), cpt_code="72148")
    assert sr.cpt_code == "72148"
    assert "Patel" in sr.ordering_provider
    assert sorted(sr.reason_codes) == ["M54.51", "R32", "R33.9", "Z85.3"], (
        "All four PCP-coded reasons should propagate into reason_codes so the "
        "PA letter can cite them verbatim."
    )

    cov = extract_coverage(_resources(bundle, "Coverage"))
    assert cov.payer_id == "aetna"

    # Z85.3 → history_of_cancer is the single ICD-derived red flag. Acute cauda
    # equina / saddle anesthesia / urinary retention red flags come from the
    # free-text note in the end-to-end test, not from this structured bundle.
    redflags = detect_redflags_from_conditions(conditions)
    labels = [r.label for r in redflags]
    assert labels == ["history_of_cancer"], (
        f"Patient C must emit exactly one ICD-derived red flag "
        f"(history_of_cancer from Z85.3). Got: {labels}. Extra labels mean a "
        "new ICD code slipped into the bundle and matched _REDFLAG_ICD_MAP."
    )
    assert redflags[0].source == "icd_code"
    assert "Z85.3" in redflags[0].evidence


# ---------------------------------------------------------------------------
# ServiceRequest priority — Patient C is STAT; A and B are routine.
# Not extracted by the extractor today (the rule engine will use priority in
# Week 2 as a tiebreaker when free-text red flags are ambiguous), so we assert
# on the raw bundle to pin the intent.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stem,expected_priority",
    [
        ("patient_a", "routine"),
        ("patient_b", "routine"),
        ("patient_c", "stat"),
    ],
)
def test_service_request_priority_matches_scenario(stem: str, expected_priority: str) -> None:
    bundle = _load(stem)
    service_requests = _resources(bundle, "ServiceRequest")
    assert len(service_requests) == 1, (
        f"{stem}.json must carry exactly one ServiceRequest; got {len(service_requests)}"
    )
    actual = service_requests[0].get("priority")
    assert actual == expected_priority, (
        f"{stem}.json ServiceRequest.priority={actual!r}, expected "
        f"{expected_priority!r}. Patient C's stat flag is the only signal "
        "in the structured bundle that the case is urgent — dropping it "
        "loses the priority channel before the note-text red flags kick in."
    )
