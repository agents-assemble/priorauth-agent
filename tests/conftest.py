"""Pytest root hooks.

`a2a_agent` loads ``.env`` on import. Week-1 guardrail tests expect
``MCP_SERVER_URL`` unset for ``patient_context`` (no MCP tool wiring). The
`A2A_TESTING_NO_MCP` flag tells ``a2a_agent.__init__`` to strip
``MCP_SERVER_URL`` after ``load_dotenv`` so CI and `pytest` stay deterministic
even when a developer has MCP set in their local ``.env``.
"""

from __future__ import annotations

import os

os.environ["A2A_TESTING_NO_MCP"] = "1"
