# demo/

Demo assets: 3 curated patient scenarios that drive the full workflow, plus the clinical notes hand-authored for each.

## Patients

| ID | Scenario | Expected outcome |
|---|---|---|
| A | 47F, M54.50 low back pain 12 wks, 8 PT sessions, NSAID + muscle-relaxant trial, no red flags | Clean approval letter |
| B | 52M, M54.50 10 wks, NSAID trial, **no documented PT** | Needs-info checklist (demo shows clinician uploading PT note → re-running → approved) |
| C | 61F, M54.51 with malignancy history (C79.51), clinical note: "saddle numbness, difficulty controlling bladder" | Red-flag fast-track — urgent banner, criteria bypassed |

## Structure

```
demo/
├── patients/           # FHIR bundles (one per patient) for reproducible PO workspace imports
├── clinical_notes/     # Hand-authored clinical narrative per patient (uploaded via PO UI as DocumentReference)
└── storyboard.md       # Demo video storyboard — each second accounted for
```

## Importing into Prompt Opinion workspace

1. Go to the Patients tab in your PO workspace.
2. Use "Upload FHIR bundle" (or equivalent) to load `demo/patients/patient_a.json` etc.
3. Open each patient, go to Documents, and upload the matching `demo/clinical_notes/patient_a.md` as a DocumentReference.

The clinical notes are the substrate for the LLM's red-flag detection pass. They are NOT Synthea-generated — we author them ourselves so Patient C has realistic narrative content ("saddle numbness", "bladder incontinence") for the LLM to pick up.

## Why these 3 patients

Together they cover:

- **Happy path** (A) — proves the basic flow works and produces a professional letter.
- **Needs-info loop** (B) — our main differentiator vs. competing PA submissions that do binary approve/deny.
- **Red-flag fast-track** (C) — clinical intelligence that surfaces cauda equina / malignancy from free text.

In the demo video we lead with B (the differentiator), not A (the happy path).
