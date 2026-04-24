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
# 1. Start the MCP server on :8000 (new terminal; needed for tool calls in Week-2+)
make mcp

# 2. Start the A2A agent on :8001 (new terminal)
make agent

# 3. (new terminal) Verify the agent card
make agent-card
```

Requires `.env` at repo root with at minimum `GOOGLE_API_KEY` and `AGENT_API_KEY` set. See root `.env.example` for the full list.

### Exposing to Prompt Opinion (two ngrok tunnels)

When registering in a live PO workspace, the **MCP server** and the **A2A agent** need **separate public HTTPS URLs** — one tunnel per local port. See GitHub issue [#17](https://github.com/agents-assemble/priorauth-agent/issues/17) for the debug history that motivated this layout.

- **A2A agent** (this service): PO's External Agents UI takes the public base — no path. `AGENT_PUBLIC_URL` in `.env` must match that same base so the agent card's `url` and `supportedInterfaces[].url` fields point at the public host (see [`a2a_agent/app.py`](app.py), which reads `AGENT_PUBLIC_URL` / `BASE_URL` when building the card).
- **MCP server**: PO's Server Hub takes the public URL **plus** the `/mcp` path — e.g. `https://<mcp-host>/mcp`. See [`../mcp_server/README.md`](../mcp_server/README.md) for the MCP-side setup.

Running both tunnels from one config file (so they can't race over the same hostname / trigger `ERR_NGROK_334`):

```bash
# One-time setup
cp ngrok.example.yml ngrok.yml
# Edit ngrok.yml: set agent.authtoken (from https://dashboard.ngrok.com) +
# replace YOUR-RESERVED-HOST.ngrok-free.dev with your reserved domain (or
# remove the url: line to get a random hostname on both endpoints).

# Every session
make ngrok-all       # or: ngrok start --all --config ngrok.yml
```

The ngrok dashboard (`http://localhost:4040`) will show two forwarding lines — one per service. Copy the `a2a` endpoint's public URL into PO's External Agents UI **and** paste it into `AGENT_PUBLIC_URL` in `.env`, then restart the agent (`make agent`) so the re-generated card reflects the new base.

If you don't have `make` (e.g. fresh Windows setup), use the PowerShell wrapper:

```powershell
pwsh -File scripts/ngrok-all.ps1
```

The single-tunnel `make ngrok` target is kept as a local-smoke convenience for iterating on the A2A app alone (e.g. `make agent-card` through a public URL), but it **must not** be used for PO round-trips — the MCP server won't be reachable and FHIR calls from the agent will fail.

## Planned follow-up PRs

- `a2a_agent/sub-agents` — add Patient Context / Criteria Evaluator / PA Letter as nested ADK agents once `shared.models` contracts are stable (Week 2 Day 2-4).
- `a2a_agent/mcp-bindings` — wire sub-agents to `mcp_server/` tools via the MCP_SERVER_URL env var once Kevin's tools are deployed (Week 2).
- `a2a_agent/prompts/*_v1.md` — first-pass prompt library, versioned per `AGENTS.md` conventions.
- `a2a_agent/deploy/fly.toml` — Fly.io deployment (end of Week 2; ngrok-removed).
