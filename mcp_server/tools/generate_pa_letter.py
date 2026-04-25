"""Tool 3 — generate_pa_letter.

Produces a :class:`shared.models.PALetter` from a validated
:class:`shared.models.PatientContext` and :class:`shared.models.CriteriaResult`
using Gemini structured JSON output (temperature 0). Authoritative identity
and decision fields are normalized server-side after the LLM parse so the
letter cannot contradict the criteria evaluation.
"""

from __future__ import annotations

import json
import logging
import os
from importlib import resources
from typing import Annotated, Any

import google.generativeai as genai
from pydantic import Field
from shared.models import CriteriaResult, Decision, PALetter, PatientContext

from mcp_server.fhir.context import McpContext

logger = logging.getLogger(__name__)

_PROMPT_FILE = "generate_pa_letter_v1.md"


def _criteria_version_tag(payer_id: str) -> str:
    """Deterministic criteria bundle tag for letters (aligns with demo fixtures)."""
    slug = (payer_id or "unknown").strip().lower() or "unknown"
    return f"{slug}_lumbar_mri.v1"


def _load_system_prompt() -> str:
    pkg = resources.files("mcp_server.prompts")
    return (pkg / _PROMPT_FILE).read_text(encoding="utf-8")


def _normalize_letter(
    draft: PALetter,
    context: PatientContext,
    criteria: CriteriaResult,
) -> PALetter:
    """Force authoritative fields from structured inputs (not model output)."""
    patient_id = context.demographics.patient_id
    urgent: str | None = None
    if criteria.red_flag_fast_track:
        urgent = (draft.urgent_banner or "").strip() or None
        if not urgent:
            urgent = (criteria.red_flag_reason or "").strip() or (
                "Urgent: red-flag clinical findings documented; expedited imaging "
                "requested per payer policy and documented evaluation."
            )

    needs_checklist = list(draft.needs_info_checklist)
    if criteria.decision == Decision.NEEDS_INFO and not needs_checklist:
        needs_checklist = [
            f"{c.description}: {c.evidence}"
            for c in criteria.criteria_missing
            if c.description or c.evidence
        ]

    return draft.model_copy(
        update={
            "decision": criteria.decision,
            "patient_id": patient_id,
            "payer_id": criteria.payer_id,
            "service_cpt": criteria.service_cpt,
            "urgent_banner": urgent if criteria.red_flag_fast_track else None,
            "needs_info_checklist": needs_checklist,
            "source_criteria_version": _criteria_version_tag(criteria.payer_id),
        }
    )


async def _gemini_generate_letter(
    context: PatientContext,
    criteria: CriteriaResult,
    clinician_note: str | None,
) -> PALetter:
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))  # type: ignore[attr-defined]

    system_prompt = _load_system_prompt()
    schema_desc = json.dumps(PALetter.model_json_schema(), indent=2)
    system_prompt += f"\n\n## JSON Schema for PALetter\n\n```json\n{schema_desc}\n```"

    note_block = ""
    if clinician_note and clinician_note.strip():
        note_block = (
            "\n## Clinician note (non-authoritative)\n\n"
            f"{clinician_note.strip()}\n"
        )

    user_content = (
        "## PatientContext\n\n"
        f"```json\n{context.model_dump_json(indent=2)}\n```\n\n"
        "## CriteriaResult\n\n"
        f"```json\n{criteria.model_dump_json(indent=2)}\n```"
        f"{note_block}"
    )

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
    parsed: dict[str, Any] = json.loads(raw)
    return PALetter.model_validate(parsed)


async def generate_pa_letter(
    patient_context_json: Annotated[
        str,
        Field(
            description=(
                "JSON-serialized PatientContext from fetch_patient_context. "
                "Pass the full JSON output of Tool 1 here."
            )
        ),
    ],
    criteria_result_json: Annotated[
        str,
        Field(
            description=(
                "JSON-serialized CriteriaResult from match_payer_criteria or "
                "evaluate_prior_auth. Pass the full JSON output of Tool 2 here."
            )
        ),
    ],
    ctx: McpContext,
    clinician_note: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional short note from the clinician (tone or logistics only); "
                "must not be treated as new clinical evidence."
            ),
        ),
    ] = None,
) -> PALetter:
    """Draft a PA letter (or needs-info / denial letter) from context + criteria."""
    context = PatientContext.model_validate_json(patient_context_json)
    criteria = CriteriaResult.model_validate_json(criteria_result_json)

    logger.info(
        "generate_pa_letter patient=%s payer=%s decision=%s ctx=%s",
        context.demographics.patient_id,
        criteria.payer_id,
        criteria.decision.value,
        type(ctx).__name__,
    )

    draft = await _gemini_generate_letter(context, criteria, clinician_note)
    return _normalize_letter(draft, context, criteria)
