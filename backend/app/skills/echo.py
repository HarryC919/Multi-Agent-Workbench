"""Echo skill — returns the input verbatim.

Useful for sanity-checking the skills pipeline end-to-end.
"""
from __future__ import annotations

from typing import Any

from app.skills.base import SkillResult


class EchoSkill:
    name = "echo"
    description = "Echo back the provided input."

    async def run(self, input: str = "", args: dict[str, Any] | None = None) -> SkillResult:
        # Honor an optional ``upper`` flag from args for parity checking.
        upper = bool((args or {}).get("upper", False))
        output = input.upper() if upper else input
        return {"output": output, "metadata": {"length": len(input)}}


SKILL = EchoSkill()