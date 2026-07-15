import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter_by_model_id
from app.database import AsyncSessionLocal
from app.dependencies import get_db
from app.schemas import ChatRequest
from app.services.conversation_service import ConversationService

router = APIRouter()


def _attach_files_to_messages(messages: list[dict], files: list) -> list[dict]:
    if not files:
        return messages

    file_texts = "\n\n".join([f"[文件: {f.name}]\n{f.content}" for f in files])
    messages = [dict(m) for m in messages]
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            messages[i]["content"] += f"\n\n{file_texts}"
            break
    return messages


async def generate_stream(request: ChatRequest):
    async with AsyncSessionLocal() as db:
        service = ConversationService(db)

        # Get or create conversation
        conversation_id = request.conversation_id
        if conversation_id:
            conversation = await service.get_conversation(conversation_id)
            if not conversation:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Conversation not found'})}\n\n"
                return
        else:
            conversation = await service.create_conversation()
            conversation_id = conversation.id

        # Save user message
        await service.add_message(
            conversation_id=conversation_id,
            role="user",
            content=request.messages[-1].content if request.messages else "",
            model=request.model,
            effort=request.effort,
            status="done",
        )

        # Create placeholder assistant message
        assistant_msg = await service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content="",
            model=request.model,
            effort=request.effort,
            status="streaming",
        )

        # Prepare messages with attached files
        messages = [m.model_dump() for m in request.messages]
        messages = _attach_files_to_messages(messages, request.files)

        try:
            adapter = await get_adapter_by_model_id(request.model, db)
        except ValueError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            await service.update_message_content(assistant_msg.id, str(exc), status="error")
            return

        full_content = ""
        full_thinking = ""
        try:
            async for chunk in adapter.stream_chat(
                messages, request.model, request.effort, thinking=request.thinking
            ):
                if chunk.thinking:
                    full_thinking += chunk.thinking
                    yield f"data: {json.dumps({'type': 'thinking', 'content': chunk.thinking})}\n\n"
                if chunk.content:
                    full_content += chunk.content
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk.content})}\n\n"
                if chunk.finish_reason:
                    yield f"data: {json.dumps({'type': 'done', 'finish_reason': chunk.finish_reason})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            await service.update_message_content(
                assistant_msg.id, str(exc), status="error"
            )
            return

        # Save final assistant message (content + persisted thinking)
        await service.update_message_content(
            assistant_msg.id, full_content, status="done", thinking=full_thinking
        )


@router.post("/chat")
async def chat_endpoint(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not request.stream:
        raise HTTPException(status_code=400, detail="Only streaming is supported")
    return StreamingResponse(
        generate_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
