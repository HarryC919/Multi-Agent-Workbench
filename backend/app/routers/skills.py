from typing import Any

from fastapi import APIRouter, Body
from pydantic import BaseModel

from app.skills import get_skill, list_skills

router = APIRouter()


class SkillInvokeRequest(BaseModel):
    """Body for ``POST /api/skills/{name}``.

    All fields are optional and the whole body may be omitted — the simplest
    curl call is ``curl -X POST /api/skills/echo``.
    """

    input: str = ""
    args: dict[str, Any] | None = None


class SkillManifestItem(BaseModel):
    name: str
    description: str


class SkillInvokeResponse(BaseModel):
    status: str  # ok | error
    skill: str
    output: str | None = None
    metadata: dict[str, Any] | None = None
    message: str | None = None  # populated on error


@router.get("/skills")
async def get_skills() -> dict[str, list[SkillManifestItem]]:
    return {"skills": [SkillManifestItem(**item) for item in list_skills()]}


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
    except Exception as exc:  # noqa: BLE001 — surface any failure to the client
        return SkillInvokeResponse(
            status="error", skill=skill_name, message=f"Skill execution failed: {exc}"
        )

    return SkillInvokeResponse(
        status="ok",
        skill=skill_name,
        output=result.get("output", ""),
        metadata=result.get("metadata"),
    )