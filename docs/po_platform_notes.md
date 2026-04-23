# Prompt Opinion platform notes

Append-only log of Prompt Opinion quirks, behaviors, and gotchas discovered during development. The goal is to save the other human's AI agent from rediscovering the same thing tomorrow.

**Format**: YYYY-MM-DD — `<topic>` — what you learned, what was surprising, what to do about it.

Newest entries at the top. Link to specific PO docs / support threads / Discord messages when relevant.

---

## 2026-04-23 — FastMCP capability extensions require `get_capabilities` monkeypatch

**Context**: Scaffolding `mcp_server/` and needing to advertise the `ai.promptopinion/fhir-context` extension (the custom capability key PO's registration UI looks for to know we accept SHARP-propagated FHIR tokens).

**Observation**: `mcp>=1.9.x`'s `FastMCP` does not expose a first-class API for adding custom capability keys. Upstream `po-community-mcp/python/mcp_instance.py` works around this by wrapping `mcp._mcp_server.get_capabilities` with a monkeypatch that mutates the returned `ServerCapabilities` Pydantic model's `model_extra` dict to inject the custom `extensions` key. Two sub-surprises:

1. `ServerCapabilities.model_extra` is `None` unless the Pydantic model was constructed with extras, so naively indexing `caps.model_extra["extensions"] = ...` raises on a freshly-built capabilities object. Must initialize `caps.__pydantic_extra__ = {}` first.
2. mypy strict complains about `caps.model_extra["extensions"] = ...` because `model_extra` is typed `dict[str, Any] | None` even after the `is None` check (the property re-reads `__pydantic_extra__` each call, so the type checker can't narrow across the assignment). Workaround: `assert caps.model_extra is not None` after the init — mypy narrows on the assertion, runtime cost is zero in `-O` builds.

**Explanation / workaround**: Encapsulated the entire mess in `mcp_server/server.py::_patch_capabilities(mcp: FastMCP) -> None` so tool files never see it. Verified live: `POST /mcp` with an `initialize` JSON-RPC returns the `capabilities.extensions["ai.promptopinion/fhir-context"]` blob with all 8 scopes we declare. Cross-reference tracker: https://github.com/modelcontextprotocol/python-sdk — watch for a first-class `extensions=` kwarg on `FastMCP(...)` and delete the monkeypatch when it ships.

**Impact**: Logic lives in `mcp_server/server.py`. Upstream-sync checklist in `mcp_server/REFERENCE.md` notes the monkeypatch as the most likely file to churn on an `mcp` bump.

**Source**: Direct read of `prompt-opinion/po-community-mcp/python/mcp_instance.py@e19ec91` + our own mypy struggle writing the strict-typed version.

---

## 2026-04-23 — FastMCP `Context` is generic; strict mypy needs a type alias

**Context**: Writing `fetch_patient_context(ctx: Context)` with `mypy --strict` on.

**Observation**: `mcp.server.fastmcp.Context` is declared `Generic[ServerSessionT, LifespanContextT, RequestT]`. Strict mypy rejects unparameterized `Context` with `error: Missing type arguments for generic type "Context"  [type-arg]`. The three typevars are plumbing concerns our tools never read — we only ever access `ctx.request_context.request.headers`, which is `Any`-typed downstream.

**Explanation / workaround**: Defined a single alias `McpContext = Context[Any, Any, Any]` in `mcp_server/fhir/context.py` and use it consistently in every tool signature. Upstream PO community MCP sidesteps this because they run mypy non-strict — doesn't show up in their source, would bite any fork that ratchets strictness.

**Impact**: `mcp_server/fhir/context.py` exports `McpContext`. All tool files import from there. Documented as part of the ruleset in `mcp_server/REFERENCE.md`.

**Source**: First clean mypy run on the MCP scaffold.

---

## 2026-04-23 — `FastMCP(stateless_http=True)` matters for PO registration

**Context**: Choosing `stateless_http=True` vs `False` when constructing the `FastMCP` instance.

**Observation**: Upstream PO community MCP sets `stateless_http=True` explicitly. Without it, FastMCP expects every client to carry an `mcp-session-id` header established via the initial `initialize` response, which breaks PO's registration flow (PO re-initializes on every tool call rather than threading a persistent session, presumably because workspace UI calls bounce across browser tabs). `stateless_http=True` makes every JSON-RPC round-trip self-contained, trading a tiny amount of FastMCP-internal session-caching for PO-compatible behaviour.

**Explanation / workaround**: Honour upstream's choice. We set `stateless_http=True` in `mcp_server/server.py`. Verified our server responds to a cold `tools/call` immediately after `initialize` without a session header threaded — matches PO's observed behaviour. If we ever want long-lived sessions (e.g. for streaming progress on a slow tool), that's a separate server on a separate port; this server stays stateless.

**Impact**: Single line in `server.py` but a hard gotcha to debug if flipped accidentally. Noted in `mcp_server/REFERENCE.md` upstream-sync checklist.

**Source**: `prompt-opinion/po-community-mcp/python/mcp_instance.py@e19ec91` + behavioural test against our own server.

---

## 2026-04-23 — `load_dotenv()` ordering + stale shell-env footgun

**Context**: Surfaced while fixing the `AGENT_API_KEY` bug on PR #2 (below). Hit *twice* in one session, worth a dedicated entry.

**Observation**: Two separate import-time failure modes around `load_dotenv()`:

1. **Ordering**: If `load_dotenv()` lives in `a2a_agent/app.py` **after** the `from a2a_agent.po_base.app_factory import create_a2a_app` line, it runs too late. `po_base/middleware.py` computes `VALID_API_KEYS = _load_valid_api_keys()` at **module import time** — so by the time `load_dotenv()` executes, the middleware has already cached `VALID_API_KEYS == set()` from an empty env, and every authenticated request 403s.
2. **No-override default**: `load_dotenv()` does NOT overwrite env vars already set in the parent process. If a developer has a stale `AGENT_API_KEY=test-placeholder` left in their shell from an earlier session, `.env` is silently ignored and the agent happily accepts a placeholder key in prod-shaped config. Almost-impossible to spot without explicit debug printouts.

**Explanation / workaround**:

1. Moved `load_dotenv(override=True)` to `a2a_agent/__init__.py` as the **first statement** (just below the module docstring). This runs unconditionally when *any* `a2a_agent.*` submodule is imported — including `po_base.middleware` — so env is populated before any module-level env reads.
2. `override=True` makes `.env` the single source of truth for local dev. Container prod is unaffected because the image has no `.env` file, so `load_dotenv` is a no-op there.
3. Also added `--env-file .env` to `make agent` as belt-and-suspenders (uvicorn loads env before our Python code even imports, pre-empting any ordering question).

**Impact / reminder**: Any future subpackage that reads env at import time (likely `mcp_server` too, once Kevin wires credentials in) must rely on the same `__init__.py` pattern, or explicitly import and call `load_dotenv(override=True)` before its own module-level state. Do NOT let env reads scatter across ad-hoc `os.getenv()` calls in `app.py`-style entry points.

**Source**: PR #2 review by @kevinsgeo caught the AGENT_API_KEY bug. I caught this ordering issue while writing the positive-auth smoke test (which Kevin's review implicitly required). Original `app.py` pattern came from upstream PO reference repo — they do not use workspace-style package entry points, so upstream dodges it.

---

## 2026-04-23 — `AGENT_API_KEY` env var silently ignored in upstream middleware

**Context**: PR #2 review — Kevin caught before merge.

**Observation**: `a2a_agent/po_base/middleware.py::_load_valid_api_keys` (verbatim from upstream) only reads `API_KEYS`, `API_KEY_PRIMARY`, `API_KEY_SECONDARY`. Our spec advertises `AGENT_API_KEY` as the canonical variant in `.env.example`, `.cursor/rules/a2a-agent.md`, and `docs/PLAN.md`. Anyone following the documented setup would get `VALID_API_KEYS == set()` and every non-agent-card request would 401 — including every single PO → us call.

My spike smoke test passed because I only hit the unauthenticated `GET /.well-known/agent-card.json` endpoint, never a POST with the `X-API-Key` header. **Lesson for the rest of the hackathon**: every scaffold PR that adds an auth path must include a positive-auth curl check (POST with the advertised key and assert non-401), not just the public endpoint.

**Explanation / workaround**: 3-line local mod to `_load_valid_api_keys` — read `AGENT_API_KEY` first, then fall through to the upstream env var list. Documented in `a2a_agent/REFERENCE.md` section "Local modifications".

**Impact**: PR #2 fix. Added `make agent-post-smoke` target planned for next PR (curl POST with X-API-Key → assert 200 or 400-with-jsonrpc-error, never 401).

**Source**: PR #2 review by @kevinsgeo.

---

## 2026-04-23 — Week 3 checklist: redact `patient_id` in logs before real-patient demo

**Context**: PR #2 review, nit #3.

**Observation**: `a2a_agent/po_base/fhir_hook.py` logs `patient_id` in plain text (`"FHIR_PATIENT_FOUND value=%s"`, lines ~190-220). Fine for our synthetic demo patients A/B/C, but for any PO-chat demo against real workspace FHIR data this is a PII/PHI leak vector.

**Explanation / workaround**: Pre-demo hardening. Replace the plain-text patient log with a hashed / first-4-chars-only format, similar to how `token_fingerprint()` is already used for the FHIR token. Keep it behind `LOG_LEVEL=DEBUG` if full identifier is ever needed locally.

**Impact**: Week 3 Day 1 checklist entry (pre-submission). Add to `docs/PLAN.md` Risk Register as "P3 — log redaction audit before demo recording".

**Source**: PR #2 review by @kevinsgeo. No action this PR.

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
