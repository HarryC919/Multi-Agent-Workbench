from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db

router = APIRouter()


@router.get("/models")
async def list_active_models(db: AsyncSession = Depends(get_db)):
    return {"models": []}


@router.get("/models/all")
async def list_all_models(db: AsyncSession = Depends(get_db)):
    return {"models": []}


@router.post("/models")
async def create_model(db: AsyncSession = Depends(get_db)):
    return {"id": "placeholder"}


@router.put("/models/{model_id}")
async def update_model(model_id: str, db: AsyncSession = Depends(get_db)):
    return {"id": model_id}


@router.delete("/models/{model_id}")
async def delete_model(model_id: str, db: AsyncSession = Depends(get_db)):
    return {"deleted": True}
