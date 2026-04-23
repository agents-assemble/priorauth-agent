# Prompt Opinion platform notes

Append-only log of Prompt Opinion quirks, behaviors, and gotchas discovered during development. The goal is to save the other human's AI agent from rediscovering the same thing tomorrow.

**Format**: YYYY-MM-DD — `<topic>` — what you learned, what was surprising, what to do about it.

Newest entries at the top. Link to specific PO docs / support threads / Discord messages when relevant.

---

## 2026-04-23 — Reference repo dependency pins (a2a-sdk namespace break)

**Context**: Platform Spike scaffold — copying PO's `po-adk-python` infra into `a2a_agent/po_base/` and running `uv sync --all-packages --all-extras --dev`.

**Observation**: PO's `requirements.txt` pins `a2a-sdk[http-server]>=0.3.0` with no upper bound. `uv` resolved this to `a2a-sdk==1.0.1`, which reorganised module paths — `a2a.server.apps` was moved. This broke `google-adk==1.31.1`'s internal import: `from a2a.server.apps import A2AStarletteApplication` raises `ModuleNotFoundError: No module named 'a2a.server.apps'`.

**Explanation / workaround**: Until `google-adk` ships a release that imports from the new `a2a-sdk` 1.0+ namespace, we must cap the SDK to `<1.0`. Added to `a2a_agent/pyproject.toml`:

```toml
"google-adk>=1.25.0,<2.0",
"a2a-sdk[http-server]>=0.3.0,<1.0",
```

Resolved versions after pin: `google-adk 1.31.1`, `a2a-sdk 0.3.26`. Agent boots and serves the agent card correctly under these pins.

**Impact**: Pinned in `a2a_agent/pyproject.toml`. Added to [REFERENCE.md](../a2a_agent/REFERENCE.md) upstream-sync checklist. When we pull updates from PO's `po-adk-python`, keep our pin; the reference repo's loose pin will silently break for other forkers until PO bumps it. Worth a tiny courtesy PR back upstream.

**Source**: Encountered during Platform Spike. `google-adk` changelog: https://github.com/google/adk-python/releases, `a2a-sdk` v1.0 notes: https://github.com/google-a2a/a2a-python/blob/main/CHANGELOG.md.

---

## 2026-04-23 — `uv sync` must use `--all-packages` in workspace layout

**Context**: First sync after adding `google-adk` + `a2a-sdk` deps to `a2a_agent/pyproject.toml`.

**Observation**: `uv sync --all-extras --dev` (what our `make install` used) reports "Resolved 147 packages" but does **not** install the workspace member's deps. `a2a-sdk` / `google-adk` were silently missing; `from a2a.types import AgentSkill` failed at runtime.

**Explanation / workaround**: In a `uv` workspace (root `pyproject.toml` has `[tool.uv.workspace]`), dependencies declared on workspace *members* are only installed when `--all-packages` is passed. Updated `Makefile`:

```makefile
install: ## Install all dependencies via uv (including workspace members)
	uv sync --all-packages --all-extras --dev
```

**Impact**: Makefile updated. Anyone (incl. Person A) pulling this branch should run `make install` (not a raw `uv sync`). Added as a header note to the `make install` target.

**Source**: `uv` workspaces docs: https://docs.astral.sh/uv/concepts/projects/workspaces/.

---

## 2026-04-23 — Upstream reference is unlicensed (flag for pre-publish)

**Context**: Bootstrapping `a2a_agent/po_base/` from `prompt-opinion/po-adk-python`.

**Observation**: The upstream repo has **no LICENSE file**. Their README clearly positions it as "Runnable examples showing how to build external agents" — hackathon starter template — but the absence of an explicit license means default-copyright-restrictive.

**Explanation / workaround**: Acceptable for hackathon use. Not acceptable for Marketplace Studio publishing. Tracked in `a2a_agent/REFERENCE.md` with attribution + fork log. Before Week 3 Day 1 (submission week), email `support@promptopinion.ai` to confirm license terms or request they add an OSS license to the reference. Backstop: rewrite `po_base/` against `a2a-sdk` directly with zero upstream code.

**Impact**: [a2a_agent/REFERENCE.md](../a2a_agent/REFERENCE.md) added. Week 3 follow-up logged.

**Source**: https://github.com/prompt-opinion/po-adk-python (checked 2026-04-23, no LICENSE file).

---

## 2026-04-23 — A2A v1 agent-card schema quirks

**Context**: Verifying local agent card at `GET /.well-known/agent-card.json`.

**Observation**: PO's `app_factory.py` carries a compatibility shim (`AgentCardV1`, `AgentExtensionV1`) because `a2a-sdk 0.3.x`'s Pydantic types don't match A2A v1 exactly. Specifically:

1. `url` is still emitted at the top level (deprecated in v1) AND duplicated inside `supportedInterfaces[0].url` (required by v1). PO's registration reads from `supportedInterfaces`.
2. `capabilities.stateTransitionHistory` must be `false` — v1-compliant, PO rejects agents that set this true.
3. `securitySchemes` uses nested typed-key format: `{"apiKey": {"apiKeySecurityScheme": {...}}}`. PO's UI expects the inner key to be `apiKeySecurityScheme` literally.

**Explanation / workaround**: The shim in `po_base/app_factory.py` handles all three automatically — we don't construct agent cards by hand. Just pass `url=...`, `require_api_key=True`, and the factory emits the v1-compliant JSON. Our live test confirmed all three flags render correctly.

When `a2a-sdk` ships native v1 support, follow the 3-step removal in [REFERENCE.md](../a2a_agent/REFERENCE.md).

**Impact**: None — factory handles it. Logged for when we upgrade the SDK.

**Source**: `po-adk-python/README.md`, top-level note: "The agent card published by all agents in this repo has been updated to comply with the A2A v1 specification as required by Prompt Opinion."

---

## 2026-04-23 — Gemini 3.1 Flash Lite Preview — stability watch

**Context**: Model selection per PO's Connectathon recommendation.

**Observation**: Google AI Studio lists `gemini-3.1-flash-lite-preview` as the Connectathon-recommended model. It is a **preview** tier — subject to rate-limit tightening, renames, or deprecation without deprecation windows.

**Explanation / workaround**: Set as default in `.env.example`. Implementation reads `os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")` so a single `.env` flip rolls back to GA. Backstop model: `gemini-2.5-flash-lite` (GA, confirmed stable).

**Weekly recheck** (Person B): every Monday, open https://aistudio.google.com/app/apikey, confirm the preview model is still listed for our key. If it disappears or rate-limits drop, flip `.env` to `gemini-2.5-flash-lite` on all deployed surfaces within 30 minutes. The backstop should remain functional because all our prompts target the flash-lite capability envelope.

**Impact**: `.env.example` updated with preview comment. Calendar reminder for Person B: Monday morning model check.

**Source**: Google AI Studio model list, user-provided identifier confirmed 2026-04-23.

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
