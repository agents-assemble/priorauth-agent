"""Tool 3 — evaluate_prior_auth (combined fetch + match).

Single-call tool that takes a ``patient_id`` + ``service_code``, fetches
the patient's clinical context from FHIR, then evaluates it against the
payer's medical-necessity criteria — all in one MCP round-trip.

This eliminates the LLM round-trip between ``fetch_patient_context`` and
``match_payer_criteria`` that the previous two-tool design required, cutting
Gemini calls from 5 to 3 per PO request. Architecturally cleaner too:
the fetch→match pipeline is an MCP-server concern, not something the
calling LLM should orchestrate.

The individual tools remain registered for backward compat and testing.
"""

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
                "FHIR Patient.id to evaluate. May be a logical id (e.g. "
                "'patient-42') or a demo id ('demo-patient-a'). If empty AND "
                "a SHARP token is present, the patient claim from the token "
                "is used."
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
    """Fetch patient context and evaluate payer criteria in a single call."""
    patient_context = await fetch_patient_context(
        patient_id=patient_id,
        service_code=service_code,
        ctx=ctx,
    )

    payer_id = patient_context.coverage.payer_id
    patient_context_json = patient_context.model_dump_json()

    logger.info(
        "evaluate_prior_auth patient=%s payer=%s service=%s",
        patient_id,
        payer_id,
        service_code,
    )

    return await match_payer_criteria(
        patient_context_json=patient_context_json,
        payer_id=payer_id,
        service_code=service_code,
        ctx=ctx,
    )
