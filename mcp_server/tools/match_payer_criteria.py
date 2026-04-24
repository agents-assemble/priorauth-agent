"""Tool 2 - match_payer_criteria.

Hybrid rule-engine + Gemini reasoning pass. Given a PatientContext,
payer_id, and service_code, evaluates the patient against the payer's
medical-necessity criteria and returns a CriteriaResult.

Two layers:

1. **Deterministic rule engine** — handles service applicability, red-flag
   fast-track (label matching), pathway selection (ICD prefix mapping),
   and preliminary conservative-therapy checks. Red-flag fast-track
   short-circuits without calling the LLM.

2. **Gemini reasoning pass** — for everything else (conservative therapy
   adequacy, coverage gating, ambiguous diagnoses). Receives the full
   PatientContext (including clinical_notes_excerpt), the full
   PayerCriteria, and the rule engine's preliminary findings. Produces
   a CriteriaResult via structured output (JSON schema mode, temp=0).

The clinical_notes_excerpt is the safety net: Gemini can read "patient
completed 8 weeks of physical therapy" in the notes even when the PT
procedure codes aren't in our CPT lookup table.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from importlib import resources
from typing import Annotated

import google.generativeai as genai
from pydantic import Field
from shared.models import (
    CriteriaResult,
    CriterionCheck,
    Decision,
    PatientContext,
)

from mcp_server.criteria.loader import load_payer_criteria
from mcp_server.criteria.schema import PayerCriteria, TherapyPathway
from mcp_server.fhir.context import McpContext

logger = logging.getLogger(__name__)

_RADICULOPATHY_PREFIXES = ("M54.1",)
_SPONDYLOLISTHESIS_DDD_PREFIXES = ("M43.1", "M51", "M47.8")


# ---------------------------------------------------------------------------
# Layer 1 — deterministic rule helpers (pure, no I/O)
# ---------------------------------------------------------------------------


def _check_service_applicable(criteria: PayerCriteria, service_code: str) -> bool:
    return service_code in criteria.service.cpt_codes


def _check_red_flags(
    context: PatientContext,
    criteria: PayerCriteria,
) -> tuple[bool, str | None, list[CriterionCheck]]:
    """Cross-ref patient red_flag_candidates against criteria red_flags.

    Returns (is_fast_track, reason_string, criterion_checks).
    """
    patient_labels = {c.label for c in context.red_flag_candidates}
    if not patient_labels:
        return False, None, []

    checks: list[CriterionCheck] = []
    for rf in criteria.red_flags:
        overlap = patient_labels & set(rf.canonical_labels)
        if overlap:
            matching_candidates = [c for c in context.red_flag_candidates if c.label in overlap]
            evidence_parts = [
                f"{c.label} (source: {c.source}, evidence: {c.evidence})"
                for c in matching_candidates
            ]
            checks.append(
                CriterionCheck(
                    id=rf.id,
                    description=rf.label,
                    met=True,
                    evidence="; ".join(evidence_parts),
                )
            )

    if checks:
        reason = (
            f"Red-flag fast-track: {checks[0].description} "
            f"matched from patient data ({checks[0].evidence})"
        )
        return True, reason, checks

    return False, None, []


def _select_pathway(
    context: PatientContext,
    criteria: PayerCriteria,
) -> TherapyPathway | None:
    """Pick the applicable conservative-therapy pathway based on ICD codes."""
    icd_codes = [c.code for c in context.active_conditions]

    for code in icd_codes:
        if any(code.startswith(p) for p in _RADICULOPATHY_PREFIXES):
            for pw in criteria.conservative_therapy.pathways:
                if pw.applies_when == "has_radiculopathy":
                    return pw

    for code in icd_codes:
        if any(code.startswith(p) for p in _SPONDYLOLISTHESIS_DDD_PREFIXES):
            for pw in criteria.conservative_therapy.pathways:
                if pw.applies_when == "has_spondylolisthesis_or_ddd":
                    return pw

    for pw in criteria.conservative_therapy.pathways:
        if pw.applies_when == "default":
            return pw

    return None


def _estimate_therapy_duration_weeks(context: PatientContext) -> float:
    """Best-effort duration estimate from structured therapy trials."""
    if not context.conservative_therapy_trials:
        return 0.0

    earliest_start: date | None = None
    latest_end: date | None = None
    total_sessions = 0

    for trial in context.conservative_therapy_trials:
        if trial.start_date:
            try:
                d = date.fromisoformat(trial.start_date)
                if earliest_start is None or d < earliest_start:
                    earliest_start = d
            except ValueError:
                pass
        if trial.last_date:
            try:
                d = date.fromisoformat(trial.last_date)
                if latest_end is None or d > latest_end:
                    latest_end = d
            except ValueError:
                pass
        if trial.sessions_or_days is not None:
            total_sessions += trial.sessions_or_days

    if earliest_start and latest_end:
        delta_days = (latest_end - earliest_start).days
        if delta_days > 0:
            return delta_days / 7.0

    if total_sessions > 0:
        return float(total_sessions)

    return 0.0


def _build_preliminary_findings(
    context: PatientContext,
    criteria: PayerCriteria,
    pathway: TherapyPathway | None,
) -> str:
    """Human-readable summary of what the rule engine found."""
    accepted = set(criteria.conservative_therapy.accepted_kinds)
    patient_kinds = {t.kind for t in context.conservative_therapy_trials if t.kind in accepted}
    duration = _estimate_therapy_duration_weeks(context)

    lines = [
        f"Payer: {criteria.payer_name} ({criteria.payer_id})",
        f"Service: CPT {context.service_request.cpt_code}",
        f"Patient: {context.demographics.age}yo {context.demographics.sex}",
        "Active conditions: "
        + (", ".join(c.code + " " + c.display for c in context.active_conditions) or "none"),
    ]

    if pathway:
        lines.append(
            f"Selected pathway: {pathway.id} ({pathway.applies_when}, {pathway.weeks}wk threshold)"
        )
    else:
        lines.append("Selected pathway: none (no matching pathway trigger found)")

    lines.append(
        f"Accepted therapy kinds found: {sorted(patient_kinds) if patient_kinds else 'none'} "
        f"(need >= {criteria.conservative_therapy.min_kinds_count} distinct)"
    )
    lines.append(f"Estimated therapy duration: {duration:.1f} weeks")

    if context.red_flag_candidates:
        labels = [c.label for c in context.red_flag_candidates]
        lines.append(f"Red-flag candidates: {labels}")
    else:
        lines.append("Red-flag candidates: none")

    if context.clinical_notes_excerpt:
        lines.append(
            f"Clinical notes excerpt available: {len(context.clinical_notes_excerpt)} chars"
        )
    else:
        lines.append("Clinical notes excerpt: empty")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Layer 2 — Gemini reasoning pass
# ---------------------------------------------------------------------------

_PROMPT_FILE = "match_criteria_v1.md"


def _load_system_prompt() -> str:
    pkg = resources.files("mcp_server.prompts")
    return (pkg / _PROMPT_FILE).read_text(encoding="utf-8")


async def _gemini_evaluate(
    context: PatientContext,
    criteria: PayerCriteria,
    preliminary: str,
) -> CriteriaResult:
    """Call Gemini with structured output to produce a CriteriaResult."""
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))  # type: ignore[attr-defined]

    system_prompt = _load_system_prompt()

    user_content = (
        "## PatientContext\n\n"
        f"```json\n{context.model_dump_json(indent=2)}\n```\n\n"
        "## PayerCriteria\n\n"
        f"```json\n{criteria.model_dump_json(indent=2)}\n```\n\n"
        "## Preliminary rule-engine findings\n\n"
        f"```\n{preliminary}\n```"
    )

    schema_desc = json.dumps(CriteriaResult.model_json_schema(), indent=2)
    system_prompt += f"\n\n## JSON Schema for CriteriaResult\n\n```json\n{schema_desc}\n```"

    model = genai.GenerativeModel(  # type: ignore[attr-defined]
        model_name=model_name,
        system_instruction=system_prompt,
    )

    response = model.generate_content(
        user_content,
        generation_config=genai.GenerationConfig(  # type: ignore[attr-defined]
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )

    raw = response.text
    parsed = json.loads(raw)
    return CriteriaResult.model_validate(parsed)


# ---------------------------------------------------------------------------
# MCP tool entry point
# ---------------------------------------------------------------------------


async def match_payer_criteria(
    patient_context_json: Annotated[
        str,
        Field(
            description=(
                "JSON-serialized PatientContext from fetch_patient_context. "
                "Pass the full JSON output of Tool 1 here."
            )
        ),
    ],
    payer_id: Annotated[
        str,
        Field(
            description=(
                "Payer identifier, e.g. 'cigna' or 'aetna'. Must match a "
                "registered payer in the criteria data directory."
            )
        ),
    ],
    service_code: Annotated[
        str,
        Field(
            description=(
                "CPT code of the service needing prior authorization, "
                "e.g. '72148' for lumbar MRI without contrast."
            )
        ),
    ],
    ctx: McpContext,
) -> CriteriaResult:
    """Evaluate a patient against payer medical-necessity criteria."""
    context = PatientContext.model_validate_json(patient_context_json)
    criteria = load_payer_criteria(payer_id)

    logger.info(
        "match_payer_criteria payer=%s service=%s patient=%s",
        payer_id,
        service_code,
        context.demographics.patient_id,
    )

    if not _check_service_applicable(criteria, service_code):
        return CriteriaResult(
            decision=Decision.DENY,
            payer_id=payer_id,
            service_cpt=service_code,
            criteria_missing=[
                CriterionCheck(
                    id=f"{payer_id}.service_not_covered",
                    description="Service CPT code not covered by this policy",
                    met=False,
                    evidence=f"CPT {service_code} not in {criteria.service.cpt_codes}",
                )
            ],
            confidence=1.0,
            reasoning_trace=(
                f"CPT {service_code} is not covered under {criteria.policy_title}. "
                f"Covered codes: {criteria.service.cpt_codes}."
            ),
            source_policy_url=criteria.source_policy_url,
        )

    is_fast_track, rf_reason, rf_checks = _check_red_flags(context, criteria)
    if is_fast_track:
        assert rf_reason is not None
        return CriteriaResult(
            decision=Decision.APPROVE,
            payer_id=payer_id,
            service_cpt=service_code,
            criteria_met=rf_checks,
            red_flag_fast_track=True,
            red_flag_reason=rf_reason,
            confidence=1.0,
            reasoning_trace=(
                f"Red-flag fast-track applied. {rf_reason}. "
                f"Conservative therapy requirements bypassed per "
                f"{criteria.policy_title}."
            ),
            source_policy_url=criteria.source_policy_url,
        )

    pathway = _select_pathway(context, criteria)
    preliminary = _build_preliminary_findings(context, criteria, pathway)

    logger.info("match_payer_criteria calling Gemini for reasoning pass")
    result = await _gemini_evaluate(context, criteria, preliminary)

    result.payer_id = payer_id
    result.service_cpt = service_code
    result.red_flag_fast_track = False
    result.red_flag_reason = None
    result.source_policy_url = criteria.source_policy_url

    return result
