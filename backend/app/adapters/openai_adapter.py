import json
from typing import AsyncIterator

import httpx

from app.adapters.base import BaseAdapter, StreamChunk


class OpenAIAdapter(BaseAdapter):
    """OpenAI adapter that also handles OpenAI-compatible vendors."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=120.0)

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
        params: dict = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        # Reasoning-class models (o1/o3, deepseek-reasoner, etc.) reject
        # temperature/top_p; we forward the params only when explicitly set
        # by the caller (AgentService) — the default `None` leaves the model's
        # own defaults in place.
        if temperature is not None:
            params["temperature"] = temperature
        if top_p is not None:
            params["top_p"] = top_p

        async with self.client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json=params,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        ) as response:
            await self._raise_for_status(response)

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                if line.startswith("data: [DONE]"):
                    break

                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                choices = data.get("choices") or []
                if not choices:
                    continue

                choice = choices[0]
                delta = choice.get("delta", {})
                content = delta.get("content") or ""
                # OpenAI-compatible reasoning models (DeepSeek reasoner, GLM z1,
                # Kimi K1.5, etc.) expose chain-of-thought via reasoning_content.
                reasoning = delta.get("reasoning_content") or ""
                finish_reason = choice.get("finish_reason")

                if reasoning and thinking:
                    yield StreamChunk(thinking=reasoning)
                if content:
                    yield StreamChunk(content=content)
                if finish_reason:
                    yield StreamChunk(content="", finish_reason=finish_reason)

    async def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            body = await response.aread()
            raise httpx.HTTPStatusError(
                f"OpenAI API error {response.status_code}: {body.decode('utf-8', errors='ignore')}",
                request=response.request,
                response=response,
            )
