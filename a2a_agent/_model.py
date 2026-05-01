"""Shared ADK model-name configuration for the root agent and all sub-agents.

Lives in its own module (not inline in ``a2a_agent/agent.py``) so sub-agent
modules can import ``_DEFAULT_MODEL`` without creating a circular dependency
back on ``a2a_agent.agent`` (which itself imports the sub-agents). The
single-source-of-truth property is preserved — there is exactly one
``_DEFAULT_MODEL`` binding in the ``a2a_agent`` package, and every ADK
``Agent`` in the package resolves its model via
``os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL)``.

Week-2 Day-1 capability-check note: if Gemini 3.1 Flash Lite is insufficient
for criteria reasoning or letter generation (PLAN.md line 275), escalating to
a bigger tier is a single ``GEMINI_MODEL`` env-var flip in the Fly.io /
``.env`` deploy — no code change, and all four agents (root + 3 subs) move
together.
"""

from __future__ import annotations

# Default: gemini-2.5-flash-lite (GA, stable, 15 RPM free tier).
# Switched from gemini-3.1-flash-lite-preview which had unpublished, lower
# rate limits causing frequent 503s on the free tier.
# Per AGENTS.md, never hardcode the model name at call sites;
# always flow through this constant.
_DEFAULT_MODEL = "gemini-2.5-flash-lite"

__all__ = ["_DEFAULT_MODEL"]
