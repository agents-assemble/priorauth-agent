# Upstream reference — attribution & fork log

This package was bootstrapped from the Prompt Opinion Google-ADK A2A reference repo.

## Source

- **Upstream**: https://github.com/prompt-opinion/po-adk-python
- **Copied from branch**: `main`
- **Copied on**: 2026-04-23
- **Upstream `README.md`**: describes the repo as "Runnable examples showing how to build external agents that connect to Prompt Opinion". Clearly intended as a starting template; no LICENSE file in the repo as of copy date.

## Risk: no explicit LICENSE

The upstream repo ships **without a LICENSE file**, which technically means default-copyright-restrictive. For hackathon use this is acceptable — the repo is PO's published reference template for the Agents Assemble Connectathon — but we flag it here so we can clarify before marketplace publishing.

**Follow-up (Week 3 Day 1)**: before publishing the A2A agent to Marketplace Studio, email `support@promptopinion.ai` to confirm license terms or request they add an OSS license to the reference repo. If they cannot confirm, we should rewrite `a2a_agent/po_base/` against the `a2a-sdk` API directly (no upstream code retained).

## What we copied, where it landed

| Upstream path | Our path | Notes |
|---|---|---|
| `shared/__init__.py` | `a2a_agent/po_base/__init__.py` | Rewrote header comment; kept `configure_logging` call |
| `shared/app_factory.py` | `a2a_agent/po_base/app_factory.py` | Imports rewritten: `from shared.` → `from a2a_agent.po_base.` |
| `shared/middleware.py` | `a2a_agent/po_base/middleware.py` | Imports rewritten |
| `shared/fhir_hook.py` | `a2a_agent/po_base/fhir_hook.py` | Imports rewritten |
| `shared/logging_utils.py` | `a2a_agent/po_base/logging_utils.py` | Unchanged |

## What we did NOT copy

- `general_agent/`, `healthcare_agent/`, `orchestrator/` — these are three different reference agents. We built our own `a2a_agent/agent.py` + `app.py` from scratch for `priorauth_agent`, using `healthcare_agent/` as a structural model.
- `shared/tools/fhir.py` — direct FHIR access tools. Our architecture routes FHIR through MCP tools in `mcp_server/`, not direct FHIR calls from the A2A agent. Will be replaced by MCP tool bindings.
- `Dockerfile`, `docker-compose.yml`, `Procfile` — we have our own root-level versions.
- `.claude/` — their local Cursor config, not relevant to us.

## Local modifications beyond the copy

Tracked in git. Headline changes:

1. **Package namespace rename**: `shared` → `a2a_agent.po_base` to avoid collision with our repo-level `shared/` (which holds Pydantic cross-service contracts — a different concern from PO's ADK plumbing).
2. **Logger name**: `configure_logging("shared")` → `configure_logging("a2a_agent.po_base")` so log output is correctly namespaced.
3. **`middleware.py::_load_valid_api_keys` — added `AGENT_API_KEY` support** (PR #2 review). Upstream reads only `API_KEYS` / `API_KEY_PRIMARY` / `API_KEY_SECONDARY`. We advertise `AGENT_API_KEY` as the canonical single-key variant across `.env.example`, `.cursor/rules/a2a-agent.md`, and `docs/PLAN.md`, so the middleware must accept it. Function docstring documents the precedence. 3-line additive change; no upstream behaviour altered.
4. **Ruff-format normalisation**: the first `ruff format` run on import collapsed upstream's aligned-colon dict literals (e.g. `_METHOD_ALIASES`, `_ROLE_ALIASES`, `_STATE_MAP` in `logging_utils.py` and similar in `middleware.py`). Upstream syncs will therefore show spurious whitespace diffs. When pulling from upstream, reapply `ruff format` immediately to normalise before eyeballing semantic changes. Keeping `po_base/` out of `ruff format` was considered and rejected: the formatter-drift noise is one-shot and disappears after each sync step, whereas split formatting config complicates every future PR forever.
5. **`fhir_hook.py::extract_fhir_context` — also mutates `llm_request`** (spike-green polish, 2026-04-23). Upstream callback only writes to `callback_context.state` and returns None. We added `_inject_prompt_note(llm_request, ...)` which appends a **redacted** system-style `types.Content` to `llm_request.contents` whenever FHIR data is extracted. Rationale + wire-level evidence in `docs/po_platform_notes.md` "LLM cannot read session state". The note format is intentionally stable (`[SYSTEM NOTE — FHIR context received...`) because the agent instruction keys off the prefix — any future edit must keep both sides in sync or the LLM goes back to confabulating. Token value is never in the note — only `token_fingerprint()` output. When pulling from upstream, DO NOT drop `_inject_prompt_note` without also simplifying the corresponding `agent.py` instruction.
6. Our own `agent.py`, `app.py`, `__init__.py` — not copied from upstream, just follow the same API.

## When upstream updates

The plan (see `docs/PLAN.md` Risk Register) anticipates that PO will update this reference repo during the hackathon. Workflow for pulling upstream changes:

```bash
# From repo root
git clone https://github.com/prompt-opinion/po-adk-python.git /tmp/po-adk-latest
git diff /tmp/po-adk-latest/shared a2a_agent/po_base  # see what drifted
# Apply relevant fixes file-by-file via StrReplace, preserving our import rewrites.
```

Any A2A-v1 spec shim changes (the `AgentCardV1` / `AgentExtensionV1` workarounds in `app_factory.py`) are the most likely to churn. Watch https://github.com/google-a2a/a2a-python/blob/main/CHANGELOG.md.
