# Prompt Opinion platform notes

Append-only log of Prompt Opinion quirks, behaviors, and gotchas discovered during development. The goal is to save the other human's AI agent from rediscovering the same thing tomorrow.

**Format**: YYYY-MM-DD — `<topic>` — what you learned, what was surprising, what to do about it.

Newest entries at the top. Link to specific PO docs / support threads / Discord messages when relevant.

---

## Template

```
## YYYY-MM-DD — <short topic>

**Context**: What were you doing?
**Observation**: What happened that was surprising or non-obvious?
**Explanation / workaround**: What's the correct mental model now? What should we do?
**Impact**: Code changes made, or follow-ups to file.
**Source**: Link to PO docs, Discord message, support email, or YouTube timestamp.
```

---

## 2026-04-22 — Initial facts from the Getting Started video

**Context**: Plan research before any code was written.
**Observations (from [Qvs_QK4meHc](https://youtu.be/Qvs_QK4meHc))**:

- Platform URL: `app.promptopinion.ai`. Sign up, add a model (Gemini 3.1 Flash Lite recommended for the Connectathon).
- Three submission paths: (1) no-code agent in PO with uploaded policy docs, (2) MCP server exposed via ngrok + registered in workspace hub, (3) custom external A2A agent built from PO's Google-ADK reference repo (Python or TypeScript).
- **Our path is (3).** We also publish (2) as a supporting marketplace listing.
- PO workspace itself IS a FHIR server. We import patients via the UI (can pick from pre-loaded, upload a bundle, or add manually) and upload clinical notes / documents per patient.
- When registering an external MCP or A2A agent, check the "pass token" checkbox — PO will propagate the FHIR token so our server can call workspace FHIR on the user's behalf.
- Google-ADK reference repo runs 3 built-in agents on different ports; the demo uses port **8001**.
- External A2A agent registration: paste ngrok URL → PO pulls the agent card → we set API key in middleware and paste it into PO.
- Marketplace publishing happens separately via "Marketplace Studio" before judging starts.

**Explanation / workaround**: We build our custom A2A agent externally and connect it as an external agent. All three-agent orchestration is internal to our process (visible via ADK traces), not configured in PO's UI.

**Impact**: Plan locked to Option 3 with Google ADK Python. Gemini 3.1 Flash Lite via free Google AI Studio key per developer.

**Source**: https://youtu.be/Qvs_QK4meHc (19m24s full walkthrough).
