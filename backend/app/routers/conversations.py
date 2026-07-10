from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    ConversationUpdate,
)
from app.services.conversation_service import ConversationService

router = APIRouter()


@router.get("/conversations")
async def list_conversations(q: str | None = None, db: AsyncSession = Depends(get_db)):
    service = ConversationService(db)
    return {"conversations": await service.list_conversations(search_query=q)}


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(data: ConversationCreate | None = None, db: AsyncSession = Depends(get_db)):
    service = ConversationService(db)
    return await service.create_conversation(title=data.title if data else None)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    service = ConversationService(db)
    conversation = await service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await service.get_messages(conversation_id)
    return ConversationDetailOut(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=messages,
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: str,
    data: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    conversation = await service.rename_conversation(conversation_id, data.title)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    service = ConversationService(db)
    deleted = await service.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True}
