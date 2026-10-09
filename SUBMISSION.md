# PriorAuth Preflight — Devpost Submission

**Demo video:** [Prior Auth - Agents Assemble](https://www.youtube.com/watch?v=pBmYClgg194)

## Inspiration

Prior authorization is one of the most frustrating workflows in healthcare. A provider may order an MRI, medication, or procedure, but care can be delayed because the payer needs specific documentation before approving it. Many tools try to solve this by generating prior authorization letters faster. We took a different approach.

For outpatient lumbar spine MRI prior authorizations, the bigger problem is often not the letter itself. It is that the chart may not be ready for submission. If key documentation is missing, the request can become a denial, creating more rework for staff and more delay for the patient.

That inspired us to build **PriorAuth Preflight**, a denial-prevention agent that checks whether a lumbar MRI request should be submitted before a letter is generated.

## What it does

PriorAuth Preflight evaluates a patient's FHIR-style chart against payer-specific lumbar spine MRI criteria from Cigna and Aetna.

The agent routes each request into one of four outcomes:

1. **DO NOT SUBMIT** — used when the chart does not support the requested lumbar MRI, such as a chart-procedure mismatch.
2. **NEEDS ADDITIONAL INFORMATION** — used when the patient has some relevant evidence, but key payer-required documentation is missing.
3. **READY FOR HUMAN REVIEW** — used when the chart appears to support submission and the case is ready for clinician or prior authorization specialist review.
4. **RED FLAG FAST-TRACK** — used when urgent red-flag findings, such as cauda equina indicators or malignancy-related concerns, support bypassing standard conservative therapy requirements.

When the chart is incomplete, the system does not blindly generate a letter. Instead, it surfaces the exact evidence gap and generates a clinician-facing documentation template so the care team knows what to fix before payer review.

## How we built it

We built the project using an A2A agent coordinated through Prompt Opinion and a FastMCP server that performs the payer criteria evaluation.

- The **A2A agent** coordinates the workflow and communicates with the user.
- The **MCP server** evaluates patient chart evidence against payer criteria.
- **Gemini** is used for reasoning and generation where natural language interpretation or documentation generation is needed.
- **FHIR-style patient context** represents patient conditions, conservative therapy history, red-flag findings, and documentation evidence.
- The output is a human-reviewable readiness artifact, not an autonomous approval or submission.

The key design choice was to treat prior authorization as a preflight workflow. The system first asks: "Should this request be submitted at all?" Only after the chart supports the request does it move toward authorization justification.

## What makes it different

Many prior authorization tools focus on generating packets, scoring approval likelihood, or drafting appeal letters. PriorAuth Preflight focuses on the step before submission. It is designed to:

- Detect chart-procedure mismatches
- Identify missing conservative therapy documentation
- Recognize urgent red-flag pathways
- Generate clinician-ready gap-fix templates
- Preserve a human-review workflow
- Avoid auto-submission or auto-approval

This makes the system safer and more practical for real healthcare environments.

## Challenges we faced

One major challenge was scope. Prior authorization is a huge space, so we intentionally narrowed the project to one high-friction workflow: **outpatient lumbar spine MRI, CPT 72148**.

Another challenge was differentiating our project from generic prior authorization agents. We solved this by focusing on denial prevention and readiness review instead of simple letter generation.

We also had to balance automation with safety. Healthcare workflows require traceability and human oversight, so our system does not make final payer decisions. Every output is framed as a readiness review for a clinician or prior authorization specialist.

Finally, we had to make the agent fast and reliable enough for a live demo. We moved key eligibility checks into deterministic MCP logic and used AI for interpretation and documentation generation where it adds the most value.

## What we learned

The most valuable healthcare AI systems are not always the ones that generate more text. Sometimes the highest-impact system is the one that prevents the wrong workflow from happening in the first place.

For prior authorization, that means stopping unsupported requests before they become denials, showing exactly what is missing, and helping the care team fix the chart before payer review.

## What's next

PriorAuth Preflight could expand beyond lumbar MRI to other high-volume authorization workflows, such as CT imaging, orthopedic procedures, specialty medications, or physical therapy authorizations.

The same framework can scale by adding new payer policies, procedure-specific criteria, and FHIR mappings while preserving the same human-reviewed preflight model.

## Built with

Python 3.11, Google ADK, FastMCP, Gemini 3.1 Flash Lite, Prompt Opinion (A2A + MCP + FHIR), Fly.io, Pydantic, httpx, uv.
