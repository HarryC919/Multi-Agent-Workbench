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

    def _map_effort_to_params(self, effort: float, model: str) -> dict:
        """Map effort (0-1) to temperature/top_p. Reasoning models drop both."""
        if "o1" in model or "o3" in model or "reasoner" in model.lower():
            return {}

        temperature = round(0.2 + effort * 0.8, 2)
        top_p = round(0.7 + effort * 0.3, 2)
        return {"temperature": temperature, "top_p": top_p}

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        effort: float,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        params = {
            "model": model,
            "messages": messages,
            "stream": True,
            **self._map_effort_to_params(effort, model),
        }

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
                finish_reason = choice.get("finish_reason")

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
