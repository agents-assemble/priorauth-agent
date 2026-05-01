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
        subject_line="PA Request — Lumbar MRI (72148)",
        sections=sections,
        rendered_html="",
        rendered_markdown="",
        needs_info_checklist=needs_info_checklist or [],
        urgent_banner=urgent_banner,
        source_criteria_version="cigna_lumbar_mri.v1",
    )


class TestEnforceSections:
    def test_canonical_order_preserved(self) -> None:
        scrambled = [
            LetterSection(heading="Supporting Documentation", body="Docs."),
            LetterSection(heading="Request", body="MRI requested."),
            LetterSection(heading="Clinical Summary", body="LBP."),
            LetterSection(heading="Patient Information", body="47yo F."),
            LetterSection(heading="Medical Necessity", body="Criteria met."),
            LetterSection(heading="Conservative Treatment History", body="PT x8."),
        ]
        result = _enforce_sections(scrambled, Decision.APPROVE)
        headings = [s.heading for s in result]
        assert headings == [
            "Request",
            "Patient Information",
            "Clinical Summary",
            "Conservative Treatment History",
            "Medical Necessity",
            "Supporting Documentation",
        ]

    def test_missing_sections_get_empty_body(self) -> None:
        partial = [
            LetterSection(heading="Request", body="MRI requested."),
        ]
        result = _enforce_sections(partial, Decision.APPROVE)
        assert len(result) == 6
        assert result[0].body == "MRI requested."
        assert result[1].body == ""

    def test_needs_info_swaps_medical_necessity_heading(self) -> None:
        sections = [
            LetterSection(heading="Medical Necessity", body="Insufficient evidence."),
        ]
        result = _enforce_sections(sections, Decision.NEEDS_INFO)
        headings = [s.heading for s in result]
        assert "Missing Documentation" in headings
        assert "Medical Necessity" not in headings

    def test_extra_sections_are_dropped(self) -> None:
        sections = [
            LetterSection(heading="Request", body="MRI."),
            LetterSection(heading="Bonus Section", body="Should be dropped."),
        ]
        result = _enforce_sections(sections, Decision.APPROVE)
        assert len(result) == 6
        headings = [s.heading for s in result]
        assert "Bonus Section" not in headings

    def test_case_insensitive_matching(self) -> None:
        sections = [
            LetterSection(heading="request", body="MRI requested."),
            LetterSection(heading="CLINICAL SUMMARY", body="LBP."),
        ]
        result = _enforce_sections(sections, Decision.APPROVE)
        assert result[0].body == "MRI requested."
        assert result[2].body == "LBP."


class TestRenderMarkdown:
    def test_basic_structure(self) -> None:
        sections = _enforce_sections(
            [LetterSection(heading="Request", body="Lumbar MRI requested.")],
            Decision.APPROVE,
        )
        letter = _make_letter(sections)
        md = _render_markdown(letter)
        assert md.startswith("# PA Request")
        assert "## Request" in md
        assert "Lumbar MRI requested." in md
        assert "## Patient Information" in md

    def test_urgent_banner_rendered(self) -> None:
        sections = _enforce_sections([], Decision.APPROVE)
        letter = _make_letter(sections, urgent_banner="Cauda equina suspected")
        md = _render_markdown(letter)
        assert "> **URGENT**: Cauda equina suspected" in md

    def test_needs_info_checklist_rendered(self) -> None:
        sections = _enforce_sections([], Decision.NEEDS_INFO)
        letter = _make_letter(
            sections,
            decision=Decision.NEEDS_INFO,
            needs_info_checklist=["Document PT sessions", "Provide imaging history"],
        )
        md = _render_markdown(letter)
        assert "## Action Items" in md
        assert "- Document PT sessions" in md
        assert "- Provide imaging history" in md


class TestRenderHtml:
    def test_basic_structure(self) -> None:
        sections = _enforce_sections(
            [LetterSection(heading="Request", body="Lumbar MRI requested.")],
            Decision.APPROVE,
        )
        letter = _make_letter(sections)
        h = _render_html(letter)
        assert "<h1>" in h
        assert "<h2>Request</h2>" in h
        assert "Lumbar MRI requested." in h
        assert "</body></html>" in h

    def test_html_escaping(self) -> None:
        sections = _enforce_sections(
            [LetterSection(heading="Request", body="Test <script>alert(1)</script>")],
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
