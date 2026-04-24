"""Free-text DocumentReference handling: decode, compress, red-flag detect.

Sister module to `mcp_server.fhir.extractors`. Lives separately because the
concerns are unrelated: `extractors.py` maps structured FHIR resources to
`shared.models` types via lookup tables, whereas this module reads the
unstructured `DocumentReference.content` attachment, compresses it down to
the LLM-readable `clinical_notes_excerpt` budget, and runs a substring +
negation pass to surface free-text red-flag candidates that the structured
ICD codes alone would miss.

Cross-package contract: `RedFlagCandidate.label` strings come from the same
canonical-label vocabulary used in `mcp_server/criteria/data/*.json`'s
`red_flags[].canonical_labels`. The Cigna catalog is the v1 superset; the
Aetna catalog is a strict subset. Adding a payer means widening
`_REDFLAG_PATTERNS` here, never the other way.

Negation is intentionally simple. We are not running a dependency-parsed
NegEx implementation - we look for a bounded set of negation triggers and
educational/counseling markers within the same sentence as the match, and
suppress when found. This is sufficient for the three demo notes (Patient A
denies all red flags, Patient B reports none, Patient C presents with
several positively); a Week-3 hardening task tracked in
`docs/payer_criteria_research.md` §clinician-review-gaps will swap this for
a tested NLP library if real-patient false-positive rates demand it.
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from shared.models import RedFlagCandidate

logger = logging.getLogger(__name__)

# LOINC code for Progress note. The PO workspace seeds DocumentReference with
# this code on every demo encounter. Real EHRs occasionally use 11488-4
# (Consultation note) or 34746-8 (Nursing note) for the same content; we
# include those as fallbacks but do not search for them explicitly - the
# search fan-out filters by 11506-3 first, falls back to all progress-note-
# class LOINCs if zero hits.
_PROGRESS_NOTE_LOINCS: frozenset[str] = frozenset(
    {
        "11506-3",  # Progress note
        "11488-4",  # Consultation note
        "34746-8",  # Nursing note
    }
)

_DEFAULT_EXCERPT_MAX_CHARS = 3000  # ~3 KB - the upper bound the PatientContext
# docstring calls "intentionally compact (~2-3 KB)". Per-section caps in
# `_SECTION_BUDGETS` keep individual sections from monopolising the budget.


# ---------------------------------------------------------------------------
# DocumentReference decode
# ---------------------------------------------------------------------------


def extract_document_text(resources: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Decode inline `DocumentReference.content` attachments to (date, text) pairs.

    Filters to progress-note LOINC types (the lumbar-PA workflow only cares
    about clinician-authored encounters; lab reports and discharge summaries
    are out of scope for v1). Sorted descending by `DocumentReference.date`
    so the caller can take the most recent without re-sorting.

    Skips - rather than crashes on - resources missing inline `data` (i.e.
    only an external `url`). The v1 tool will not follow external URLs
    because the FHIR token's scope may not extend to whatever blob store
    the URL points to (S3, Azure Blob, etc.); chasing those refs is a
    Week-3 hardening task once we know the real shape of PO workspace
    DocumentReference attachments.
    """
    out: list[tuple[str, str]] = []
    for res in resources:
        if not _is_progress_note(res):
            continue
        if res.get("status") not in (None, "current"):
            continue
        text = _decode_inline_content(res)
        if not text:
            continue
        when = res.get("date") or res.get("created") or ""
        out.append((str(when)[:10], text))
    out.sort(key=lambda pair: pair[0], reverse=True)
    return out


def _is_progress_note(res: dict[str, Any]) -> bool:
    type_codings = res.get("type", {}).get("coding", [])
    for coding in type_codings:
        if "loinc" not in coding.get("system", "").lower():
            continue
        if str(coding.get("code", "")) in _PROGRESS_NOTE_LOINCS:
            return True
    # Empty `type` is a real-world case for some EHRs that only set `category`.
    # Treat as progress note rather than discarding - false positives here cost
    # us a slightly off-target excerpt; false negatives cost us all the red
    # flags from the most clinically relevant document.
    return not type_codings


