"""Security-invariant tests for :func:`a2a_agent.po_base.fhir_hook._inject_prompt_note`.

Scope: pure-helper tests only — no ADK harness mocks. The full
:func:`extract_fhir_context` callback would require mocking ``callback_context``,
``llm_request``, and ``google.genai`` together; the value of these tests is
pinning the redaction property structurally so a future refactor cannot plumb
the raw FHIR token into the injected prompt text by accident.

Kevin proposed the first two tests in the PR #9 review; the third pins down the
cross-file contract that :const:`FHIR_CONTEXT_NOTE_PREFIX` is a single source
of truth (PR #9 review suggestion #1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from a2a_agent.po_base.fhir_hook import FHIR_CONTEXT_NOTE_PREFIX, _inject_prompt_note


@dataclass
class _StubLlmRequest:
    """Minimal duck-typed stand-in for ``google.adk.models.LlmRequest``.

    The helper only touches ``llm_request.contents`` (read + append), so a
    plain list is a sufficient fake without pulling the full ADK machinery.
    """

    contents: list[Any] = field(default_factory=list)


def test_inject_prompt_note_redacts_token() -> None:
    """The raw JWT MUST NEVER appear in the injected prompt text.

    This is the load-bearing security invariant for the helper. The helper's
    signature (takes ``fhir_token_fingerprint``, not a raw token) makes it
    structurally impossible to leak without both the call site *and* the
    parameter name changing in a single visible diff — but we pin it here
    anyway so a future "convenience" refactor that plumbs the raw token
    through fails the build immediately.
    """
    req = _StubLlmRequest()
    raw_token = "eyJhbGciOiJSUzI1NiJ9.SECRET_PAYLOAD_DO_NOT_LEAK.SECRET_SIGNATURE"
    fingerprint = "len=62 sha256=deadbeefcafe"

    ok = _inject_prompt_note(
        req,
        patient_id="p-42",
        fhir_url="https://fhir.example.org/r4",
        fhir_token_fingerprint=fingerprint,
    )

    assert ok is True, "helper must report success when google.genai is importable"
    assert len(req.contents) == 1, "exactly one content part should be appended"

    text = req.contents[0].parts[0].text

    assert "p-42" in text, "patient_id must be present so the LLM can quote it"
    assert fingerprint in text, "token fingerprint must be present for observability"
    assert raw_token not in text, "RAW TOKEN MUST NEVER APPEAR IN INJECTED TEXT"
    assert "SECRET_PAYLOAD_DO_NOT_LEAK" not in text, "token body must not leak"
    assert "SECRET_SIGNATURE" not in text, "token signature must not leak"
    assert "https://fhir.example.org/r4" not in text, "raw fhir_url must be redacted to 'set'"
    assert "fhir_url=set" in text, "fhir_url presence must be conveyed as 'set'"


def test_inject_prompt_note_degrades_gracefully_on_bad_shape() -> None:
    """Unexpected ``llm_request.contents`` shape must not raise.

    Session state is still populated by the time the helper runs; a silent
    False return is the correct failure mode for the LLM-visibility half of
    the hook. The caller logs ``prompt_note_injected=false`` so the silent
    path remains observable in production.
    """

    @dataclass
    class _BadShape:
        contents: int = 0

    result = _inject_prompt_note(
        _BadShape(),
        patient_id="patient-any",
        fhir_url="",
        fhir_token_fingerprint="",
    )
    assert result is False, "non-list contents must degrade to False, not raise"


def test_inject_prompt_note_uses_hoisted_prefix_constant() -> None:
    """The injected note MUST start with :const:`FHIR_CONTEXT_NOTE_PREFIX`.

    The agent-side instruction in ``a2a_agent/agent.py`` imports the same
    constant and tells Gemini to look for it — this test enforces the
    cross-file contract structurally so the hook and the instruction cannot
    drift silently (PR #9 review suggestion #1, by @kevinsgeo).
    """
    req = _StubLlmRequest()
    assert _inject_prompt_note(
        req,
        patient_id="p-1",
        fhir_url="https://x",
        fhir_token_fingerprint="len=0 sha256=none",
    )
    text = req.contents[0].parts[0].text
    assert text.startswith(FHIR_CONTEXT_NOTE_PREFIX), (
        f"injected note must start with the exported prefix constant so the "
        f"agent instruction in agent.py can match it; got: {text[:80]!r}"
    )
