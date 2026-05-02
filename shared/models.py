"""Pydantic contracts shared between the MCP server and the A2A agent.

These are the single source of truth for cross-service types. Both
`mcp_server/` and `a2a_agent/` import from this module. Do not duplicate
these types elsewhere.

Any change here must be reviewed by BOTH humans per CODEOWNERS.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Demographics + clinical primitives
# ---------------------------------------------------------------------------


class Demographics(BaseModel):
    """Minimal patient demographics used for letter header + age gating."""

    patient_id: str
    age: int = Field(ge=0, le=120)
    sex: str = Field(description="FHIR administrative-gender code: male, female, other, unknown")


class Condition(BaseModel):
    """A clinically relevant diagnosis."""

    code: str = Field(description="ICD-10-CM code, e.g. M54.50")
    display: str
    onset_date: str | None = Field(default=None, description="ISO-8601 date of onset")
    duration_weeks: int | None = Field(default=None, ge=0)


class TherapyTrial(BaseModel):
    """A documented conservative-therapy trial.

    `kind` examples: "NSAID", "MUSCLE_RELAXANT", "GABAPENTINOID",
    "PHYSICAL_THERAPY", "EPIDURAL_INJECTION".
    """

    kind: str
    drug_or_procedure: str
    start_date: str | None = None
    sessions_or_days: int | None = Field(default=None, ge=0)
    last_date: str | None = None


class PriorImaging(BaseModel):
    """A prior imaging study for duplicate-imaging window checks."""

    modality: str = Field(description="e.g. 'MR Lumbar', 'CT Lumbar'")
    date: str
    loinc_code: str | None = None


class RedFlagCandidate(BaseModel):
    """Something detected that might be a red flag — the criteria evaluator makes the final call."""

    label: str = Field(description="e.g. 'saddle_anesthesia', 'bowel_bladder_dysfunction'")
    source: str = Field(description="Where it was found: 'icd_code' or 'clinical_note'")
    evidence: str = Field(description="Quoted text or code supporting the candidate")


class ServiceRequest(BaseModel):
    """The ordered service that needs prior auth."""

    cpt_code: str = Field(description="e.g. '72148' (MR lumbar w/o contrast)")
    description: str
    ordered_date: str
    ordering_provider: str
    reason_codes: list[str] = Field(default_factory=list, description="ICD-10 codes")


class Coverage(BaseModel):
    """Payer identification that drives criteria lookup."""

    payer_id: str = Field(description="Internal payer key, e.g. 'cigna', 'aetna'")
    payer_name: str
    member_id: str | None = None
    plan_name: str | None = None


# ---------------------------------------------------------------------------
# Level 1: Patient context (produced by Tool 1, consumed by Tools 2 and 3)
# ---------------------------------------------------------------------------


class PatientContext(BaseModel):
    """Normalized clinical context for a prior-auth decision.

    Produced by the MCP tool `fetch_patient_context`. Consumed by
    `match_payer_criteria` and `generate_pa_letter`.

    This is intentionally compact (~2-3 KB) so sub-agents reason over clean
    structured input rather than raw FHIR bundles.
    """

    demographics: Demographics
    active_conditions: list[Condition] = Field(default_factory=list)
    conservative_therapy_trials: list[TherapyTrial] = Field(default_factory=list)
    prior_imaging: list[PriorImaging] = Field(default_factory=list)
    red_flag_candidates: list[RedFlagCandidate] = Field(default_factory=list)
    service_request: ServiceRequest
    coverage: Coverage
    clinical_notes_excerpt: str = Field(
        default="",
        description="Concatenated + truncated free-text clinical notes used for LLM reasoning.",
    )


# ---------------------------------------------------------------------------
# Level 2: Criteria evaluation (produced by Tool 2, consumed by Tool 3)
# ---------------------------------------------------------------------------


class Decision(StrEnum):
    APPROVE = "approve"
    NEEDS_INFO = "needs_info"
    DENY = "deny"
    DO_NOT_SUBMIT = "do_not_submit"


class CriterionCheck(BaseModel):
    """A single payer criterion with its evaluation result."""

    id: str = Field(
        description="Stable identifier, e.g. 'cigna.lumbar_mri.conservative_therapy_6wk'",
    )
    description: str
    met: bool
    evidence: str = Field(description="How it was (or wasn't) supported by PatientContext")
    source_document: str | None = Field(
        default=None,
        description=(
            "FHIR resource reference backing this check, "
            "e.g. 'Condition/M54.51', 'Procedure/2026-03-15', 'DocumentReference/2026-04-01'."
        ),
    )
    snippet: str | None = Field(
        default=None,
        description="Short quoted text from the chart that supports or refutes this criterion.",
    )


class CriteriaResult(BaseModel):
    """Result of payer-criteria evaluation.

    Produced by the MCP tool `match_payer_criteria`. Consumed by
    `generate_pa_letter`.
    """

    decision: Decision
    payer_id: str
    service_cpt: str
    criteria_met: list[CriterionCheck] = Field(default_factory=list)
    criteria_missing: list[CriterionCheck] = Field(default_factory=list)
    red_flag_fast_track: bool = Field(
        default=False,
        description="True when a red flag bypasses normal criteria (e.g. cauda equina).",
    )
    red_flag_reason: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_trace: str = Field(
        description="Short human-readable explanation of how the decision was reached."
    )
    source_policy_url: str | None = Field(
        default=None,
        description="URL of the payer's published policy document for this criteria set.",
    )
    evaluated_at: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of when the evaluation was performed.",
    )
    policy_version_tag: str | None = Field(
        default=None,
        description="Version tag of the payer criteria JSON used, e.g. 'aetna_lumbar_mri.v2026'.",
    )
    evidence_sources_used: list[str] = Field(
        default_factory=list,
        description=(
            "FHIR resource types that returned non-empty data for this evaluation, "
            "e.g. ['Patient', 'Condition', 'MedicationRequest', 'Procedure', 'DocumentReference']."
        ),
    )
    review_status: str = Field(
        default="pending_human_review",
        description=(
            "Always starts as 'pending_human_review'. Never 'auto_approved' — "
            "human sign-off is required before submission."
        ),
    )


# ---------------------------------------------------------------------------
# Level 3: Generated PA letter (produced by Tool 3)
# ---------------------------------------------------------------------------


class LetterSection(BaseModel):
    heading: str
    body: str


class PALetter(BaseModel):
    """Ready-to-submit prior-authorization letter (or needs-info checklist).

    Produced by the MCP tool `generate_pa_letter`.
    """

    decision: Decision
    patient_id: str
    payer_id: str
    service_cpt: str
    subject_line: str
    sections: list[LetterSection] = Field(default_factory=list)
    rendered_html: str = Field(description="Fully rendered HTML letter for display in PO.")
    rendered_markdown: str = Field(description="Markdown version for fallback display.")
    needs_info_checklist: list[str] = Field(
        default_factory=list,
        description=(
            "Populated when decision == NEEDS_INFO. Each item is one missing piece of evidence."
        ),
    )
    urgent_banner: str | None = Field(
        default=None,
        description="Populated when red_flag_fast_track is True on the source CriteriaResult.",
    )
    source_criteria_version: str = Field(
        default="",
        description="Version tag of the payer criteria JSON used, e.g. 'cigna_lumbar_mri.v1'.",
    )


# ---------------------------------------------------------------------------
# Level 3b: Clinician gap-fix note (produced by generate_gap_fix_note)
# ---------------------------------------------------------------------------


class GapFixNote(BaseModel):
    """Clinician-facing note template to close documentation gaps.

    Produced by the MCP tool ``generate_gap_fix_note`` when the criteria
    result is ``needs_info`` or ``do_not_submit``.  Contains a fill-in-
    the-blank addendum the clinician can paste into their chart, with
    ``[bracketed placeholders]`` for unfilled fields.
    """

    decision: Decision
    patient_id: str
    payer_id: str
    service_cpt: str
    template_text: str = Field(
        description=(
            "Fill-in-the-blank clinical addendum with [bracketed placeholders] "
            "for fields the clinician must complete."
        ),
    )
    fields_to_complete: list[str] = Field(
        default_factory=list,
        description=(
            "Each [placeholder] from template_text with a short explanation of what to fill."
        ),
    )
    rendered_markdown: str = Field(
        default="",
        description="Markdown rendering of the template for display.",
    )


# ---------------------------------------------------------------------------
# Level 4: Combined pipeline result (produced by run_prior_auth)
# ---------------------------------------------------------------------------


class PriorAuthResult(BaseModel):
    """Combined result from the full prior-auth pipeline.

    Produced by the MCP tool ``run_prior_auth``. Contains both the
    criteria evaluation and the generated letter so the entire PA
    workflow completes in a single tool call.
    """

    criteria: CriteriaResult
    letter: PALetter | None = Field(
        default=None,
        description="Generated PA letter. None if letter generation failed.",
    )
