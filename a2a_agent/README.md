# a2a_agent/

Google ADK A2A agent — our Devpost submission deliverable.

**Owner**: Person B (Sanjit). Person A reviews PRs but does not drive.

Bootstrapped from the [Prompt Opinion Google-ADK reference](https://github.com/prompt-opinion/po-adk-python). See [`REFERENCE.md`](REFERENCE.md) for what we copied, what we changed, and the upstream-sync workflow.

## What this service does

**PriorAuth Preflight — Lumbar MRI.** Receives A2A calls from Prompt Opinion (with a SHARP-propagated FHIR token in message metadata), orchestrates internal sub-agents, and performs denial-prevention preflight: chart-procedure mismatch detection (DO NOT SUBMIT safety gate), missing-documentation identification with clinician gap-fix templates, red-flag fast-track, and ready-to-submit PA letter generation.

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

### Exposing to Prompt Opinion (two tunnels)

When registering in a live PO workspace, the **MCP server** and the **A2A agent** need **separate public HTTPS URLs**. ngrok's free tier only supports one online endpoint, so we use **two different tools**:

| Service | Local port | Tunnel tool | Make target | PO registration surface |
|---|---|---|---|---|
| **MCP server** | `:8000` | Cloudflare Tunnel (`cloudflared`) | `make cf-tunnel` | Server Hub → `https://<cf-host>/mcp` |
| **A2A agent** | `:8001` | ngrok | `make ngrok` | External Agents UI → `https://<ngrok-host>/` (base only) |

See GitHub issue [#17](https://github.com/agents-assemble/priorauth-agent/issues/17) for the debug history that motivated this split.

#### One-time setup

```bash
# ngrok (A2A)
cp ngrok.example.yml ngrok.yml
# Edit ngrok.yml: set agent.authtoken (from https://dashboard.ngrok.com)

# cloudflared (MCP) — no config needed, just install
brew install cloudflared          # macOS
# winget install cloudflare.cloudflared   # Windows
```

#### Every session

```bash
# Terminal 1 — MCP tunnel (prints a *.trycloudflare.com URL)
make cf-tunnel

# Terminal 2 — A2A tunnel (prints ngrok forwarding URL)
make ngrok
```

Then:

1. Copy the cloudflared URL + `/mcp` into PO's **Server Hub**.
2. Copy the ngrok forwarding URL into PO's **External Agents UI** and into `AGENT_PUBLIC_URL` in `.env`.
3. Restart `make agent` so the agent card regenerates with the new public base.

Run `make tunnels` for a quick cheat-sheet of these steps.

On Windows without `make`:

```powershell
pwsh -File scripts/tunnels.ps1
```

## Week 2 — orchestration (Person B)

Handoff order, MCP tool names, and a **draft** root orchestrator instruction live in [`orchestration.py`](orchestration.py). `agent.py` still runs the **Week 1** root prompt until a follow-up PR swaps `instruction=` to `ORCHESTRATOR_INSTRUCTION_V1` and enables real sub-agent transfers with Kevin’s MCP tools bound.

### `patient_context` + MCP (step 1)

Set **`MCP_SERVER_URL`** in `.env` to the full MCP JSON-RPC URL (e.g. `http://localhost:8000/mcp`). The `patient_context` sub-agent then loads a Google ADK [`McpToolset`](https://github.com/google/adk-python) for **`fetch_patient_context`**, with `x-fhir-server-url` / `x-fhir-access-token` taken from the same session state the FHIR hook writes when PO sends SHARP context. `criteria_evaluator` and `pa_letter` are still unbound until their tools exist on the MCP server.

## Planned follow-up PRs

- `a2a_agent/sub-agents` — add Patient Context / Criteria Evaluator / PA Letter as nested ADK agents once `shared.models` contracts are stable (Week 2 Day 2-4).
- `a2a_agent/mcp-bindings` — wire sub-agents to `mcp_server/` tools via the MCP_SERVER_URL env var once Kevin's tools are deployed (Week 2).
- `a2a_agent/prompts/*_v1.md` — first-pass prompt library, versioned per `AGENTS.md` conventions.
- `a2a_agent/deploy/fly.toml` — Fly.io deployment (end of Week 2; ngrok-removed).
