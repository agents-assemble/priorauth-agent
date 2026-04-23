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

## 2026-04-23 — Person A (PR #2 review pass)

- Done: Reviewed @Sanjit2004's `a2a_agent/platform-spike` (PR #2). First pass `REQUEST_CHANGES` on the silent `AGENT_API_KEY` bug (upstream middleware only read `API_KEYS` / `API_KEY_PRIMARY` / `API_KEY_SECONDARY`, so our documented canonical env var 401'd every authenticated request) + mypy-strict nit (43 vendored `po_base/**` errors hiding behind CI `continue-on-error: true`). Cross-checked the vendored files against `prompt-opinion/po-adk-python@6b2f742` via the GH MCP — matches upstream modulo the declared import rewrites. Sanjit's fix pass surfaced a second load_dotenv ordering bug (module-import-time env read in middleware beat `app.py`'s `load_dotenv()`) and addressed all nits; re-verified auth end-to-end locally — correct key → 200, wrong → 403, none → 401, agent-card unauth → 200 — and confirmed `override=True` defeats stale shell exports as advertised. Approved, merged as `d2afa05`.
- Blocked: Nothing. Week 1 platform spike is on `main`, `make agent` + agent card verified live, mypy strict actually runs clean now.
- Next: Start Week 2 MCP-server prep. Immediate units on a new branch (`mcp_server/week2-prep`): (1) hand-author the 3 demo-patient clinical-note markdown under `demo/clinical_notes/` (esp. Patient C cauda-equina for the red-flag/needs-info substrate), (2) scaffold `tests/` + golden-file harness so Week-2 tool PRs (`fetch_patient_context`, `match_payer_criteria`, `generate_pa_letter`) inherit it from day one. Separate tiny follow-up: flip CI `continue-on-error: true` on mypy to fail-fast now that strict passes, so regressions surface at review time.

## 2026-04-23 — Person B (PR #2 fix pass)

- Done: Addressed Kevin's review on PR #2. (1) Fixed the blocking `AGENT_API_KEY` bug in `a2a_agent/po_base/middleware.py::_load_valid_api_keys` — upstream middleware only read `API_KEYS`/`API_KEY_PRIMARY`/`API_KEY_SECONDARY`, so our documented canonical `AGENT_API_KEY` was silently ignored and every auth'd request 403'd. (2) Added `[[tool.mypy.overrides]]` for `a2a_agent.po_base.*` mirroring the ruff per-file-ignores — mypy strict now actually passes 11 source files clean instead of hiding 43 upstream errors behind CI's `continue-on-error: true`. (3) Found a **second** bug while writing the positive-auth smoke test: `load_dotenv()` in `app.py` ran after `middleware.py` had already cached `VALID_API_KEYS` from empty env; moved `load_dotenv(override=True)` to `a2a_agent/__init__.py` top-level, added `--env-file .env` to `make agent` as belt-and-suspenders. (4) Updated `REFERENCE.md` and `docs/po_platform_notes.md` with the middleware local-mod, the ruff-format normalisation note (Kevin nit #2), a Week 3 log-redaction task (nit #3), and the load_dotenv footgun writeup. (5) **Manually verified** auth end-to-end via curl: correct `X-API-Key` → HTTP 200, wrong key → 403, no key → 401. Ruff check, ruff format --check, mypy strict all clean.
- Blocked: Nothing on our side. Waiting on Kevin to re-review the follow-up commit and approve.
- Next: Once PR #2 merges → resume step 6 (register agent in PO workspace with ngrok URL), step 7 (round-trip PO chat → Gemini). Also planning a `make agent-post-smoke` target for the next PR so positive-auth is covered in CI, not just by my manual curl.

## 2026-04-23 — Person A

- Done: PR #1 merged (`3ae6909`) — Python 3.11 pinned, `mcp_server`/`a2a_agent` workspace-member stubs + `uv.lock`, 7 ruff lints resolved across `shared/models.py` (incl. `Decision` → `StrEnum`, semantically null) + scaffolding stubs. CI validated end-to-end: it blocked the broken state and went green on the fix commit.
- Blocked: Nothing for me; **critical-path blocker is `week1_spike`** — @Sanjit2004 needs to run PO signup + Gemini key + fork PO community MCP / Google-ADK reference + ngrok round-trip before any tool code can land.
- Next: While the spike is in flight — (1) hand-author the 3 demo patients' clinical-note markdown into `demo/clinical_notes/` (esp. Patient C's cauda-equina narrative, the needs-info/red-flag substrate), (2) scaffold `tests/` + golden-file harness so Week 2 tool PRs inherit it.

## 2026-04-22 — Shared

- Done: Repo bootstrapped via AI agent. Shared brain committed (AGENTS.md, CODEOWNERS, shared/, .cursor/rules/, docs/PLAN.md, docs/po_platform_notes.md, this file). CI workflow stub, docker-compose, Makefile, pyproject.toml skeletons landed.
- Blocked: Sanjit needs to provide GitHub username to replace `@sanjit-github` placeholder in CODEOWNERS. GitHub repo needs to be created under `github.com/agents-assemble` and remote added.
- Next: Both humans review this initial commit, merge it as PR #1. Then Person B leads the Week 1 Platform Spike (PO signup, Gemini key, fork reference repos, ngrok round-trip). Person A sets up CI + import demo patients once spike is done.
