# Architecture

High-level architecture for the PriorAuth Agent. For strategic context (why), see [`PLAN.md`](PLAN.md). For PO-specific quirks, see [`po_platform_notes.md`](po_platform_notes.md).

## Runtime diagram

```
┌──────────────────────────────── Prompt Opinion Workspace ───────────────────────────────┐
│                                                                                          │
│   Clinician ──► General User Agent                                                        │
│                       │                                                                   │
│                       │  A2A call + FHIR token (SHARP)                                    │
│                       ▼                                                                   │
│            ┌──── Our A2A Agent (Fly.io HTTPS) ────┐                                       │
│            │   Root Orchestrator                  │                                       │
│            │   ├── Patient Context Sub-agent ─────┼──► our MCP Server ──► Workspace FHIR  │
│            │   ├── Criteria Evaluator Sub-agent ──┼──► our MCP Server                     │
│            │   └── PA Letter Sub-agent ───────────┼──► our MCP Server                     │
│            └──────────────────────────────────────┘                                       │
│                                                                                          │
│   Workspace FHIR Server (imported patients + hand-authored clinical notes)                │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                   ▲                                    ▲
                                   │                                    │
                       Our A2A Agent and MCP Server       shared Gemini 3.1 Flash Lite LLM
                         are two separate deployables       (Google AI Studio free tier)
                         in one repo, connected via
                         MCP_SERVER_URL env var
```

## Key design decisions (ADRs)

### ADR-001 — Submit as Option 3 (custom external A2A agent), not Option 1 or 2

Prompt Opinion offers three submission paths. We chose Option 3 because it keeps all orchestration logic in code (testable, reproducible, versioned) while still demonstrating the multi-agent handoff story that the hackathon is named after. Option 1 (no-code agents in PO UI) would require us to click through a UI for every agent-config change; Option 2 (MCP only) would cap us at "I built a tool" rather than "I built a workflow". Option 3 gives us the full story with minimal platform coupling.

### ADR-002 — Google ADK as the A2A framework, Python as the language

PO publishes working reference repos for Google ADK in Python and TypeScript. We fork the Python one because (a) Python has the strongest FHIR + LLM ecosystem, (b) it's already the reference impl that speaks PO's A2A dialect correctly, (c) FastMCP is mature in Python.

### ADR-003 — Gemini 3.1 Flash Lite as the shared LLM

PO's getting-started video explicitly recommends Gemini 3.1 Flash Lite via Google AI Studio (free tier). Every developer gets their own free API key. Model name is always read from `GEMINI_MODEL` env var. A capability check on Week 2 Day 1 decides whether we escalate to a larger Gemini tier.

### ADR-004 — One Devpost submission (A2A agent), two marketplace listings

We publish both the A2A agent AND the MCP toolkit to PO's Marketplace Studio for ecosystem visibility. But we submit only the A2A agent to Devpost, to concentrate narrative polish on one thing. The MCP toolkit gets credited inside the A2A submission's architecture section.

### ADR-005 — `shared/` is the single source of truth for cross-service types

Pydantic models (`PatientContext`, `CriteriaResult`, `PALetter`) live in `shared/models.py`. Both `mcp_server/` and `a2a_agent/` import from there. This is enforced by `CODEOWNERS` (both humans must approve any `shared/` change) and by a Cursor rule (`shared-contracts.md`). This prevents the #1 failure mode of two-agent-driven collab: both agents inventing slightly different schemas.

### ADR-006 — Fly.io for production deployment, ngrok for local dev only

Judges need persistent public HTTPS URLs to invoke our services during judging. ngrok URLs are unstable. Both deployables go to Fly.io by end of Week 2; ngrok URLs are swapped out of PO workspace at that point and must never appear in production config.

### ADR-007 — 3 demo patients cover happy path, needs-info, red-flag

Patient A = textbook approval, Patient B = needs-info (no PT documented), Patient C = cauda equina red-flag fast-track. The three cases together are the core of the demo video. Clinical notes for Patient C are hand-authored (not Synthea-generated) to ensure realistic narrative content for the LLM red-flag detection pass.