def _decode_inline_content(res: dict[str, Any]) -> str:
    """Return the first decoded text/* attachment, empty string if none."""
    for entry in res.get("content", []):
        attachment = entry.get("attachment", {})
        ctype = str(attachment.get("contentType", "")).lower()
        data = attachment.get("data")
        # Accept anything text-like - the demo bundles use text/markdown but
        # PO real workspace seeded notes are reportedly text/plain.
        if not isinstance(data, str) or not data:
            continue
        if not (ctype.startswith("text/") or ctype == "" or "markdown" in ctype):
            continue
        try:
            decoded = base64.b64decode(data, validate=False).decode("utf-8", errors="replace")
        except (ValueError, UnicodeDecodeError) as exc:
            logger.warning("documentreference_decode_error err=%s", exc)
            continue
        return decoded
    return ""


# ---------------------------------------------------------------------------
# Excerpt compression
# ---------------------------------------------------------------------------


# Per-section character budgets. Headings are matched as substrings against
# H1/H2/H3 markdown headings, case-insensitively. A section whose heading
# doesn't match ANY keyword here is dropped from the excerpt entirely
# (boilerplate footers, "Note for reviewer" sections, etc.).
#
# Budgets are tuned so Assessment + Conservative Therapy + Plan never get
# crowded out by a long Subjective or Objective section. Patient C's note
# is the worst case: subjective is 1500+ chars but the cauda-equina red
# flags live in Assessment - the Subjective cap protects Assessment from
# the global trim. See `tests/mcp_server/test_notes.py::test_excerpt_fits
# _default_budget_for_all_demo_notes` for the regression bound.
_SECTION_BUDGETS: dict[str, int] = {
    "complaint": 400,
    "subjective": 500,
    "conservative": 1100,
    "therapy": 1100,  # often one-or-the-other heading; both whitelisted
    "objective": 350,
    "assessment": 1000,
    "red": 600,  # "Red flags", "Red-flag symptoms"
    "plan": 700,
    "icd": 350,
}

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def compress_excerpt(note_text: str, *, max_chars: int = _DEFAULT_EXCERPT_MAX_CHARS) -> str:
    """Compress a clinical-note markdown blob to fit the excerpt budget.

    The output keeps the priority sections (chief complaint, conservative
    therapy, assessment, red flags, plan, ICDs) verbatim and drops less
    relevant sections (e.g., separate Vitals / Objective subsections that
    don't surface findings the rule engine cares about).

    Critically, the conservative-therapy section is preserved as bulleted
    lines - the rule engine's `min_kinds_count` check counts distinct
    `TherapyTrial.kind` values from structured FHIR, but the LLM also reads
    `clinical_notes_excerpt` to draft the PA letter and conflating an NSAID
    + muscle-relaxant trial into one sentence ("a 6-week NSAID + muscle-
    relaxant trial") loses the per-drug duration and tolerability detail
    the letter needs. This was the explicit gap flagged in PR #4 review #2.

    When the input is plain text (no markdown structure), falls back to the
    first `max_chars - 20` characters with an ellipsis suffix.
    """
    if not note_text:
        return ""
    body = _FRONTMATTER_RE.sub("", note_text, count=1).strip()

    sections = _split_sections(body)
    if not sections:
        return _truncate_to_budget(body, max_chars)

    # Always keep: the preamble (no heading) plus every section whose
    # heading matches a priority keyword. Original document order preserved
    # so the excerpt reads top-to-bottom like the source note. Each
    # priority section is independently capped via `_SECTION_BUDGETS` so
    # one verbose section can't crowd out later high-signal ones.
    chunks: list[str] = []
    for sec in sections:
        if sec.heading == "":
            chunks.append(_truncate_to_budget(sec.body.strip(), _SECTION_BUDGETS["complaint"]))
            continue
        budget = _section_budget(sec.heading)
        if budget is None:
            continue
        body_capped = _truncate_to_budget(sec.body.strip(), budget)
        chunks.append(f"## {sec.heading}\n{body_capped}")
    excerpt = "\n\n".join(c for c in chunks if c).strip()
    return _truncate_to_budget(excerpt, max_chars)


@dataclass
class _Section:
    heading: str  # empty string for the preamble before the first heading
    body: str


