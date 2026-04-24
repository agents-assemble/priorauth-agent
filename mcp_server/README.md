# mcp_server/

FastMCP server — the "Superpower" toolkit for prior authorization.

**Owner**: Person A (Kevin). Person B reviews PRs but does not drive.

## Tools

| Tool | Status | Returns |
|---|---|---|
| `fetch_patient_context(patient_id, service_code)` | structured-data extraction live (Week 1); free-text PR-B pending | `shared.models.PatientContext` |
| `match_payer_criteria(patient_context, payer_id, service_code)` | Week 2 | `shared.models.CriteriaResult` |
| `generate_pa_letter(patient_context, criteria_result, clinician_note?)` | Week 2 | `shared.models.PALetter` |

`fetch_patient_context` runs ~6 parallel FHIR queries (`Patient`,
`Condition`, `MedicationRequest`, `Procedure`, `ServiceRequest`,
`Coverage`, `DiagnosticReport`) when a SHARP context is present, and falls
back to a hardcoded Patient A fixture when not (local-curl dev path before
PO registration is live). The mapping between FHIR codes and the
`shared.models` shape lives in `mcp_server/fhir/extractors.py`; therapy-
trial kinds and red-flag canonical labels are pinned to the taxonomy in
`mcp_server/criteria/schema.py` (PR #8) so the Week-2 rule engine can
match without translation. Free-text red-flag detection over
`DocumentReference.content` ships in PR-B alongside the `clinical_notes
_excerpt` extractor.

All cross-service types are imported from `shared/models.py` — see
[`.cursor/rules/mcp-server.md`](../.cursor/rules/mcp-server.md) for
conventions this package follows.

## Actual layout (Week 1)

```
mcp_server/
├── __init__.py               # top-level load_dotenv(override=True)
├── main.py                   # FastAPI ASGI entry point (uvicorn target)
├── server.py                 # FastMCP instance + capability patch + tool registrations
├── fhir/
│   ├── __init__.py
│   ├── constants.py          # SHARP-on-MCP header names (x-fhir-*)
│   ├── context.py            # FhirContext + extraction from MCP headers
│   ├── client.py             # Async httpx FHIR R4 client (retries + paging)
│   └── extractors.py         # FHIR R4 → shared.models mapping (kind + ICD-redflag)
├── tools/
│   ├── __init__.py
│   └── fetch_patient_context.py
├── REFERENCE.md              # upstream attribution + fork log
├── README.md                 # this file
└── pyproject.toml            # mcp_server workspace member
```

Landing in Week 2:
- `mcp_server/data/criteria/<payer>_lumbar_mri.json`
- `mcp_server/prompts/match_criteria_v1.md`, `generate_letter_v1.md`
- `mcp_server/tools/match_payer_criteria.py`
- `mcp_server/tools/generate_pa_letter.py`
- `mcp_server/Dockerfile` + `mcp_server/fly.toml`

## Run locally

From repo root:

```bash
make install   # first time only
make mcp       # serves on :8000 with --reload + --env-file .env
```

Sanity check the MCP `initialize` handshake (shows our server name +
`ai.promptopinion/fhir-context` capability extension):

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
```

Exercise `fetch_patient_context` in demo mode (no FHIR context — uses the
hardcoded Patient A fixture):

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"fetch_patient_context","arguments":{"patient_id":"demo-patient-a","service_code":"72148"}}}'
```

Against a real FHIR server, add the SHARP headers on the request:

```
x-fhir-server-url: https://fhir.example.org
x-fhir-access-token: <bearer-token>
x-patient-id: <patient-logical-id>   # optional if token has `patient` claim
```

Or use the `make` target (reads env vars; same shape as the curl above):

```bash
FHIR_URL=https://fhir.example.org \
FHIR_TOKEN=<bearer-token> \
PATIENT_ID=<patient-logical-id> \
make mcp-fetch-patient
```

## Forking note

This package was scaffolded from `prompt-opinion/po-community-mcp`'s Python
reference at commit `e19ec91`. See [`REFERENCE.md`](./REFERENCE.md) for the
file-by-file adaptation log, local modifications, and upstream-sync
workflow.
