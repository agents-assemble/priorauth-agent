"""Pydantic schema for payer-criteria JSON files.

Consumed by `mcp_server.tools.match_payer_criteria` (Week 2) to evaluate
a `PatientContext` against one or more payer policies. Stored JSON files
live in `mcp_server/criteria/data/`.

Design notes
------------
- **Not in `shared/`**: the criteria shape is a private contract between
  this module and the rule engine. `a2a_agent/` only ever consumes
  `CriteriaResult` (which lives in `shared/models.py`). Keeping the
  criteria schema in `mcp_server/` avoids a both-reviewer gate every
  time we adjust the rule shape.
- **`TherapyKind` is a `Literal`**: Pydantic rejects any JSON that
  references a therapy-kind string outside the canonical 13. The
  canonical list is frozen by `docs/payer_criteria_research.md`
  §"Normalized `TherapyTrial.kind` taxonomy"; `fetch_patient_context`
  is expected to produce `TherapyTrial.kind` values from this same set.
- **`PathwayTrigger` is a `Literal`**: the rule engine needs a finite
  vocabulary to branch on. Extend explicitly (via a schema-version bump)
  rather than letting arbitrary strings in.
"""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "v1"

TherapyKind: TypeAlias = Literal[
    "ACTIVITY_MODIFICATION",
    "EDUCATION",
    "NSAID",
    "ANALGESIC_NON_OPIOID",
    "ANALGESIC_OPIOID",
    "MUSCLE_RELAXANT",
    "GABAPENTINOID",
    "ORAL_CORTICOSTEROID",
    "EPIDURAL_INJECTION",
    "PHYSICAL_THERAPY",
    "OCCUPATIONAL_THERAPY",
    "SPINAL_MANIPULATION",
    "HOME_EXERCISE",
]

PathwayTrigger: TypeAlias = Literal[
    "default",
    "has_radiculopathy",
    "has_spondylolisthesis_or_ddd",
]


class _Strict(BaseModel):
    """Reject unknown fields so schema drift surfaces loudly in tests."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ServiceApplicability(_Strict):
    """Which ordered services this criteria file applies to."""

    cpt_codes: list[str] = Field(min_length=1)
    description: str


class RedFlag(_Strict):
    """A clinical condition that bypasses the conservative-therapy requirement.

    The rule engine cross-references `canonical_labels` against
    `PatientContext.red_flag_candidates[].label`; any intersection triggers
    a `red_flag_fast_track` APPROVE decision. Upstream extraction of those
    candidates from FHIR / clinical notes is `fetch_patient_context`'s
    responsibility — this schema describes the policy side only.
    """

    id: str = Field(description="Stable ID, e.g. 'cigna.redflag.cauda_equina'")
    label: str = Field(description="Human-readable policy label")
    canonical_labels: list[str] = Field(
        min_length=1,
        description=(
            "Normalized labels the engine matches against "
            "PatientContext.red_flag_candidates[].label"
        ),
    )
    description: str = Field(description="Paraphrased operational criteria from the policy")
    source_section: str = Field(description="Policy section, e.g. 'SP-1.2 Motor Weakness'")


class TherapyPathway(_Strict):
    """One time-thresholded approval path (patient condition + required weeks)."""

    id: str
    applies_when: PathwayTrigger
    weeks: int = Field(ge=1, le=52)
    description: str
    source_section: str


class ConservativeTherapyRule(_Strict):
    """Time-thresholded approval paths + what counts as conservative therapy."""

    pathways: list[TherapyPathway] = Field(min_length=1)
    accepted_kinds: list[TherapyKind] = Field(
        min_length=1,
        description=(
            "Normalized TherapyTrial.kind values that count toward the trial duration. "
            "Anything outside this list is treated as non-qualifying."
        ),
    )
    min_kinds_count: int = Field(
        default=1,
        ge=1,
        description="How many distinct accepted kinds must appear in the trial set.",
    )
    notes: str = ""


class PriorImagingRule(_Strict):
    """Repeat-imaging guidance. Neither Cigna nor Aetna publishes a hard window in v1."""

    has_hard_lookback_window: bool = Field(
        default=False,
        description=(
            "True only if the policy publishes a bright-line 'no repeat MRI within N months' rule."
        ),
    )
    lookback_months: int | None = Field(default=None, ge=1, le=60)
    narrative: str = Field(
        description=(
            "Paraphrase of the policy's repeat-imaging guidance for the engine's reasoning trace."
        )
    )


class CoverageGating(_Strict):
    """ICD-10 inclusions / exclusions + optional age gating.

    `*_icd_patterns` entries are matched as string prefixes against
    `Condition.code` (e.g. pattern `"M48.0"` matches codes `M48.00`
    through `M48.09`). Exact codes with no child children are fine too.
    Empty lists mean "policy does not publish an explicit list."
    """

    covered_icd_patterns: list[str] = Field(default_factory=list)
    excluded_icd_patterns: list[str] = Field(default_factory=list)
    excluded_scope: str | None = Field(
        default=None,
        description=(
            "If exclusions only apply to a specific clinical scenario (not a blanket "
            "exclusion), document that scope here. Engine must respect the scope."
        ),
    )
    age_min: int | None = Field(default=None, ge=0, le=120)
    age_max: int | None = Field(default=None, ge=0, le=120)


class PayerCriteria(_Strict):
    """Top-level payer-criteria document. One file per (payer, procedure-family) pair."""

    schema_version: str = Field(description="Matches SCHEMA_VERSION; change = migration required.")
    payer_id: str = Field(description="Internal key, e.g. 'cigna', 'aetna'.")
    payer_name: str
    policy_title: str
    policy_version: str = Field(description="e.g. 'V1.0.2026' or 'CPB 0236 (unknown)'.")
    policy_effective_date: str | None = Field(
        default=None, description="ISO-8601 if the policy publishes one."
    )
    source_policy_url: str = Field(description="Canonical verified URL.")
    last_verified: str = Field(description="ISO-8601 date the doc was spot-checked.")

    service: ServiceApplicability
    red_flags: list[RedFlag] = Field(min_length=1)
    conservative_therapy: ConservativeTherapyRule
    prior_imaging: PriorImagingRule
    coverage_gating: CoverageGating

    notes: str = Field(
        default="",
        description="Free-text policy-level notes (ambiguities, cross-refs, engineer heads-up).",
    )
