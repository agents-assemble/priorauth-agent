"""Parse + invariant + representative-case tests for `mcp_server.criteria`.

Golden-file-style checks that the Cigna and Aetna JSONs:
1. Parse against the Pydantic schema (catches extra fields, bad enums,
   non-canonical TherapyKind strings).
2. Carry the corrections surfaced in PR #6's verification pass
   (Aetna canonical www URL, no ICD-10 exclusions for lumbar MRI).
3. Support the expected case discrimination that the Week-2 rule engine
   will implement (Patient A/B/C style trial sets + red-flag matches).

No rule engine runs here — these are data-shape assertions only.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import get_args

import pytest
from _pytest.monkeypatch import MonkeyPatch
from mcp_server.criteria import (
    SCHEMA_VERSION,
    CriteriaNotFoundError,
    CriteriaSchemaMismatchError,
    PayerCriteria,
    load_payer_criteria,
    registered_payer_ids,
)
from mcp_server.criteria import loader as criteria_loader
from mcp_server.criteria.schema import TherapyKind
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Registry + parse
# ---------------------------------------------------------------------------


def test_registered_payers_are_cigna_and_aetna() -> None:
    assert registered_payer_ids() == ["aetna", "cigna"]


@pytest.mark.parametrize("payer_id", ["cigna", "aetna"])
def test_payer_criteria_parses(payer_id: str) -> None:
    criteria = load_payer_criteria(payer_id)
    assert isinstance(criteria, PayerCriteria)
    assert criteria.payer_id == payer_id
    assert criteria.schema_version == SCHEMA_VERSION
    assert criteria.last_verified == "2026-04-23"
    assert "72148" in criteria.service.cpt_codes


def test_loader_raises_for_unknown_payer() -> None:
    with pytest.raises(CriteriaNotFoundError):
        load_payer_criteria("unitedhealthcare")


def test_loader_raises_on_schema_version_mismatch(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Simulate a future migration by patching the registry to point at a fake file."""
    bad = tmp_path / "fake.json"
    bad.write_text(json.dumps({"schema_version": "v999-future"}), encoding="utf-8")

    class _FakePkg:
        def __truediv__(self, _name: str) -> Path:
            return bad

    monkeypatch.setattr(criteria_loader, "_PAYER_FILES", {"fake": "fake.json"})
    monkeypatch.setattr("mcp_server.criteria.loader.resources.files", lambda _pkg: _FakePkg())

    with pytest.raises(CriteriaSchemaMismatchError):
        criteria_loader.load_payer_criteria("fake")


def test_extra_fields_are_rejected() -> None:
    """Schema uses `extra='forbid'` — a stray top-level key must fail validation."""
    good = load_payer_criteria("cigna").model_dump()
    good["bogus_field"] = "should-fail"
    with pytest.raises(ValidationError):
        PayerCriteria.model_validate(good)


# ---------------------------------------------------------------------------
# Taxonomy invariants
# ---------------------------------------------------------------------------


def test_canonical_therapy_kinds_count_matches_research_doc() -> None:
    """The taxonomy frozen in the research doc has 13 normalized kinds."""
    assert len(get_args(TherapyKind)) == 13


@pytest.mark.parametrize("payer_id", ["cigna", "aetna"])
def test_all_accepted_kinds_are_canonical(payer_id: str) -> None:
    """Literal[] in schema already enforces this, but assert explicitly for legibility."""
    canonical = set(get_args(TherapyKind))
    criteria = load_payer_criteria(payer_id)
    assert set(criteria.conservative_therapy.accepted_kinds).issubset(canonical)


def test_gabapentinoid_is_not_accepted_by_either_payer() -> None:
    """Per `docs/payer_criteria_research.md` §Normalized taxonomy: neither policy names
    gabapentinoids, flagged as clinician-review gap. JSONs must not smuggle it in."""
    for payer_id in ("cigna", "aetna"):
        criteria = load_payer_criteria(payer_id)
        assert "GABAPENTINOID" not in criteria.conservative_therapy.accepted_kinds


# ---------------------------------------------------------------------------
# PR #6 verification-pass corrections
# ---------------------------------------------------------------------------


def test_aetna_source_url_is_canonical_www_not_es_mirror() -> None:
    """Per PR #6 Aetna canonical-URL verification log: use www.aetna.com, not es.aetna.com."""
    aetna = load_payer_criteria("aetna")
    assert aetna.source_policy_url.startswith("https://www.aetna.com/")
    assert "es.aetna.com" not in aetna.source_policy_url


def test_aetna_has_no_icd_exclusions_for_lumbar_mri() -> None:
    """Per PR #6 correction: CPB 0236's only ICD-10 exclusion (R40.20-R40.2444 Coma) is
    scoped to cervical MRI after normal cervical CT and does NOT apply to lumbar MRI.
    Z-code exclusions cited in the original research were BoneMRI-scoped, not main policy.
    """
    aetna = load_payer_criteria("aetna")
    assert aetna.coverage_gating.excluded_icd_patterns == []
    assert aetna.coverage_gating.excluded_scope is None


def test_cigna_source_url_is_evicore_v1_0_2026_pdf() -> None:
    cigna = load_payer_criteria("cigna")
    assert "evicore.com" in cigna.source_policy_url
    assert "V1.0.2026" in cigna.source_policy_url
    assert cigna.policy_version == "V1.0.2026"
    assert cigna.policy_effective_date == "2026-02-03"


