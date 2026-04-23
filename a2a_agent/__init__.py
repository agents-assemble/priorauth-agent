"""Google ADK A2A agent for prior authorization (lumbar MRI).

Entry point: `a2a_agent.app:a2a_app` (uvicorn ASGI application).
See a2a_agent/README.md for architecture, a2a_agent/REFERENCE.md for
the upstream PO reference repo we forked from.
"""

# CRITICAL: load .env at package top-level, BEFORE any submodule is imported.
# `po_base/middleware.py` computes VALID_API_KEYS at module import time by
# reading os.getenv(...). If load_dotenv() runs in app.py instead, middleware
# has already cached VALID_API_KEYS == set() by the time .env is read, and
# every authenticated request returns 403.
# override=True: .env is the single source of truth for local dev, so a stale
# shell export (e.g. AGENT_API_KEY=test-placeholder left over from a prior
# session) cannot silently override the real generated key. Harmless in prod
# containers — there is no .env file baked into the image, so load_dotenv
# returns False and env stays whatever fly.toml / docker-compose set.
from dotenv import load_dotenv

load_dotenv(override=True)
