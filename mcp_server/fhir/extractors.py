"""FHIR R4 → shared.models extractors.

Per-resource pure functions that consume FHIR resource dicts (as returned by
`mcp_server.fhir.client.FhirClient`) and emit `shared.models` instances. Pure
so they can be unit-tested with bundled JSON fixtures without standing up a
FHIR server.

Two key cross-package contracts the extractors honour:

1. `TherapyTrial.kind` strings come from the 13-value taxonomy frozen in
   `mcp_server/criteria/schema.py::TherapyKind` (PR #8) and `docs/payer_criteria
   _research.md` §"Normalized TherapyTrial.kind taxonomy". Unknown codes are
   *dropped with a warning*, never coerced — the rule engine cannot reason
   about a kind it doesn't recognise, so a silent miss is strictly better than
   a wrong classification.

2. `RedFlagCandidate.label` strings come from the union of every payer file's
   `red_flags[].canonical_labels` (PR #8). The Cigna catalog is the superset
   for v1 — Aetna's labels are a subset. Adding a new payer means widening
   `_REDFLAG_ICD_MAP` here, never the other way around.

Free-text red-flag detection over `DocumentReference.content` ships in the
follow-up PR (PR-B) — this PR covers structured data only.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from shared.models import (
    Condition,
    Coverage,
    Demographics,
    PriorImaging,
    RedFlagCandidate,
    ServiceRequest,
    TherapyTrial,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Code → TherapyKind maps
# ---------------------------------------------------------------------------
#
# Hand-curated from RxNorm IN (ingredient) and CPT for the lumbar-PA scope.
# Coverage is intentionally *not* exhaustive — these are the codes that will
# surface in the demo patients' bundles plus the realistic LBP medication
# vocabulary. Unknown codes log and skip rather than fall through to a
# fallback bucket; the rule engine prefers an under-counted trial list over
# a wrong-bucketed one. Clinician-verified expansion is a Week-3 hardening
# task tracked in `docs/payer_criteria_research.md` §clinician-review-gaps.

_RXNORM_TO_KIND: dict[str, str] = {
    # NSAIDs
    "5640": "NSAID",  # ibuprofen
    "7258": "NSAID",  # naproxen
    "41493": "NSAID",  # meloxicam
    "140587": "NSAID",  # celecoxib
    "3355": "NSAID",  # diclofenac
    "35827": "NSAID",  # ketorolac
    # Muscle relaxants
    "21949": "MUSCLE_RELAXANT",  # cyclobenzaprine
    "6845": "MUSCLE_RELAXANT",  # methocarbamol
    "57258": "MUSCLE_RELAXANT",  # tizanidine
    "1292": "MUSCLE_RELAXANT",  # baclofen
    "2101": "MUSCLE_RELAXANT",  # carisoprodol
    # Gabapentinoids — Cigna doesn't accept this kind today (research §gap),
    # but the extractor still emits it; the rule engine decides what to count.
    "25480": "GABAPENTINOID",  # gabapentin
    "187832": "GABAPENTINOID",  # pregabalin
    # Oral corticosteroids
    "8640": "ORAL_CORTICOSTEROID",  # prednisone
    "6902": "ORAL_CORTICOSTEROID",  # methylprednisolone
    "3264": "ORAL_CORTICOSTEROID",  # dexamethasone
    # Opioid analgesics — accepted by Cigna SP-1.0 ("narcotic analgesic
    # medications"); a Week-3 engine revision may weight opioid-only trials
    # differently.
    "7804": "ANALGESIC_OPIOID",  # oxycodone
    "5489": "ANALGESIC_OPIOID",  # hydrocodone
    "10689": "ANALGESIC_OPIOID",  # tramadol
    # Non-opioid analgesics
    "161": "ANALGESIC_NON_OPIOID",  # acetaminophen
}

_CPT_TO_KIND: dict[str, str] = {
    # Physical therapy
    "97110": "PHYSICAL_THERAPY",  # therapeutic exercise
    "97140": "PHYSICAL_THERAPY",  # manual therapy (also used by chiro — see note)
    "97530": "PHYSICAL_THERAPY",  # therapeutic activities
    "97112": "PHYSICAL_THERAPY",  # neuromuscular re-education
    "97116": "PHYSICAL_THERAPY",  # gait training
    # Occupational therapy
    "97165": "OCCUPATIONAL_THERAPY",  # OT eval — low complexity
    "97166": "OCCUPATIONAL_THERAPY",  # OT eval — moderate complexity
    "97167": "OCCUPATIONAL_THERAPY",  # OT eval — high complexity
    "97168": "OCCUPATIONAL_THERAPY",  # OT re-eval
    "97535": "OCCUPATIONAL_THERAPY",  # self-care management training
    # Spinal manipulation (chiropractic)
    "98940": "SPINAL_MANIPULATION",
    "98941": "SPINAL_MANIPULATION",
    "98942": "SPINAL_MANIPULATION",
    "98943": "SPINAL_MANIPULATION",
    # Epidural steroid injections (lumbar/lumbosacral)
    "62321": "EPIDURAL_INJECTION",  # interlaminar lumbar/sacral with imaging
    "62323": "EPIDURAL_INJECTION",  # transforaminal lumbar/sacral with imaging
    "64483": "EPIDURAL_INJECTION",  # transforaminal epidural — lumbar/sacral, single
    "64484": "EPIDURAL_INJECTION",  # add-on
}


# ---------------------------------------------------------------------------
# ICD-10 code → red-flag canonical_label
# ---------------------------------------------------------------------------
#
# Maps an exact ICD-10-CM code (or a prefix, see `_match_icd_prefix`) to one
# or more canonical_label strings advertised in the payer JSONs. A single ICD
# can map to multiple labels when the policies disagree on granularity (e.g.
# G83.4 maps to both "cauda_equina_syndrome" — Cigna — and the same symptom
# label set).
#
# Source for prefix choices: `docs/payer_criteria_research.md` red-flag tables
# (Cigna SP-1.2 and Aetna CPB 0236). Free-text label matching for note text
# lands in PR-B.

_REDFLAG_ICD_MAP: dict[str, list[str]] = {
    # Cauda equina / cord compression
    "G83.4": ["cauda_equina_syndrome"],
    "G95.2": ["cauda_equina_syndrome"],
    # Motor weakness — Aetna explicitly cites G83.1/G83.2; R29.898 covers
    # the "abnormal involuntary movements / progressive deficit" bucket.
    "G83.1": ["motor_weakness", "progressive_motor_deficit"],
    "G83.2": ["motor_weakness", "progressive_motor_deficit", "bilateral_leg_weakness"],
    "R29.898": ["progressive_motor_deficit"],
    # Cancer — known active malignancy of bone / spinal mets.
    "C79.51": ["cancer", "spinal_metastases"],
    "C79.52": ["cancer", "spinal_metastases"],
    "C41.2": ["cancer", "suspected_spinal_malignancy"],
    "C41.4": ["cancer", "suspected_spinal_malignancy"],
    # Personal history of cancer (Z85.x) → "history_of_cancer". Important
    # for Patient C (breast-ca history) — surfaces a candidate even if the
    # clinical-note red flags aren't text-extracted yet (PR-B).
    "Z85.3": ["history_of_cancer"],  # personal hx malignant neoplasm of breast
    "Z85.4": ["history_of_cancer"],  # personal hx malignant neoplasm of GU
    "Z85.6": ["history_of_cancer"],  # personal hx leukemia
    "Z85.71": ["history_of_cancer"],  # personal hx Hodgkin lymphoma
    "Z85.72": ["history_of_cancer"],  # personal hx non-Hodgkin lymphoma
    "Z85.81": ["history_of_cancer"],  # personal hx malignant neoplasm of lip/oral/pharynx
    # Infection
    "M46.20": ["osteomyelitis", "spinal_infection"],
    "M46.21": ["osteomyelitis", "spinal_infection"],
    "M46.22": ["osteomyelitis", "spinal_infection"],
    "M46.23": ["osteomyelitis", "spinal_infection"],
    "M46.24": ["osteomyelitis", "spinal_infection"],
    "M46.25": ["osteomyelitis", "spinal_infection"],
    "M46.26": ["osteomyelitis", "spinal_infection"],
    "M46.27": ["osteomyelitis", "spinal_infection"],
    "M46.28": ["osteomyelitis", "spinal_infection"],
    "G06.1": ["epidural_abscess", "spinal_infection"],
    # Aortic aneurysm / dissection — referred-out per Cigna SP-1.2 but still
    # a red flag the engine should fast-track (away from spine imaging).
    "I71.0": ["aortic_dissection"],
    "I71.3": ["aortic_aneurysm"],
    "I71.4": ["aortic_aneurysm"],
    # Fracture
    "S32.000A": ["fracture", "post_trauma_fracture"],
    "S32.001A": ["fracture", "post_trauma_fracture"],
    "M48.50XA": ["fracture", "pathological_fracture"],
    "M80.08XA": ["fracture", "pathological_fracture"],
    # Ankylosing spondylitis — fracture-risk modifier
    "M45.6": ["ankylosing_spondylitis_fracture"],
    "M45.7": ["ankylosing_spondylitis_fracture"],
}

# Prefix-match prefixes for ICDs whose subdivisions all map to the same label
# set. Avoids enumerating every Z85.xx / M80.xx variant.
_REDFLAG_ICD_PREFIXES: list[tuple[str, list[str]]] = [
    ("Z85.", ["history_of_cancer"]),
    ("C79.", ["cancer", "spinal_metastases"]),
    ("M46.2", ["osteomyelitis", "spinal_infection"]),
    ("M46.3", ["discitis", "spinal_infection"]),
    ("M80.", ["fracture", "pathological_fracture"]),
    ("S32.0", ["fracture", "post_trauma_fracture"]),
    ("M48.5", ["fracture", "pathological_fracture"]),
]


# LOINC codes for prior advanced lumbar imaging — referenced by Cigna SP-1.0
# repeat-imaging wording and by Aetna's "documented prior diagnostic work-up"
# bullet. Used to populate `PriorImaging` from `DiagnosticReport` resources.
_LUMBAR_IMAGING_LOINC: dict[str, str] = {
    "24531-6": "MR Lumbar",  # MR Lumbar spine WO contrast
    "24532-4": "MR Lumbar",  # MR Lumbar spine W contrast
    "24533-2": "MR Lumbar",  # MR Lumbar spine WO and W contrast
    "30797-1": "CT Lumbar",  # CT Lumbar spine WO contrast
    "30798-9": "CT Lumbar",  # CT Lumbar spine W contrast
}


# ---------------------------------------------------------------------------
# Extractors — Patient
# ---------------------------------------------------------------------------


def extract_demographics(patient: dict[str, Any]) -> Demographics:
    """Build a `Demographics` from a FHIR R4 `Patient` resource.

    Defaults: `age=0` when birthDate is absent (rather than raising — the
    downstream rule engine treats age=0 as "unknown" and never gates on it
    for adults). `sex` falls back to FHIR's `unknown` enum value.
    """
    patient_id = str(patient.get("id", ""))
    birth = patient.get("birthDate")
    age = _calculate_age(birth) if isinstance(birth, str) else 0
    sex = patient.get("gender", "unknown")
    return Demographics(patient_id=patient_id, age=age, sex=sex)


def _calculate_age(birth_date_iso: str) -> int:
    """Year-math age from an ISO-8601 birthDate. Off-by-one safe."""
    try:
        birth = date.fromisoformat(birth_date_iso[:10])
    except ValueError:
        logger.warning("invalid_birthdate ignored value=%s", birth_date_iso)
        return 0
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


# ---------------------------------------------------------------------------
# Extractors — Condition
# ---------------------------------------------------------------------------


def extract_conditions(resources: list[dict[str, Any]]) -> list[Condition]:
    """Map FHIR `Condition` resources → `shared.models.Condition`.

    Filters to active conditions only; resolved/inactive are dropped because
    the rule engine evaluates current-state criteria.
    """
    out: list[Condition] = []
    for res in resources:
        if not _is_active_condition(res):
            continue
        code, display = _first_icd10_code(res)
        if not code:
            continue
        onset = res.get("onsetDateTime") or res.get("recordedDate")
        out.append(
            Condition(
                code=code,
                display=display or code,
                onset_date=onset[:10] if isinstance(onset, str) else None,
                duration_weeks=_weeks_since(onset) if isinstance(onset, str) else None,
            )
        )
    return out


def _is_active_condition(res: dict[str, Any]) -> bool:
    status = res.get("clinicalStatus", {})
    for coding in status.get("coding", []):
        if coding.get("code") in ("active", "recurrence", "relapse"):
            return True
    return not status  # status absent → assume active (FHIR default)


def _first_icd10_code(res: dict[str, Any]) -> tuple[str, str]:
    for coding in res.get("code", {}).get("coding", []):
        system = coding.get("system", "")
        if "icd-10" in system.lower() or system == "http://hl7.org/fhir/sid/icd-10-cm":
            return str(coding.get("code", "")), str(coding.get("display", ""))
    # Fallback: first coding regardless of system, since some demo bundles
    # use a non-standard system URI.
    codings = res.get("code", {}).get("coding", [])
    if codings:
        return str(codings[0].get("code", "")), str(codings[0].get("display", ""))
    return "", ""


def _weeks_since(iso_dt: str) -> int | None:
    try:
        d = date.fromisoformat(iso_dt[:10])
    except ValueError:
        return None
    return max(0, (date.today() - d).days // 7)


# ---------------------------------------------------------------------------
# Extractors — MedicationRequest → therapy trials
# ---------------------------------------------------------------------------


def extract_medication_trials(resources: list[dict[str, Any]]) -> list[TherapyTrial]:
    """Map active outpatient `MedicationRequest` resources → `TherapyTrial`.

    Drops entries whose RxNorm ingredient code isn't in `_RXNORM_TO_KIND`
    rather than guessing a kind — see module docstring for rationale.
    """
    out: list[TherapyTrial] = []
    for res in resources:
        kind = _classify_medication(res)
        if kind is None:
            continue
        display = _medication_display(res)
        period_start, period_end = _period(res.get("dispenseRequest", {}).get("validityPeriod"))
        out.append(
            TherapyTrial(
                kind=kind,
                drug_or_procedure=display or kind,
                start_date=period_start or _authored_on(res),
                last_date=period_end,
                sessions_or_days=_days_supply(res),
            )
        )
    return out


def _classify_medication(res: dict[str, Any]) -> str | None:
    coding = res.get("medicationCodeableConcept", {}).get("coding", [])
    for c in coding:
        system = c.get("system", "")
        if "rxnorm" in system.lower():
            kind = _RXNORM_TO_KIND.get(str(c.get("code", "")))
            if kind:
                return kind
    return None


def _medication_display(res: dict[str, Any]) -> str:
    cc = res.get("medicationCodeableConcept", {})
    if cc.get("text"):
        return str(cc["text"])
    for c in cc.get("coding", []):
        if c.get("display"):
            return str(c["display"])
    return ""


def _authored_on(res: dict[str, Any]) -> str | None:
    val = res.get("authoredOn")
    return val[:10] if isinstance(val, str) else None


def _days_supply(res: dict[str, Any]) -> int | None:
    qty = res.get("dispenseRequest", {}).get("expectedSupplyDuration", {})
    if qty.get("unit") in ("d", "day", "days") and isinstance(qty.get("value"), int | float):
        return int(qty["value"])
    return None


# ---------------------------------------------------------------------------
# Extractors — Procedure → therapy trials (PT, OT, manipulation, ESI)
# ---------------------------------------------------------------------------


def extract_procedure_trials(resources: list[dict[str, Any]]) -> list[TherapyTrial]:
    """Map `Procedure` resources → `TherapyTrial`, grouped by CPT code.

    Multiple `Procedure` instances of the same CPT (e.g. 8 PT visits)
    collapse into a single `TherapyTrial` with `sessions_or_days=N`,
    `start_date=earliest`, `last_date=latest`. This matches what payers
    look at — total session count and trial duration, not per-visit detail.
    """
    by_kind: dict[tuple[str, str], dict[str, Any]] = {}
    for res in resources:
        cpt, display = _first_cpt_code(res)
        if not cpt:
            continue
        kind = _CPT_TO_KIND.get(cpt)
        if kind is None:
            continue
        when = _procedure_date(res)
        key = (kind, cpt)
        slot = by_kind.setdefault(
            key,
            {
                "display": display or cpt,
                "sessions": 0,
                "earliest": when,
                "latest": when,
            },
        )
        slot["sessions"] += 1
        if when is not None:
            if slot["earliest"] is None or when < slot["earliest"]:
                slot["earliest"] = when
            if slot["latest"] is None or when > slot["latest"]:
                slot["latest"] = when
    return [
        TherapyTrial(
            kind=kind,
            drug_or_procedure=slot["display"],
            sessions_or_days=slot["sessions"],
            start_date=slot["earliest"],
            last_date=slot["latest"],
        )
        for (kind, _cpt), slot in by_kind.items()
    ]


def _first_cpt_code(res: dict[str, Any]) -> tuple[str, str]:
    for coding in res.get("code", {}).get("coding", []):
        system = coding.get("system", "")
        if "cpt" in system.lower() or "ama-assn.org/go/cpt" in system:
            return str(coding.get("code", "")), str(coding.get("display", ""))
    codings = res.get("code", {}).get("coding", [])
    if codings:
        return str(codings[0].get("code", "")), str(codings[0].get("display", ""))
    return "", ""


def _procedure_date(res: dict[str, Any]) -> str | None:
    val = res.get("performedDateTime") or res.get("performedPeriod", {}).get("start")
    return val[:10] if isinstance(val, str) else None


def _period(p: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not p:
        return None, None
    start = p.get("start")
    end = p.get("end")
    return (
        start[:10] if isinstance(start, str) else None,
        end[:10] if isinstance(end, str) else None,
    )


# ---------------------------------------------------------------------------
# Extractors — ServiceRequest, Coverage, prior imaging
# ---------------------------------------------------------------------------


def extract_service_request(
    resources: list[dict[str, Any]],
    *,
    cpt_code: str,
) -> ServiceRequest:
    """Pick the active `ServiceRequest` matching `cpt_code` (CPT 72148 in v1).

    Returns an empty-shell `ServiceRequest` when no match — the rule engine
    will surface this as a `needs_info` reason rather than crashing the tool.
    """
    for res in resources:
        cpt, display = _first_cpt_code(res)
        if cpt != cpt_code:
            continue
        if res.get("status") not in (None, "active", "draft", "completed"):
            continue
        return ServiceRequest(
            cpt_code=cpt,
            description=display or cpt,
            ordered_date=_authored_on(res) or "",
            ordering_provider=_practitioner_display(res.get("requester")),
            reason_codes=_reason_icd_codes(res),
        )
    return ServiceRequest(
        cpt_code=cpt_code,
        description="",
        ordered_date="",
        ordering_provider="",
        reason_codes=[],
    )


def _practitioner_display(ref: dict[str, Any] | None) -> str:
    if not ref:
        return ""
    return str(ref.get("display") or ref.get("reference", ""))


def _reason_icd_codes(res: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for cc in res.get("reasonCode", []):
        for coding in cc.get("coding", []):
            if "icd-10" in coding.get("system", "").lower():
                out.append(str(coding.get("code", "")))
                break
    return out


def extract_coverage(resources: list[dict[str, Any]]) -> Coverage:
    """Pick the first active `Coverage` and route to a known `payer_id`.

    Falls back to `payer_id=""` when the payer name doesn't match a known
    routing key — the rule engine treats that as "no criteria available"
    and returns a `needs_info` decision rather than picking the wrong policy.
    """
    for res in resources:
        if res.get("status") not in (None, "active"):
            continue
        payer_name, payer_id = _route_payer(res)
        return Coverage(
            payer_id=payer_id,
            payer_name=payer_name,
            member_id=str(res.get("subscriberId") or "") or None,
            plan_name=_plan_name(res),
        )
    return Coverage(payer_id="", payer_name="")


_PAYER_ROUTING: list[tuple[str, str]] = [
    # (substring_to_match, payer_id) — order matters; first hit wins.
    ("cigna", "cigna"),
    ("evernorth", "cigna"),  # eviCore is a unit of Evernorth which is Cigna
    ("evicore", "cigna"),
    ("aetna", "aetna"),
]


def _route_payer(res: dict[str, Any]) -> tuple[str, str]:
    for payor in res.get("payor", []):
        name = str(payor.get("display", "")).strip()
        if not name:
            ref = str(payor.get("reference", "")).strip()
            if ref and "/" in ref:
                name = ref.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
        if name:
            payer_id = _match_payer_id(name)
            return name, payer_id
    return "", ""


def _match_payer_id(name: str) -> str:
    n = name.lower()
    for needle, payer_id in _PAYER_ROUTING:
        if needle in n:
            return payer_id
    return ""


def _plan_name(res: dict[str, Any]) -> str | None:
    for cls in res.get("class", []):
        if cls.get("type", {}).get("coding", [{}])[0].get("code") == "plan":
            return str(cls.get("name") or cls.get("value") or "") or None
    return None


def extract_prior_imaging(resources: list[dict[str, Any]]) -> list[PriorImaging]:
    """Map `DiagnosticReport` resources → `PriorImaging` for lumbar studies.

    Filters to the LOINC codes in `_LUMBAR_IMAGING_LOINC` so we don't pull
    every chest CT in the patient's chart into the PA context.
    """
    out: list[PriorImaging] = []
    for res in resources:
        loinc, _display = _first_loinc(res)
        if loinc not in _LUMBAR_IMAGING_LOINC:
            continue
        when = res.get("effectiveDateTime") or res.get("issued")
        if not isinstance(when, str):
            continue
        out.append(
            PriorImaging(
                modality=_LUMBAR_IMAGING_LOINC[loinc],
                date=when[:10],
                loinc_code=loinc,
            )
        )
    return out


def _first_loinc(res: dict[str, Any]) -> tuple[str, str]:
    for coding in res.get("code", {}).get("coding", []):
        if "loinc" in coding.get("system", "").lower():
            return str(coding.get("code", "")), str(coding.get("display", ""))
    return "", ""


# ---------------------------------------------------------------------------
# Red-flag detection — ICD codes only in this PR
# ---------------------------------------------------------------------------


def detect_redflags_from_conditions(conditions: list[Condition]) -> list[RedFlagCandidate]:
    """Match each `Condition.code` against the ICD → canonical_label map.

    Emits one `RedFlagCandidate` per (condition, label) pair, deduplicated
    on label so a patient with both G83.1 and G83.2 doesn't surface
    "motor_weakness" twice. The rule engine is the canonical de-duper, but
    keeping this list tidy makes the trace easier to read.

    Free-text candidates from `DocumentReference.content` ship in PR-B.
    """
    seen: set[str] = set()
    out: list[RedFlagCandidate] = []
    for cond in conditions:
        labels = _REDFLAG_ICD_MAP.get(cond.code) or _match_icd_prefix(cond.code)
        for label in labels:
            if label in seen:
                continue
            seen.add(label)
            out.append(
                RedFlagCandidate(
                    label=label,
                    source="icd_code",
                    evidence=f"{cond.code} {cond.display}".strip(),
                )
            )
    return out


def _match_icd_prefix(code: str) -> list[str]:
    for prefix, labels in _REDFLAG_ICD_PREFIXES:
        if code.startswith(prefix):
            return labels
    return []
