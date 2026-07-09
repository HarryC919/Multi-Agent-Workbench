from typing import AsyncIterator

from app.adapters.base import BaseAdapter, StreamChunk


class AnthropicAdapter(BaseAdapter):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        effort: float,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="")
