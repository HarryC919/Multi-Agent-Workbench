from abc import ABC, abstractmethod
from typing import AsyncIterator


class StreamChunk:
    def __init__(
        self,
        content: str = "",
        finish_reason: str | None = None,
        thinking: str = "",
    ):
        self.content = content
        self.finish_reason = finish_reason
        self.thinking = thinking


class BaseAdapter(ABC):
    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        thinking: bool = False,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        pass
