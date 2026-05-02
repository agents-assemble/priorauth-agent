"""Tool 4 — generate_gap_fix_note.

Produces a :class:`shared.models.GapFixNote` from a
:class:`shared.models.PatientContext` and :class:`shared.models.CriteriaResult`
whose decision is ``needs_info`` or ``do_not_submit``.

The note is a fill-in-the-blank clinical addendum that the ordering clinician
can paste into their chart to close documentation gaps. For small, predictable
gap sets the template is built deterministically; for larger or fuzzier gaps
Gemini is called with structured output (temperature 0).
"""

from __future__ import annotations

import json
import logging
import os
from importlib import resources
from typing import Annotated, Any

import google.generativeai as genai
from pydantic import Field
from shared.models import CriteriaResult, Decision, GapFixNote, PatientContext

from mcp_server.fhir.context import McpContext

logger = logging.getLogger(__name__)

_PROMPT_FILE = "generate_gap_fix_note_v1.md"


def _load_system_prompt() -> str:
    pkg = resources.files("mcp_server.prompts")
    return (pkg / _PROMPT_FILE).read_text(encoding="utf-8")


def _normalize(
    draft: GapFixNote,
    context: PatientContext,
    criteria: CriteriaResult,
) -> GapFixNote:
    """Force authoritative identity fields from structured inputs."""
    return draft.model_copy(
        update={
            "decision": criteria.decision,
            "patient_id": context.demographics.patient_id,
            "payer_id": criteria.payer_id,
            "service_cpt": criteria.service_cpt,
        }
    )


async def _gemini_generate_note(
    context: PatientContext,
    criteria: CriteriaResult,
) -> GapFixNote:
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))  # type: ignore[attr-defined]

    system_prompt = _load_system_prompt()
    schema_desc = json.dumps(GapFixNote.model_json_schema(), indent=2)
    system_prompt += f"\n\n## JSON Schema for GapFixNote\n\n```json\n{schema_desc}\n```"

    user_content = (
        "## PatientContext\n\n"
        f"```json\n{context.model_dump_json(indent=2)}\n```\n\n"
        "## CriteriaResult\n\n"
        f"```json\n{criteria.model_dump_json(indent=2)}\n```"
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
    return GapFixNote.model_validate(parsed)


async def generate_gap_fix_note(
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
                "JSON-serialized CriteriaResult from match_payer_criteria. "
                "Must have decision 'needs_info' or 'do_not_submit'."
            )
        ),
    ],
    ctx: McpContext,
) -> GapFixNote:
    """Generate a clinician gap-fix note template from context + criteria.

    Only valid when criteria.decision is needs_info or do_not_submit.
    Returns a GapFixNote with a fill-in-the-blank addendum, placeholder
    list, and markdown rendering.
    """
    context = PatientContext.model_validate_json(patient_context_json)
    criteria = CriteriaResult.model_validate_json(criteria_result_json)

    if criteria.decision not in (Decision.NEEDS_INFO, Decision.DO_NOT_SUBMIT):
        logger.warning(
            "generate_gap_fix_note called with decision=%s — returning empty note",
            criteria.decision.value,
        )
        return GapFixNote(
            decision=criteria.decision,
            patient_id=context.demographics.patient_id,
            payer_id=criteria.payer_id,
            service_cpt=criteria.service_cpt,
            template_text="No documentation gaps identified.",
            fields_to_complete=[],
            rendered_markdown="*No documentation gaps identified.*",
        )

    logger.info(
        "generate_gap_fix_note patient=%s decision=%s gaps=%d",
        context.demographics.patient_id,
        criteria.decision.value,
        len(criteria.criteria_missing),
    )

    draft = await _gemini_generate_note(context, criteria)
    return _normalize(draft, context, criteria)
