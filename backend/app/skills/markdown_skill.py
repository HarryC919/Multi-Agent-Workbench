"""Markdown-defined skill — a prompt-based skill loaded from a .md file.

Phase 3 first round: each .md file in the ``skills_md/`` directory defines a
skill whose markdown body is used as a system prompt for a single-turn LLM
call. The skill's ``name`` and ``description`` come from YAML frontmatter
(with fallbacks to the filename and first heading).

Framework boundary: this module does NOT import LangChain. The ``_chat_model``
is injected by ``_wrap_skill_as_tool`` in ``agent_service.py`` at call time.
``run()`` only imports ``SystemMessage``/``HumanMessage`` inside the method
body, keeping the module-level import surface clean.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from app.skills.base import SkillResult

logger = logging.getLogger(__name__)

# YAML frontmatter: --- ... --- at the very start of the file.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# First Markdown heading: # Title
_FIRST_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


class MarkdownSkill:
    """A skill whose behavior is defined by a .md file.

    The markdown body (minus frontmatter) is the system prompt. When invoked,
    the skill calls the LLM with ``[SystemMessage(instructions), HumanMessage(input)]``
    and returns the response.

    ``_chat_model`` is set by the agent service at wrap time; without it,
    ``run()`` returns an error shape.
    """

    def __init__(self, name: str, description: str, instructions: str):
        self.name = name
        self.description = description
        self.instructions = instructions
        self._chat_model: Any = None  # BaseChatModel, injected later

    def set_chat_model(self, model: Any) -> None:
        """Inject the LangChain chat model (called by ``_wrap_skill_as_tool``)."""
        self._chat_model = model

    async def run(self, input: str = "", args: dict[str, Any] | None = None) -> SkillResult:
        if self._chat_model is None:
            return {
                "output": f"[markdown skill '{self.name}': no chat model configured]",
                "metadata": {"error": True, "skill_name": self.name},
            }

        # LangChain imports live inside the method body to keep the module-level
        # import surface clean (framework boundary).
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=self.instructions),
            HumanMessage(content=input or ""),
        ]

        try:
            result = await self._chat_model.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001 — surface, don't crash
            logger.warning("Markdown skill '%s' LLM call failed: %s", self.name, exc)
            return {
                "output": f"[markdown skill '{self.name}' error: {exc}]",
                "metadata": {"error": True, "skill_name": self.name},
            }

        content = result.content if hasattr(result, "content") else str(result)
        return {"output": str(content), "metadata": {"skill_name": self.name}}


# ------------------------------------------------------------------ parser


def parse_markdown_skill(filepath: Path) -> MarkdownSkill | None:
    """Parse a .md file into a MarkdownSkill, or return None on failure.

    Frontmatter rules (in priority order):
      1. YAML frontmatter: ``name`` (required), ``description`` (optional).
      2. No frontmatter: ``filepath.stem`` → name, first ``# heading`` → description.
      3. Body after frontmatter (or entire file if no frontmatter) → instructions.

    Returns ``None`` if no valid name can be determined.
    """
    try:
        raw = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read %s: %s", filepath, exc)
        return None

    if not raw.strip():
        logger.warning("Skipping empty markdown skill file: %s", filepath)
        return None

    name: str | None = None
    description: str | None = None
    body = raw

    # Try YAML frontmatter first.
    fm_match = _FRONTMATTER_RE.match(raw)
    if fm_match:
        body = raw[fm_match.end() :]
        try:
            import yaml

            fm = yaml.safe_load(fm_match.group(1)) or {}
            if isinstance(fm, dict):
                name = fm.get("name")
                if isinstance(name, str):
                    name = name.strip()
                description = fm.get("description")
                if isinstance(description, str):
                    description = description.strip()
        except Exception as exc:  # noqa: BLE001 — invalid YAML, fall through
            logger.warning("Invalid YAML frontmatter in %s: %s", filepath, exc)

    # Fallback: filename stem → name.
    if not name:
        name = filepath.stem.strip()
        if not name:
            logger.warning("Cannot determine skill name from %s", filepath)
            return None

    # Fallback: first # heading → description.
    if not description:
        heading_match = _FIRST_HEADING_RE.search(body)
        if heading_match:
            description = heading_match.group(1).strip()
        else:
            description = f"Skill defined by {filepath.name}"

    instructions = body.strip()
    if not instructions:
        logger.warning("Markdown skill %s has empty instructions (body)", filepath)
        return None

    return MarkdownSkill(name=name, description=description or "", instructions=instructions)


__all__ = ["MarkdownSkill", "parse_markdown_skill"]