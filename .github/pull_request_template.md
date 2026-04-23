## Why

<!-- Motivation. Link to the todo in docs/PLAN.md if relevant. -->

## What

<!-- Concrete changes. Bullet list. -->

## Testing

<!-- How did you verify? Unit tests? Manual? Smoke test against which patient? -->

## Impact on the other human

<!--
Does this unblock or block them? If yes, make sure you updated STATUS.md.
Does this touch shared/, fly.toml, AGENTS.md, .cursor/rules/, or CI? If yes,
both reviewers must approve per CODEOWNERS.
-->

## Checklist

- [ ] PR is ≤ 400 changed lines (if larger, split)
- [ ] Conventional Commits title (`feat(...)`, `fix(...)`, etc.)
- [ ] No `.env` or secret material committed
- [ ] No shared-contract duplication (imported from `shared.models`)
- [ ] Prompt version bumped if LLM behavior changed
- [ ] Golden files updated with explanation if expected outputs changed
- [ ] STATUS.md updated if this affects the teammate's work
- [ ] New PO platform quirks logged in `docs/po_platform_notes.md`
