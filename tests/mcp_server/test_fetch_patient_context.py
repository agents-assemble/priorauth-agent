"""Smoke tests for the scaffolded `fetch_patient_context` tool.

These are deliberately narrow — the Week-1 scaffold only has a demo-mode
fallback (no FHIR) and the Patient-read skeleton (with FHIR). Week-2 PRs
that add Condition / MedicationRequest / Procedure extraction will land
proper golden-file tests across all 3 demo patients.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from mcp_server.fhir.context import FhirContextError
from mcp_server.tools.fetch_patient_context import fetch_patient_context
from shared.models import PatientContext

# ---------------------------------------------------------------------------
# Minimal fakes for mcp.server.fastmcp.Context — we only need the
# `request_context.request.headers` chain that our extraction helpers read.
# ---------------------------------------------------------------------------


@dataclass
class _FakeRequest:
    headers: dict[str, str]


def _ctx(headers: dict[str, str] | None = None) -> Any:
    req = _FakeRequest(headers=headers or {})
    return SimpleNamespace(request_context=SimpleNamespace(request=req))


@pytest.mark.asyncio
async def test_demo_mode_returns_patient_a() -> None:
    result = await fetch_patient_context(
        patient_id="demo-patient-a", service_code="72148", ctx=_ctx()
    )
    assert isinstance(result, PatientContext)
    assert result.demographics.patient_id == "demo-patient-a"
    assert result.demographics.age == 47
    assert result.demographics.sex == "female"
    assert result.service_request.cpt_code == "72148"
    assert result.coverage.payer_id == "cigna"
    # Notes blob must be non-empty so downstream Week-2 Gemini reasoning has substrate.
    assert "low back pain" in result.clinical_notes_excerpt.lower()


@pytest.mark.asyncio
async def test_unknown_patient_no_fhir_raises_structured_error() -> None:
    with pytest.raises(FhirContextError) as exc_info:
        await fetch_patient_context(
            patient_id="not-a-real-patient", service_code="72148", ctx=_ctx()
        )
    msg = str(exc_info.value)
    assert "pass token" in msg
    assert "demo-patient-a" in msg


@pytest.mark.asyncio
async def test_pydantic_round_trip_preserves_shape() -> None:
    result = await fetch_patient_context(
        patient_id="demo-patient-a", service_code="72148", ctx=_ctx()
    )
    round_tripped = PatientContext.model_validate(result.model_dump())
    assert round_tripped == result
