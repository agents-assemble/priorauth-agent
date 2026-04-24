# Upstream reference — attribution & fork log

This package was scaffolded from Prompt Opinion's community MCP reference
implementation (Python flavour). Unlike `a2a_agent/po_base/` (which vendors
upstream as a sub-package for easier sync), this package **adapts** upstream
code inline — the upstream surface we borrow is small (~70 lines across 4
files) and does not justify a separate namespace. Attribution lives in
per-file docstrings plus this log.

## Source

- **Upstream**: https://github.com/prompt-opinion/po-community-mcp (`python/`
  subtree)
- **Copied from commit**: `e19ec91729898ddb6d7acf3632b8cb8eaef03cf0`
  (latest `main` as of 2026-04-23)
- **Upstream license**: same gap as `a2a_agent/REFERENCE.md` — no LICENSE
  file in the upstream repo. Treating as "published reference for the Agents
  Assemble Connectathon" per the upstream README's intent. Same Week-3
  follow-up (`support@promptopinion.ai` confirmation before Marketplace
  publishing) applies.

## What we adapted, where it landed

| Upstream path | Our path | Notes |
|---|---|---|
| `python/mcp_constants.py` | `mcp_server/fhir/constants.py` | Verbatim — header names are part of the SHARP-on-MCP contract and must not drift. |
| `python/fhir_context.py` | `mcp_server/fhir/context.py` (`FhirContext`) | Added `frozen=True, slots=True` for hashability + smaller footprint. |
| `python/fhir_utilities.py` | `mcp_server/fhir/context.py` (`get_fhir_context`, `get_patient_id_if_context_exists`) | Added `jwt.DecodeError` catch (opaque SHARP tokens are legal per spec); returns `None` instead of raising `ValueError` so tools own the error surface. |
| `python/fhir_client.py` | `mcp_server/fhir/client.py` | Substantially extended — async context manager + injectable `httpx.AsyncClient` (connection-pool reuse across a single tool call), 2x retry on `ConnectError` with exponential backoff, auto-paging via `Bundle.link[next]`. Upstream truncates silently at the first page. |
| `python/mcp_instance.py` (capability patch) | `mcp_server/server.py::_patch_capabilities` | Same monkeypatch on `FastMCP._mcp_server.get_capabilities` to advertise the `ai.promptopinion/fhir-context` extension. Our scope list is the lumbar-MRI PA superset (see comment in that file). |
| `python/main.py` | `mcp_server/main.py` | Same lifespan-based session manager + streamable_http mount; we add `MCP_ALLOWED_ORIGINS` env to tighten CORS beyond dev. |
| `python/mcp_utilities.py` | _(not adopted)_ | Upstream's `create_text_response` helper raises when is_error — incompatible with our Pydantic return contract. Tools raise `FhirContextError` instead. |

## Files with no upstream equivalent

These are fully authored locally — no upstream reference. Listed here so
future syncs don't accidentally treat them as adapted code:

- `mcp_server/fhir/extractors.py` — FHIR R4 → `shared.models` mapping
  layer. Upstream returns plain strings from each tool and never normalises
  RxNorm / CPT / ICD-10 into a typed shape. The kind-taxonomy and red-flag
  ICD maps here are the on-the-wire contract with `mcp_server/criteria/`
  (PR #8) — change them together or pin explicit cross-file tests.
- `mcp_server/fhir/notes.py` — DocumentReference base64 decode +
  clinical-note excerpt compression + free-text red-flag substring
  detection with a sentence-scoped negation / educational-marker pass.
  Upstream has no equivalent (its tools return raw FHIR JSON to the
  client). The red-flag pattern catalog and negation triggers are pinned
  to the same canonical_label vocabulary as `extractors.py` and the
  payer JSON files in `mcp_server/criteria/data/` — when a payer's
  `red_flags[].canonical_labels` widens, this module's
  `_REDFLAG_PATTERNS` must widen with it (otherwise the rule engine has
  a label the extractor will never produce).

## What we did NOT copy

- `python/tools/patient_age_tool.py`, `patient_allergies_tool.py`,
  `patient_id_tool.py` — upstream-specific demo tools. Our three tools
  (`fetch_patient_context`, `match_payer_criteria`, `generate_pa_letter`)
  are domain-specific and use `shared/models.py` Pydantic returns rather
  than upstream's `str` returns.
- `python/Dockerfile`, `docker-compose-local.yml` — we have root-level
  `docker-compose.yml`; a dedicated `mcp_server/Dockerfile` lands in Week 2
  when we deploy to Fly.io.
- `dotnet/`, `typescript/` subdirectories — different language stacks.

## Local modifications beyond the initial copy

Tracked in git. Headline changes:

1. **Namespace**: upstream uses module-root imports (`from fhir_client
   import FhirClient`). We use the repo-qualified `mcp_server.fhir.client`
   to integrate with the uv workspace and pytest discovery.
2. **Pydantic return types**: upstream tools return `str`; ours return
   `shared.models` Pydantic models so `match_payer_criteria` /
   `generate_pa_letter` can consume structured JSON without re-parsing.
3. **`FhirContextError` sentinel** instead of `raise ValueError(...)` — see
   `mcp_server/fhir/context.py` docstring.
4. **Scope list**: upstream declares 4 scopes (Patient/Observation/
   MedicationStatement/Condition). Ours declares 8, aligned 1:1 with
   `a2a_agent/app.py::fhir_scopes` for lumbar MRI PA.

## Upstream-sync workflow

Mirrors `a2a_agent/REFERENCE.md` but the surface is smaller so diffing is
easier:

```bash
# From repo root
git clone https://github.com/prompt-opinion/po-community-mcp.git /tmp/po-mcp-latest
diff -u /tmp/po-mcp-latest/python/mcp_constants.py mcp_server/fhir/constants.py
diff -u /tmp/po-mcp-latest/python/fhir_utilities.py mcp_server/fhir/context.py
diff -u /tmp/po-mcp-latest/python/fhir_client.py    mcp_server/fhir/client.py
diff -u /tmp/po-mcp-latest/python/mcp_instance.py   mcp_server/server.py
# Apply relevant upstream fixes via StrReplace, preserving our namespace +
# extension points.
```

The most likely source of upstream churn is the `get_capabilities` monkeypatch
— FastMCP has an open discussion about first-class extension support, and
when that ships the patch can be deleted. Track
https://github.com/modelcontextprotocol/python-sdk/issues for the relevant
RFC.
