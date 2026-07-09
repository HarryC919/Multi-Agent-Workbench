from fastapi import APIRouter

router = APIRouter()


@router.post("/skills/{skill_name}")
async def invoke_skill(skill_name: str):
    return {"status": "not_implemented", "skill": skill_name}
