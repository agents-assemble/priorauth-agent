"""Payer-criteria schema, data, and loader.

Week 2's `mcp_server.tools.match_payer_criteria` imports from here. The
criteria shape is intentionally internal to `mcp_server/` — `a2a_agent/`
only ever sees `CriteriaResult` (in `shared/`), never the JSON structure.
"""

from __future__ import annotations

from .loader import (
    CriteriaNotFoundError,
    CriteriaSchemaMismatchError,
    load_payer_criteria,
    registered_payer_ids,
)
from .schema import (
    SCHEMA_VERSION,
    ConservativeTherapyRule,
    CoverageGating,
    PayerCriteria,
    PriorImagingRule,
    RedFlag,
    ServiceApplicability,
    TherapyKind,
    TherapyPathway,
)

__all__ = [
    "SCHEMA_VERSION",
    "ConservativeTherapyRule",
    "CoverageGating",
    "CriteriaNotFoundError",
    "CriteriaSchemaMismatchError",
    "PayerCriteria",
    "PriorImagingRule",
    "RedFlag",
    "ServiceApplicability",
    "TherapyKind",
    "TherapyPathway",
    "load_payer_criteria",
    "registered_payer_ids",
]