# ---------------------------------------------------------------------------
# Conservative-therapy pathways (engine branches on these)
# ---------------------------------------------------------------------------


def test_cigna_has_single_6wk_default_pathway() -> None:
    cigna = load_payer_criteria("cigna")
    pathways = cigna.conservative_therapy.pathways
    assert len(pathways) == 1
    (only,) = pathways
    assert only.applies_when == "default"
    assert only.weeks == 6


def test_aetna_has_both_4wk_and_6wk_pathways() -> None:
    """Aetna's two time-thresholded bullets: radiculopathy 6wk + spondylolisthesis/DDD 4wk."""
    aetna = load_payer_criteria("aetna")
    by_trigger = {p.applies_when: p for p in aetna.conservative_therapy.pathways}
    assert by_trigger["has_radiculopathy"].weeks == 6
    assert by_trigger["has_spondylolisthesis_or_ddd"].weeks == 4
    assert "default" not in by_trigger


# ---------------------------------------------------------------------------
# Red-flag catalog
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payer_id", ["cigna", "aetna"])
def test_cauda_equina_red_flag_present(payer_id: str) -> None:
    """Patient C's red-flag fast-track depends on this matching under both payers."""
    criteria = load_payer_criteria(payer_id)
    all_labels: set[str] = set()
    for rf in criteria.red_flags:
        all_labels.update(rf.canonical_labels)
    assert "cauda_equina_syndrome" in all_labels


@pytest.mark.parametrize("payer_id", ["cigna", "aetna"])
def test_fracture_and_infection_red_flags_present(payer_id: str) -> None:
    """Two other universal red-flag categories both payers agree on."""
    criteria = load_payer_criteria(payer_id)
    all_labels: set[str] = set()
    for rf in criteria.red_flags:
        all_labels.update(rf.canonical_labels)
    assert "fracture" in all_labels
    assert "spinal_infection" in all_labels


def test_red_flag_ids_are_unique_within_each_payer() -> None:
    for payer_id in ("cigna", "aetna"):
        criteria = load_payer_criteria(payer_id)
        ids = [rf.id for rf in criteria.red_flags]
        assert len(ids) == len(set(ids)), f"Duplicate red_flag ids in {payer_id}: {ids}"


# ---------------------------------------------------------------------------
# Representative-case discrimination previews (Patient A / B / C shape)
# ---------------------------------------------------------------------------


def test_patient_a_style_trial_set_has_matching_kinds_under_both_payers() -> None:
    """Patient A: NSAID (naproxen) + MUSCLE_RELAXANT (cyclobenzaprine) + PHYSICAL_THERAPY.

    Under Cigna: all three kinds accepted.
    Under Aetna: NSAID + MUSCLE_RELAXANT accepted; PT not named in footnote.
    Either way, ≥1 kind matches → satisfies `min_kinds_count: 1` for v1.
    """
    patient_a_kinds = {"NSAID", "MUSCLE_RELAXANT", "PHYSICAL_THERAPY"}

    cigna = load_payer_criteria("cigna")
    assert patient_a_kinds & set(cigna.conservative_therapy.accepted_kinds)

    aetna = load_payer_criteria("aetna")
    aetna_accepted = set(aetna.conservative_therapy.accepted_kinds)
    assert "NSAID" in aetna_accepted
    assert "MUSCLE_RELAXANT" in aetna_accepted
    assert "PHYSICAL_THERAPY" not in aetna_accepted  # footnote does not name PT


def test_patient_b_self_directed_home_exercise_rejected_by_cigna() -> None:
    """Patient B: NSAID only + self-directed YouTube stretches.

    Cigna lists HOME_EXERCISE but requires it be provider-directed — the JSON's notes
    field captures that; the rule engine enforces the gate. Aetna doesn't name
    HOME_EXERCISE at all. Either way, a self-directed stretch trial should NOT be
    treated as adding a qualifying kind; the NSAID alone is the only counting trial.
    """
    cigna = load_payer_criteria("cigna")
    assert "provider-directed" in cigna.conservative_therapy.notes.lower()

    aetna = load_payer_criteria("aetna")
    assert "HOME_EXERCISE" not in aetna.conservative_therapy.accepted_kinds


def test_patient_c_red_flag_label_matches_under_both_payers() -> None:
    """Patient C: acute cauda equina. Extractor produces a red_flag_candidate with label
    `cauda_equina_syndrome`. Both payers' red-flag catalogs must recognize this label."""
    candidate_label = "cauda_equina_syndrome"
    for payer_id in ("cigna", "aetna"):
        criteria = load_payer_criteria(payer_id)
        matched = [rf for rf in criteria.red_flags if candidate_label in rf.canonical_labels]
        assert matched, f"No {payer_id} red flag matches {candidate_label!r}"


# ---------------------------------------------------------------------------
# Ensure the JSON files themselves are valid JSON (belt + suspenders with loader)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    [
        "cigna_evicore_lumbar_mri.v1_0_2026.json",
        "aetna_lumbar_mri.v2026.json",
    ],
)
def test_json_file_is_valid_json(filename: str) -> None:
    raw = (resources.files("mcp_server.criteria.data") / filename).read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert parsed["schema_version"] == SCHEMA_VERSION
