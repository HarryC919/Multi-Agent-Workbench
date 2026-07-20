"""POST /api/agent-chat — multi-step reasoning (AgentService phase 1).

Mirrors the shape of ``routers/chat.py`` so the frontend, in a later phase,
can swap endpoints without touching the rest of the request lifecycle.
"""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter_by_model_id
from app.database import AsyncSessionLocal
from app.schemas import AgentChatRequest
from app.services.agent_service import AgentService
from app.services.conversation_service import ConversationService

router = APIRouter()


async def generate_agent_stream(request: AgentChatRequest):
    async with AsyncSessionLocal() as db:
        conv_service = ConversationService(db)
        agent_service = AgentService(db)

        conversation_id = request.conversation_id
        if conversation_id:
            conversation = await conv_service.get_conversation(conversation_id)
            if not conversation:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Conversation not found'})}\n\n"
                return
        else:
            conversation = await conv_service.create_conversation()
            conversation_id = conversation.id

        # Persist the user's message — same as /api/chat.
        await conv_service.add_message(
            conversation_id=conversation_id,
            role="user",
            content=request.messages[-1].content if request.messages else "",
            model=request.model,
            status="done",
        )

        try:
            adapter = await get_adapter_by_model_id(request.model, db)
        except ValueError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            return

        async for line in agent_service.stream_agent_chat(request, adapter, conversation):
            yield line


@router.post("/agent-chat")
async def agent_chat_endpoint(request: AgentChatRequest):
    # Reuse the same guards as /api/chat so behavior feels symmetric.
    if not request.stream:
        raise HTTPException(status_code=400, detail="Only streaming is supported")
    return StreamingResponse(
        generate_agent_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )