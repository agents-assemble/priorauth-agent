"""Tests for Tool 3 — generate_pa_letter.

Tier 1 — no LLM (mocked ``_gemini_generate_letter``), always runs in CI.
Tier 2 — ``@pytest.mark.llm`` optional real Gemini (same convention as match tests).
Tier 3 — ASGI MCP protocol smoke (initialize → tools/call), Gemini mocked.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from mcp_server.main import app
from mcp_server.tools.generate_pa_letter import (
    _criteria_version_tag,
    _normalize_letter,
    generate_pa_letter,
)
from pydantic import ValidationError
from shared.models import (
    CriteriaResult,
    CriterionCheck,
    Decision,
    LetterSection,
    PALetter,
)

from tests.mcp_server.test_match_payer_criteria import (
    _patient_a,
    _patient_b,
    _patient_c,
    _patient_d,
)

_SSE_DATA_RE = re.compile(r"^data:\s*(.+)$", re.MULTILINE)


def _parse_first_sse_json(text: str) -> dict[str, Any] | None:
    for m in _SSE_DATA_RE.finditer(text):
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
    return None


def _approve_criteria_cigna() -> CriteriaResult:
    return CriteriaResult(
        decision=Decision.APPROVE,
        payer_id="cigna",
        service_cpt="72148",
        criteria_met=[
            CriterionCheck(
                id="cigna.test",
                description="Met",
                met=True,
                evidence="Structured trials documented.",
            )
        ],
        red_flag_fast_track=False,
        confidence=0.95,
        reasoning_trace="Meets conservative therapy and pathway.",
        source_policy_url="https://example.com/policy",
    )


def _needs_info_criteria() -> CriteriaResult:
    missing = CriterionCheck(
        id="cigna.pt.duration",
        description="Adequate PT course",
        met=False,
        evidence="Only one visit documented.",
    )
    return CriteriaResult(
        decision=Decision.NEEDS_INFO,
        payer_id="cigna",
        service_cpt="72148",
        criteria_missing=[missing],
        red_flag_fast_track=False,
        confidence=0.8,
        reasoning_trace="Insufficient conservative therapy documentation.",
        source_policy_url="https://example.com/policy",
    )


def _wrong_draft_letter() -> PALetter:
    """Deliberately inconsistent with typical PatientContext + CriteriaResult."""
    return PALetter(
        decision=Decision.DENY,
        patient_id="wrong-id",
        payer_id="humana",
        service_cpt="99999",
        subject_line="Test",
        sections=[LetterSection(heading="H", body="B")],
        rendered_html="<p>html</p>",
        rendered_markdown="# md",
        needs_info_checklist=[],
        urgent_banner="SHOULD_CLEAR_WHEN_NOT_FAST_TRACK",
        source_criteria_version="model_hallucination",
    )


class TestNormalizeLetter:
    def test_criteria_version_tag(self) -> None:
        assert _criteria_version_tag("cigna") == "cigna_lumbar_mri.v1"
        assert _criteria_version_tag("Aetna") == "aetna_lumbar_mri.v1"

    def test_overrides_identity_and_decision(self) -> None:
        ctx = _patient_a()
        crit = _approve_criteria_cigna()
        out = _normalize_letter(_wrong_draft_letter(), ctx, crit)
        assert out.decision == Decision.APPROVE
        assert out.patient_id == "patient-a"
        assert out.payer_id == "cigna"
        assert out.service_cpt == "72148"
        assert out.source_criteria_version == "cigna_lumbar_mri.v1"

    def test_clears_urgent_banner_when_not_fast_track(self) -> None:
        ctx = _patient_a()
        crit = _approve_criteria_cigna()
        out = _normalize_letter(_wrong_draft_letter(), ctx, crit)
        assert out.urgent_banner is None

    def test_fast_track_fills_empty_banner(self) -> None:
        ctx = _patient_c()
        crit = CriteriaResult(
            decision=Decision.APPROVE,
            payer_id="cigna",
            service_cpt="72148",
            criteria_met=[],
            red_flag_fast_track=True,
            red_flag_reason="Cauda equina concern documented.",
            confidence=1.0,
            reasoning_trace="Fast track",
            source_policy_url="https://example.com/policy",
        )
        draft = _wrong_draft_letter()
        draft = draft.model_copy(update={"urgent_banner": None})
        out = _normalize_letter(draft, ctx, crit)
        assert out.urgent_banner == "Cauda equina concern documented."

    def test_needs_info_backfills_checklist(self) -> None:
        ctx = _patient_b()
        crit = _needs_info_criteria()
        draft = PALetter(
            decision=Decision.NEEDS_INFO,
            patient_id="x",
            payer_id="x",
            service_cpt="72148",
            subject_line="s",
            sections=[],
            rendered_html="<p></p>",
            rendered_markdown="",
            needs_info_checklist=[],
            urgent_banner=None,
            source_criteria_version="x",
        )
        out = _normalize_letter(draft, ctx, crit)
        assert len(out.needs_info_checklist) == 1
        assert "Adequate PT course" in out.needs_info_checklist[0]


@pytest.mark.asyncio
async def test_generate_pa_letter_applies_normalization_after_mock_llm() -> None:
    ctx = _patient_a()
    crit = _approve_criteria_cigna()
    wrong = _wrong_draft_letter()

    with patch(
        "mcp_server.tools.generate_pa_letter._gemini_generate_letter",
        new_callable=AsyncMock,
        return_value=wrong,
    ):
        out = await generate_pa_letter(
            patient_context_json=ctx.model_dump_json(),
            criteria_result_json=crit.model_dump_json(),
            ctx=None,  # type: ignore[arg-type]
        )

    assert out.decision == Decision.APPROVE
    assert out.patient_id == "patient-a"
    assert out.payer_id == "cigna"
    assert out.service_cpt == "72148"
    assert out.source_criteria_version == "cigna_lumbar_mri.v1"
    assert out.urgent_banner is None


@pytest.mark.asyncio
async def test_invalid_patient_json_raises() -> None:
    crit = _approve_criteria_cigna()
    with pytest.raises(ValidationError):
        await generate_pa_letter(
            patient_context_json="{not json",
            criteria_result_json=crit.model_dump_json(),
            ctx=None,  # type: ignore[arg-type]
        )


@pytest.mark.llm
@pytest.mark.skipif(not os.environ.get("GOOGLE_API_KEY"), reason="GOOGLE_API_KEY not set")
@pytest.mark.asyncio
async def test_llm_smoke_patient_a_approve() -> None:
    """Calls real Gemini when ``-m llm`` is selected and ``GOOGLE_API_KEY`` is set."""
    ctx = _patient_a()
    crit = _approve_criteria_cigna()
    out = await generate_pa_letter(
        patient_context_json=ctx.model_dump_json(),
        criteria_result_json=crit.model_dump_json(),
        ctx=None,  # type: ignore[arg-type]
    )
    assert out.decision == Decision.APPROVE
    assert out.patient_id == "patient-a"
    assert len(out.rendered_html) > 20
    assert len(out.rendered_markdown) > 10


def _do_not_submit_criteria() -> CriteriaResult:
    return CriteriaResult(
        decision=Decision.DO_NOT_SUBMIT,
        payer_id="cigna",
        service_cpt="72148",
        criteria_missing=[
            CriterionCheck(
                id="system.chart_mismatch",
                description="Chart must contain spine-related diagnosis",
                met=False,
                evidence="Active conditions: J02.9 (Acute pharyngitis), I10 (Hypertension).",
                source_document="Condition",
            )
        ],
        confidence=1.0,
        reasoning_trace="No lumbar/spine diagnoses found in the chart.",
    )


@pytest.mark.asyncio
async def test_do_not_submit_letter_bypasses_llm() -> None:
    """DO_NOT_SUBMIT generates a letter deterministically without calling Gemini."""
    ctx = _patient_d()
    crit = _do_not_submit_criteria()
    out = await generate_pa_letter(
        patient_context_json=ctx.model_dump_json(),
        criteria_result_json=crit.model_dump_json(),
        ctx=None,  # type: ignore[arg-type]
    )
    assert out.decision == Decision.DO_NOT_SUBMIT
    assert out.patient_id == "patient-d"
    assert "DO NOT SUBMIT" in out.subject_line
    assert "DO NOT SUBMIT" in out.rendered_markdown
    assert len(out.sections) == 5
    chart_mismatch_section = next((s for s in out.sections if "Chart Mismatch" in s.heading), None)
    assert chart_mismatch_section is not None


def test_mcp_protocol_tools_call_via_asgi() -> None:
    """Same JSON-RPC + SSE path production clients use (see ``mcp_patient_context``)."""
    ctx = _patient_a()
    crit = _approve_criteria_cigna()
    wrong = _wrong_draft_letter()

    with (
        patch(
            "mcp_server.tools.generate_pa_letter._gemini_generate_letter",
            new_callable=AsyncMock,
            return_value=wrong,
        ),
        TestClient(app, base_url="http://test") as client,
    ):
        hdrs = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        init_resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            },
            headers=hdrs,
        )
        assert init_resp.status_code == 200
        session_id = init_resp.headers.get("mcp-session-id", "")
        if session_id:
            hdrs = {**hdrs, "mcp-session-id": session_id}
        client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=hdrs,
        )
        call_resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "generate_pa_letter",
                    "arguments": {
                        "patient_context_json": ctx.model_dump_json(),
                        "criteria_result_json": crit.model_dump_json(),
                    },
                },
            },
            headers=hdrs,
        )

    assert call_resp.status_code == 200
    parsed = _parse_first_sse_json(call_resp.text) or json.loads(call_resp.text)
    result = parsed.get("result", {})
    assert result.get("isError") is not True
    content = result.get("content", [])
    texts = [c.get("text", "") for c in content if c.get("type") == "text"]
    combined = "\n".join(texts)
    letter = PALetter.model_validate_json(combined)
    assert letter.patient_id == "patient-a"
    assert letter.decision == Decision.APPROVE
    assert letter.source_criteria_version == "cigna_lumbar_mri.v1"
