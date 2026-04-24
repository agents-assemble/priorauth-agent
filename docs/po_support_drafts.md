# Prompt Opinion support — outgoing ticket drafts

Append-only log of support messages we've drafted or sent to `support@promptopinion.ai` / PO Discord during the hackathon. Newest at the top. When PO responds, fold their answer into `docs/po_platform_notes.md` under the relevant behavior entry.

This file is NOT tracked in PRs-by-default — update status with `sent / awaiting-reply / resolved` and commit whenever you want a durable record.

---

## 2026-04-23 — SENT — `taskId` reuse on general-agent follow-up messages

**Status**: **SENT 2026-04-23 ~19:15 CDT** — awaiting-reply
**Channel (primary)**: email → `support@promptopinion.ai`
**Channel (secondary)**: post a condensed version in the Agents Assemble Connectathon Discord once support has acknowledged — defer until we have a ticket number / reply to quote.
**Sent by**: Sanjit Saji
**Key trace IDs in body** (for quick PO support lookup): `traceparent` values captured from spike log at 18:11 CDT. When support replies, fold their answer into `docs/po_platform_notes.md` Note #2 ("PO reuses `taskId` on follow-up messages") under a "**Resolution**" subheading and flip status here to `resolved`.
**If no reply in 48h**: bump via Discord with link to this ticket subject line. Do NOT re-send email — clutters their queue.

---

### Subject

```
Bug: PO general agent reuses completed taskId on A2A follow-ups (-32602)
```

### Body (this is what you send)

```
Hi PO team,

Short bug report from the Agents Assemble Connectathon.

TL;DR — Your general agent reuses the previous task's taskId when it
auto-sends a follow-up to an external A2A agent. Per A2A v1, completed
tasks are terminal, so our external agent correctly rejects with
JSON-RPC -32602. Result: multi-turn conversations between the general
agent and any external A2A agent die after turn 1.

Repro (happened 2026-04-23 in our workspace)
  1. Open chat with the general agent ("Po").
  2. Ask something that routes to a registered external A2A agent. In
     our case: "Get prior auth for a lumbar MRI on this patient".
  3. External agent completes the task and returns
     TASK_STATE_COMPLETED.
  4. General agent decides to be helpful and auto-sends a follow-up
     with extra context — reusing the same taskId.
  5. External agent rejects with:
       {"error": {"code": -32602,
                  "message": "Task <uuid> is in terminal state: completed"}}
  6. General agent surfaces this as "the external system indicated the
     task reached a completed state" and bails out of the multi-turn
     flow.

Traces for server-side lookup
  trace-id:    88e7de8783869d36d14971fc4c0bb41f
               (covers both spans — the succeeded first turn and the
               failed follow-up, 25s apart)
  workspace:   019dbb71-27c3-7dc2-90c1-7fa53b942524
  ext. agent:  "Prior Auth (Lumbar MRI)"
               po_a2a_id 019dbbdd-b2c3-7cb2-b399-14b48500c2e1
  ngrok URL:   https://creed-goofiness-amusement.ngrok-free.dev
  stack:       Google ADK Python 1.31.1 + a2a-sdk 0.3.26

Suggested fix (sender side)
  On follow-up, omit params.message.taskId unless the prior task is in
  a non-terminal state (e.g. input-required, working). A2A v1's
  Message.contextId is the right vehicle for conversation linking —
  taskId is per-task-instance. Any external agent built on the
  reference google/adk-python + a2a-python stack will reject the
  current behavior the same way ours did.

Impact
  Blocks multi-turn conversations between your general agent and any
  external A2A agent. Single-turn works, so the hackathon spike gate
  is green for us, but this blocks our Week-3 submission's needs-info
  flow which requires a second turn after a DocumentReference upload.

Happy to share the full bidirectional trace (JSON-RPC payloads,
headers, timestamps) — we have it captured locally. The agent is
still registered and serving at the URL above through the
Connectathon if you want a live repro.

Thanks — FHIR token propagation via "pass token" worked flawlessly
on first try, which is rare for an A2A integration. This one issue
aside, the platform UX has been great to build against.

Sanjit Saji
Agents Assemble Connectathon — Team Agents Assemble
[your email]
```

