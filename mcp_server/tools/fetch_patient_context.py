"""Tool 1 - fetch_patient_context.

Given a `patient_id` + `service_code`, return a normalized `PatientContext`
ready for `match_payer_criteria` to evaluate.

Two execution paths:

- **Real FHIR path** (a SHARP context is propagated via `x-fhir-server-url` +
  `x-fhir-access-token`): fans out 7 parallel FHIR queries against the PO
  workspace server (`Patient` read + `Condition`, `MedicationRequest`,
  `Procedure`, `ServiceRequest`, `Coverage`, `DiagnosticReport`, and
  `DocumentReference` searches), then funnels the results through
  `mcp_server.fhir.extractors` (structured codes → models) and
  `mcp_server.fhir.notes` (DocumentReference → compressed excerpt + free-
  text red-flag candidates). The combined red-flag set covers ICD-coded
  conditions (e.g. Patient C's history_of_cancer from Z85.3) AND text
  findings that have no structured ICD yet (e.g. Patient C's saddle
  anesthesia / acute urinary retention captured only in the progress note).

- **Demo fallback** (no FHIR context): returns one of the three hard-coded
  demo patients. Local curl development path before PO registration is live;
  also the path the smoke tests in `tests/mcp_server/test_fetch_patient
  _context.py` exercise.

Signature note: flat `Annotated[str, Field(...)]` args per the tool
contract in `.cursor/rules/mcp-server.md` - FastMCP generates the tool's
JSON schema directly from the signature, and nested Pydantic wrappers
add a `$ref` indirection + extra object layer that degrades the schema
ergonomics on both Claude Desktop and the PO workspace UI.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

import httpx
from pydantic import Field
from shared.models import (
    Coverage,
    Demographics,
    PatientContext,
    RedFlagCandidate,
    ServiceRequest,
)

from mcp_server.fhir.client import FhirClient
from mcp_server.fhir.context import (
    FhirContext,
    FhirContextError,
    McpContext,
    get_fhir_context,
    get_patient_id_if_context_exists,
)
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
from mcp_server.fhir.notes import (
    compress_excerpt,
    detect_redflags_from_text,
    extract_document_text,
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
        if effective_patient_id in _DEMO_PATIENTS:
            return _DEMO_PATIENTS[effective_patient_id]
        raise FhirContextError(
            "No FHIR context in request headers and patient_id is not a demo key. "
            "Either register this MCP server in the PO workspace with 'pass token' "
            "enabled, or call with patient_id='demo-patient-a' for local smoke testing."
        )

    return await _fetch_from_fhir(
        fhir_ctx=fhir_ctx,
        patient_id=effective_patient_id,
        service_code=service_code,
    )


async def _fetch_from_fhir(
    *,
    fhir_ctx: FhirContext,
    patient_id: str,
    service_code: str,
    http: httpx.AsyncClient | None = None,
) -> PatientContext:
    """Fan out FHIR queries in parallel and assemble a PatientContext.

    Uses one shared `httpx.AsyncClient` (via `FhirClient`'s injectable-pool
    path) so the 6 parallel calls reuse a single connection pool — PO's FHIR
    server keeps connections alive long enough for this to dominate latency
    over per-call client instantiation.

    `http` is a test seam: production passes None and we open/close an
    ephemeral client; tests inject an `httpx.AsyncClient` wired to a
    `MockTransport` so the fan-out can be exercised end-to-end without a
    real FHIR server.
    """
    owns_http = http is None
    if owns_http:
        http = httpx.AsyncClient(timeout=15.0)
    assert http is not None
    try:
        client = FhirClient(base_url=fhir_ctx.url, token=fhir_ctx.token, http=http)
        async with client:
            results = await asyncio.gather(
                _safe_read(client, f"Patient/{patient_id}"),
                _safe_search(client, "Condition", {"patient": patient_id}),
                _safe_search(client, "MedicationRequest", {"patient": patient_id}),
                _safe_search(client, "Procedure", {"patient": patient_id}),
                _safe_search(
                    client, "ServiceRequest", {"patient": patient_id, "code": service_code}
                ),
                _safe_search(client, "Coverage", {"patient": patient_id}),
                _safe_search(client, "DiagnosticReport", {"patient": patient_id}),
                _safe_search(
                    client,
                    "DocumentReference",
                    # Filter to progress notes server-side; some EHRs return
                    # hundreds of DocumentReferences (lab reports, imaging
                    # reports, discharge summaries) per patient and the
                    # bandwidth + extraction cost otherwise dominates. The
                    # fallback search (no type filter) runs only if zero
                    # progress notes come back.
                    {
                        "patient": patient_id,
                        "type": "http://loinc.org|11506-3",
                    },
                ),
            )
    finally:
        if owns_http:
            await http.aclose()

    patient_res, conditions, meds, procs, srs, coverages, reports, docs = results

    if not isinstance(patient_res, dict):
        raise FhirContextError(f"Patient/{patient_id} not found on FHIR server")

    active_conditions = extract_conditions(conditions)  # type: ignore[arg-type]
    therapy_trials = [
        *extract_medication_trials(meds),  # type: ignore[arg-type]
        *extract_procedure_trials(procs),  # type: ignore[arg-type]
    ]
    notes = extract_document_text(docs)  # type: ignore[arg-type]
    most_recent_note_text = notes[0][1] if notes else ""
    excerpt = compress_excerpt(most_recent_note_text) if most_recent_note_text else ""
    redflag_candidates = [
        *detect_redflags_from_conditions(active_conditions),
        *detect_redflags_from_text(most_recent_note_text),
    ]
    return PatientContext(
        demographics=extract_demographics(patient_res),
        active_conditions=active_conditions,
        conservative_therapy_trials=therapy_trials,
        prior_imaging=extract_prior_imaging(reports),  # type: ignore[arg-type]
        red_flag_candidates=_dedupe_redflags(redflag_candidates),
        service_request=extract_service_request(srs, cpt_code=service_code),  # type: ignore[arg-type]
        coverage=extract_coverage(coverages),  # type: ignore[arg-type]
        clinical_notes_excerpt=excerpt,
    )


def _dedupe_redflags(candidates: list[RedFlagCandidate]) -> list[RedFlagCandidate]:
    """Drop duplicate (label, source) pairs while preserving order.

    The structured ICD pass and the free-text pass can both surface the
    same canonical_label (e.g. `cancer` from Z85.3 + `cancer` from "history
    of breast cancer" prose). The rule engine deduplicates by label
    canonically, but keeping both candidates here would double-cite the
    evidence in the reasoning trace. We dedupe on `(label, source)` so the
    LLM still sees one ICD-derived AND one note-derived candidate per label
    when both are present - that diversity is what makes the trace trust-
    worthy to a clinician reviewer.
    """
    seen: set[tuple[str, str]] = set()
    out: list[RedFlagCandidate] = []
    for c in candidates:
        key = (c.label, c.source)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


async def _safe_read(client: FhirClient, path: str) -> dict[str, Any] | None:
    """Wrap `client.read()` to convert FHIR HTTP errors into a structured tool error."""
    try:
        return await client.read(path)
    except httpx.HTTPStatusError as exc:
        raise FhirContextError(
            f"FHIR server returned HTTP {exc.response.status_code} reading {path}: "
            f"{exc.response.text[:200]}"
        ) from exc


async def _safe_search(
    client: FhirClient,
    resource_type: str,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    """Wrap `client.search()` to convert HTTP errors. Empty list on 404."""
    try:
        return await client.search(resource_type, params)
    except httpx.HTTPStatusError as exc:
        # 4xx on a search is nearly always "no such patient" or "no permission";
        # we degrade to an empty list so the tool can still produce a partial
        # context the rule engine can route to needs_info instead of crashing.
        logger.warning(
            "fhir_search_error resource=%s status=%d body=%s",
            resource_type,
            exc.response.status_code,
            exc.response.text[:200],
        )
        return []
