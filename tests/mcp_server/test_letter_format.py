"""Tests for deterministic letter formatting.

Verifies that _enforce_sections, _render_markdown, and _render_html
produce a consistent canonical structure regardless of Gemini's output.
"""

from __future__ import annotations

from mcp_server.tools.generate_pa_letter import (
    _enforce_sections,
    _render_html,
    _render_markdown,
)
from shared.models import Decision, LetterSection, PALetter


def _make_letter(
    sections: list[LetterSection],
    decision: Decision = Decision.APPROVE,
    urgent_banner: str | None = None,
    needs_info_checklist: list[str] | None = None,
) -> PALetter:
    return PALetter(
        decision=decision,
        patient_id="test-patient",
        payer_id="cigna",
        service_cpt="72148",
        subject_line="Prior Authorization Readiness Review",
        sections=sections,
        rendered_html="",
        rendered_markdown="",
        needs_info_checklist=needs_info_checklist or [],
        urgent_banner=urgent_banner,
        source_criteria_version="cigna_lumbar_mri.v1",
    )


_V2_CANONICAL_HEADINGS = [
    "Summary",
    "Records Reviewed",
    "Criteria Trace",
    "Policy Reference",
    "Authorization Basis",
]


class TestEnforceSections:
    def test_canonical_order_preserved(self) -> None:
        scrambled = [
            LetterSection(heading="Policy Reference", body="Cigna CPB."),
            LetterSection(heading="Summary", body="Request meets criteria."),
            LetterSection(heading="Criteria Trace", body="All met."),
            LetterSection(heading="Records Reviewed", body="Note dated 2026-04-15."),
            LetterSection(heading="Authorization Basis", body="Criteria met."),
        ]
        result = _enforce_sections(scrambled, Decision.APPROVE)
        headings = [s.heading for s in result]
        assert headings == _V2_CANONICAL_HEADINGS

    def test_missing_sections_get_empty_body(self) -> None:
        partial = [
            LetterSection(heading="Summary", body="Request meets criteria."),
        ]
        result = _enforce_sections(partial, Decision.APPROVE)
        assert len(result) == 5
        assert result[0].body == "Request meets criteria."
        assert result[1].body == ""

    def test_needs_info_swaps_authorization_basis_heading(self) -> None:
        sections = [
            LetterSection(heading="Authorization Basis", body="Insufficient evidence."),
        ]
        result = _enforce_sections(sections, Decision.NEEDS_INFO)
        headings = [s.heading for s in result]
        assert "Recommended Next Steps" in headings
        assert "Authorization Basis" not in headings

    def test_extra_sections_are_dropped(self) -> None:
        sections = [
            LetterSection(heading="Summary", body="OK."),
            LetterSection(heading="Bonus Section", body="Should be dropped."),
        ]
        result = _enforce_sections(sections, Decision.APPROVE)
        assert len(result) == 5
        headings = [s.heading for s in result]
        assert "Bonus Section" not in headings

    def test_case_insensitive_matching(self) -> None:
        sections = [
            LetterSection(heading="summary", body="Request meets criteria."),
            LetterSection(heading="CRITERIA TRACE", body="All met."),
        ]
        result = _enforce_sections(sections, Decision.APPROVE)
        assert result[0].body == "Request meets criteria."
        assert result[2].body == "All met."


class TestRenderMarkdown:
    def test_basic_structure(self) -> None:
        sections = _enforce_sections(
            [LetterSection(heading="Summary", body="Criteria met.")],
            Decision.APPROVE,
        )
        letter = _make_letter(sections)
        md = _render_markdown(letter)
        assert md.startswith("Prior Authorization Readiness Review")
        assert "Readiness Decision: APPROVED" in md
        assert "Summary:" in md
        assert "Criteria met." in md
        assert "Human Review Note:" in md

    def test_urgent_banner_rendered(self) -> None:
        sections = _enforce_sections([], Decision.APPROVE)
        letter = _make_letter(sections, urgent_banner="Cauda equina suspected")
        md = _render_markdown(letter)
        assert "URGENT: Cauda equina suspected" in md

    def test_needs_info_checklist_not_in_markdown(self) -> None:
        sections = _enforce_sections([], Decision.NEEDS_INFO)
        letter = _make_letter(
            sections,
            decision=Decision.NEEDS_INFO,
            needs_info_checklist=["Document PT sessions", "Provide imaging history"],
        )
        md = _render_markdown(letter)
        assert "Readiness Decision: NEEDS ADDITIONAL INFORMATION" in md
        assert "Recommended Next Steps:" in md

    def test_header_block_contains_patient_metadata(self) -> None:
        sections = _enforce_sections([], Decision.APPROVE)
        letter = _make_letter(sections)
        md = _render_markdown(letter)
        assert "Procedure: Lumbar spine MRI without contrast" in md
        assert "CPT: 72148" in md
        assert "Payer: cigna" in md
        assert "Patient ID: test-patient" in md


class TestRenderHtml:
    def test_basic_structure(self) -> None:
        sections = _enforce_sections(
            [LetterSection(heading="Summary", body="Criteria met.")],
            Decision.APPROVE,
        )
        letter = _make_letter(sections)
        h = _render_html(letter)
        assert "<strong>" in h
        assert "<h3>Summary</h3>" in h
        assert "Criteria met." in h
        assert "</body></html>" in h

    def test_html_escaping(self) -> None:
        sections = _enforce_sections(
            [LetterSection(heading="Summary", body="Test <script>alert(1)</script>")],
            Decision.APPROVE,
        )
        letter = _make_letter(sections)
        h = _render_html(letter)
        assert "<script>" not in h
        assert "&lt;script&gt;" in h

    def test_urgent_banner_rendered(self) -> None:
        sections = _enforce_sections([], Decision.APPROVE)
        letter = _make_letter(sections, urgent_banner="Cauda equina")
        h = _render_html(letter)
        assert "<blockquote>" in h
        assert "Cauda equina" in h

    def test_needs_info_checklist_as_list(self) -> None:
        sections = _enforce_sections([], Decision.NEEDS_INFO)
        letter = _make_letter(
            sections,
            decision=Decision.NEEDS_INFO,
            needs_info_checklist=["Item 1", "Item 2"],
        )
        h = _render_html(letter)
        assert "<li>Item 1</li>" in h
        assert "<li>Item 2</li>" in h
