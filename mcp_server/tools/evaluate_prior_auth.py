"""Combined MCP tool: fetch patient context, then match payer criteria."""

from __future__ import annotations

import logging
from typing import Annotated

from pydantic import Field
from shared.models import CriteriaResult

from mcp_server.fhir.context import McpContext
from mcp_server.tools.fetch_patient_context import fetch_patient_context
from mcp_server.tools.match_payer_criteria import match_payer_criteria

logger = logging.getLogger(__name__)


async def evaluate_prior_auth(
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
        Field(
            description=(
                "CPT code of the requested service, e.g. '72148' for lumbar MRI."
            )
        ),
    ],
    ctx: McpContext,
) -> CriteriaResult:
    """Fetch the PatientContext and evaluate payer criteria in-process."""
    patient_context = await fetch_patient_context(
        patient_id=patient_id,
        service_code=service_code,
        ctx=ctx,
    )
    payer_id = patient_context.coverage.payer_id

    logger.info(
        "evaluate_prior_auth patient=%s payer=%s service=%s",
        patient_context.demographics.patient_id,
        payer_id,
        service_code,
    )

    return await match_payer_criteria(
        patient_context_json=patient_context.model_dump_json(),
        payer_id=payer_id,
        service_code=service_code,
        ctx=ctx,
    )
