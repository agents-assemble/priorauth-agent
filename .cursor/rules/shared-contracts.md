---
description: Shared contract rules for the shared/ package
globs: ["shared/**/*.py", "mcp_server/**/*.py", "a2a_agent/**/*.py"]
alwaysApply: true
---

# Shared contracts rule

All cross-service types live in `shared/models.py` and only there.

## You MUST

- Import types from `shared.models` when they cross the MCP <-> A2A boundary:
  `from shared.models import PatientContext, CriteriaResult, PALetter, Decision`
- Treat `shared/models.py` as a schema contract. Changes there require BOTH humans' review.
- When adding a new cross-service type, add it to `shared/models.py` first, then update callers.

## You MUST NOT

- Redefine `PatientContext`, `CriteriaResult`, `PALetter`, `Decision`, or any other shared model inside `mcp_server/` or `a2a_agent/` — even a subclass or parallel implementation.
- Silently add fields to shared models without bumping version tags on the affected prompts or golden files.
- Use `dict` or untyped `Any` to pass cross-service data. Use the Pydantic models.

## When in doubt

If you're unsure whether a type is "shared", ask: would the OTHER service ever receive this over the wire? If yes, it goes in `shared/`.
