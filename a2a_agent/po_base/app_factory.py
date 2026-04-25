"""
A2A application factory — shared by all agents in this repo.

Each agent's app.py calls create_a2a_app() with its own name, description,
URL, and optional FHIR extension URI.  The factory handles the AgentCard
boilerplate, wires up the A2A transport, and optionally attaches API key
middleware.

Security modes
──────────────
  require_api_key=True  (default)
      Agent card advertises X-API-Key as required.
      All requests except /.well-known/agent-card.json are blocked without a
      valid key.  Use this for agents that handle sensitive data (e.g. FHIR).

  require_api_key=False
      Agent card declares no security scheme — any caller can send requests
      without a key.  The agent card itself makes this discoverable so Prompt
      Opinion and other callers know no key is needed.  Use this for public or
      read-only utility agents (e.g. ICD-10 lookups, date/time queries).

Usage:
    from a2a_agent.po_base.app_factory import create_a2a_app
    from .agent import root_agent

    # Authenticated agent (requires X-API-Key) with FHIR + SMART scopes
    a2a_app = create_a2a_app(
        agent=root_agent,
        name="healthcare_fhir_agent",
        description="Queries patient FHIR data.",
        url="http://localhost:8001",
        port=8001,
        fhir_extension_uri="https://your-workspace/schemas/a2a/v1/fhir-context",
        fhir_scopes=[
            {"name": "patient/Patient.rs",           "required": True},
            {"name": "patient/MedicationRequest.rs", "required": True},
            {"name": "patient/Condition.rs",         "required": True},
            {"name": "patient/Observation.rs",       "required": True},
        ],
        require_api_key=True,   # default — can be omitted
    )

    # Anonymous agent (no key needed)
    a2a_app = create_a2a_app(
        agent=root_agent,
        name="general_agent",
        description="Public utility agent.",
        url="http://localhost:8002",
        port=8002,
        require_api_key=False,
    )
"""

import logging
import os
from typing import Any
from urllib.parse import urlparse

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentSkill,
)
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from pydantic import Field


class AgentExtensionV1(AgentExtension):
    """AgentExtension subclass that adds the `params` field for SMART scope declarations.

    The installed a2a-sdk does not define `params` on AgentExtension, so the
    scopes payload would be silently dropped during JSON serialisation.  Declaring
    the field explicitly here ensures it is included in the agent card output.

    Once the a2a-sdk ships native v1 support this subclass can be removed.
    """

    params: dict[str, Any] | None = Field(default=None)


class AgentCardV1(AgentCard):
    """AgentCard subclass that patches two fields missing/changed in A2A v1.

    1. supportedInterfaces — not defined in installed a2a-sdk; added here so
       it is included in the serialised JSON.
    2. securitySchemes — the parent types this as dict[str, SecurityScheme],
       which forces Pydantic to serialise using the OLD flat format
       (type/name/in).  Po v1 expects the NEW nested-key format
       (apiKeySecurityScheme/...).  Overriding to dict[str, Any] lets the
       v1-format dict pass through unmodified.

    Both overrides can be removed once the a2a-sdk ships native v1 support.
    """

    supportedInterfaces: list[dict[str, Any]] = Field(default_factory=list)
    securitySchemes: dict[str, Any] | None = None  # override parent's typed field


from a2a_agent.po_base.middleware import ApiKeyMiddleware, JsonRpcPathCompatMiddleware

logger = logging.getLogger(__name__)


def _normalize_agent_card_public_url(raw: str) -> str:
    """Strip accidental ``/mcp`` suffix and trailing slashes from the agent base.

    A2A JSON-RPC is posted to ``/`` on the agent process (see ``a2a.utils.constants
    DEFAULT_RPC_URL``). The MCP server uses ``/mcp``. If ``AGENT_PUBLIC_URL`` is
    pasted with an ``/mcp`` suffix (easy to confuse with ``MCP_SERVER_URL``),
    Prompt Opinion will POST JSON-RPC to ``…/mcp`` on port 8001 — Starlette has no
    such route → **HTTP 404**.
    """
    u = raw.strip().rstrip("/")
    suffix = "/mcp"
    if len(u) >= len(suffix) and u.lower().endswith(suffix):
        logger.warning(
            "AGENT_PUBLIC_URL must be the A2A agent base (no %r path). Stripped "
            "from %r — restart `make agent` after fixing .env so the agent card "
            "matches this URL.",
            suffix,
            raw,
        )
        u = u[: -len(suffix)].rstrip("/")
    return u


