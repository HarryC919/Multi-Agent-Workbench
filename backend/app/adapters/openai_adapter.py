from typing import AsyncIterator

from app.adapters.base import BaseAdapter, StreamChunk


class OpenAIAdapter(BaseAdapter):
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        effort: float,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="")