def _split_sections(body: str) -> list[_Section]:
    """Split markdown body on H1/H2/H3 headings into (heading, body) pairs."""
    headings = list(_HEADING_RE.finditer(body))
    if not headings:
        return [_Section(heading="", body=body)]
    sections: list[_Section] = []
    preamble = body[: headings[0].start()].strip()
    if preamble:
        sections.append(_Section(heading="", body=preamble))
    for i, match in enumerate(headings):
        heading_text = match.group(2).strip()
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        sec_body = body[start:end].strip()
        sections.append(_Section(heading=heading_text, body=sec_body))
    return sections


def _section_budget(heading: str) -> int | None:
    """Return per-section char budget for a matching priority heading, or None."""
    lowered = heading.lower()
    for keyword, budget in _SECTION_BUDGETS.items():
        if keyword in lowered:
            return budget
    return None


def _truncate_to_budget(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 0:
        return ""
    cut = text[: max_chars - 1]
    # Snap back to the last sentence/word boundary to avoid mid-word cuts.
    for sep in ("\n\n", ". ", "; ", ", ", " "):
        idx = cut.rfind(sep)
        if idx >= max_chars // 2:
            return cut[:idx].rstrip() + "…"
    return cut.rstrip() + "…"


# ---------------------------------------------------------------------------
# Free-text red-flag detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _RedFlagPattern:
    """One canonical_label and the lowercase substrings that imply it.

    All patterns are matched case-insensitively as plain substrings (no
    regex). Punctuation in the patterns is significant: the demo notes use
    `bowel/bladder` with a slash, so the pattern includes the slash.
    """

    label: str
    patterns: tuple[str, ...] = field(default_factory=tuple)


# v1 catalog. Sourced from the union of canonical_labels across
# `mcp_server/criteria/data/*.json`. Patterns are hand-tuned against the
# three demo notes; expansion (and a clinician spot-check) is a Week-3
# hardening task. Phrase variants are duplicated rather than collapsed via
# regex - readability beats compactness for a list a clinician will
# eventually need to audit.

_REDFLAG_PATTERNS: tuple[_RedFlagPattern, ...] = (
    _RedFlagPattern(
        "saddle_anesthesia",
        (
            "saddle anesthesia",
            "saddle anaesthesia",
            "saddle numbness",
            "saddle paresthesia",
            "saddle sensory loss",
            "perineal numbness",
            "perianal numbness",
            "numbness in the perineal",
            "numbness in the perianal",
            "numbness in the saddle",
            "decreased sensation s2-s4",
            "decreased sensation in the s2-s4",
            "decreased light touch and pinprick in the s2-s4",
            "decreased light touch in the s2-s4",
        ),
    ),
    _RedFlagPattern(
        "bowel_bladder_dysfunction",
        (
            "bowel/bladder dysfunction",
            "bowel and bladder dysfunction",
            "bowel/bladder incontinence",
            "fecal incontinence",
            "bowel incontinence",
            "urinary incontinence",
            "decreased rectal tone",
            "diminished rectal tone",
            "decreased anal sphincter tone",
            "loss of anal sphincter",
            "loss of sphincter tone",
            "unable to voluntarily contract the external anal sphincter",
            "loss of voluntary sphincter",
        ),
    ),
    _RedFlagPattern(
        "acute_urinary_retention",
        (
            "urinary retention",
            "retention of urine",
            "difficulty initiating urination",
            "post-void residual",
            "post void residual",
            "overflow incontinence",
        ),
    ),
    _RedFlagPattern(
        "cauda_equina_syndrome",
        ("cauda equina",),
    ),
    _RedFlagPattern(
        "motor_weakness",
        (
            "motor weakness",
            "lower-extremity weakness",
            "lower extremity weakness",
        ),
    ),
    _RedFlagPattern(
        "foot_drop",
        ("foot drop", "footdrop"),
    ),
    _RedFlagPattern(
        "bilateral_leg_weakness",
        (
            "bilateral lower-extremity weakness",
            "bilateral lower extremity weakness",
            "bilateral leg weakness",
            "weakness in both legs",
            "weakness of both legs",
        ),
    ),
    _RedFlagPattern(
        "progressive_motor_deficit",
        (
            "progressive motor deficit",
            "progressive neurologic deficit",
            "progressively worsening weakness",
        ),
    ),
    _RedFlagPattern(
        "severe_radicular_pain",
        (
            "severe radicular pain",
            "9/10 radicular",
            "10/10 radicular",
        ),
    ),
    _RedFlagPattern(
        "spinal_stenosis",
        ("spinal stenosis", "lumbar stenosis"),
    ),
    _RedFlagPattern(
        "neurogenic_claudication",
        ("neurogenic claudication",),
    ),
    _RedFlagPattern(
        "myelopathy",
        ("myelopathy",),
    ),
    _RedFlagPattern(
        "multiple_sclerosis",
        ("multiple sclerosis",),
    ),
    _RedFlagPattern(
        "transverse_myelitis",
        ("transverse myelitis",),
    ),
    _RedFlagPattern(
        "epidural_abscess",
        ("epidural abscess",),
    ),
    _RedFlagPattern(
        "osteomyelitis",
        ("osteomyelitis", "vertebral osteo"),
    ),
    _RedFlagPattern(
        "discitis",
        ("discitis",),
    ),
    _RedFlagPattern(
        "spinal_infection",
        ("spinal infection", "disc-space infection", "disc space infection"),
    ),
    _RedFlagPattern(
        "aortic_aneurysm",
        ("aortic aneurysm", "abdominal aortic aneurysm"),
    ),
    _RedFlagPattern(
        "aortic_dissection",
        ("aortic dissection",),
    ),
    _RedFlagPattern(
        "pathological_fracture",
        ("pathologic fracture", "pathological fracture"),
    ),
    _RedFlagPattern(
        "post_trauma_fracture",
        ("traumatic fracture", "post-trauma fracture", "post traumatic fracture"),
    ),
    _RedFlagPattern(
        "ankylosing_spondylitis_fracture",
        ("ankylosing spondylitis",),
    ),
    _RedFlagPattern(
        "spinal_cord_injury_trauma",
        ("spinal cord injury",),
    ),
    _RedFlagPattern(
        "spinal_cord_compression",
        ("spinal cord compression", "cord compression"),
    ),
    _RedFlagPattern(
        "epidural_lipomatosis",
        ("epidural lipomatosis",),
    ),
    _RedFlagPattern(
        "tethered_cord",
        ("tethered cord",),
    ),
    _RedFlagPattern(
        "congenital_scoliosis",
        ("congenital scoliosis",),
    ),
    _RedFlagPattern(
        "history_of_cancer",
        (
            "history of breast cancer",
            "history of prostate cancer",
            "history of lung cancer",
            "history of colon cancer",
            "history of malignancy",
            "personal history of malignant",
        ),
    ),
)


# Negation triggers: when one of these tokens appears in the same sentence
# (and BEFORE the matched span - we don't suppress on triggers that follow
# the match, e.g. "saddle numbness, denied"), the candidate is dropped.
# Whole-word matching only - "no" must not match "noted", "not" must not
# match "notable".
_NEGATION_TRIGGERS: frozenset[str] = frozenset(
    {
        "denies",
        "deny",
        "denied",
        "no",
        "without",
        "negative",
        "not",
        "absent",
        "intact",
        "normal",
        "unremarkable",
        "reassuring",
    }
)

# Multi-token negation phrases checked anywhere in the sentence (before or
# after the match). These are stronger signals than the single-token list
# because they only mean "this thing is NOT happening".
_NEGATION_PHRASES: tuple[str, ...] = (
    "ruled out",
    "no evidence of",
    "no signs of",
    "no symptoms of",
    "no history of",
    "with no",
)

# Educational / counseling / hypothetical context. When any of these appear
# in the same sentence, the match is treated as an instruction-to-the-
# patient or hypothetical scenario, not a current finding. Without this
# Patient A would falsely trip on "patient educated on red-flag symptoms
# (saddle numbness, leg weakness, bowel/bladder changes, fever)" and
# Patient B on the same kind of anticipatory-guidance phrasing.
_EDUCATIONAL_MARKERS: tuple[str, ...] = (
    "educated on",
    "education about",
    "education on",
    "counseled on",
    "counseled about",
    "advised on",
    "advised to watch",
    "instructed on",
    "instructed to watch",
    "watch for",
    "if develops",
    "if develop",
    "if she develops",
    "if he develops",
    "should develop",
    "or sooner if",
    "warning signs",
    "red-flag symptoms (",
    "red flag symptoms (",
    "risk of",
    "to evaluate for",
    "must be ruled out",
    "rule out",
)

# Sentence boundary markers. We tokenise on these to scope negation and
# educational checks. Markdown bullet markers ("- ") are not boundaries -
# a bulleted line is one sentence.
_SENTENCE_BOUNDARIES: tuple[str, ...] = (". ", "? ", "! ", "\n\n", "\n## ", "\n### ")

# Word boundary character set - used to verify a single-token negation
# trigger is whole-word.
_WORD_BOUNDARY = re.compile(r"\W")


def detect_redflags_from_text(note_text: str) -> list[RedFlagCandidate]:
    """Substring-with-negation pass over a clinical note for red flags.

    Returns at most one candidate per canonical_label - the first match
    wins, subsequent matches just expand the evidence string. Education
    and counseling sentences are suppressed. Sentences with negation
    triggers BEFORE the match are suppressed. The structured ICD pass in
    `mcp_server.fhir.extractors.detect_redflags_from_conditions` is the
    other half of the red-flag picture; the rule engine deduplicates by
    label, so emitting both an ICD-derived and note-derived candidate for
    the same label is fine and actually adds evidence diversity to the
    reasoning trace.
    """
    if not note_text:
        return []
    lowered = note_text.lower()
    by_label: dict[str, RedFlagCandidate] = {}
    for pattern in _REDFLAG_PATTERNS:
        for substring in pattern.patterns:
            for pos in _find_all(lowered, substring):
                if _is_suppressed(lowered, pos, pos + len(substring)):
                    continue
                if pattern.label in by_label:
                    # Already have evidence for this label; skip - prevents
                    # the trace from getting noisy on docs that mention the
                    # same finding in multiple sentences.
                    break
                evidence = _evidence_excerpt(note_text, pos, pos + len(substring))
                by_label[pattern.label] = RedFlagCandidate(
                    label=pattern.label,
                    source="clinical_note",
                    evidence=evidence,
                )
                break
    return list(by_label.values())


def _find_all(haystack: str, needle: str) -> list[int]:
    """Return all start positions of `needle` in `haystack` (non-overlapping)."""
    out: list[int] = []
    start = 0
    n = len(needle)
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            return out
        out.append(idx)
        start = idx + n


def _sentence_window(text: str, match_start: int, match_end: int) -> tuple[int, int]:
    """Return (sentence_start, sentence_end) covering the match position."""
    # Walk left to nearest sentence boundary.
    sent_start = 0
    for boundary in _SENTENCE_BOUNDARIES:
        idx = text.rfind(boundary, 0, match_start)
        if idx != -1 and idx + len(boundary) > sent_start:
            sent_start = idx + len(boundary)
    # Walk right to nearest sentence boundary.
    sent_end = len(text)
    for boundary in _SENTENCE_BOUNDARIES:
        idx = text.find(boundary, match_end)
        if idx != -1 and idx < sent_end:
            sent_end = idx
    return sent_start, sent_end


def _is_suppressed(lowered_text: str, match_start: int, match_end: int) -> bool:
    sent_start, sent_end = _sentence_window(lowered_text, match_start, match_end)
    sentence = lowered_text[sent_start:sent_end]
    pre = lowered_text[sent_start:match_start]

    # Educational / hypothetical context anywhere in the sentence.
    for marker in _EDUCATIONAL_MARKERS:
        if marker in sentence:
            return True

    # Multi-token negation phrases anywhere in the sentence.
    for phrase in _NEGATION_PHRASES:
        if phrase in sentence:
            return True

    # Single-token negation triggers before the match (whole-word).
    return any(token in _NEGATION_TRIGGERS for token in _tokenize(pre))


def _tokenize(text: str) -> list[str]:
    """Lowercase token split on non-word chars. Empty-string filtered."""
    return [t for t in _WORD_BOUNDARY.split(text) if t]


_EVIDENCE_PAD = 60  # chars on each side of the match span


def _evidence_excerpt(original_text: str, match_start: int, match_end: int) -> str:
    """Return a short excerpt around the match for the candidate's evidence field."""
    left = max(0, match_start - _EVIDENCE_PAD)
    right = min(len(original_text), match_end + _EVIDENCE_PAD)
    snippet = original_text[left:right].strip()
    snippet = re.sub(r"\s+", " ", snippet)
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(original_text) else ""
    return f"{prefix}{snippet}{suffix}"
