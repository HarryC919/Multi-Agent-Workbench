from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body
from pydantic import BaseModel

from app.config import settings
from app.skills import get_skill, list_skills, reload_markdown_skills

router = APIRouter()

# Resolve skills_md_dir relative to the backend root (same pattern as config.py).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class SkillInvokeRequest(BaseModel):
    """Body for ``POST /api/skills/{name}``.

    All fields are optional and the whole body may be omitted - the simplest
    curl call is ``curl -X POST /api/skills/echo``.
    """

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


@router.get("/skills")
async def get_skills() -> dict[str, list[SkillManifestItem]]:
    return {"skills": [SkillManifestItem(**item) for item in list_skills()]}


# IMPORTANT: static routes must be declared BEFORE the parameterized
# ``/skills/{skill_name}`` route, otherwise ``POST /api/skills/reload`` is
# captured as ``skill_name == "reload"`` and dispatched to ``invoke_skill``.
@router.post("/skills/reload")
async def reload_skills() -> dict[str, Any]:
    """Hot-reload markdown-defined skills from the skills_md/ directory.

    Only affects skills loaded from .md files; Python-defined skills
    (echo, current_time, web_search) are untouched.
    """
    skills_dir = _BACKEND_ROOT / settings.skills_md_dir
    try:
        count = reload_markdown_skills(skills_dir)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc)}
    return {"status": "ok", "reloaded": count}


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
