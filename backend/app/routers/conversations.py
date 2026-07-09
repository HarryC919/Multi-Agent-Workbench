from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db

router = APIRouter()


@router.get("/conversations")
async def list_conversations(q: str | None = None, db: AsyncSession = Depends(get_db)):
    return {"conversations": [], "q": q}


@router.post("/conversations")
async def create_conversation(db: AsyncSession = Depends(get_db)):
    return {"id": "placeholder", "title": "新会话"}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    return {"id": conversation_id, "title": "新会话", "messages": []}


@router.patch("/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    return {"id": conversation_id, "title": "重命名"}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    return {"deleted": True}
