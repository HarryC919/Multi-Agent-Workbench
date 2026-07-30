import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.skills import get_skill, list_skills, reload_markdown_skills
from app.skills.markdown_skill import assemble_markdown_skill
from app.skills.registry import delete_markdown_skill, get_markdown_skill_source

router = APIRouter()

# Resolve skills_md_dir relative to the backend root (same pattern as config.py).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent

# Skill names must be valid filenames: start with a letter, then alnum/_/-.
_SKILL_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")


def _skills_dir() -> Path:
    return _BACKEND_ROOT / settings.skills_md_dir


def _validate_skill_name(name: str) -> None:
    """Reject names that could path-traverse or aren't valid identifiers."""
    if not name or not _SKILL_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail=f"Invalid skill name: {name!r}")


class SkillInvokeRequest(BaseModel):
    """Body for ``POST /api/skills/{name}``."""

    input: str = ""
    args: dict[str, Any] | None = None


class SkillManifestItem(BaseModel):
    name: str
    description: str
    source: str = "python"  # "python" | "markdown"


class SkillInvokeResponse(BaseModel):
    status: str  # ok | error
    skill: str
    output: str | None = None
    metadata: dict[str, Any] | None = None
    message: str | None = None  # populated on error


class MarkdownSkillCreateRequest(BaseModel):
    name: str
    description: str = ""
    content: str


class MarkdownSkillUpdateRequest(BaseModel):
    description: str | None = None  # None = keep existing
    content: str


@router.get("/skills")
async def get_skills() -> dict[str, list[SkillManifestItem]]:
    return {"skills": [SkillManifestItem(**item) for item in list_skills()]}


# IMPORTANT: static routes must be declared BEFORE the parameterized
# ``/skills/{skill_name}`` route, otherwise ``POST /api/skills/reload`` (and
# the ``md`` CRUD routes below) are captured as ``skill_name`` and dispatched
# to ``invoke_skill``.
@router.post("/skills/reload")
async def reload_skills() -> dict[str, Any]:
    """Hot-reload markdown-defined skills from the skills_md/ directory."""
    try:
        count = reload_markdown_skills(_skills_dir())
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc)}
    return {"status": "ok", "reloaded": count}


# ---- markdown skill file CRUD (declared before /{skill_name}) ----


@router.get("/skills/md/{name}")
async def get_markdown_skill(name: str) -> dict[str, Any]:
    """Get the parsed source of a markdown skill (for editing)."""
    _validate_skill_name(name)
    source = get_markdown_skill_source(name, _skills_dir())
    if source is None:
        raise HTTPException(status_code=404, detail=f"Markdown skill {name!r} not found")
    return source


@router.post("/skills/md")
async def create_markdown_skill(payload: MarkdownSkillCreateRequest) -> dict[str, Any]:
    """Create a new .md skill file and reload the registry."""
    _validate_skill_name(payload.name)
    skills_dir = _skills_dir()
    skills_dir.mkdir(exist_ok=True)
    filepath = skills_dir / f"{payload.name}.md"
    if filepath.exists():
        raise HTTPException(status_code=400, detail=f"Skill {payload.name!r} already exists")
    # Also reject names colliding with Python-defined skills.
    if get_skill(payload.name) is not None:
        raise HTTPException(status_code=400, detail=f"Skill name {payload.name!r} already registered")
    filepath.write_text(
        assemble_markdown_skill(payload.name, payload.description, payload.content),
        encoding="utf-8",
    )
    reload_markdown_skills(skills_dir)
    return {"status": "ok", "name": payload.name}


@router.put("/skills/md/{name}")
async def update_markdown_skill(name: str, payload: MarkdownSkillUpdateRequest) -> dict[str, Any]:
    """Update an existing .md skill's content and reload."""
    _validate_skill_name(name)
    skills_dir = _skills_dir()
    filepath = skills_dir / f"{name}.md"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Markdown skill {name!r} not found")

    # If description is None, preserve the existing one.
    description = payload.description
    if description is None:
        existing = get_markdown_skill_source(name, skills_dir)
        description = existing["description"] if existing else ""

    filepath.write_text(
        assemble_markdown_skill(name, description, payload.content),
        encoding="utf-8",
    )
    reload_markdown_skills(skills_dir)
    return {"status": "ok", "name": name}


@router.delete("/skills/md/{name}")
async def delete_markdown_skill_endpoint(name: str) -> dict[str, Any]:
    """Delete a .md skill file and reload. Python skills return 400."""
    _validate_skill_name(name)
    skills_dir = _skills_dir()
    filepath = skills_dir / f"{name}.md"
    if not filepath.exists():
        # If it's a registered Python skill, give a clearer error.
        if get_skill(name) is not None:
            raise HTTPException(status_code=400, detail=f"Cannot delete built-in Python skill {name!r}")
        raise HTTPException(status_code=404, detail=f"Markdown skill {name!r} not found")
    delete_markdown_skill(name, skills_dir)
    return {"status": "ok", "deleted": name}


@router.post("/skills/{skill_name}")
async def invoke_skill(
    skill_name: str,
    payload: SkillInvokeRequest = Body(default_factory=SkillInvokeRequest),
) -> SkillInvokeResponse:
    skill = get_skill(skill_name)
    if skill is None:
        return SkillInvokeResponse(
            status="error", skill=skill_name, message=f"Unknown skill: {skill_name!r}"
        )

    try:
        result = await skill.run(payload.input, payload.args)
    except Exception as exc:  # noqa: BLE001 - surface any failure to the client
        return SkillInvokeResponse(
            status="error", skill=skill_name, message=f"Skill execution failed: {exc}"
        )

    return SkillInvokeResponse(
        status="ok",
        skill=skill_name,
        output=result.get("output", ""),
        metadata=result.get("metadata"),
    )