---

### Appendix — send only if support asks for "more detail"

Keep this in your back pocket. If the triage person or their engineer replies with *"can you share the exact requests and responses?"* paste the block below as a follow-up email or attach it as a text file.

```
Full request/response trace — task reuse bug, 2026-04-23 18:11 local time

Request 1 — succeeded, created task
  traceparent: 00-88e7de8783869d36d14971fc4c0bb41f-5da7b7e9c8410467-01
  jsonrpc.id:  437827b9-faac-4f22-b646-1dc74332ab1c
  received:    2026-04-23 18:11:06.596

  {
    "jsonrpc": "2.0",
    "id": "437827b9-faac-4f22-b646-1dc74332ab1c",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "2aa1362a-ea61-4c7c-9a06-956a31a1e0da",
        "role": "user",
        "parts": [{ "text": "The user wants to get a prior
                             authorization for a lumbar MRI.
                             Please initiate this process." }],
        "metadata": {
          "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context":
            { ...FHIR token, URL, patientId — redacted in this dump... }
        }
      }
    }
  }

Response 1 — 200 OK, new task created and completed
  task.id:     dd249d0c-fbc5-48f5-b428-40c81adaba53
  context.id:  b56d1faf-c719-420b-b700-a9073713805c
  task state:  TASK_STATE_COMPLETED
  (Full task response with artifacts available on request.)

Request 2 — 25 seconds later, PO reused completed taskId
  traceparent: 00-88e7de8783869d36d14971fc4c0bb41f-295be8ff845561a7-01
  jsonrpc.id:  9f9357fd-d307-456a-a0ee-ac1f4405ed57
  received:    2026-04-23 18:11:31.353

  {
    "jsonrpc": "2.0",
    "id": "9f9357fd-d307-456a-a0ee-ac1f4405ed57",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "dcc31c9a-c9bc-4ad4-a257-a642611d3f31",
        "role": "user",
        "taskId": "dd249d0c-fbc5-48f5-b428-40c81adaba53",  <-- completed task id
        "parts": [{ "text": "I have the patient ID:
                             82e4deff-9345-4f99-9ff3-2314362a14f5. ..." }],
        "metadata": { ...same FHIR context blob as request 1... }
      }
    }
  }

Response 2 — 200 OK with JSON-RPC error
  {
    "jsonrpc": "2.0",
    "id": "9f9357fd-d307-456a-a0ee-ac1f4405ed57",
    "error": {
      "code": -32602,
      "message": "Task dd249d0c-fbc5-48f5-b428-40c81adaba53
                  is in terminal state: completed"
    }
  }

Spec reference
  A2A v1 task lifecycle defines `completed`, `canceled`, `failed`, and
  `rejected` as terminal states. Receiving agents MUST reject further
  message/send calls targeting a terminal taskId. The reference stack
  (google/adk-python + a2a-python) enforces this by default in the
  TaskStore/TaskManager — not configurable without overriding the
  handler, which would break spec compliance.

PO source IP on both requests: 20.80.113.52 (Azure US-East-2).
```

---

### Expected follow-ups after sending

- **Paste the ticket number / thread id back here** once support replies. That's the durable index for everything else.
- **If acknowledged as a bug**: update `docs/po_platform_notes.md` entry #2 (the `taskId` reuse one) with "PO acknowledged — tracking <their ticket id>". Flip this draft's status to `acknowledged / awaiting-fix`.
- **If disputed**: update the entry with their reasoning — they may be reading an older A2A draft or intending conversation-continuation semantics we haven't seen documented. Escalate to Discord publicly only after email exchange has stabilized.
- **If they ship a fix**: retest with the same repro, update `po_platform_notes.md` status to `resolved-<date>`, consider whether our middleware needs to drop any defensive workaround we added.

---
