# Prompt Opinion platform notes

Append-only log of Prompt Opinion quirks, behaviors, and gotchas discovered during development. The goal is to save the other human's AI agent from rediscovering the same thing tomorrow.

**Format**: YYYY-MM-DD — `<topic>` — what you learned, what was surprising, what to do about it.

Newest entries at the top. Link to specific PO docs / support threads / Discord messages when relevant.

---

## 2026-04-23 — LLM cannot read session state; FHIR hook must inject a redacted prompt note

**Context**: Week-1 Platform Spike round-trip. PO general agent → our external A2A agent. `before_model_callback=extract_fhir_context` ran, extracted `patientId=82e4deff-...`, `fhirUrl=https://app.promptopinion.ai/api/workspaces/...`, and a 1558-char JWT, and wrote all three to `callback_context.state`. Live agent-log proof: `hook_called_fhir_found ... patient_id=82e4... fhir_url_set=True fhir_token=len=1558 sha256=6be5b48af078`.

**Observation**: Gemini responded saying *"FHIR context has not been received (required session state keys `patient_id`, `fhir_url`, `fhir_token` are currently missing)"* — the exact opposite of reality. Our original `a2a_agent/agent.py` instruction told the model to "check session state keys". That's an impossible instruction: ADK `before_model_callback` hooks can mutate the request, but `callback_context.state` is a hook-side Python dict with no reflection into the LLM's prompt. The LLM had nothing to "check" and confabulated a negative answer.

**Explanation / workaround**: Two-part fix in `a2a_agent/po_base/fhir_hook.py` + `a2a_agent/agent.py`:

1. Added `_inject_prompt_note(llm_request, ...)` helper. On successful FHIR extraction the hook now appends a `types.Content(role="user", parts=[types.Part.from_text(...)])` to `llm_request.contents` containing a **redacted** summary: `[SYSTEM NOTE — FHIR context received from A2A caller: patient_id=..., fhir_url=set, fhir_token=len=1558 sha256=6be5b48af078. ...do NOT echo the token or URL verbatim to the user.]`. Token value is never emitted — only the `token_fingerprint()` output. URL is reduced to `set`/`[EMPTY]`. Helper degrades silently if `google.genai` isn't importable (e.g. in a bare test harness) — session state is still populated, the LLM just loses visibility for that turn, logged as `prompt_note_injected=false`.
2. Rewrote the instruction in `agent.py` from "check session state keys" to "look for a line beginning with `[SYSTEM NOTE — FHIR context received`". Explicit pattern the LLM can actually see. Reinforced "never echo the token or URL verbatim" as a standalone negative constraint so a jailbreak-style prompt can't trick the model into leaking the redacted fingerprint.