def _warn_agent_url_same_host_as_mcp(agent_url: str) -> None:
    """Same public hostname for MCP and A2A breaks PO (wrong upstream on one port)."""
    mcp_raw = (os.environ.get("MCP_SERVER_URL") or "").strip()
    if not mcp_raw or not agent_url.strip():
        return
    mcp_base = mcp_raw.strip().rstrip("/")
    if mcp_base.lower().endswith("/mcp"):
        mcp_base = mcp_base[: -len("/mcp")].rstrip("/")
    try:
        agent_netloc = urlparse(agent_url).netloc
        mcp_netloc = urlparse(mcp_base).netloc
    except ValueError:
        return
    if agent_netloc and agent_netloc == mcp_netloc:
        logger.error(
            "AGENT_PUBLIC_URL host %r matches MCP_SERVER_URL host %r. They must "
            "be two different tunnels (MCP → :8000, A2A → :8001). PO will see 404s "
            "or wrong payloads otherwise. See docs/LOCAL_DEV_ONE_MACHINE.md.",
            agent_netloc,
            mcp_netloc,
        )


def create_a2a_app(
    agent,
    name: str,
    description: str,
    url: str,
    port: int = 8001,
    version: str = "1.0.0",
    fhir_extension_uri: str | None = None,
    fhir_scopes: list[dict[str, Any]] | None = None,
    require_api_key: bool = True,
    skills: list[AgentSkill] | None = None,
):
    """
    Build and return an A2A ASGI application for the given ADK agent.

    Args:
        agent:               The ADK Agent instance (root_agent from agent.py).
        name:                Agent name — shown in the agent card and Prompt Opinion UI.
        description:         Short description of what this agent does.
        url:                 Public base URL where this agent is reachable.
        port:                Port the agent listens on (used by to_a2a).
        version:             Semver string, e.g. "1.0.0".
        fhir_extension_uri:  If provided, advertises FHIR context support in the
                             agent card.  Callers use this URI as the metadata key
                             when sending FHIR credentials.  Omit for non-FHIR agents.
        fhir_scopes:         SMART-on-FHIR scopes the agent requires, expressed as a
                             list of dicts: [{"name": "patient/Patient.rs", "required": True}, ...]
                             Scopes with "required": True cannot be unchecked by the user
                             in the Prompt Opinion UI.  Only used when fhir_extension_uri
                             is also provided.  Omit for non-FHIR agents.
        require_api_key:     If True (default), the agent card declares X-API-Key as
                             required and ApiKeyMiddleware is attached — all requests
                             without a valid key are rejected with 401/403.
                             If False, no security scheme is declared and no middleware
                             is attached — the agent is publicly accessible.

    Returns:
        A Starlette ASGI application ready to be served with uvicorn.
    """
    public_url = _normalize_agent_card_public_url(url)
    _warn_agent_url_same_host_as_mcp(public_url)

    # Optional FHIR extension — only included when the agent supports it.
    # Uses AgentExtensionV1 to add `params` (SMART scopes) to the serialised JSON.
    # Per the Po spec the extension-level `required` is false — individual scopes
    # carry their own required flag inside params.scopes.
    extensions = []
    if fhir_extension_uri:
        extension_params = None
        if fhir_scopes:
            extension_params = {"scopes": fhir_scopes}
        extensions = [
            AgentExtensionV1(
                uri=fhir_extension_uri,
                description="FHIR context allowing the agent to query a FHIR server securely",
                required=False,
                params=extension_params,
            )
        ]

    # Security scheme — advertised in the agent card so callers know what to send.
    # Uses the A2A v1 nested-key format (apiKeySecurityScheme) which is what
    # the Po backend parses to produce securityType="ApiKey".  The parent
    # AgentCard.securitySchemes field is typed as dict[str, SecurityScheme],
    # which would force the OLD flat format (type/name/in) on serialisation
    # — hence securitySchemes is overridden to dict[str, Any] in AgentCardV1.
    if require_api_key:
        security_schemes = {
            "apiKey": {
                "apiKeySecurityScheme": {
                    "name": "X-API-Key",
                    "location": "header",  # Po backend uses "location", not "in"
                    "description": "API key required to access this agent.",
                }
            }
        }
        security = [{"apiKey": []}]
    else:
        # No security scheme — agent is publicly accessible.
        security_schemes = None
        security = None

    # AgentCardV1 is a local subclass of AgentCard that adds `supportedInterfaces`
    # as a proper Pydantic field so it is included in the serialised JSON.
    # `url` is still required by the installed library — kept until the library
    # ships native A2A v1 support, at which point it can be dropped.
    agent_card = AgentCardV1(
        name=name,
        description=description,
        url=public_url,  # still required by installed a2a-sdk; remove when library reaches v1
        version=version,
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=False,
            stateTransitionHistory=False,  # v1: field kept but must be false
            extensions=extensions,
        ),
        # supportedInterfaces replaces url + preferredTransport in A2A v1.
        # First entry is the preferred transport.
        supportedInterfaces=[
            {
                "url": public_url,
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            },
        ],
        skills=skills or [],
        securitySchemes=security_schemes,
        security=security,
    )

    app = to_a2a(agent, port=port, agent_card=agent_card)

    # Outermost first: normalize mistaken POST /mcp (MCP path) to POST / for A2A.
    if require_api_key:
        app.add_middleware(ApiKeyMiddleware)
    app.add_middleware(JsonRpcPathCompatMiddleware)

    return app
