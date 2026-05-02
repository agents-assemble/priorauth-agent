"""Tool 3 — generate_pa_letter.

Produces a :class:`shared.models.PALetter` from a validated
:class:`shared.models.PatientContext` and :class:`shared.models.CriteriaResult`
using Gemini structured JSON output (temperature 0). Authoritative identity
and decision fields are normalized server-side after the LLM parse so the
letter cannot contradict the criteria evaluation.
"""

from __future__ import annotations

import html
import json
import logging
import os
from importlib import resources
from typing import Annotated, Any

import google.generativeai as genai
from pydantic import Field
from shared.models import CriteriaResult, Decision, LetterSection, PALetter, PatientContext

from mcp_server.fhir.context import McpContext

logger = logging.getLogger(__name__)

_CANONICAL_SECTIONS: list[str] = [
    "Summary",
    "Records Reviewed",
    "Criteria Trace",
    "Policy Reference",
    "Authorization Basis",
]

_NEEDS_INFO_HEADING_SWAP: dict[str, str] = {
    "Authorization Basis": "Recommended Next Steps",
}

_DENY_HEADING_SWAP: dict[str, str] = {
    "Authorization Basis": "Recommended Next Steps",
}

_PROMPT_FILE = "generate_pa_letter_v2.md"


def _criteria_version_tag(payer_id: str) -> str:
    """Deterministic criteria bundle tag for letters (aligns with demo fixtures)."""
    slug = (payer_id or "unknown").strip().lower() or "unknown"
    return f"{slug}_lumbar_mri.v1"


def _load_system_prompt() -> str:
    pkg = resources.files("mcp_server.prompts")
    return (pkg / _PROMPT_FILE).read_text(encoding="utf-8")


def _enforce_sections(
    raw_sections: list[LetterSection],
    decision: Decision,
) -> list[LetterSection]:
    """Reorder and rename sections to match the canonical structure."""
    if decision == Decision.NEEDS_INFO:
        heading_swap = _NEEDS_INFO_HEADING_SWAP
    elif decision == Decision.DENY:
        heading_swap = _DENY_HEADING_SWAP
    else:
        heading_swap = {}

    lookup: dict[str, str] = {}
    for sec in raw_sections:
        lookup[sec.heading.strip().lower()] = sec.body

    ordered: list[LetterSection] = []
    for canonical in _CANONICAL_SECTIONS:
        heading = heading_swap.get(canonical, canonical)
        key = canonical.lower()
        alt_key = heading.lower()
        body = lookup.get(key) or lookup.get(alt_key) or ""
        ordered.append(LetterSection(heading=heading, body=body))

    return ordered


_DECISION_LABEL = {
    "approve": "APPROVED",
    "needs_info": "NEEDS ADDITIONAL INFORMATION",
    "deny": "DENIED",
}

_CPT_PROCEDURE_NAME: dict[str, str] = {
    "72148": "Lumbar spine MRI without contrast",
}

_HUMAN_REVIEW_NOTE = (
    "This is a prior authorization readiness review, not a final payer "
    "determination. A clinician or prior authorization specialist should "
    "review the chart and payer policy before submission."
)


def _render_markdown(
    letter: PALetter,
    context: PatientContext | None = None,
    criteria: CriteriaResult | None = None,
) -> str:
    """Render the letter in the readiness-review format."""
    decision_text = _DECISION_LABEL.get(letter.decision, letter.decision.upper())
    procedure = _CPT_PROCEDURE_NAME.get(letter.service_cpt, f"CPT {letter.service_cpt}")

    lines: list[str] = [letter.subject_line]
    lines.append(f"Procedure: {procedure}")
    lines.append(f"CPT: {letter.service_cpt}")
    lines.append(f"Payer: {letter.payer_id}")
    lines.append(f"Patient ID: {letter.patient_id}")
    if context:
        d = context.demographics
        lines.append(f"Patient: {d.age}-year-old {d.sex}")
    lines.append("")

    lines.append(f"Readiness Decision: {decision_text}")
    if letter.urgent_banner:
        lines.append(f"URGENT: {letter.urgent_banner}")
    lines.append("")

    for sec in letter.sections:
        lines.append(f"{sec.heading}:")
        for body_line in sec.body.splitlines():
            lines.append(body_line)
        lines.append("")

    lines.append("Human Review Note:")
    lines.append(_HUMAN_REVIEW_NOTE)
    lines.append("")

    return "\n".join(lines)


def _render_html(letter: PALetter) -> str:
    """Render a canonical HTML letter from structured sections."""
    parts: list[str] = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'></head><body>",
        f"<p><strong>{html.escape(letter.subject_line)}</strong></p>",
    ]
    if letter.urgent_banner:
        parts.append(
            f"<blockquote><strong>URGENT</strong>: {html.escape(letter.urgent_banner)}</blockquote>"
        )
    for sec in letter.sections:
        parts.append(f"<h3>{html.escape(sec.heading)}</h3>")
        escaped_body = html.escape(sec.body).replace("\n", "<br>")
        parts.append(f"<p>{escaped_body}</p>")
    if letter.needs_info_checklist:
        parts.append("<h3>Action Items</h3><ul>")
        for item in letter.needs_info_checklist:
            parts.append(f"<li>{html.escape(item)}</li>")
        parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


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

    sections = _enforce_sections(draft.sections, criteria.decision)

    normalized = draft.model_copy(
        update={
            "decision": criteria.decision,
            "patient_id": patient_id,
            "payer_id": criteria.payer_id,
            "service_cpt": criteria.service_cpt,
            "urgent_banner": urgent if criteria.red_flag_fast_track else None,
            "needs_info_checklist": needs_checklist,
            "source_criteria_version": _criteria_version_tag(criteria.payer_id),
            "sections": sections,
        }
    )

    normalized.rendered_markdown = _render_markdown(normalized, context, criteria)
    normalized.rendered_html = _render_html(normalized)

    return normalized


async def _gemini_generate_letter(
    context: PatientContext,
    criteria: CriteriaResult,
    clinician_note: str | None,
) -> PALetter:
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))  # type: ignore[attr-defined]

    system_prompt = _load_system_prompt()
    schema_desc = json.dumps(PALetter.model_json_schema(), indent=2)
    system_prompt += f"\n\n## JSON Schema for PALetter\n\n```json\n{schema_desc}\n```"

    note_block = ""
    if clinician_note and clinician_note.strip():
        note_block = f"\n## Clinician note (non-authoritative)\n\n{clinician_note.strip()}\n"

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
