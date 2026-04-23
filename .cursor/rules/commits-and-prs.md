---
description: Commit message and PR conventions enforced across the repo
alwaysApply: true
---

# Commits + PRs

## Commit messages (Conventional Commits)

Format: `<type>(<scope>): <short summary>`

- `feat(mcp): add match_payer_criteria rule engine`
- `fix(a2a): correct handoff payload validation`
- `chore(shared): add urgent_banner field to PALetter`
- `docs: document Prompt Opinion token passthrough behavior`
- `test(mcp): add golden test for Patient C red-flag path`
- `refactor(a2a): split orchestrator into router + executor`

Allowed `<type>`: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `ci`.
Allowed `<scope>`: `mcp`, `a2a`, `shared`, `docs`, `infra`, `demo`, or omit.

## Pull request rules

- PRs are ≤ 400 changed lines. Split larger work.
- PR title mirrors the commit message style.
- PR description includes: **Why** (motivation), **What** (changes), **Testing** (how verified). Link relevant todo in `docs/PLAN.md`.
- If you change a golden test file, the PR description must explain the output change.
- Every PR updates `STATUS.md` if it unblocks or blocks the other human.
- Every PR that touches `shared/`, `AGENTS.md`, `.cursor/rules/`, `fly.toml`, or CI requires BOTH reviewers per `CODEOWNERS`.

## Things NEVER committed

- `.env` files
- Actual API keys, tokens, passwords (including Gemini keys, PO session tokens, Fly.io tokens)
- Large binary artifacts (demo videos go to Devpost / Drive, not git)
- Patient PHI — the demo patients are synthetic; never commit real patient data

## Commits during agent sessions

At the end of each Cursor session, commit what's working — even if incomplete — with a clear WIP message. This preserves context for the next session (yours or your teammate's).
