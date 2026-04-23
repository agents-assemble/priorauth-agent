# STATUS.md

Daily status log. Both humans append here at the end of each coding session.
Both AI agents read this at the start of each session.

**Format per entry:**

```
## YYYY-MM-DD — <Person A or B>
- Done: <what I finished>
- Blocked: <anything blocked, or "nothing">
- Next: <what I'll pick up next session>
```

Newest entries go at the top. Keep each entry tight — 3 bullets, one line each.

---

## 2026-04-23 — Person B

- Done: Platform Spike scaffold (steps 1–5 of 8). Signed up on app.promptopinion.ai with Gemini 3.1 Flash Lite Preview, grabbed Google AI Studio API key. Forked `prompt-opinion/po-adk-python` into `a2a_agent/po_base/` (namespace-renamed `shared/` → `po_base/` to avoid collision with our repo's Pydantic-contracts `shared/`). Wrote `a2a_agent/agent.py` (trivial root agent, no tools yet) and `a2a_agent/app.py` advertising all 8 SMART-on-FHIR scopes we'll need Week 2. Pinned `a2a-sdk<1.0` and `google-adk<2.0` to dodge the upstream 1.0 namespace break (logged in `docs/po_platform_notes.md`). Added `make agent`, `make ngrok`, `make agent-card` targets. **End-to-end verified**: uvicorn boots on :8001, `GET /.well-known/agent-card.json` returns a valid A2A v1 JSON card with our FHIR extension, X-API-Key security, and `prior-auth-lumbar-mri` skill. Ruff + format clean.
- Blocked: Nothing — NGROK_AUTHTOKEN is the only missing piece for step 6 (PO registration); I'll grab it tomorrow and paste the tunnel URL into PO myself.
- Next: Branch `a2a_agent/platform-spike` up for review. After merge: (1) NGROK auth + register agent in PO workspace (step 6), (2) run a real round-trip from PO chat → our agent → Gemini → response (step 7), (3) log any residual PO UI quirks (step 8). Then Week 2 starts: wire MCP bindings once @kevinsgeo's `fetch_patient_context` tool is up.

## 2026-04-23 — Person A

- Done: Local dev env bootstrapped — pinned Python 3.11 via `.python-version`, added minimal workspace-member stubs (`mcp_server/pyproject.toml`, `a2a_agent/pyproject.toml`, matching `__init__.py` each) so `uv sync` resolves, committed `uv.lock` for reproducibility. Verified `shared.models` imports cleanly under the locked toolchain (ruff 0.15, mypy 1.20, pytest 9.0).
- Blocked: Nothing — waiting on Week 1 platform spike (Person B) before scaffolding MCP tools.
- Next: Heads-up @Sanjit2004 — the `a2a_agent/` stubs are throwaway placeholders; overwrite them wholesale when you fork the PO Google-ADK reference. Committed on branch `mcp_server/kevin`, not yet merged.

## 2026-04-22 — Shared

- Done: Repo bootstrapped via AI agent. Shared brain committed (AGENTS.md, CODEOWNERS, shared/, .cursor/rules/, docs/PLAN.md, docs/po_platform_notes.md, this file). CI workflow stub, docker-compose, Makefile, pyproject.toml skeletons landed.
- Blocked: Sanjit needs to provide GitHub username to replace `@sanjit-github` placeholder in CODEOWNERS. GitHub repo needs to be created under `github.com/agents-assemble` and remote added.
- Next: Both humans review this initial commit, merge it as PR #1. Then Person B leads the Week 1 Platform Spike (PO signup, Gemini key, fork reference repos, ngrok round-trip). Person A sets up CI + import demo patients once spike is done.
