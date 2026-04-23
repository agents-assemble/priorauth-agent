# AGENTS.md

Both AI coding agents working on this repo read this file on every session. Follow it strictly.

## Project context

- **Hackathon**: [Agents Assemble](https://agents-assemble.devpost.com/) by Prompt Opinion / Darena Health.
- **Deadline**: **May 11, 2026 @ 11:00pm EDT**. Internal ship date: **May 9, 2026** (48-hour buffer).
- **Goal**: Submit a Prior Authorization A2A agent for lumbar MRI (CPT 72148) via "Option 3" (custom external A2A agent), using FHIR + MCP + A2A.
- **Humans**:
  - **Person A (MCP lead)**: Kevin Shine George (`@kevinsgeo`)
  - **Person B (A2A lead)**: Sanjit Saji (`@Sanjit2004`)
- **Shared model**: both humans use Cursor with Claude Opus 4.7 for style consistency.

## Session-start protocol (do this before any task)

1. Read [`STATUS.md`](STATUS.md) to see current state and what the other human is doing.
2. If you need strategic context: consult [`docs/PLAN.md`](docs/PLAN.md).
3. If you touch Prompt Opinion integration in any way: consult [`docs/po_platform_notes.md`](docs/po_platform_notes.md).
4. If you need a cross-service type: import from `shared/` — never redefine locally.

## Tech stack (locked — do not swap without both reviewers approving)

| Concern | Choice |
|---|---|
| Language | Python 3.11 |
| Package manager | **uv** (not pip / poetry / pipenv / venv directly) |
| Lint + format | **ruff** |
| Type check | **mypy** |
| Tests | **pytest** + pytest-asyncio |
| MCP framework | **FastMCP** (forked from PO community MCP) |
| A2A framework | **Google ADK** (Python; forked from PO A2A reference) |
| Shared types | **Pydantic v2** |
| LLM | **Gemini 3.1 Flash Lite** via Google AI Studio (`GEMINI_MODEL`, `GOOGLE_API_KEY` env vars) |
| Deployment | **Fly.io** (public HTTPS, one app per service) |
| Dev exposure | **ngrok** (local dev only — never in production config) |

## Directory ownership (matches CODEOWNERS)

| Path | Primary owner | Reviewer |
|---|---|---|
| `mcp_server/` | Person A (Kevin) | Person B |
| `a2a_agent/` | Person B (Sanjit) | Person A |
| `shared/` | **BOTH must review** | — |
| `AGENTS.md`, `.cursor/rules/` | **BOTH must review** | — |
| `fly.toml` (either service) | **BOTH must review** | — |
| `.github/workflows/` | **BOTH must review** | — |
| `docs/PLAN.md` | **BOTH must review** | — |
| `demo/`, `README.md` | Either | Other |

## Shared contracts rule (violation = PR rejection)

Any cross-service type lives in `shared/` **only**. This includes `PatientContext`, `CriteriaResult`, `PALetter`, MCP tool I/O schemas, and ADK handoff schemas.

- **Import like this**: `from shared.models import PatientContext`
- **Never**: redefine or duplicate these types inside `mcp_server/` or `a2a_agent/`.
- **Changing these types**: open a PR to `shared/`, get both reviewers to approve, then update both consumers in the same PR or immediate follow-ups.

## LLM hygiene

- `temperature=0` on all criteria evaluation and letter generation calls.
- Use Gemini's **structured output** (JSON schema mode) whenever the tool output must match a Pydantic model.
- **Never hardcode the model name** — always read from `os.environ["GEMINI_MODEL"]`.
- Prompts live in `*_prompts/` folders, versioned by filename (e.g. `match_criteria_v1.md`). Bump the version on meaningful changes; never silently mutate a prompt.

## Commit + PR conventions

- **Conventional Commits**: `feat(mcp): ...`, `fix(a2a): ...`, `chore(shared): ...`, `docs: ...`, `test(mcp): ...`, `refactor(a2a): ...`.
- PRs are **≤ 400 changed lines**. If larger, split into smaller sequential PRs.
  - **Exception — vendored / adapted-upstream code**: lines copied or adapted from an attributed upstream reference do not count toward the 400-line cap, **provided** the adapted files are listed in a `REFERENCE.md` at the package root with the upstream commit pin and a per-file adaptation log (see `a2a_agent/po_base/REFERENCE.md` and `mcp_server/REFERENCE.md` for the shape). **Net-new authored code in the same PR must still fit under 400 lines.** This carve-out is auditable (grep the REFERENCE.md line count vs. the PR diff) so it cannot be gamed.
- **Never delete or skip a test to make CI green.** If a golden file must change, explain why in the PR body.
- Every PR must append an entry to `STATUS.md` if it blocks or unblocks something for the other human.

## Knowledge capture (do this every time)

- **New Prompt Opinion behavior or quirk** discovered → append to `docs/po_platform_notes.md` in the **same PR** that discovered it. This saves the other agent the same 30 minutes tomorrow.
- **Architecture decision** of any weight → add a short ADR paragraph to `docs/ARCHITECTURE.md`.
- **End of each coding session** → append 3 lines to `STATUS.md` under your name: done / blocked / next.

## Do NOT do

- Do not use `pip`, `poetry`, `pipenv`, or raw `venv` directly — always `uv`.
- Do not commit `.env` files or any secret material. `.env.example` is the only committed env file.
- Do not modify `shared/`, `fly.toml`, `AGENTS.md`, `.cursor/rules/`, or CI workflow without both reviewers.
- Do not use OpenAI or Anthropic SDKs — Gemini via `google-generativeai` only.
- Do not leave ngrok URLs in any production config — swap for Fly.io URLs by end of Week 2.
- Do not paraphrase payer criteria without citing the source policy URL inline in the JSON.
- Do not run parallel refactors on `shared/` without coordinating with your teammate first.

## Getting started (for a fresh agent session)

1. You already read this file (good).
2. Read `STATUS.md` next.
3. If unsure what to pick up, ask your human — do not invent work.
4. Start from the smallest scoped PR that makes real progress. Many small correct PRs beat one huge one.

## Guardrails for Claude Opus 4.7 specifically

- Prefer editing over creating; only create new files when necessary per the plan.
- Avoid broad refactors that cross directory ownership boundaries unless both humans agreed.
- When you discover something surprising about PO, ADK, FastMCP, or Gemini — write it down (`docs/po_platform_notes.md`) before you forget.
- If two approaches are equally valid, pick the one that requires fewer lines of code.
