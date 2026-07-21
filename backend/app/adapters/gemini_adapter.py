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

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        thinking: bool = False,
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        # Gemini thinking (includeThoughts) is not wired up in this iteration;
        # the toggle is silently ignored for Gemini models.
        contents = self._convert_messages(messages)

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
            f":streamGenerateContent?alt=sse&key={self.api_key}"
        )
        payload: dict = {
            "contents": contents,
        }
        # Inject sampling params only when explicitly provided, so each model's
        # trained defaults stay intact when the caller passes nothing.
        gen_cfg: dict = {}
        if temperature is not None:
            gen_cfg["temperature"] = temperature
        if top_p is not None:
            gen_cfg["topP"] = top_p
        if gen_cfg:
            payload["generationConfig"] = gen_cfg

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
