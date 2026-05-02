# PriorAuth Preflight

> Denial-prevention preflight for lumbar MRI prior authorization, built for the [Agents Assemble](https://agents-assemble.devpost.com/) hackathon.

Most PA agents generate packets. **PriorAuth Preflight decides whether a lumbar MRI packet should be generated at all, then fixes missing documentation first.** It evaluates payer criteria against a patient's FHIR chart, detects chart-procedure mismatches (DO NOT SUBMIT safety gate), surfaces missing documentation with clinician-ready gap-fix templates, and generates ready-to-submit PA letters only when the chart is complete — in seconds instead of hours.

---

## Architecture

```
Prompt Opinion workspace
├── Clinician ↔ General User Agent ↔ (A2A + FHIR token) ↔ OUR A2A Agent
│                                                            ↓
│                                      Orchestrator → {PatientContext, CriteriaEvaluator, PALetter} sub-agents
│                                                            ↓
│                                                      OUR MCP Server (3 tools) ↔ Workspace FHIR
└── Gemini 3.1 Flash Lite (shared LLM)
```

See `[docs/PLAN.md](docs/PLAN.md)` for full strategic context, `[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)` for the diagram and architecture decisions.

## Project layout


| Path             | Purpose                                                                   | Owner             |
| ---------------- | ------------------------------------------------------------------------- | ----------------- |
| `mcp_server/`    | FastMCP server — 3 tools (fetch context, match criteria, generate letter) | Person A (Kevin)  |
| `a2a_agent/`     | Google ADK A2A agent — orchestrator + 3 sub-agents                        | Person B (Sanjit) |
| `shared/`        | Pydantic contracts shared between services                                | Both              |
| `demo/`          | 3 demo patients + hand-authored clinical notes                            | Both              |
| `docs/`          | Plan, architecture, PO platform notes                                     | Both              |
| `.cursor/rules/` | Scoped agent rules                                                        | Both              |


## Team

- **Person A (MCP lead)**: Kevin Shine George ([@kevinsgeo](https://github.com/kevinsgeo))
- **Person B (A2A lead)**: Sanjit Saji ([@Sanjit2004](https://github.com/Sanjit2004))

Conventions for the agents live in `[AGENTS.md](AGENTS.md)`. Daily status in `[STATUS.md](STATUS.md)`.

## Getting started (local dev)

> Prerequisites: Python 3.11+, `[uv](https://docs.astral.sh/uv/)`, `[ngrok](https://ngrok.com/)` or Cloudflare Tunnel, Docker (optional for local stack), a free [Google AI Studio](https://aistudio.google.com/) API key, a [Prompt Opinion](https://app.promptopinion.ai/) account.

**Run MCP (8000) + A2A (8001) on one computer and register both in Prompt
Opinion** (full handoff for a teammate, e.g. Person A on a single machine): see
[docs/LOCAL_DEV_ONE_MACHINE.md](docs/LOCAL_DEV_ONE_MACHINE.md) — two public
urls, `MCP_SERVER_URL` + `AGENT_PUBLIC_URL`, PO Server Hub + External Agents
UI.

```bash
# Clone + install
git clone git@github.com:agents-assemble/priorauth-agent.git
cd priorauth-agent
uv sync

# Configure env
cp .env.example .env
# Fill in GOOGLE_API_KEY and other values (see doc above for full list)

# Run everything locally (MCP + A2A + optional ngrok)
make dev

# Run integration smoke test against all 3 demo patients
make integration

# Lint + typecheck + test
make check
```

## Submission summary (what the judges see)

- **Category**: Option 3 — Custom external A2A Agent.
- **Primary deliverable**: `PriorAuth Preflight` published to the Prompt Opinion Marketplace.
- **Secondary deliverable**: `PriorAuth Toolkit` MCP server, also published to the marketplace for ecosystem visibility.
- **Demo video**: under 3 minutes, pre-recorded, leads with the `needs-info` + gap-fix differentiator.
- **Devpost writeup**: see `[SUBMISSION.md](SUBMISSION.md)` (draft).

## License

TBD (private hackathon repo).