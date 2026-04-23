---
description: Google ADK A2A agent conventions (Person B — Sanjit's deployable)
globs: ["a2a_agent/**/*.py", "a2a_agent/**/*.json", "a2a_agent/**/*.md"]
alwaysApply: true
---

# A2A agent conventions

Owner: Person B (Sanjit). Person A reviews PRs here but does not drive.

## Structure

- Root orchestrator + 3 sub-agents all live in `a2a_agent/agent.py` (or split into `a2a_agent/sub_agents/` if it gets large).
- The agent card (`card.json`) advertises skills + endpoints to Prompt Opinion. It is served from the agent's public URL at the path documented in the reference repo.
- Middleware enforces the API key that PO uses to call us. Key value lives in `.env` only.
- Environment variables required: `GEMINI_MODEL`, `GOOGLE_API_KEY`, `MCP_SERVER_URL`, `AGENT_PUBLIC_URL`, `AGENT_API_KEY`.

## Sub-agent contract

Each sub-agent:

- Has a specific clinical role (patient context, criteria evaluation, PA letter).
- Is bound to exactly ONE MCP tool from `mcp_server/` (via `MCP_SERVER_URL`).
- Reads and writes types imported from `shared.models` — never invents local shapes.
- Has a short, specific system prompt. Prompts live in `a2a_agent/prompts/` and are versioned by filename.

## Handoff conventions

- Handoffs go through the root orchestrator; sub-agents do not call each other directly.
- Handoff payloads are Pydantic-validated against `shared/models.py`.
- Orchestrator enforces the sequence: patient_context → criteria_evaluator → pa_letter (unless red-flag fast-track branches).
- Trace every handoff via ADK's built-in tracing — these traces are what we demo in the final video.

## LLM hygiene (agent-level)

- All sub-agents use Gemini 3.1 Flash Lite via `GEMINI_MODEL` env var.
- Orchestrator `temperature=0.2` (allows minimal variability in routing); sub-agents that produce structured output `temperature=0`.
- Never call an OpenAI or Anthropic SDK from this package.

## PO integration notes

- `AGENT_PUBLIC_URL` must point to the Fly.io HTTPS URL in production (ngrok only for local dev).
- When PO registers our agent, it pulls the agent card from `${AGENT_PUBLIC_URL}/.well-known/agent-card.json` (or whatever path the PO reference uses — confirm on Day 1 and write to `docs/po_platform_notes.md`).
- The "pass FHIR token" checkbox in PO must be ON; our middleware forwards the token to the MCP server as-is.
