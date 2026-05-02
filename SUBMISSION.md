# PriorAuth Preflight — Devpost Submission Draft

## Tagline

Most PA agents generate packets. PriorAuth Preflight decides whether a lumbar
MRI packet should be generated at all — then fixes missing documentation first.

---

## Inspiration

Physicians spend 13 hours per week on prior authorization. 94% of clinicians
report care delays caused by the PA process. The problem isn't generating
paperwork faster — it's submitting paperwork that's doomed to be denied because
the chart doesn't support the request yet.

We built PriorAuth Preflight to prevent avoidable denials before submission,
not just automate the submission itself.

## What it does

PriorAuth Preflight is a denial-prevention agent for outpatient lumbar MRI
(CPT 72148) that runs inside a Prompt Opinion workspace. When a clinician
requests a prior authorization preflight, the agent:

1. **Pulls patient context** from the workspace FHIR server (demographics,
   conditions, medications, procedures, clinical notes).
2. **Evaluates payer criteria** (Cigna/eviCore and Aetna) using a deterministic
   rule engine plus a Gemini reasoning pass on free-text notes.
3. **Returns one of four outcomes:**
   - **APPROVED** — chart supports the request; here's a ready-to-submit letter
     with an evidence-backed criteria trace and audit metadata.
   - **NEEDS ADDITIONAL INFORMATION** — chart is close but gaps exist; here's
     exactly which criteria are unmet, with evidence snippets citing the chart,
     plus a clinician-ready gap-fix template (fill-in-the-blank addendum) to
     close the gaps.
   - **DO NOT SUBMIT** — chart-procedure mismatch detected (e.g., sore-throat
     chart + lumbar MRI order); a safety gate that stops guaranteed denials.
   - **RED FLAG FAST-TRACK** — clinical urgency (cauda equina, malignancy)
     detected from unstructured notes; criteria bypassed, urgent submission.

## How we built it

- **One Python monorepo, two deployables**: a Google ADK A2A agent
  (orchestrator + sub-agents) and a FastMCP server (3 tools), both deployed to
  Fly.io.
- **LLM**: Gemini 3.1 Flash Lite via Google AI Studio (free tier, temperature 0
  for all clinical decisions).
- **FHIR**: Prompt Opinion's workspace FHIR server with SHARP token
  propagation — no separate auth needed.
- **Payer criteria**: Cigna/eviCore V1.0.2026 and Aetna CPB 0236, paraphrased
  from public policy documents with source URLs cited inline in versioned JSON.
- **Team**: two people, both using Cursor with Claude Opus 4.7, coordinating
  via committed convention files (AGENTS.md, STATUS.md, shared/ contracts).

## What makes it different

| Feature | Most PA agents | PriorAuth Preflight |
|---|---|---|
| Output | Approve/deny packet | 4-tier: approve, needs-info, do-not-submit, red-flag |
| Missing documentation | "Denied — incomplete" | Gap-fix template: fill-in-the-blank addendum |
| Chart-procedure mismatch | Generates anyway | Safety gate: DO NOT SUBMIT |
| Evidence trail | "Criteria met" | Per-criterion snippet + source document reference |
| Clinical notes | Ignored or summarized | Red-flag detection from free text (cauda equina) |
| Agent architecture | Single monolithic agent | 3 visible sub-agents with ADK-traced handoffs |

**Key differentiators:**

1. **Needs-info feedback loop** — returns a specific, actionable missing-evidence
   checklist tied to cited payer criteria, plus a clinician-ready template.
2. **DO NOT SUBMIT safety gate** — prevents guaranteed denials when the chart
   doesn't match the requested procedure.
3. **Red-flag fast-track** — detects clinical urgency from unstructured notes
   (saddle anesthesia, bowel/bladder dysfunction) and bypasses normal criteria.
4. **Evidence snippets with source citations** — every criterion check cites
   the specific FHIR resource and chart text that supports or refutes it.

## Impact

- **Time**: 20+ minutes of manual prior-auth review → under 30 seconds.
- **Denials prevented**: DO NOT SUBMIT gate catches chart-procedure mismatches
  before they become denials. Gap-fix templates let clinicians close
  documentation gaps before submission.
- **Clinical safety**: Red-flag fast-track surfaces cauda equina and malignancy
  from free-text notes, ensuring urgent cases aren't delayed by normal PA
  timelines.

## Built with

Python 3.11, Google ADK, FastMCP, Gemini 3.1 Flash Lite, Prompt Opinion
(A2A + MCP + FHIR), Fly.io, Pydantic, httpx, uv.

## Marketplace links

- **A2A Agent**: [PriorAuth Preflight — Lumbar MRI](TBD)
- **MCP Toolkit**: [PriorAuth Toolkit](TBD)
