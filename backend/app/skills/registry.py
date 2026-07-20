"""In-memory skill registry.

Submodules of ``app.skills`` expose a module-level ``SKILL`` attribute that
implements :class:`app.skills.base.Skill`. Importing this registry module
loads them once and indexes them by ``name``.

Keeping process-local state here mirrors the "layer-A placeholder; deep
agent tool integration comes later" decision in the development plan.
"""
from __future__ import annotations

from app.skills.base import Skill, SkillResult
from app.skills import echo, current_time

_REGISTRY: dict[str, Skill] = {}


def _register(skill: Skill) -> None:
    if skill.name in _REGISTRY:
        raise RuntimeError(f"Duplicate skill name registered: {skill.name!r}")
    _REGISTRY[skill.name] = skill


_register(echo.SKILL)  # type: ignore[arg-type]
_register(current_time.SKILL)  # type: ignore[arg-type]


def list_skills() -> list[dict[str, str]]:
    """Return a JSON-serializable manifest of registered skills."""
    return [{"name": s.name, "description": s.description} for s in _REGISTRY.values()]


def get_skill(name: str) -> Skill | None:
    """Look up a skill by name; returns ``None`` when not registered."""
    return _REGISTRY.get(name)


__all__ = ["list_skills", "get_skill", "SkillResult"]