"""Skills package.

A *skill* is a small, self-contained async callable discovered at startup
from submodules of this package. Each submodule exposes a module-level
``SKILL`` instance implementing :class:`app.skills.base.Skill`.
"""
from app.skills import base, echo, current_time  # noqa: F401
from app.skills.registry import get_skill, list_skills, iter_skills

__all__ = ["base", "get_skill", "list_skills", "iter_skills"]