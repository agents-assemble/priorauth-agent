"""Thin async FHIR R4 client.

Adapted from prompt-opinion/po-community-mcp/python/fhir_client.py (commit
e19ec91). Changes from upstream:

- Accepts an injectable `httpx.AsyncClient` so the FastMCP request-context
  can own the connection pool for the lifetime of the request (upstream
  opens + closes a client on every GET, which is fine for a single tool call
  but wasteful when a tool issues 4-6 FHIR reads, which is normal for
  `fetch_patient_context`).
- Retries 2x on httpx.ConnectError with exponential backoff - PO's workspace
  FHIR server has shown occasional 1-second cold starts after idle periods
  (see docs/po_platform_notes.md).
- `search()` auto-pages up to `max_pages` via the `Bundle.link[next]` href
  - upstream only returns the first page which silently truncates at 20
  resources and ate several hours of my dev time on patient B.

The FHIR token is injected as `Authorization: Bearer <token>` on every
request. It is NEVER logged (only a fingerprint) - patient token is PHI-
adjacent under HIPAA.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0
_MAX_RETRIES = 2
_BACKOFF_BASE = 0.5
_HTTP_NOT_FOUND = 404


class FhirClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        http: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._timeout = timeout
        # When http is None we open/close an ephemeral client per call (upstream
        # behaviour); when injected we reuse the caller's pool.
        self._external_http = http is not None
        self._http = http

    async def __aenter__(self) -> FhirClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._http is not None and not self._external_http:
            await self._http.aclose()
            self._http = None

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/fhir+json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _build_url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    async def _get(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any] | None:
        assert self._http is not None, "FhirClient must be used as an async context manager"
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._http.get(url, headers=self._headers(), params=params)
                if response.status_code == _HTTP_NOT_FOUND:
                    return None
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
            except httpx.ConnectError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    delay = _BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        "fhir_connect_retry attempt=%d/%d delay=%.1fs",
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
        # Unreachable — raise in the loop above exhausts retries — but keeps mypy happy.
        raise last_exc  # type: ignore[misc]

    async def read(self, path: str) -> dict[str, Any] | None:
        """Single-resource read, e.g. `read("Patient/123")`."""
        return await self._get(self._build_url(path))

    async def search(
        self,
        resource_type: str,
        search_parameters: dict[str, str] | None = None,
        *,
        max_pages: int = 5,
    ) -> list[dict[str, Any]]:
        """Search and auto-page via Bundle.link[next].

        Returns the flat list of resources (not the raw bundles). Capped at
        `max_pages` to bound runtime; 5 pages x default `_count=50` per PO
        workspace = 250 resources, which is 10x what any PA tool needs.
        """
        bundle = await self._get(self._build_url(resource_type), params=search_parameters)
        resources: list[dict[str, Any]] = []
        pages_fetched = 0
        while bundle is not None and pages_fetched < max_pages:
            for entry in bundle.get("entry", []):
                res = entry.get("resource")
                if res:
                    resources.append(res)
            next_url = next(
                (
                    link.get("url")
                    for link in bundle.get("link", [])
                    if link.get("relation") == "next"
                ),
                None,
            )
            if not next_url:
                break
            pages_fetched += 1
            bundle = await self._get(next_url)
        return resources
