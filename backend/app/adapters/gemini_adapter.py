import json
from typing import AsyncIterator

import httpx

from app.adapters.base import BaseAdapter, StreamChunk


class GeminiAdapter(BaseAdapter):
    """Google Gemini REST streaming adapter."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=120.0)

    @staticmethod
    def _convert_messages(messages: list[dict[str, str]]) -> list[dict]:
        contents = []
        for msg in messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        return contents

    @staticmethod
    def _map_effort(effort: float) -> tuple[float, float]:
        temperature = round(0.2 + effort * 0.8, 2)
        top_p = round(0.7 + effort * 0.3, 2)
        return temperature, top_p

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        effort: float,
        thinking: bool = False,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        # Gemini thinking (includeThoughts) is not wired up in this iteration;
        # the toggle is silently ignored for Gemini models.
        contents = self._convert_messages(messages)
        temperature, top_p = self._map_effort(effort)

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
            f":streamGenerateContent?alt=sse&key={self.api_key}"
        )
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "topP": top_p,
            },
        }

        async with self.client.stream(
            "POST",
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as response:
            await self._raise_for_status(response)

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                try:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    if text:
                        yield StreamChunk(content=text)
                except (KeyError, IndexError, TypeError):
                    continue

                # Gemini doesn't always send a finish reason in the same SSE event,
                # so we rely on stream end for completion.

    async def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            body = await response.aread()
            raise httpx.HTTPStatusError(
                f"Gemini API error {response.status_code}: {body.decode('utf-8', errors='ignore')}",
                request=response.request,
                response=response,
            )
