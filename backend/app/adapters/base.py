from abc import ABC, abstractmethod
from typing import AsyncIterator


class StreamChunk:
    def __init__(self, content: str = "", finish_reason: str | None = None):
        self.content = content
        self.finish_reason = finish_reason


class BaseAdapter(ABC):
    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        effort: float,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        pass
