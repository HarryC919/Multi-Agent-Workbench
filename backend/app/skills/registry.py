"""In-memory skill registry.

Submodules of ``app.skills`` expose a module-level ``SKILL`` attribute that
implements :class:`app.skills.base.Skill`. Importing this registry module
loads them once and indexes them by ``name``.

Phase 3: markdown-defined skills (.md files in ``skills_md/``) are also
registered here via ``discover_markdown_skills()``. Their source is tracked
separately so ``reload_markdown_skills()`` can clear and re-import them
without affecting Python-defined skills.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.skills.base import Skill, SkillResult
from app.skills import echo, current_time, web_search

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, Skill] = {}
# Track which skill names came from .md files so reload can selectively remove them.
_MARKDOWN_SKILL_NAMES: set[str] = set()


def _register(skill: Skill) -> None:
    if skill.name in _REGISTRY:
        raise RuntimeError(f"Duplicate skill name registered: {skill.name!r}")
    _REGISTRY[skill.name] = skill


_register(echo.SKILL)  # type: ignore[arg-type]
_register(current_time.SKILL)  # type: ignore[arg-type]
_register(web_search.SKILL)  # type: ignore[arg-type]


def list_skills() -> list[dict[str, str]]:
    """Return a JSON-serializable manifest of registered skills.

    Each entry includes a ``source`` field: ``"python"`` for skills defined
    in .py modules, ``"markdown"`` for skills loaded from .md files.
    """
    results: list[dict[str, str]] = []
    for name, skill in _REGISTRY.items():
        source = "markdown" if name in _MARKDOWN_SKILL_NAMES else "python"
        results.append({"name": name, "description": skill.description, "source": source})
    return results


def get_skill(name: str) -> Skill | None:
    """Look up a skill by name; returns ``None`` when not registered."""
    return _REGISTRY.get(name)


def iter_skills() -> list[Skill]:
    """Return all registered Skill instances.

    AgentService phase 2a uses this to wrap each Skill as a LangChain tool
    for the LangGraph ``create_react_agent`` executor.
    """
    return list(_REGISTRY.values())


# ----------------------------------------------------------- markdown skills


def discover_markdown_skills(skills_dir: Path) -> list[Skill]:
    """Scan ``skills_dir`` for .md files and register them as MarkdownSkill instances.

    Files with duplicate names (already in ``_REGISTRY``) are skipped with a
    warning. Returns the list of newly registered skills.
    """
    from app.skills.markdown_skill import parse_markdown_skill

    if not skills_dir.is_dir():
        logger.info("Markdown skills directory does not exist: %s", skills_dir)
        return []

    registered: list[Skill] = []
    for filepath in sorted(skills_dir.glob("*.md")):
        skill = parse_markdown_skill(filepath)
        if skill is None:
            continue

        if skill.name in _REGISTRY:
            logger.warning(
                "Skipping markdown skill %r from %s: name already registered",
                skill.name,
                filepath.name,
            )
            continue

        _register(skill)
        _MARKDOWN_SKILL_NAMES.add(skill.name)
        registered.append(skill)
        logger.info("Registered markdown skill %r from %s", skill.name, filepath.name)

    return registered


def reload_markdown_skills(skills_dir: Path) -> int:
    """Clear previously loaded markdown skills and re-scan the directory.

    Returns the number of skills reloaded.
    """
    # Remove markdown-sourced skills from the registry.
    for name in list(_MARKDOWN_SKILL_NAMES):
        _REGISTRY.pop(name, None)
    _MARKDOWN_SKILL_NAMES.clear()

    new_skills = discover_markdown_skills(skills_dir)
    return len(new_skills)


def get_markdown_skill_source(name: str, skills_dir: Path) -> dict | None:
    """Read and parse a markdown skill's source file.

    Returns ``{name, description, content}`` (content = instruction body
    without frontmatter), or ``None`` if the .md file does not exist.
    Used by the Skills Manager edit endpoint to pre-fill the form.
    """
    from app.skills.markdown_skill import parse_markdown_skill

    filepath = skills_dir / f"{name}.md"
    if not filepath.is_file():
        return None
    skill = parse_markdown_skill(filepath)
    if skill is None:
        return None
    return {"name": skill.name, "description": skill.description, "content": skill.instructions}


def delete_markdown_skill(name: str, skills_dir: Path) -> bool:
    """Delete a markdown skill's .md file and unregister it.

    Returns ``True`` if the file was deleted, ``False`` if it didn't exist.
    The in-memory registry entry is removed regardless (best-effort).
    """
    filepath = skills_dir / f"{name}.md"
    deleted = False
    if filepath.is_file():
        filepath.unlink()
        deleted = True
    # Remove from the in-memory registry if present.
    _REGISTRY.pop(name, None)
    _MARKDOWN_SKILL_NAMES.discard(name)
    return deleted


__all__ = [
    "list_skills",
    "get_skill",
    "iter_skills",
    "discover_markdown_skills",
    "reload_markdown_skills",
    "get_markdown_skill_source",
    "delete_markdown_skill",
    "SkillResult",
]