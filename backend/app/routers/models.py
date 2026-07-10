from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models import ModelConfig
from app.schemas import ModelConfigCreate, ModelConfigOut, ModelConfigUpdate

router = APIRouter()


@router.get("/models", response_model=list[ModelConfigOut])
async def list_active_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ModelConfig).where(ModelConfig.is_active == True).order_by(ModelConfig.created_at)
    )
    return result.scalars().all()


@router.get("/models/all", response_model=list[ModelConfigOut])
async def list_all_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelConfig).order_by(ModelConfig.created_at))
    return result.scalars().all()


@router.post("/models", response_model=ModelConfigOut)
async def create_model(data: ModelConfigCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(ModelConfig).where(ModelConfig.model_id == data.model_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Model {data.model_id} already exists")

    model = ModelConfig(**data.model_dump())
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.put("/models/{model_id}", response_model=ModelConfigOut)
async def update_model(
    model_id: str, data: ModelConfigUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ModelConfig).where(ModelConfig.model_id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(model, field, value)

    await db.commit()
    await db.refresh(model)
    return model


@router.delete("/models/{model_id}")
async def delete_model(model_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelConfig).where(ModelConfig.model_id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    await db.delete(model)
    await db.commit()
    return {"deleted": True}
