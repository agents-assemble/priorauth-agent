"""Tool 1 - fetch_patient_context.

Given a `patient_id` + `service_code`, return a normalized `PatientContext`
ready for `match_payer_criteria` to evaluate.

This file is intentionally Week-1-scaffold tier:

- When PO propagates a SHARP FHIR context (via x-fhir-server-url +
  x-fhir-access-token headers), it performs a real `Patient/{id}` read and
  wraps the demographics into a `PatientContext`. The clinical-list fields
  (conditions, therapies, imaging, red flags) are empty placeholders for now
  - the real extraction lands in Week-2 PRs alongside the corresponding
  golden-file tests. The scaffold exists so PO registration + the round-trip
  can be verified without waiting on Week-2 extraction code.

- Without a FHIR context (local dev + curl before PO registration is live),
  it falls back to three hard-coded demo patients (A/B/C) from the plan's
  "Demo Data Strategy" section. Any unknown patient_id raises
  FhirContextError so the error path is exercised too.

Signature note: this tool takes flat `Annotated[str, Field(...)]` args
rather than a shared.models BaseModel input wrapper - MCP renders the JSON
schema directly from the signature and nested wrappers degrade the schema
ergonomics. `.cursor/rules/mcp-server.md` currently says "accepts a Pydantic
input model"; this is flagged in STATUS.md as something to reconcile in a
follow-up rule update.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

import httpx
from pydantic import Field
from shared.models import (
    Coverage,
    Demographics,
    PatientContext,
    ServiceRequest,
)

from mcp_server.fhir.client import FhirClient
from mcp_server.fhir.context import (
    FhirContextError,
    McpContext,
    get_fhir_context,
    get_patient_id_if_context_exists,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Demo fixtures - used only when no FHIR context is present (local curl dev).
# Faithful to docs/PLAN.md "Demo Data Strategy". These will move to
# `demo/patients/` as FHIR bundles in a follow-up PR.
# ---------------------------------------------------------------------------

_DEMO_SERVICE_CPT = "72148"
_DEMO_SERVICE_DESCRIPTION = "MRI Lumbar Spine without contrast"

_DEMO_PATIENTS: dict[str, PatientContext] = {
    "demo-patient-a": PatientContext(
        demographics=Demographics(patient_id="demo-patient-a", age=47, sex="female"),
        service_request=ServiceRequest(
            cpt_code=_DEMO_SERVICE_CPT,
            description=_DEMO_SERVICE_DESCRIPTION,
            ordered_date="2026-04-15",
            ordering_provider="Dr. Alice Chen, MD",
            reason_codes=["M54.50"],
        ),
        coverage=Coverage(payer_id="cigna", payer_name="Cigna HealthCare"),
        clinical_notes_excerpt=(
            "47F with 12 weeks of mechanical low back pain. Completed 8 sessions of PT and "
            "a 6-week NSAID + muscle-relaxant trial without resolution. No red flags."
        ),
    ),
}


def _calculate_age(birth_date_iso: str) -> int:
    """Year-math age from an ISO-8601 birthDate. Off-by-one safe."""
    birth = date.fromisoformat(birth_date_iso)
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


async def fetch_patient_context(
    patient_id: Annotated[
        str,
        Field(
            description=(
                "FHIR Patient.id to build context for. May be a logical id (e.g. "
                "'patient-42') or a demo id ('demo-patient-a'). If empty AND a SHARP "
                "token is present, the `patient` claim from the token is used."
            )
        ),
    ],
    service_code: Annotated[
        str,
        Field(
            description=(
                "CPT code of the service needing prior authorization. For this agent "
                "this is always '72148' (MR Lumbar w/o contrast); the parameter is "
                "kept explicit so the tool signature does not change when we expand "
                "to more services post-hackathon."
            )
        ),
    ],
    ctx: McpContext,
) -> PatientContext:
    """Return a normalized PatientContext for the requested patient + service."""
    fhir_ctx = get_fhir_context(ctx)

    # Prefer the SHARP-claimed patient id over the arg when both are present —
    # mirrors upstream PO-MCP semantics and keeps tools impossible to misuse
    # across patients by passing a rogue id.
    effective_patient_id = get_patient_id_if_context_exists(ctx) or patient_id
    logger.info(
        "fetch_patient_context patient_id=%s service_code=%s fhir_ctx=%s",
        effective_patient_id,
        service_code,
        "present" if fhir_ctx else "absent",
    )

    if fhir_ctx is None:
        # Demo fallback — local dev path before PO registration.
        if effective_patient_id in _DEMO_PATIENTS:
            return _DEMO_PATIENTS[effective_patient_id]
        raise FhirContextError(
            "No FHIR context in request headers and patient_id is not a demo key. "
            "Either register this MCP server in the PO workspace with 'pass token' "
            "enabled, or call with patient_id='demo-patient-a' for local smoke testing."
        )

    # Real FHIR path — Week-1 skeleton. Only pulls demographics; Week-2 PRs
    # extend this to Condition / MedicationRequest / Procedure / etc.
    async with FhirClient(base_url=fhir_ctx.url, token=fhir_ctx.token) as client:
        try:
            patient = await client.read(f"Patient/{effective_patient_id}")
        except httpx.HTTPStatusError as exc:
            raise FhirContextError(
                f"FHIR server returned HTTP {exc.response.status_code} reading Patient/"
                f"{effective_patient_id}: {exc.response.text[:200]}"
            ) from exc

    if patient is None:
        raise FhirContextError(f"Patient/{effective_patient_id} not found on FHIR server")

    birth = patient.get("birthDate")
    age = _calculate_age(birth) if birth else 0
    sex = patient.get("gender", "unknown")

    return PatientContext(
        demographics=Demographics(patient_id=effective_patient_id, age=age, sex=sex),
        # Clinical-list fields left empty — Week 2 tool work fills these.
        service_request=ServiceRequest(
            cpt_code=service_code,
            description=_DEMO_SERVICE_DESCRIPTION if service_code == _DEMO_SERVICE_CPT else "",
            ordered_date="",
            ordering_provider="",
            reason_codes=[],
        ),
        coverage=Coverage(payer_id="", payer_name=""),
    )
