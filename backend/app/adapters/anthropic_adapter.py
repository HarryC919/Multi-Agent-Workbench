import json
from typing import AsyncIterator

import httpx

from app.adapters.base import BaseAdapter, StreamChunk


class AnthropicAdapter(BaseAdapter):
    """Anthropic Messages API adapter, also supports Anthropic-compatible endpoints."""

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=120.0)

    @staticmethod
    def _map_effort(effort: float) -> float:
        return round(0.2 + effort * 0.8, 2)

    @staticmethod
    def _convert_messages(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
        """Extract system message(s) and keep only user/assistant roles."""
        system_parts = []
        converted = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
            else:
                converted.append({"role": msg["role"], "content": msg["content"]})
        return "\n".join(system_parts).strip(), converted

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        effort: float,
        thinking: bool = False,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        system, msgs = self._convert_messages(messages)
        payload: dict = {
            "model": model,
            "messages": msgs,
            "max_tokens": 4096,
            "temperature": self._map_effort(effort),
            "stream": True,
        }
        if system:
            payload["system"] = system

        # Extended thinking: Anthropic requires temperature to be unset and
        # max_tokens to exceed the thinking budget. When enabled, override
        # both and add the thinking config.
        if thinking:
            payload.pop("temperature", None)
            payload["max_tokens"] = 8192
            payload["thinking"] = {"type": "enabled", "budget_tokens": 4096}

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        async with self.client.stream(
            "POST",
            f"{self.base_url}/messages",
            json=payload,
            headers=headers,
        ) as response:
            await self._raise_for_status(response)

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                event_type = data.get("type")
                if event_type == "content_block_delta":
                    delta = data.get("delta", {})
                    # Distinguish thinking deltas from text deltas.
                    if delta.get("type") == "thinking_delta":
                        thought = delta.get("thinking", "")
                        if thought:
                            yield StreamChunk(thinking=thought)
                    else:
                        text = delta.get("text", "")
                        if text:
                            yield StreamChunk(content=text)
                elif event_type == "message_stop":
                    yield StreamChunk(content="", finish_reason="stop")
                elif event_type == "error":
                    error = data.get("error", {})
                    raise RuntimeError(f"Anthropic stream error: {error}")

    async def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            body = await response.aread()
            raise httpx.HTTPStatusError(
                f"Anthropic API error {response.status_code}: {body.decode('utf-8', errors='ignore')}",
                request=response.request,
                response=response,
            )
