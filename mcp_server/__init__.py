"""FastMCP server package - prior-auth tools for lumbar MRI (CPT 72148).

Three tools (landing across Week 1-2):
- fetch_patient_context  - Week 1, FHIR extraction (scaffolded, stub-tier)
- match_payer_criteria   - Week 2, rule engine + Gemini reasoning
- generate_pa_letter     - Week 2, Gemini letter synthesis

Entry point: `mcp_server.main:app` (FastAPI ASGI). Run via `make mcp`.

.env is loaded here at package top-level, BEFORE any submodule is imported.
Currently nothing in this package caches env state at module-import time the
way `a2a_agent/po_base/middleware.py` does, but the same footgun can
re-emerge the moment we add e.g. a `_GEMINI_MODEL = os.getenv(...)` at module
scope in tools/. Staying consistent with `a2a_agent/__init__.py` — see
docs/po_platform_notes.md entry `2026-04-23 — load_dotenv() ordering`.
"""

from dotenv import load_dotenv

load_dotenv(override=True)
