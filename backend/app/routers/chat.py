from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest

router = APIRouter()


async def generate_stream(request: ChatRequest):
    # Placeholder for Phase 2 implementation
    yield f"data: {{\"type\": \"text\", \"content\": \"Chat endpoint placeholder\"}}\n\n"
    yield f"data: {{\"type\": \"done\", \"finish_reason\": \"stop\"}}\n\n"


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.stream:
        raise HTTPException(status_code=400, detail="Only streaming is supported")
    return StreamingResponse(
        generate_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
