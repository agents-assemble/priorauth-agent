---
description: FastMCP server conventions (Person A — Kevin's deployable)
globs: ["mcp_server/**/*.py", "mcp_server/**/*.json", "mcp_server/**/*.md"]
alwaysApply: true
---

# MCP server conventions

Owner: Person A (Kevin). Person B reviews PRs here but does not drive.

## Structure

- Tools live in `mcp_server/tools/` — one file per tool.
- FHIR client lives in `mcp_server/fhir/client.py`. It reads the SHARP-propagated token from request headers. Never hardcode a token.
- Payer criteria JSON files live in `mcp_server/data/criteria/`. Filename pattern: `<payer>_<service>.json` (e.g. `cigna_lumbar_mri.json`).
- Prompts live in `mcp_server/prompts/` with a version tag in the filename (e.g. `match_criteria_v1.md`). Bump the version on meaningful changes.

## Tool contract

Each tool:

- Takes flat `Annotated[T, Field(description=...)]` parameters — one per logical argument — rather than a single nested Pydantic input model. Rationale: FastMCP generates each tool's JSON schema directly from the function signature, and a nested `BaseModel` wrapper introduces a `$ref` indirection + an extra object layer that degrades the schema ergonomics for MCP clients (verified 2026-04-23 against Claude Desktop and PO's workspace UI — both render flat args as individual form fields, nested models as a single blob). Each argument's `Field(description=...)` becomes the parameter's `description` in the generated schema, so descriptions must be written for the MCP client (not a Python consumer).
  - **Exception**: when an argument is intrinsically a structured record (e.g. a list of criteria rows, a nested coverage object), define it in `shared.models` and annotate the parameter with that model. The rule above applies to simple scalar/list args only, which is the common case for the three Week-2 tools.
- Returns a Pydantic output model from `shared.models`. Complex return types are always wrapped — FastMCP's structured-content surface renders them cleanly on the client side.
- Is registered in `mcp_server/server.py` via FastMCP with `name=` and `description=` kwargs (the description is what shows up in the MCP client's tool picker).
- Has a golden-file test in `tests/mcp_server/` covering all 3 demo patients.

## Payer criteria JSON

Every criteria file MUST:

- Have a `source_policy_url` field pointing to the payer's public policy document.
- Paraphrase criteria in plain English, with a stable `id` per criterion (e.g. `cigna.lumbar_mri.conservative_therapy_6wk`).
- Include `version` and `effective_date`.
- NEVER copy payer criteria verbatim — paraphrase.

## LLM usage inside tools

- `temperature=0` for all structured generation.
- Use Gemini structured output (JSON schema mode) bound to the Pydantic output model.
- Model name from `os.environ["GEMINI_MODEL"]` — never hardcoded.
- Every prompt change bumps the version in the filename.

## Testing

- Golden-file tests over all 3 demo patients (A: happy path, B: needs-info, C: red flag).
- Rule-engine branches tested separately from LLM-reasoning branches so one can fail clearly.
- Mark LLM tests with `@pytest.mark.llm` so they can be skipped in fast CI runs.
