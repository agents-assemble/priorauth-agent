# PriorAuth Preflight — Demo Video Storyboard (<3 min)

Lead with the differentiator: DO_NOT_SUBMIT safety gate and needs-info + gap-fix.
Four patients, four outcomes, one agent.

---

## 0:00–0:15 — Hook + Positioning

> "Physicians spend 13 hours a week on prior auth. 94% say it delays care.
> Most PA agents generate packets. **PriorAuth Preflight decides whether a
> packet should be generated at all — then fixes missing documentation first.**"

Cut to PO workspace showing our agent registered in the marketplace.

---

## 0:15–0:45 — Patient D: DO NOT SUBMIT (safety gate)

**Setup**: Patient D has a sore-throat chart (streptococcal pharyngitis) but
someone ordered a lumbar MRI. Zero lumbar symptoms in the record.

- Clinician opens Patient D in PO, asks for PA preflight.
- Agent returns instant **DO NOT SUBMIT** banner.
- Show: "No documented lumbar symptoms or qualifying spine indication."
- **Punchline**: "We stopped a guaranteed denial before it wasted anyone's time."

---

## 0:45–1:25 — Patient B: NEEDS ADDITIONAL INFORMATION + Gap-Fix

**Setup**: Patient B has low back pain + NSAID trial but PT is incomplete
(1 intake + 3 no-shows, substituting YouTube stretches).

- Clinician asks for PA preflight.
- Agent returns **NEEDS ADDITIONAL INFORMATION** with criteria trace showing
  PT requirement is unmet.
- Gap-fix template appears below: fill-in-the-blank clinical addendum with
  `[bracketed placeholders]` for PT documentation.
- **Punchline**: "Not just 'missing PT' — here's the exact note to write."
- (Optional beat) Clinician uploads PT note, re-runs → APPROVED.

---

## 1:25–1:55 — Patient A: APPROVED (happy path)

**Setup**: Patient A has complete documentation (12-week LBP, 8 PT sessions,
NSAID + muscle-relaxant trial, no red flags).

- Clinician asks for PA preflight.
- Agent returns **APPROVED** with full readiness review letter.
- Show criteria trace: all criteria met with evidence snippets and source
  document references.
- Show audit footer: policy version, timestamp, pending human review.
- **Punchline**: "20 minutes of manual review → 15 seconds."

---

## 1:55–2:25 — Patient C: RED FLAG FAST-TRACK

**Setup**: Patient C has cauda equina symptoms (saddle anesthesia, bladder
dysfunction) detected from free-text clinical notes.

- Clinician asks for PA preflight.
- Agent returns **APPROVED** with urgent banner and red-flag fast-track.
- Show: criteria bypassed, red-flag reason cited from narrative note text.
- **Punchline**: "Clinical intelligence from unstructured notes — not just
  billing codes."

---

## 2:25–2:50 — Architecture + Impact

- Quick architecture diagram: PO workspace → A2A agent → 3 sub-agents → MCP
  server → workspace FHIR.
- ADK trace panel showing the multi-agent handoff.
- Impact numbers:
  - 20+ min manual PA → under 30 seconds
  - 4 decision outcomes (approve / needs-info / do-not-submit / red-flag)
  - 2 payers (Cigna + Aetna) with real policy citations
  - Gap-fix templates prevent avoidable denials

---

## 2:50–3:00 — Close

> "PriorAuth Preflight. Built on MCP + A2A + FHIR. Live in the Prompt Opinion
> marketplace."

Logo + marketplace link.