**Impact**: `a2a_agent/po_base/fhir_hook.py` (hook behavior + top docstring), `a2a_agent/agent.py` (instruction). Logged as local mod in `a2a_agent/REFERENCE.md`. Pure-helper tests pin the redaction invariant in `tests/a2a_agent/test_fhir_hook_inject.py` (added via PR #9 review response to Kevin). Any future sub-agent that needs to reason over FHIR context must either (a) read via the upcoming MCP `fetch_patient_context` tool, or (b) expect the same system-note pattern in its prompt — we will not add more dict-introspection-masquerading-as-LLM-tooling.

**Known limitation (acknowledged; deferred to Week 2)**: the injected content is `role="user"`, which means a real user message that happens to begin with the same `[SYSTEM NOTE — FHIR context received...]` pattern is indistinguishable from our hook-injected note to the LLM. For the Week-1 spike this is acceptable because the note is only used to *narrate* receipt, not *gate* behavior. Once sub-agents start conditioning tool calls on the presence of the note (e.g. "only call `match_payer_criteria` if FHIR context is confirmed"), spoofability becomes a real concern. The Gemini-native fix is to mutate `llm_request.config.system_instruction` (which is not reachable from the user role in the chat template) instead of `contents`. Revisit at Week-2 Day-1 capability check when the three ADK sub-agents land. Flagged by @kevinsgeo in PR #9 review.

**Source**: Observed 2026-04-23 18:11 CDT during first PO round-trip. Agent-log sample in [STATUS.md](../STATUS.md) 2026-04-23 Person B entry. Redaction invariant + cross-file contract pinned in `tests/a2a_agent/test_fhir_hook_inject.py`.

---

## 2026-04-23 — PO reuses `taskId` on follow-up messages; A2A v1 rejects terminal-state reuse

**Context**: Week-1 spike round-trip. After our agent returned `TASK_STATE_COMPLETED` on the first message, PO's general agent tried to "help" by auto-sending a follow-up with the patient_id. PO emitted that follow-up with `params.message.taskId = "dd249d0c-fbc5-48f5-b428-40c81adaba53"` — the exact task id we just completed.

**Observation**: ADK's A2A task manager returned `{"error": {"code": -32602, "message": "Task dd249d0c-... is in terminal state: completed"}}`. Per A2A v1 spec, completed tasks are immutable; new messages should create a **new** task (no `taskId`, or a fresh one). PO appears to conflate "conversation continuation" with "task continuation". Wire proof in agent log: two successive `POST /` with `params.message.taskId=<same uuid>`, first returns 200 + completed task, second returns JSON-RPC -32602.

**Explanation / workaround**: Nothing to fix on our side — ADK's rejection is spec-correct. Short-term: accept that multi-turn via PO's general-agent tool chain is broken until PO fixes task lifecycle. The user-visible symptom is PO showing *"Task ... is in terminal state: completed"* after the second message, then falling back to its own reasoning. Non-blocking for the Week-1 spike gate (single round-trip clears it) and non-blocking for the demo video (Patient B needs-info flow is a single turn with an uploaded-note interstitial, not a chained auto-reply). Options if it bites us during Week-2/3:

1. Cleanest: report to PO support — share the trace id from the `traceparent` header so they can look up our request server-side. W3C tracing is already enabled on their end.
2. Workaround: middleware strips `taskId` from the payload when it matches a completed task in our own bookkeeping. Cheap, but hides a real PO bug and masks contract drift — do not ship without documenting.
3. Override: configure ADK task manager to reopen completed tasks. Breaks A2A v1 compliance — rejected.

**Impact**: Logged. No code change this PR. File a PO support ticket pre-Week-2-Day-1 capability check so there's a name on it when we're debugging multi-turn demos.

**Source**: Same round-trip as the note above. PO user-side symptom: *"The request to initiate the prior authorization for the lumbar MRI has been processed, but the external system indicated that the task reached a completed state..."*.

---

## 2026-04-23 — PO backend source IP (Azure US-East-2) + two-fetch registration pattern

**Context**: Live A2A agent log during Week-1 spike PO registration and first round-trip.

**Observations**:

1. **Source IP**: all inbound calls from PO to our agent came from `20.80.113.52` — Microsoft Azure US East 2 datacenter range. That matches PO's known hosting footprint (they're on Azure). Means our Fly.io production deployment can safely allowlist the Azure US-East-2 egress ranges in place of wide-open ingress if we want defense-in-depth beyond the API key. Not urgent — API key + ngrok tunnel scoping is enough for dev — but worth a fly.toml comment when we deploy.
2. **Two-fetch on registration**: PO fetched `/.well-known/agent-card.json` **twice** within ~21 seconds while adding our agent — `18:08:05` and `18:08:26` CDT. No X-API-Key on either (agent card is public, correct). Most likely pattern: first fetch validates the URL+card schema live while the user is typing; second fetch snapshots the card on "Save". No code action needed; just good to know the second fetch is normal, not a retry / flap.
3. **Tracing header**: every PO → agent request carries a W3C `traceparent` header (`00-<trace-id>-<span-id>-<flags>`). PO runs distributed tracing server-side. Means any PO support ticket should include the trace id from our request log for one-shot server-side lookup. No sampling suppression observed — flag byte was `01` (sampled) on the spike request.

