"""Prompt Opinion ADK base library (forked from prompt-opinion/po-adk-python).

This package provides the A2A protocol plumbing that PO expects:

- `app_factory.create_a2a_app` — builds the uvicorn ASGI app + agent card
- `middleware.ApiKeyMiddleware` — validates X-API-Key and bridges FHIR metadata
- `fhir_hook.extract_fhir_context` — ADK before_model_callback that pulls
  FHIR creds out of A2A message metadata into session state
- `logging_utils` — structured JSON logging helpers

Upstream source: https://github.com/prompt-opinion/po-adk-python
See ../REFERENCE.md for attribution, the exact upstream commit we copied from,
and the list of our local modifications.

Import sub-modules directly, e.g.:
    from a2a_agent.po_base.middleware import ApiKeyMiddleware
"""

from a2a_agent.po_base.logging_utils import configure_logging

configure_logging("a2a_agent.po_base")
