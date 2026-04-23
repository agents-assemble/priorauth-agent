# a2a_agent/

Google ADK A2A agent — our Devpost submission deliverable.

**Owner**: Person B (Sanjit). Person A reviews PRs but does not drive.

Bootstrapped from the [Prompt Opinion Google-ADK reference](https://github.com/prompt-opinion/po-adk-python). See [`REFERENCE.md`](REFERENCE.md) for what we copied, what we changed, and the upstream-sync workflow.

## What this service does

Receives A2A calls from Prompt Opinion (with a SHARP-propagated FHIR token in message metadata), orchestrates three internal sub-agents (Patient Context → Criteria Evaluator → PA Letter), and returns a submittable PA letter — or a needs-info checklist, or a red-flag-fast-track letter.

## Sub-agents (Week 2 — not in the spike yet)

1. **Patient Context** — bound to MCP tool `fetch_patient_context`. Clinical data retrieval.
2. **Criteria Evaluator** — bound to MCP tool `match_payer_criteria`. Decides approve / needs-info / deny; flags red flags.
3. **PA Letter** — bound to MCP tool `generate_pa_letter`. Produces the final deliverable.

All three route through a root orchestrator. Sub-agents do NOT call each other directly; handoffs flow through the orchestrator. Every handoff is ADK-traced — these traces are what we demo in the video.

See [`.cursor/rules/a2a-agent.md`](../.cursor/rules/a2a-agent.md) for conventions. All cross-service types are imported from [`shared.models`](../shared/models.py) — never redefined locally.

## Current structure (Week 1 Platform Spike)

```
a2a_agent/
├── agent.py              # Root agent (no sub-agents or tools yet — spike scope)
├── app.py                # uvicorn entry + agent card advertisement
├── __init__.py
├── pyproject.toml
├── po_base/              # PO reference ADK plumbing (see REFERENCE.md)
│   ├── __init__.py
│   ├── app_factory.py    # builds the A2A ASGI app + agent card
│   ├── middleware.py     # X-API-Key enforcement + FHIR metadata bridging
│   ├── fhir_hook.py      # before_model_callback that extracts FHIR creds
│   └── logging_utils.py
├── prompts/              # versioned system prompts (populated Week 2)
├── REFERENCE.md          # attribution + local-mod log
└── README.md
```

`Dockerfile` and `fly.toml` land end of Week 2 when we deploy publicly.

## Running locally

From the repo root, after `uv sync --all-extras --dev`:

```bash
# 1. Start the agent on :8001
make agent

# 2. (new terminal) Verify the agent card
make agent-card

# 3. (new terminal) Expose via ngrok for PO registration
make ngrok
```

Requires `.env` at repo root with at minimum `GOOGLE_API_KEY` and `AGENT_API_KEY` set. See root `.env.example` for the full list.

## Planned follow-up PRs

- `a2a_agent/sub-agents` — add Patient Context / Criteria Evaluator / PA Letter as nested ADK agents once `shared.models` contracts are stable (Week 2 Day 2-4).
- `a2a_agent/mcp-bindings` — wire sub-agents to `mcp_server/` tools via the MCP_SERVER_URL env var once Kevin's tools are deployed (Week 2).
- `a2a_agent/prompts/*_v1.md` — first-pass prompt library, versioned per `AGENTS.md` conventions.
- `a2a_agent/deploy/fly.toml` — Fly.io deployment (end of Week 2; ngrok-removed).
