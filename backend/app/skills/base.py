"""Skill protocol + result schema for the in-memory skill registry."""
from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class SkillResult(TypedDict, total=False):
    """Return shape from ``Skill.run``.

    ``output`` is the human-readable result; ``metadata`` carries arbitrary
    structured data (token counts, timings, etc.) for future agent tool use.
    """

    output: str
    metadata: dict[str, Any] | None


@runtime_checkable
class Skill(Protocol):
    """A skill is identified by a unique name and a one-line description."""

    name: str
    description: str

    async def run(self, input: str = "", args: dict[str, Any] | None = None) -> SkillResult:
        """Execute the skill.

        Implementations should not raise on bad input — return an error
        shape (``{"output": "...", "metadata": {"error": True}}``) instead,
        so the router can wrap everything in a uniform response envelope.
        """
        ...