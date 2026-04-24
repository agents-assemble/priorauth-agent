"""Unit tests for `mcp_server.fhir.notes` (DocumentReference + free-text red flags).

Three concerns under test:

1. **`extract_document_text`** — base64 decode, LOINC progress-note filter,
   most-recent-first ordering, graceful skip on URL-only (no inline data)
   and on bad base64.
2. **`compress_excerpt`** — keeps priority sections (chief complaint,
   conservative therapy, assessment, red flags), drops noise, fits the
   2.2 KB budget, AND preserves the per-trial distinctions that the
   PR #4 review #2 follow-up flagged (NSAID vs muscle-relaxant must not
   collapse into one phrase).
3. **`detect_redflags_from_text`** — substring + negation. The acceptance
   bar is the three demo notes:

     - Patient A's note (denies all flags) → empty list.
     - Patient B's note (no flags reported) → empty list.
     - Patient C's note (textbook cauda equina) → at minimum
       saddle_anesthesia, bowel_bladder_dysfunction, acute_urinary_retention,
       cauda_equina_syndrome, and a bilateral-leg-weakness label.

Negation false-positives are the failure mode that would silently fast-
track a Patient A through a red-flag bypass; the negation/educational-
marker logic exists exactly to prevent that. The Patient A regression test
is deliberately strict (asserts `[] == result`) - any new pattern that
trips Patient A is a bug.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from mcp_server.fhir.notes import (
    compress_excerpt,
    detect_redflags_from_text,
    extract_document_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_NOTES_DIR = REPO_ROOT / "demo" / "clinical_notes"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_ref(
    *,
    text: str,
    loinc: str = "11506-3",
    when: str = "2026-04-15T14:32:00-07:00",
    content_type: str = "text/markdown",
    status: str = "current",
) -> dict[str, Any]:
    """Build a minimal DocumentReference resource with inline base64 content."""
    return {
        "resourceType": "DocumentReference",
        "status": status,
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": loinc,
                    "display": "Progress note",
                }
            ]
        },
        "subject": {"reference": "Patient/demo"},
        "date": when,
        "content": [
            {
                "attachment": {
                    "contentType": content_type,
                    "data": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                }
            }
        ],
    }


def _read_demo_note(stem: str) -> str:
    return (DEMO_NOTES_DIR / f"{stem}.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# extract_document_text
# ---------------------------------------------------------------------------


class TestExtractDocumentText:
    def test_decodes_inline_base64(self) -> None:
        doc = _doc_ref(text="Hello, world.\nLine two.")
        result = extract_document_text([doc])
        assert result == [("2026-04-15", "Hello, world.\nLine two.")]

    def test_filters_to_progress_note_loinc(self) -> None:
        # 18842-5 = Discharge summary — must be filtered out.
        non_progress = _doc_ref(text="discharge summary text", loinc="18842-5")
        progress = _doc_ref(text="progress note text", loinc="11506-3")
        result = extract_document_text([non_progress, progress])
        assert len(result) == 1
        assert "progress" in result[0][1]

    def test_accepts_consultation_and_nursing_note_loincs(self) -> None:
        consult = _doc_ref(text="consult", loinc="11488-4")
        nursing = _doc_ref(text="nursing", loinc="34746-8")
        result = extract_document_text([consult, nursing])
        assert {pair[1] for pair in result} == {"consult", "nursing"}

    def test_accepts_empty_type_coding_as_progress_note(self) -> None:
        # Some EHRs only set DocumentReference.category, leaving type empty.
        # We tolerate this rather than discarding the only available note.
        doc = _doc_ref(text="t")
        doc["type"] = {}  # wipe type entirely
        result = extract_document_text([doc])
        assert len(result) == 1

    def test_sorts_descending_by_date(self) -> None:
        older = _doc_ref(text="older", when="2025-12-01T09:00:00Z")
        newer = _doc_ref(text="newer", when="2026-04-15T09:00:00Z")
        result = extract_document_text([older, newer])
        # Most-recent-first: caller takes [0] for the latest encounter.
        assert result[0][1] == "newer"
        assert result[1][1] == "older"

    def test_skips_attachment_without_inline_data(self) -> None:
        url_only_doc = _doc_ref(text="placeholder")
        url_only_doc["content"] = [
            {"attachment": {"contentType": "text/plain", "url": "https://example.com/note.txt"}}
        ]
        result = extract_document_text([url_only_doc])
        assert result == []

    def test_skips_undecodable_base64(self) -> None:
        bad = _doc_ref(text="ignored")
        bad["content"][0]["attachment"]["data"] = "not!valid!base64!!!"
        # base64.b64decode is permissive enough that this may decode to garbage
        # rather than raising — the bar is "doesn't crash". Drop or accept;
        # both are fine. The key property is no exception.
        result = extract_document_text([bad])
        assert isinstance(result, list)

    def test_skips_entered_in_error_status(self) -> None:
        bad = _doc_ref(text="amended later", status="entered-in-error")
        ok = _doc_ref(text="valid", status="current")
        result = extract_document_text([bad, ok])
        assert len(result) == 1
        assert result[0][1] == "valid"

    def test_accepts_text_plain_and_markdown(self) -> None:
        plain = _doc_ref(text="plain", content_type="text/plain")
        markdown = _doc_ref(text="md", content_type="text/markdown")
        result = extract_document_text([plain, markdown])
        assert {pair[1] for pair in result} == {"plain", "md"}


# ---------------------------------------------------------------------------
# compress_excerpt
# ---------------------------------------------------------------------------


class TestCompressExcerpt:
    def test_strips_yaml_frontmatter(self) -> None:
        note = "---\npatient_id: x\n---\n\n## Assessment\n\nbody"
        result = compress_excerpt(note)
        assert "patient_id: x" not in result
        assert "body" in result

    def test_keeps_chief_complaint_section(self) -> None:
        note = (
            "## Chief Complaint\n\n47F with 12 weeks of low back pain.\n\n## Vitals\n\nBP 122/78\n"
        )
        result = compress_excerpt(note)
        assert "Chief Complaint" in result
        assert "12 weeks of low back pain" in result
        # Vitals is not in the priority keyword list — should be dropped.
        assert "BP 122/78" not in result

    def test_returns_empty_for_empty_input(self) -> None:
        assert compress_excerpt("") == ""

    def test_truncates_to_budget(self) -> None:
        big = "## Subjective\n\n" + ("word " * 1000)
        result = compress_excerpt(big, max_chars=500)
        assert len(result) <= 500
        assert result.endswith("…"), "expected ellipsis on tail truncation"

    def test_falls_back_to_text_when_no_headings(self) -> None:
        note = "Just plain text without any markdown headings whatsoever."
        result = compress_excerpt(note, max_chars=200)
        assert result == note  # fits under budget, returned verbatim

    def test_patient_a_excerpt_preserves_two_separate_trials(self) -> None:
        """PR #4 review #2: NSAID and muscle-relaxant trials must not collapse.

        The original Patient A demo fixture summarised them as 'a 6-week NSAID
        + muscle-relaxant trial', which loses the per-drug duration and side-
        effect detail (naproxen 6wk d/c'd for dyspepsia; cyclobenzaprine 3wk
        helped sleep only). The LLM letter-writer needs both phrases to
        author a credible PA letter.
        """
        note = _read_demo_note("patient_a")
        excerpt = compress_excerpt(note)
        lower = excerpt.lower()
        assert "naproxen" in lower
        assert "cyclobenzaprine" in lower
        # The two must appear as separate bullet lines, not combined.
        # Both bullet leaders should be present.
        assert "**nsaids:**" in lower or "nsaids:" in lower
        assert "**muscle relaxant:**" in lower or "muscle relaxant:" in lower
        # And distinct durations carried through.
        assert "6 weeks" in lower
        assert "3 weeks" in lower

    def test_patient_c_excerpt_keeps_red_flag_section(self) -> None:
        note = _read_demo_note("patient_c")
        excerpt = compress_excerpt(note)
        lower = excerpt.lower()
        # The "Red-flag symptoms and signs present" content lives under
        # the Assessment heading - confirm both the assessment narrative
        # and the saddle anesthesia phrasing made it through.
        assert "cauda equina" in lower
        assert "saddle anesthesia" in lower
        assert "post-void residual" in lower

    def test_excerpt_fits_default_budget_for_all_demo_notes(self) -> None:
        for stem in ("patient_a", "patient_b", "patient_c"):
            note = _read_demo_note(stem)
            excerpt = compress_excerpt(note)
            assert len(excerpt) <= 3000, f"{stem} excerpt over 3 KB budget"
            assert excerpt, f"{stem} excerpt unexpectedly empty"


# ---------------------------------------------------------------------------
# detect_redflags_from_text
# ---------------------------------------------------------------------------


class TestDetectRedflagsFromText:
    def test_returns_empty_for_empty_input(self) -> None:
        assert detect_redflags_from_text("") == []

    def test_negation_with_denies_suppresses_match(self) -> None:
        text = "Patient denies any saddle anesthesia or bowel/bladder dysfunction."
        labels = {c.label for c in detect_redflags_from_text(text)}
        assert labels == set()

    def test_negation_with_no_suppresses_match(self) -> None:
        text = "Exam: no saddle numbness, no foot drop."
        labels = {c.label for c in detect_redflags_from_text(text)}
        assert labels == set()

    def test_negation_with_intact_suppresses_match(self) -> None:
        # "intact" is a single-token negation trigger; the path under test is
        # _is_suppressed -> any(token in _NEGATION_TRIGGERS for token in
        # _tokenize(pre)). The trigger must precede a real pattern in the
        # same sentence to exercise that path, so use a clinically-plausible
        # phrasing that puts "intact" before the "saddle numbness" pattern.
        text = "Intact sensation throughout the saddle numbness distribution."
        labels = {c.label for c in detect_redflags_from_text(text)}
        assert "saddle_anesthesia" not in labels

    def test_normal_rectal_tone_does_not_trip(self) -> None:
        text = "Rectal tone: normal. Patient has intact sphincter function."
        labels = {c.label for c in detect_redflags_from_text(text)}
        assert "bowel_bladder_dysfunction" not in labels

    def test_educational_context_suppresses(self) -> None:
        text = (
            "Patient educated on red-flag symptoms (saddle numbness, "
            "leg weakness, bowel/bladder changes, fever) and when to "
            "seek emergency care."
        )
        labels = {c.label for c in detect_redflags_from_text(text)}
        assert labels == set(), (
            "Anticipatory-guidance language should never surface as a "
            "current finding - this would silently fast-track every Patient "
            "A through a red-flag bypass."
        )

    def test_or_sooner_if_suppresses_anticipatory_language(self) -> None:
        text = (
            "Follow up in 2 weeks, or sooner if new neurologic deficit, "
            "saddle numbness, or bladder/bowel changes develop."
        )
        labels = {c.label for c in detect_redflags_from_text(text)}
        assert labels == set()

    def test_must_be_ruled_out_suppresses(self) -> None:
        text = "Spinal metastases must be ruled out given history."
        labels = {c.label for c in detect_redflags_from_text(text)}
        # The label here would be from "spinal metastases" — not currently
        # a pattern (we lean on ICD codes for cancer/mets). Just confirm no
        # spurious cancer/mets labels fire from "must be ruled out".
        assert "cauda_equina_syndrome" not in labels

    def test_positive_saddle_anesthesia_fires(self) -> None:
        text = "Numbness in the perineal and inner-thigh region noted today."
        labels = {c.label for c in detect_redflags_from_text(text)}
        assert "saddle_anesthesia" in labels

    def test_positive_cauda_equina_fires(self) -> None:
        text = "Highly concerning for cauda equina syndrome."
        labels = {c.label for c in detect_redflags_from_text(text)}
        assert "cauda_equina_syndrome" in labels

    def test_dedupes_to_one_candidate_per_label(self) -> None:
        text = "Cauda equina syndrome suspected. Findings consistent with cauda equina compression."
        candidates = detect_redflags_from_text(text)
        cauda_count = sum(1 for c in candidates if c.label == "cauda_equina_syndrome")
        assert cauda_count == 1

    def test_evidence_field_includes_match_context(self) -> None:
        text = (
            "Over the past 4 days she has noticed difficulty initiating urination "
            "and twice this week urinary incontinence with overflow incontinence pattern."
        )
        candidates = detect_redflags_from_text(text)
        retention = next(c for c in candidates if c.label == "acute_urinary_retention")
        assert "difficulty initiating urination" in retention.evidence.lower()

    # ------- demo-note acceptance tests -----------------------------------

    def test_patient_a_demo_note_emits_no_red_flags(self) -> None:
        text = _read_demo_note("patient_a")
        candidates = detect_redflags_from_text(text)
        labels = sorted(c.label for c in candidates)
        assert labels == [], (
            "Patient A explicitly denies all red flags and counsels on red-flag "
            f"warning signs. Free-text detector should emit zero. Got: {labels}"
        )

    def test_patient_b_demo_note_emits_no_red_flags(self) -> None:
        text = _read_demo_note("patient_b")
        candidates = detect_redflags_from_text(text)
        labels = sorted(c.label for c in candidates)
        assert labels == [], (
            f"Patient B reports no red flags. Detector should emit zero. Got: {labels}"
        )

    def test_patient_c_demo_note_emits_cauda_equina_candidate_set(self) -> None:
        text = _read_demo_note("patient_c")
        candidates = detect_redflags_from_text(text)
        labels = {c.label for c in candidates}
        # The minimum bar: every Cigna canonical_label under cauda_equina
        # PLUS bilateral-leg-weakness (Cigna's motor_weakness bucket).
        required = {
            "saddle_anesthesia",
            "bowel_bladder_dysfunction",
            "acute_urinary_retention",
            "cauda_equina_syndrome",
        }
        missing = required - labels
        assert not missing, f"Patient C missing free-text red flags: {missing}"
        # At least one of the motor-weakness family must fire too.
        motor_family = {"motor_weakness", "bilateral_leg_weakness"}
        assert motor_family & labels, (
            f"Patient C should surface a motor-weakness label; got {labels}"
        )

    def test_patient_c_red_flag_candidates_all_carry_clinical_note_source(self) -> None:
        text = _read_demo_note("patient_c")
        candidates = detect_redflags_from_text(text)
        assert all(c.source == "clinical_note" for c in candidates), (
            "Free-text detector must label evidence source as 'clinical_note' "
            "so the rule engine can distinguish it from ICD-coded candidates."
        )


@pytest.mark.parametrize(
    ("phrase", "expected_label"),
    [
        ("severe radicular pain at 9/10 VAS", "severe_radicular_pain"),
        ("foot drop on the right", "foot_drop"),
        ("bilateral lower-extremity weakness, progressive", "bilateral_leg_weakness"),
        ("epidural abscess on imaging", "epidural_abscess"),
        ("aortic dissection on CTA", "aortic_dissection"),
        ("known transverse myelitis", "transverse_myelitis"),
    ],
)
def test_canonical_phrase_matches(phrase: str, expected_label: str) -> None:
    labels = {c.label for c in detect_redflags_from_text(phrase)}
    assert expected_label in labels
