# a2a_agent/

Google ADK A2A agent — the "Full Agent" submission.

**Owner**: Person B (Sanjit). Person A reviews PRs but does not drive.

## What this service does

Receives A2A calls from the Prompt Opinion general user agent (with a SHARP-propagated FHIR token), orchestrates three internal sub-agents (Patient Context → Criteria Evaluator → PA Letter), and returns a submittable PA letter (or needs-info checklist, or red-flag-fast-track letter).

## Sub-agents

1. **Patient Context** — bound to MCP tool `fetch_patient_context`. Clinical data retrieval specialist.
2. **Criteria Evaluator** — bound to MCP tool `match_payer_criteria`. Decides approve / needs-info / deny and flags red flags.
3. **PA Letter** — bound to MCP tool `generate_pa_letter`. Produces the final deliverable.

All three sub-agents route through a root orchestrator. Sub-agents do NOT call each other directly; handoffs flow through the orchestrator. Trace every handoff via ADK's built-in tracing — these are what we demo in the video.

See [`.cursor/rules/a2a-agent.md`](../.cursor/rules/a2a-agent.md) for conventions this package follows. All cross-service types are imported from [`shared`](../shared/models.py).

## Planned structure

```
a2a_agent/
├── agent.py              # Root orchestrator + 3 sub-agents + handoff definitions
├── middleware.py         # API key enforcement; PO uses this key to authenticate calls
├── card.json             # A2A agent card (skills + endpoints) served at /.well-known/...
├── prompts/
│   ├── orchestrator_v1.md
│   ├── patient_context_v1.md
│   ├── criteria_evaluator_v1.md
│   └── pa_letter_v1.md
├── Dockerfile
├── fly.toml
└── pyproject.toml
```

Scaffolded during Week 1 Day 1–2 as part of the platform spike.

## Forking note

This package is forked from Prompt Opinion's Google ADK A2A reference implementation (Python variant). Attribution and upstream link to be added during the fork commit.
