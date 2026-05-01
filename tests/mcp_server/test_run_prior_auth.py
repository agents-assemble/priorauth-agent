"""Tests for the combined run_prior_auth pipeline tool.

Tier 1 — no LLM: mocks the three sub-tools to verify orchestration,
error handling, and return shape.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from mcp_server.tools.run_prior_auth import run_prior_auth
from shared.models import (
    CriteriaResult,
    CriterionCheck,
    Decision,
    LetterSection,
    PALetter,
    PriorAuthResult,
)

from tests.mcp_server.test_match_payer_criteria import _patient_a


def _approve_criteria() -> CriteriaResult:
    return CriteriaResult(
        decision=Decision.APPROVE,
        payer_id="cigna",
        service_cpt="72148",
        criteria_met=[CriterionCheck(id="cigna.test", description="Met", met=True, evidence="ok")],
        red_flag_fast_track=False,
        confidence=0.95,
        reasoning_trace="Meets criteria.",
        source_policy_url="https://example.com/policy",
    )


def _mock_letter() -> PALetter:
    return PALetter(
        decision=Decision.APPROVE,
        patient_id="patient-a",
        payer_id="cigna",
        service_cpt="72148",
        subject_line="PA Request — Lumbar MRI",
        sections=[
            LetterSection(heading="Request", body="Lumbar MRI requested."),
            LetterSection(heading="Patient Information", body="47yo female."),
            LetterSection(heading="Clinical Summary", body="LBP 12 weeks."),
            LetterSection(heading="Conservative Treatment History", body="PT 8 sessions."),
            LetterSection(heading="Medical Necessity", body="Criteria met."),
            LetterSection(heading="Supporting Documentation", body="Progress note."),
        ],
        rendered_html="",
        rendered_markdown="",
        needs_info_checklist=[],
        urgent_banner=None,
        source_criteria_version="cigna_lumbar_mri.v1",
    )


@pytest.mark.asyncio
async def test_run_prior_auth_returns_criteria_and_letter() -> None:
    ctx_obj = _patient_a()
    criteria = _approve_criteria()
    letter = _mock_letter()

    with (
        patch(
            "mcp_server.tools.run_prior_auth.fetch_patient_context",
            new_callable=AsyncMock,
            return_value=ctx_obj,
        ),
        patch(
            "mcp_server.tools.run_prior_auth.match_payer_criteria",
            new_callable=AsyncMock,
            return_value=criteria,
        ),
        patch(
            "mcp_server.tools.run_prior_auth.generate_pa_letter",
            new_callable=AsyncMock,
            return_value=letter,
        ),
    ):
        result = await run_prior_auth(
            patient_id="patient-a",
            service_code="72148",
            ctx=None,  # type: ignore[arg-type]
        )

    assert isinstance(result, PriorAuthResult)
    assert result.criteria.decision == Decision.APPROVE
    assert result.letter is not None
    assert result.letter.patient_id == "patient-a"


@pytest.mark.asyncio
async def test_run_prior_auth_returns_criteria_when_letter_fails() -> None:
    ctx_obj = _patient_a()
    criteria = _approve_criteria()

    with (
        patch(
            "mcp_server.tools.run_prior_auth.fetch_patient_context",
            new_callable=AsyncMock,
            return_value=ctx_obj,
        ),
        patch(
            "mcp_server.tools.run_prior_auth.match_payer_criteria",
            new_callable=AsyncMock,
            return_value=criteria,
        ),
        patch(
            "mcp_server.tools.run_prior_auth.generate_pa_letter",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Gemini 503"),
        ),
    ):
        result = await run_prior_auth(
            patient_id="patient-a",
            service_code="72148",
            ctx=None,  # type: ignore[arg-type]
        )

    assert isinstance(result, PriorAuthResult)
    assert result.criteria.decision == Decision.APPROVE
    assert result.letter is None


@pytest.mark.asyncio
async def test_run_prior_auth_passes_correct_args_to_sub_tools() -> None:
    ctx_obj = _patient_a()
    criteria = _approve_criteria()
    letter = _mock_letter()

    mock_fetch = AsyncMock(return_value=ctx_obj)
    mock_match = AsyncMock(return_value=criteria)
    mock_letter_fn = AsyncMock(return_value=letter)

    with (
        patch("mcp_server.tools.run_prior_auth.fetch_patient_context", mock_fetch),
        patch("mcp_server.tools.run_prior_auth.match_payer_criteria", mock_match),
        patch("mcp_server.tools.run_prior_auth.generate_pa_letter", mock_letter_fn),
    ):
        await run_prior_auth(
            patient_id="patient-a",
            service_code="72148",
            ctx=None,  # type: ignore[arg-type]
        )

    mock_fetch.assert_called_once_with(patient_id="patient-a", service_code="72148", ctx=None)
    mock_match.assert_called_once()
    call_kwargs = mock_match.call_args.kwargs
    assert call_kwargs["payer_id"] == "cigna"
    assert call_kwargs["service_code"] == "72148"
    mock_letter_fn.assert_called_once()
