# demo/clinical_notes/

Hand-authored clinical progress notes for the 3 demo patients. These are the substrate for the LLM's red-flag detection and conservative-therapy extraction passes.

## Files

| File | Patient | Scenario | Expected LLM behavior |
|---|---|---|---|
| `patient_a.md` | demo-patient-a (47F) | **Happy path** — 12 wks LBP, 8 PT + NSAID + muscle-relaxant, radicular without red flags | Extract: 6+ weeks conservative therapy met, no red flags. Criteria-match → **approved**. |
| `patient_b.md` | demo-patient-b (52M) | **Needs info** — 10 wks LBP, NSAID trial documented, PT course incomplete (1 intake, 3 no-shows) | Extract: conservative therapy is *partially* documented. Criteria-match → **needs-info**, with a specific checklist item: "completed PT course documentation". |
| `patient_c.md` | demo-patient-c (61F) | **Red-flag fast-track** — breast-ca hx, saddle anesthesia, urinary retention + incontinence, bilateral LE weakness | Extract: cauda-equina red flags + malignancy history. Standard criteria bypassed → **urgent/fast-tracked** with red-flag banner. |

## Why hand-authored (and not Synthea-generated)

Synthea produces structured FHIR resources (`Condition`, `Observation`, `MedicationRequest`, etc.) but its free-text `DocumentReference` output is boilerplate and does not contain the specific clinical language - "saddle numbness", "overflow incontinence", "night pain unrelieved by rest", "decreased rectal tone", "ER+ breast cancer, 7 years out" - that we need our LLM red-flag detector to demonstrate it can recognize.

The whole differentiation story of the demo is: *"our agent reads free-text notes, not just structured codes."* That only works if the notes actually contain medically meaningful narrative content. We write the notes ourselves to guarantee that signal.

## Format

Each file is a markdown document with:

1. **YAML front-matter** — provenance metadata (`patient_id`, `encounter_date`, `provider`, `doctype`, `fhir_document_reference_type`, and for Patient C `urgency: stat`). Consumers that know the format can parse this; an LLM that doesn't just reads it as a header and keeps going.
2. **Body** — a realistic PCP/urgent-care progress note in loose SOAP structure (Subjective / Objective / Assessment / Plan) with explicit ICD-10 coding at the bottom and an electronic signature line.

Notes are written to be clinically plausible but are **entirely fictional**. No real patient data is involved.

## How they're consumed end-to-end

1. Imported into the Prompt Opinion workspace as **FHIR `DocumentReference`** resources attached to the corresponding patient. The `fhir_document_reference_type` value (LOINC `11506-3` = "Progress note") is the `DocumentReference.type.coding[0].code`. The markdown body goes in `DocumentReference.content.attachment.data` (base64-encoded) with `contentType: "text/markdown"`.
2. `mcp_server` tool `fetch_patient_context` searches `DocumentReference?patient={id}&type=http://loinc.org|11506-3` and pulls the most recent note as `PatientContext.clinical_notes_excerpt`. (Truncation strategy for very long notes is TBD - for these three files we expect to fit comfortably in context.)
3. `a2a_agent` passes the excerpt to Gemini alongside the structured `PatientContext` fields when running:
   - **red-flag detection** (Patient C)
   - **conservative-therapy completeness check** (Patient A vs. Patient B)
   - **PA letter generation** (all three — the letter cites specific language from the note, e.g. "the patient failed an 8-session course of supervised PT documented 2026-02-10 through 2026-03-28").

## Keeping these in sync with `mcp_server` demo fixtures

`mcp_server/tools/fetch_patient_context.py` currently hardcodes a one-line `clinical_notes_excerpt` for `demo-patient-a` as a Week-1 scaffold. That excerpt is a compressed summary of this file's body. When the `DocumentReference`-reading extraction lands (tracked in STATUS.md as "real-FHIR extraction PR"), the hardcoded excerpt is deleted and these `.md` files become the canonical source.

If you edit a note, update the matching fixture (if it still exists) in the same PR.

## Red-flag vocabulary the notes intentionally include

These phrases are embedded in `patient_c.md` (and absent from A/B) so we can write assertion-level tests against the LLM's extraction:

- "saddle anesthesia" / "saddle numbness"
- "urinary retention" / "urinary incontinence" / "post-void residual"
- "decreased rectal tone" / "loss of voluntary sphincter contraction"
- "bilateral lower-extremity weakness" / "progressive"
- "history of breast cancer" / "ER+" / "no evidence of recurrence"
- "night pain unrelieved by rest"

If you add a new red-flag phrase to the vocabulary, add it here and add a corresponding golden-file test.
