"""Load and validate payer-criteria JSON files by `payer_id`.

Uses `importlib.resources` so the JSONs travel with the installed
package (works under `uv sync`, Docker, Fly.io). Loader is pure —
no caching yet; revisit if profiling shows it matters.
"""

from __future__ import annotations

import json
from importlib import resources

from .schema import SCHEMA_VERSION, PayerCriteria

# Registry: payer_id -> filename inside `mcp_server/criteria/data/`.
# Add new payers here (one line per payer) as they're encoded.
_PAYER_FILES: dict[str, str] = {
    "cigna": "cigna_evicore_lumbar_mri.v1_0_2026.json",
    "aetna": "aetna_lumbar_mri.v2026.json",
}


class CriteriaNotFoundError(KeyError):
    """Raised when no criteria JSON is registered for the given payer_id."""


class CriteriaSchemaMismatchError(ValueError):
    """Raised when a loaded JSON's schema_version does not match SCHEMA_VERSION."""


def load_payer_criteria(payer_id: str) -> PayerCriteria:
    """Load and validate the criteria JSON for `payer_id`.

    Raises:
        CriteriaNotFoundError: no JSON is registered for `payer_id`.
        CriteriaSchemaMismatchError: loaded JSON's schema_version != SCHEMA_VERSION.
        pydantic.ValidationError: JSON fails schema validation (extra fields,
            non-canonical TherapyKind, unknown PathwayTrigger, etc.).
    """
    if payer_id not in _PAYER_FILES:
        raise CriteriaNotFoundError(
            f"No criteria JSON registered for payer_id={payer_id!r}. "
            f"Registered: {sorted(_PAYER_FILES)}"
        )

    filename = _PAYER_FILES[payer_id]
    data_pkg = resources.files("mcp_server.criteria.data")
    raw = (data_pkg / filename).read_text(encoding="utf-8")
    payload = json.loads(raw)

    found_version = payload.get("schema_version")
    if found_version != SCHEMA_VERSION:
        raise CriteriaSchemaMismatchError(
            f"{filename}: schema_version={found_version!r}, expected {SCHEMA_VERSION!r}"
        )
    return PayerCriteria.model_validate(payload)


def registered_payer_ids() -> list[str]:
    """Return payer_ids with registered criteria JSONs (stable order, useful in tests)."""
    return sorted(_PAYER_FILES)
