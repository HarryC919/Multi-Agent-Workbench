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
from app.services.knowledge_service import KnowledgeService
from app.skills import iter_skills
from app.skills.retrieve_notes import get_retrieve_notes_skill

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

        # Phase 2a: expose all registered skills as LangChain tools. The
        # request may whitelist a subset via enable_skills (handled by the
        # service). Skills filtered out are simply not provided here.
        skills = list(iter_skills())

        # Phase 2b-i: when a knowledge base is selected, build a per-request
        # retrieve_notes skill bound to that KB and append it. It is always-on
        # (the user explicitly armed RAG by selecting a KB), so if the request
        # carries an enable_skills whitelist, also append "retrieve_notes" to
        # keep it from being filtered out by AgentService._select_tools.
        if request.rag_knowledge_base_id:
            kb_svc = KnowledgeService(db)
            skills.append(
                get_retrieve_notes_skill(request.rag_knowledge_base_id, kb_svc)
            )
            if isinstance(request.enable_skills, list) and "retrieve_notes" not in request.enable_skills:
                request.enable_skills.append("retrieve_notes")

        async for line in agent_service.stream_agent_chat(request, adapter, conversation, skills=skills):
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