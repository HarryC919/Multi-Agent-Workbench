"""Current-time skill — returns the wall clock time in UTC and local TZ."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.skills.base import SkillResult


class CurrentTimeSkill:
    name = "current_time"
    description = "Return the current wall-clock time in UTC and local timezone."

    async def run(self, input: str = "", args: dict[str, Any] | None = None) -> SkillResult:
        utc_now = datetime.now(timezone.utc)
        local_now = datetime.now().astimezone()
        return {
            "output": utc_now.isoformat(),
            "metadata": {
                "utc": utc_now.isoformat(),
                "local": local_now.isoformat(),
                "tz": str(local_now.tzinfo),
            },
        }


SKILL = CurrentTimeSkill()