**Explanation / workaround**:

1. For Week-2 Fly.io deploy: add a comment in `fly.toml` next to the public HTTPS section flagging Azure US-East-2 as the expected source range, and bookmark Microsoft's downloadable IP range JSON (`https://www.microsoft.com/en-us/download/details.aspx?id=56519`) in case we want to tighten ingress post-demo. Do NOT add the allowlist now — PO may change hosting before judging and breaking discovery mid-demo is the worst possible failure.
2. No action on the two-fetch pattern beyond this note (saves someone future time when they see two 200s in a row on registration and panic).
3. For tracing: when we open a PO support ticket, paste the relevant `traceparent` header from our log.

**Impact**: Documentation only this PR. Follow-up: `fly.toml` comment when we deploy in Week 2.

**Source**: Agent log `a2a_agent.po_base.middleware incoming_http_request` entries 2026-04-23 18:08:05 / 18:08:26 / 18:11:06 CDT.

---

## 2026-04-23 — Payer policy WAFs block automated extraction; manual-verification-pass workflow

**Context**: Payer-criteria research for PR #6 (`docs/payer_criteria_research.md`). Needed to extract the lumbar MRI medical-necessity policy text from Cigna (via eviCore) and Aetna (CPB 0236) for paraphrase + citation.

**Observation**: Two distinct extraction failure modes hit during one research session:

1. **Aetna Incapsula bot-challenge**. Direct fetch of `https://www.aetna.com/cpb/medical/data/200_299/0236.html` returned a JavaScript-challenge HTML page (incident ID `1345000620024825391-18399296386830212`) instead of policy content. Aetna runs Imperva Incapsula on `www.aetna.com`; any non-browser User-Agent (or even a real browser's first request without prior session cookies) trips the challenge. Worked around by falling back to `https://es.aetna.com/cpb/medical/data/200_299/0236.html` — Aetna's Spanish-portal mirror that hosts the **English-language CPBs verbatim** for Spanish-speaking US members. The mirror is not behind Incapsula and served identical policy text.
2. **eviCore PDF size cap**. The Cigna lumbar MRI policy is delegated to eviCore's spine-imaging guideline V1.0.2026 (`evicore.com/.../pdfs/.../spine_imaging_v1_0_2026.pdf`). First fetch hit our tool's 200 KB text-extraction cap (extracted text was ~205 KB); had to re-fetch with a higher token limit to capture the conservative-therapy + red-flag sections at the end of the document.

**Why it matters**: Payer-criteria source citations need to be the **canonical** URL the policy is published at, not a mirror or a cached PDF. Citing `es.aetna.com` in `aetna_lumbar_mri.json::source_policy_url` would look like sloppy research to a clinician reviewer (and to a judge), even though the content is identical. So we landed a **manual-verification-pass workflow**:

1. Original automated extraction uses whatever source works (mirror, PDF, cache) and logs the discrepancy in a "Source integrity notes" section of the research doc.
2. Before any criteria JSON encodes a `source_policy_url`, a human re-fetches the canonical URL from a normal browser session, runs spot-checks on the extracted thresholds + structural phrasing + red-flag taxonomy + ICD code lists against the live page, and appends a verification log to the research doc with results + decision.
3. Verification log format is a markdown table with columns `# | Expected | Observed | Result`. PR #6 has the worked example (`docs/payer_criteria_research.md` → `## Aetna canonical-URL verification log`).
4. Discrepancies surfaced by the verification pass are corrected in the doc **before** the JSON encoding PR is opened, not after.

**Concrete payoff from running the pattern once**: PR #6's verification pass caught a real misattribution in Aetna §5 — the original automated extraction had attributed the BoneMRI experimental subsection's Z-code exclusions (`Z01.818`, `Z01.89`, `Z08`, `Z12.x`, `Z85.x`) to the main CPB 0236 lumbar MRI policy. They are scoped only to BoneMRI on the live page. Had this propagated into `aetna_lumbar_mri.json`, the rule engine would have over-rejected legitimate cases where a covered lumbar MRI happens to carry a personal-cancer-history Z-code alongside a covered lumbar diagnosis (e.g., `Z85.3` + `M54.16` + 6wk conservative therapy is a *covered* MRI under CPB 0236). Caught at doc-review cost; would have been caught at golden-file-test cost otherwise — order-of-magnitude more expensive.

**Explanation / workaround**:

- For each new payer added to the criteria set (v2 candidates: UnitedHealth, Anthem, Humana, BCBS regionals), assume the canonical policy URL is behind a WAF and budget the manual verification pass into the research timeline. Roughly: 30 min automated extraction → 15 min manual verification pass → 0–30 min discrepancy correction depending on what's caught.
- Mirror discovery trick that worked once for Aetna: try the Spanish-language portal subdomain (`es.<payer>.com`). Many US payers host English CPBs there for Spanish-speaking-member entry, often without WAF rules.
- For PDF-delivered policies (eviCore, AIM, NIA, etc.): always re-fetch with a generous text-extraction limit on the first pass; conservative-therapy duration + red-flag sections tend to live at the document's end and silently truncate.
- Never cite a mirror URL or a PDF-cache URL as the JSON's `source_policy_url`. The canonical URL must verify successfully (or the entry doesn't ship until it does).

