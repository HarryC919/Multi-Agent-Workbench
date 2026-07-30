"""Skills package.

A *skill* is a small, self-contained async callable discovered at startup
from submodules of this package. Each submodule exposes a module-level
``SKILL`` instance implementing :class:`app.skills.base.Skill`.

Phase 3: markdown-defined skills (``.md`` files in ``skills_md/``) are also
discovered and registered via ``discover_markdown_skills``. They can be
hot-reloaded at runtime with ``reload_markdown_skills``.
"""
from app.skills import base, echo, current_time, web_search  # noqa: F401
from app.skills.registry import (
    get_skill,
    list_skills,
    iter_skills,
    discover_markdown_skills,
    reload_markdown_skills,
)

__all__ = [
    "base",
    "get_skill",
    "list_skills",
    "iter_skills",
    "discover_markdown_skills",
    "reload_markdown_skills",
]