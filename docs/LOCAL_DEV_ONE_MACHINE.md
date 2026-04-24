# Run MCP + A2A on one machine (handoff for PO testing)

This is the **single place** to run the **MCP server** (port 8000), the **A2A
agent** (port 8001), and **register both in Prompt Opinion** from **one
developer laptop** (e.g. Person A running the full dev stack for the team).

> **Do not use one public hostname for both 8000 and 8001.**  
> The MCP app answers at `POST /mcp`; the A2A app serves
> `GET /.well-known/agent-card.json`. If both map to the same host, the wrong
> process handles the request (404s). You need **two public URL bases** (or one
> ngrok config with **two endpoints** and **two** URLs).  
> See [issue #17](https://github.com/agents-assemble/priorauth-agent/issues/17).

---

## 1. Get the code

```bash
git clone https://github.com/agents-assemble/priorauth-agent.git
cd priorauth-agent
git pull origin main
uv sync --all-packages --all-extras --dev
cp .env.example .env
```

Fill `.env` (see section 3). **Never commit `.env`.**

**Windows (no `make` installed):** use the `uv run` commands in section 4 for
`mcp` and `agent` — same as the Makefile, see below.

---

## 2. What runs where

| Service | Port | Register in PO as |
|--------|------|----------------------|
| **MCP** (FastMCP) | 8000 | **Server / MCP** URL = `https://<mcp-tunnel>/mcp` |
| **A2A** (Google ADK) | 8001 | **External agent** = `https://<a2a-tunnel>` (no path) |

The A2A process calls MCP using **`MCP_SERVER_URL`** in `.env`. For one
machine, that value is the **public** MCP URL (with `/mcp`), **not** your
A2A URL.

---

## 3. `.env` (required for a full PO round-trip)

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/) — Gemini. |
| `GEMINI_MODEL` | e.g. `gemini-3.1-flash-lite-preview` (see `.env.example`). |
| `AGENT_API_KEY` | Random string; same value must be configured in PO for the **external agent** (`X-API-Key`). Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |
| `AGENT_PUBLIC_URL` | **https base only** of the **A2A** tunnel (port **8001**). No trailing path. After you change it, **restart** the A2A process so the agent card URL updates. |
| `MCP_SERVER_URL` | **Full** MCP JSON-RPC URL: `https://<mcp-tunnel-host>/mcp` → your **:8000**. Must differ from the A2A public host. On one machine, set this to your **MCP** tunnel, not `localhost`, when PO in the cloud must call you. |
| `PO_PLATFORM_BASE_URL` | Usually `https://app.promptopinion.ai` (FHIR extension URI in the agent card). |

Optional: `NGROK_AUTHTOKEN` in `.env` for `make ngrok` (ngrok v3 reads config).

**pass token in PO**  
For both MCP and the external agent, enable the option so the workspace **FHIR
token** is sent to A2A and propagated to MCP headers (`x-fhir-server-url`,
`x-fhir-access-token`) when `fetch_patient_context` runs.

---

## 4. Start the two services (local processes)

**Terminal 1 — MCP**

```bash
make mcp
# Windows / explicit:
# uv run --package mcp_server uvicorn mcp_server.main:app --host 0.0.0.0 --port 8000 --log-level info --reload --env-file .env
```

**Terminal 2 — A2A**

```bash
make agent
# Windows / explicit:
# uv run --package a2a_agent uvicorn a2a_agent.app:a2a_app --host 0.0.0.0 --port 8001 --log-level info --reload --env-file .env
```

Wait until both are listening before you register tunnels and PO.

---

## 5. Expose to the internet (two tunnels)

PO runs in the cloud; it must reach your laptop. Free-tier default in this
repo: **Cloudflare** for MCP and **ngrok** for **A2A** (avoids a single static
name binding to two ports — see `ngrok.example.yml` and `make tunnels`).

**Terminal 3 — MCP tunnel (→ :8000)**

```bash
make cf-tunnel
# or: cloudflared tunnel --url http://localhost:8000
```

Copy the printed `https://*.trycloudflare.com` (or your stable URL). Your PO
**MCP** registration is: **`https://<that-host>/mcp`**

Put the **same** `https://<that-host>/mcp` into `.env` as:

```env
MCP_SERVER_URL=https://<that-host>/mcp
```

Then **restart** `make agent` so the A2A side picks up the updated `MCP_SERVER_URL`.

**Terminal 4 — A2A tunnel (→ :8001)**

1. `cp ngrok.example.yml ngrok.yml`, set `agent.authtoken` in `ngrok.yml` (or
   use `${NGROK_AUTHTOKEN}` with `NGROK_AUTHTOKEN` in `.env`).
2. `make ngrok` (or `ngrok start --all --config ngrok.yml`).

Copy the **https** URL shown for 8001. Set in `.env`:

```env
AGENT_PUBLIC_URL=https://<a2a-ngrok-or-reserved-host>
```

**Restart** `make agent` again.

> **ngrok v3** with two endpoints in one `ngrok.yml` is also valid (one host for
> MCP, one for A2A) if you have two free random URLs or two reserved hostnames
> in the dashboard. See `ngrok.example.yml` (A2A-only by default) and
> [issue #17](https://github.com/agents-assemble/priorauth-agent/issues/17).

---

## 6. Register in Prompt Opinion (same browser / workspace)

1. **MCP (Server / Hub):** `https://<mcp-tunnel>/mcp` — enable **pass token** if
   the UI offers it.
2. **External A2A agent:** `https://<a2a-tunnel>` (base from `AGENT_PUBLIC_URL`) —
   set the **API key** to your `AGENT_API_KEY` — **pass token** on.

3. In the workspace, use a **patient** that exists in the workspace FHIR and
   ask the general agent to use your external prior-auth agent.

**Sanity checks (optional)**

- Agent card: `curl -s https://<a2a-tunnel>/.well-known/agent-card.json`
- MCP init (from any machine that can hit your MCP URL; or localhost):

  `make mcp-initialize` (hits local 8000 only).

---

## 7. If someone else already runs MCP and you only run A2A

Set **`MCP_SERVER_URL`** to **their** public `https://…/mcp`, not yours. You
only need **`make agent`** and your **A2A** tunnel for `AGENT_PUBLIC_URL`. That
is a split-machine setup; this doc is for **all-in-one** on one laptop.

---

## 8. Quick failure checklist

- **404** on agent card: wrong tunnel, or same hostname as MCP pointing at the
  wrong port.
- **A2A cannot call MCP:** `MCP_SERVER_URL` missing `/mcp`, or points at A2A
  host, or tunnel down.
- **MCP 401/403 on FHIR:** “pass token” and workspace FHIR not propagated —
  see `docs/po_platform_notes.md`.
- **Tests:** `A2A_TESTING_NO_MCP=1` is set in `tests/conftest.py` so CI does
  not load `MCP_SERVER_URL` from `.env` for guardrail tests. Production dev on
  your machine is unaffected.

---

## 9. Related

- [AGENTS.md](../AGENTS.md) — team conventions
- [a2a_agent/README.md](../a2a_agent/README.md) — A2A + `MCP_SERVER_URL` / `patient_context`
- [mcp_server/README.md](../mcp_server/README.md) — MCP SHARP headers
- [docs/po_platform_notes.md](po_platform_notes.md) — Prompt Opinion quirks
- [scripts/ngrok-all.ps1](../scripts/ngrok-all.ps1) — Windows helper (if your
  `ngrok.yml` defines the endpoints you use)