**Impact**: Workflow documented here. PR #6 provides the worked example. Risk Register entry "Payer criteria accuracy + IP" extended in `docs/PLAN.md` to reference this workflow as the mitigation.

**Source**: PR #6 review (`@Sanjit2004` non-blocking note #2 explicitly requested the canonical-URL verification before encoding); Aetna live page verified 2026-04-23 from a non-bot-blocked browser session.

---

## 2026-04-23 — SHARP JWT trust model: we don't verify, FHIR server does

**Context**: Writing `get_patient_id_if_context_exists` in `mcp_server/fhir/context.py` and deciding how to extract the `patient` claim from the `x-fhir-access-token` header.

**Observation**: Upstream (`po-community-mcp/python/fhir_utilities.py`) decodes the token with `jwt.decode(..., options={"verify_signature": False})` and uses the `patient` claim for FHIR lookups without signature verification. At first glance this looks broken — anyone could forge a JWT with an arbitrary `patient` claim and read another patient's context.

**Why it's actually fine**: The security boundary is not at our MCP layer — it's at the **next hop**, the FHIR server. When our `FhirClient` forwards the same token as `Authorization: Bearer <token>`, the FHIR server re-authorizes against its own JWKS (which it owns and rotates) and rejects forged tokens and mismatched-`patient`-claim tokens. Our layer only uses the decoded claim for **routing** — which patient id to scope the FHIR search to. Any authorization decision still lands on the FHIR server.

**Assumption we're inheriting**: the PO workspace FHIR is correctly configured to enforce `patient` claim matching. If that ever stops holding (dev FHIR with auth off, misconfigured workspace, a FHIR proxy that strips the token), a caller could spoof the claim. Worth surfacing to the PO team the first time we test against a non-sandbox workspace.

**Why we can't verify at this layer**: public keys rotate per PO workspace and we don't own the JWKS endpoint. Adding verification here would be a second, weaker authorization point that duplicates the FHIR server's work and introduces drift risk (our JWKS cache vs. theirs).

**Source**: `mcp_server/fhir/context.py::get_patient_id_if_context_exists` docstring; this note is cross-referenced from there. PR #3 review thread (Sanjit) asked for this to be explicit.

---

## 2026-04-23 — FastMCP capability extensions require `get_capabilities` monkeypatch

