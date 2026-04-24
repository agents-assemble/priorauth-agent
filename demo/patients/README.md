# demo/patients/

FHIR R4 transaction bundles for the three demo patients. These are imported into the Prompt Opinion workspace FHIR server (per `demo/README.md`) so the rest of the pipeline — MCP tool fan-out, sub-agent handoff, PA letter — has a reproducible substrate.

The bundles carry **structured FHIR only** (Patient, Condition, MedicationRequest, Procedure, ServiceRequest, Coverage). Free-text clinical narrative lives in `demo/clinical_notes/*.md` and is uploaded separately via the PO Documents UI as `DocumentReference` resources — see `demo/README.md` step 3. The split is intentional: structured data goes through transaction import (fast, idempotent), free-text notes go through the UI (preserves the "upload a note → re-evaluate" demo loop in the Patient-B needs-info story).

## Files

| File | Patient | Age / Sex | Coverage | Scenario |
|---|---|---|---|---|
| `patient_a.json` | `demo-patient-a` | 47F | Cigna HealthCare | Happy path — 12 wks LBP, 8 PT sessions, NSAID + muscle-relaxant, no red-flag ICDs |
| `patient_b.json` | `demo-patient-b` | 52M | Cigna HealthCare | Needs-info — NSAID only, 1 PT intake + 3 no-shows, no red flags |
| `patient_c.json` | `demo-patient-c` | 61F | Aetna Better Health | Red-flag fast-track — hx breast cancer (Z85.3), urinary retention + incontinence (R32 / R33.9), saddle anesthesia only in note text |

## Shape of each bundle

| Resource | A | B | C | Notes |
|---|---|---|---|---|
| `Patient` | 1 | 1 | 1 | Stable ID = filename stem; `use: "anonymous"` name |
| `Condition` | 2 | 1 | 4 | All `clinicalStatus.coding[0].code = "active"` so `extract_conditions` keeps them |
| `MedicationRequest` | 2 | 1 | 0 | RxNorm codings only — drug `.text` is redundant with coding.display and is included for reviewability |
| `Procedure` | 8 | 1 | 0 | Patient A's 8 × CPT 97110 collapse into **one** `TherapyTrial` with `sessions_or_days=8` (see `extractors.extract_procedure_trials`) |
| `ServiceRequest` | 1 | 1 | 1 | CPT 72148; Patient C is `priority: "stat"` |
| `Coverage` | 1 | 1 | 1 | `payor[0].display` substring-matched to a known payer_id by `_PAYER_ROUTING` |

## Design decisions

### Why `demo-patient-a` and not `patient-a`

Bundle IDs align with the YAML front-matter in `demo/clinical_notes/*.md` (`patient_id: "demo-patient-a"`) and with the `_DEMO_PATIENTS` dict key in `mcp_server/tools/fetch_patient_context.py`. The inline test fixtures in `tests/mcp_server/test_fetch_patient_context_fhir.py` use short `patient-a` ids because they're hand-rolled and self-contained; the two are independent fixture universes and don't need to agree on IDs.

### Why `G83.4` (cauda equina) is *not* in Patient C's bundle

Patient C's clinical note lists G83.4 as a **provisional** ICD code at the bottom — meaning the PCP suspected cauda equina but had not yet coded it as a billing diagnosis, because the MRI hadn't happened yet. The narrative of the red-flag demo is:

> The agent surfaces cauda-equina red flags from the **free-text progress note** before the MRI has confirmed the structural finding and before the coder has attached G83.4 to the encounter.

If we pre-coded G83.4 as a structured `Condition`, `extract_conditions` → `detect_redflags_from_conditions` would surface `cauda_equina_syndrome` from the ICD map without ever reading the note. The demo would still *work*, but the free-text detection pass (shipped in PR #12) would look redundant. Keeping G83.4 out of the bundle forces the rule engine to earn the red-flag fast-track via the note text — which is the whole differentiation story.

Z85.3 (history of breast cancer) **is** in the bundle because it's a stable, long-documented history code that any real EHR would carry into the PA submission. Surfacing `history_of_cancer` via ICD is expected and good — the note text then adds the *acute* red flags on top.

### Why Patient A uses CPT 97110 for all 8 PT sessions

The PT extractor (`_CPT_TO_KIND`) recognises `97110`, `97140`, `97530`, `97112`, `97116` as `PHYSICAL_THERAPY`. A real PT would bill a mix across a course — intake as `97161`–`97164`, follow-ups as `97110`/`97140`, manual therapy as `97140`. None of the PT evaluation codes (`97161`–`97164`) are mapped today, so using them would cause the bundle to report zero PT trials despite 8 documented visits. Keeping all 8 as `97110` is the minimum-fuss way to exercise `sessions_or_days=8` through the extractor. When the evaluation codes are mapped (Week-3 hardening), bump the Patient A bundle to use realistic intake/follow-up split.

### Why Patient B's one PT visit is also CPT 97110

The note describes this as an "intake evaluation" — realistically `97161` — but per the paragraph above, an unmapped code would make the PT trial vanish entirely. The `needs_info` story hinges on the rule engine seeing **exactly one** PT session and deciding that's insufficient. Calling the intake `97110` preserves the single-session count through the extractor. The free-text note still carries the realistic "PT intake evaluation ... no-show for the following three scheduled sessions" narrative that Gemini reads.

## Importing into a FHIR server

These are `type: "transaction"` bundles, so a single POST to the FHIR root applies everything:

```bash
curl -X POST \
  -H "Content-Type: application/fhir+json" \
  -H "Authorization: Bearer $TOKEN" \
  --data @demo/patients/patient_a.json \
  "$FHIR_BASE_URL/"
```

For the Prompt Opinion workspace, follow the instructions in `demo/README.md` (UI-driven bundle upload, then upload matching clinical note via the Documents tab).

All resources use `request.method: "PUT"` with a stable resource URL, so re-running an import is idempotent — the same resources get updated in place, not duplicated.

## Golden-file tests

`tests/demo/test_patient_bundles.py` loads each bundle and runs the resources through the structured-data extractors in `mcp_server.fhir.extractors`. The assertions pin:

- Demographics (`patient_id`, `age`, `sex`)
- Active-condition set (ICD codes)
- Therapy-trial shape (kind, session count, NSAID vs. muscle-relaxant split)
- ServiceRequest CPT + requester + reason codes
- Coverage → `payer_id` routing
- ICD-derived red-flag candidates (none for A/B; `history_of_cancer` for C)

**Free-text extraction is not covered here.** Those tests live alongside the notes module in `tests/mcp_server/test_notes.py` (PR #12) and the end-to-end `tests/mcp_server/test_fetch_patient_context_fhir.py` which combines structured + free-text paths.

## Keeping bundles in sync with clinical notes

If you edit a note in `demo/clinical_notes/`, check whether the bundle needs a matching structured update (new Condition, new trial, etc.). The note is the source of clinical truth; the bundle is its structured projection. A drift between them will show up as:

- Rule-engine evidence that cites the note but has no structured support (Week 2 will flag this)
- `extract_conditions` emitting a code that's not in the note's ICD list (review catch)

When in doubt, the tests in `tests/demo/test_patient_bundles.py` are the contract.
