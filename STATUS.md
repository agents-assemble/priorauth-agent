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

## 2026-04-23 — Person A (demo clinical notes)

- Done: Hand-authored 3 demo clinical progress notes under `demo/clinical_notes/` — `patient_a.md` (47F happy-path: 12wk LBP + 8 PT sessions + NSAID + muscle-relaxant + radicular symptoms, explicitly no red flags), `patient_b.md` (52M needs-info: NSAID trial documented but PT course incomplete — 1 intake visit + 3 no-shows, patient substituting YouTube stretches), `patient_c.md` (61F red-flag fast-track: ER+ breast-ca hx 7yr out on anastrozole, presents with saddle anesthesia, post-void residual 310mL with overflow incontinence, decreased rectal tone, bilateral LE weakness, night pain unrelieved by rest — textbook cauda equina). Each note is markdown with YAML front-matter carrying `DocumentReference`-ready metadata (LOINC 11506-3). Added `demo/clinical_notes/README.md` documenting format, end-to-end consumption path, and the exact red-flag vocabulary the LLM extraction will be tested against. Pure demo content — no code changes, no lock/dep changes.
- Blocked: Nothing. Parallel track while PR #3 (MCP scaffold) is in review.
- Next: Once PR #3 merges, follow-up PR to (a) delete the hardcoded `clinical_notes_excerpt` in `fetch_patient_context.py` and replace with a real `DocumentReference` search + base64-decode + truncation; (b) add a golden-file test asserting the red-flag vocabulary from `patient_c.md` is surfaced verbatim. In parallel: small CI-hardening PR flipping `continue-on-error: true` → `false` on the mypy step now that strict is actually clean.

## 2026-04-23 — Person B (PR #2 fix pass)

- Done: Addressed Kevin's review on PR #2. (1) Fixed the blocking `AGENT_API_KEY` bug in `a2a_agent/po_base/middleware.py::_load_valid_api_keys` — upstream middleware only read `API_KEYS`/`API_KEY_PRIMARY`/`API_KEY_SECONDARY`, so our documented canonical `AGENT_API_KEY` was silently ignored and every auth'd request 403'd. (2) Added `[[tool.mypy.overrides]]` for `a2a_agent.po_base.*` mirroring the ruff per-file-ignores — mypy strict now actually passes 11 source files clean instead of hiding 43 upstream errors behind CI's `continue-on-error: true`. (3) Found a **second** bug while writing the positive-auth smoke test: `load_dotenv()` in `app.py` ran after `middleware.py` had already cached `VALID_API_KEYS` from empty env; moved `load_dotenv(override=True)` to `a2a_agent/__init__.py` top-level, added `--env-file .env` to `make agent` as belt-and-suspenders. (4) Updated `REFERENCE.md` and `docs/po_platform_notes.md` with the middleware local-mod, the ruff-format normalisation note (Kevin nit #2), a Week 3 log-redaction task (nit #3), and the load_dotenv footgun writeup. (5) **Manually verified** auth end-to-end via curl: correct `X-API-Key` → HTTP 200, wrong key → 403, no key → 401. Ruff check, ruff format --check, mypy strict all clean.
- Blocked: Nothing on our side. Waiting on Kevin to re-review the follow-up commit and approve.
- Next: Once PR #2 merges → resume step 6 (register agent in PO workspace with ngrok URL), step 7 (round-trip PO chat → Gemini). Also planning a `make agent-post-smoke` target for the next PR so positive-auth is covered in CI, not just by my manual curl.

## 2026-04-23 — Person A

- Done: Local dev env bootstrapped — pinned Python 3.11 via `.python-version`, added minimal workspace-member stubs (`mcp_server/pyproject.toml`, `a2a_agent/pyproject.toml`, matching `__init__.py` each) so `uv sync` resolves, committed `uv.lock` for reproducibility. Verified `shared.models` imports cleanly under the locked toolchain (ruff 0.15, mypy 1.20, pytest 9.0).
- Blocked: Nothing — waiting on Week 1 platform spike (Person B) before scaffolding MCP tools.
- Next: Heads-up @Sanjit2004 — the `a2a_agent/` stubs are throwaway placeholders; overwrite them wholesale when you fork the PO Google-ADK reference. Committed on branch `mcp_server/kevin`, not yet merged.

## 2026-04-22 — Shared

- Done: Repo bootstrapped via AI agent. Shared brain committed (AGENTS.md, CODEOWNERS, shared/, .cursor/rules/, docs/PLAN.md, docs/po_platform_notes.md, this file). CI workflow stub, docker-compose, Makefile, pyproject.toml skeletons landed.
- Blocked: Sanjit needs to provide GitHub username to replace `@sanjit-github` placeholder in CODEOWNERS. GitHub repo needs to be created under `github.com/agents-assemble` and remote added.
- Next: Both humans review this initial commit, merge it as PR #1. Then Person B leads the Week 1 Platform Spike (PO signup, Gemini key, fork reference repos, ngrok round-trip). Person A sets up CI + import demo patients once spike is done.