**Context**: Scaffolding `mcp_server/` and needing to advertise the `ai.promptopinion/fhir-context` extension (the custom capability key PO's registration UI looks for to know we accept SHARP-propagated FHIR tokens).

**Observation**: `mcp>=1.9.x`'s `FastMCP` does not expose a first-class API for adding custom capability keys. Upstream `po-community-mcp/python/mcp_instance.py` works around this by wrapping `mcp._mcp_server.get_capabilities` with a monkeypatch that mutates the returned `ServerCapabilities` Pydantic model's `model_extra` dict to inject the custom `extensions` key. Two sub-surprises:

1. `ServerCapabilities.model_extra` is `None` unless the Pydantic model was constructed with extras, so naively indexing `caps.model_extra["extensions"] = ...` raises on a freshly-built capabilities object. Must initialize `caps.__pydantic_extra__ = {}` first.
2. mypy strict complains about `caps.model_extra["extensions"] = ...` because `model_extra` is typed `dict[str, Any] | None` even after the `is None` check (the property re-reads `__pydantic_extra__` each call, so the type checker can't narrow across the assignment). Workaround: `assert caps.model_extra is not None` after the init — mypy narrows on the assertion, runtime cost is zero in `-O` builds.

**Explanation / workaround**: Encapsulated the entire mess in `mcp_server/server.py::_patch_capabilities(mcp: FastMCP) -> None` so tool files never see it. Verified live: `POST /mcp` with an `initialize` JSON-RPC returns the `capabilities.extensions["ai.promptopinion/fhir-context"]` blob with all 8 scopes we declare. Cross-reference tracker: [https://github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) — watch for a first-class `extensions=` kwarg on `FastMCP(...)` and delete the monkeypatch when it ships.

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

1. Moved `load_dotenv(override=True)` to `a2a_agent/__init__.py` as the **first statement** (just below the module docstring). This runs unconditionally when *any* `a2a_agent.`* submodule is imported — including `po_base.middleware` — so env is populated before any module-level env reads.
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

**Source**: Encountered during Platform Spike. `google-adk` changelog: [https://github.com/google/adk-python/releases](https://github.com/google/adk-python/releases), `a2a-sdk` v1.0 notes: [https://github.com/google-a2a/a2a-python/blob/main/CHANGELOG.md](https://github.com/google-a2a/a2a-python/blob/main/CHANGELOG.md).

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

**Source**: `uv` workspaces docs: [https://docs.astral.sh/uv/concepts/projects/workspaces/](https://docs.astral.sh/uv/concepts/projects/workspaces/).

---

## 2026-04-23 — Upstream reference is unlicensed (flag for pre-publish)

**Context**: Bootstrapping `a2a_agent/po_base/` from `prompt-opinion/po-adk-python`.

**Observation**: The upstream repo has **no LICENSE file**. Their README clearly positions it as "Runnable examples showing how to build external agents" — hackathon starter template — but the absence of an explicit license means default-copyright-restrictive.

**Explanation / workaround**: Acceptable for hackathon use. Not acceptable for Marketplace Studio publishing. Tracked in `a2a_agent/REFERENCE.md` with attribution + fork log. Before Week 3 Day 1 (submission week), email `support@promptopinion.ai` to confirm license terms or request they add an OSS license to the reference. Backstop: rewrite `po_base/` against `a2a-sdk` directly with zero upstream code.

**Impact**: [a2a_agent/REFERENCE.md](../a2a_agent/REFERENCE.md) added. Week 3 follow-up logged.

**Source**: [https://github.com/prompt-opinion/po-adk-python](https://github.com/prompt-opinion/po-adk-python) (checked 2026-04-23, no LICENSE file).

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

**Weekly recheck** (Person B): every Monday, open [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey), confirm the preview model is still listed for our key. If it disappears or rate-limits drop, flip `.env` to `gemini-2.5-flash-lite` on all deployed surfaces within 30 minutes. The backstop should remain functional because all our prompts target the flash-lite capability envelope.

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

**Source**: [https://youtu.be/Qvs_QK4meHc](https://youtu.be/Qvs_QK4meHc) (19m24s full walkthrough).