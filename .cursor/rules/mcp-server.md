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

- Accepts a Pydantic input model from `shared.models`.
- Returns a Pydantic output model from `shared.models`.
- Is registered in `mcp_server/server.py` via FastMCP.
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
