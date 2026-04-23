# mcp_server/

FastMCP server — the "Superpower" toolkit for prior authorization.

**Owner**: Person A (Kevin). Person B reviews PRs but does not drive.

## Tools exposed

1. `fetch_patient_context(patient_id, service_code) -> PatientContext` — pulls relevant FHIR resources from PO workspace FHIR and returns a normalized clinical context.
2. `match_payer_criteria(patient_context, payer_id, service_code) -> CriteriaResult` — two-stage evaluation (rule engine + Gemini reasoning) against payer criteria JSON.
3. `generate_pa_letter(patient_context, criteria_result, clinician_note?) -> PALetter` — produces a submittable CMS-10114-style letter, a needs-info checklist, or a red-flag-banner letter.

See [`.cursor/rules/mcp-server.md`](../.cursor/rules/mcp-server.md) for conventions this package follows. All cross-service types are imported from [`shared`](../shared/models.py).

## Planned structure

```
mcp_server/
├── server.py                    # FastMCP entrypoint, 3 tool registrations
├── tools/
│   ├── fetch_patient_context.py
│   ├── match_payer_criteria.py
│   └── generate_pa_letter.py
├── fhir/
│   └── client.py                # Thin FHIR client; reads SHARP token from headers
├── data/criteria/
│   ├── cigna_lumbar_mri.json
│   └── aetna_lumbar_mri.json
├── prompts/
│   ├── match_criteria_v1.md
│   └── generate_letter_v1.md
├── Dockerfile
├── fly.toml
└── pyproject.toml
```

Scaffolded during Week 1 Day 5–7 after the platform spike confirms round-trip works.

## Forking note

This package is forked from Prompt Opinion's community MCP reference implementation ("PO community MCP"). Attribution and upstream link to be added during the fork commit.
