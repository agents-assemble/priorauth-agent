"""Combined MCP tool: full prior-auth pipeline in one call.

Runs fetch_patient_context → match_payer_criteria → generate_pa_letter
server-side so the A2A agent needs only a single tool invocation (and
a single MCP round-trip) for the complete PA workflow. Letter generation
failure is non-fatal — the CriteriaResult is always returned.
"""

from __future__ import annotations

import logging
from typing import Annotated

from pydantic import Field
from shared.models import PriorAuthResult

from mcp_server.fhir.context import McpContext
from mcp_server.tools.fetch_patient_context import fetch_patient_context
from mcp_server.tools.generate_pa_letter import generate_pa_letter
from mcp_server.tools.match_payer_criteria import match_payer_criteria

logger = logging.getLogger(__name__)


async def run_prior_auth(
    patient_id: Annotated[
        str,
        Field(
            description=(
                "FHIR Patient.id to evaluate. May be a logical id or a demo id. "
                "If empty and a SHARP token is present, the patient claim is used."
            )
        ),
    ],
    service_code: Annotated[
        str,
        Field(description="CPT code of the requested service, e.g. '72148' for lumbar MRI."),
    ],
    ctx: McpContext,
) -> PriorAuthResult:
    """Run the complete prior-authorization pipeline in one call.

    1. Fetch patient context from FHIR (no LLM).
    2. Evaluate payer criteria (1 Gemini call, or 0 for red-flag fast-track).
    3. Generate PA letter (1 Gemini call).
    """
    patient_context = await fetch_patient_context(
        patient_id=patient_id,
        service_code=service_code,
        ctx=ctx,
    )

    payer_id = patient_context.coverage.payer_id

    logger.info(
        "run_prior_auth patient=%s payer=%s service=%s",
        patient_context.demographics.patient_id,
        payer_id,
        service_code,
    )

    criteria_result = await match_payer_criteria(
        patient_context_json=patient_context.model_dump_json(),
        payer_id=payer_id,
        service_code=service_code,
        ctx=ctx,
    )

    letter = None
    try:
        letter = await generate_pa_letter(
            patient_context_json=patient_context.model_dump_json(),
            criteria_result_json=criteria_result.model_dump_json(),
            ctx=ctx,
        )
    except Exception:
        logger.exception(
            "run_prior_auth letter generation failed patient=%s; returning criteria only",
            patient_context.demographics.patient_id,
        )

    return PriorAuthResult(criteria=criteria_result, letter=letter)
