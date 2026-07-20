"""Skills package.

A *skill* is a small, self-contained async callable discovered at startup
from submodules of this package. Each submodule exposes a module-level
``SKILL`` instance implementing :class:`app.skills.base.Skill`.

This first iteration keeps an in-memory registry only — no persistence, no
UI. Deep integration as agent tools is deferred to AgentService phase 2.
"""
from app.skills import base, echo, current_time  # noqa: F401
from app.skills.registry import get_skill, list_skills

__all__ = ["base", "get_skill", "list_skills"]