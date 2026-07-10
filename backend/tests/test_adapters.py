import json

import httpx
import pytest
import respx

from app.adapters.anthropic_adapter import AnthropicAdapter
from app.adapters.gemini_adapter import GeminiAdapter
from app.adapters.openai_adapter import OpenAIAdapter


async def collect_chunks(adapter):
    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[{"role": "user", "content": "Hi"}],
        model="gpt-test",
        effort=0.5,
    ):
        chunks.append(chunk)
    return chunks


@respx.mock
async def test_openai_adapter_stream():
    route = respx.post("https://api.openai.com/v1/chat/completions")

    async def stream_response(request: httpx.Request):
        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ]
        body = "\n".join(lines) + "\n"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    route.side_effect = stream_response

    # Construct the adapter directly: this test exercises stream parsing, not
    # credential resolution (which get_adapter now validates against .env).
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.openai.com/v1")
    chunks = await collect_chunks(adapter)

    contents = [c.content for c in chunks if c.content]
    finish = [c.finish_reason for c in chunks if c.finish_reason]

    assert contents == ["Hello", " world"]
    assert finish == ["stop"]


@respx.mock
async def test_anthropic_adapter_stream():
    route = respx.post("https://api.anthropic.com/v1/messages")

    async def stream_response(request: httpx.Request):
        lines = [
            "data: " + json.dumps({"type": "content_block_delta", "delta": {"text": "Hi"}}),
            "data: " + json.dumps({"type": "content_block_delta", "delta": {"text": " there"}}),
            "data: " + json.dumps({"type": "message_stop"}),
        ]
        body = "\n".join(lines) + "\n"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    route.side_effect = stream_response

    adapter = AnthropicAdapter(api_key="test-key")
    chunks = await collect_chunks(adapter)

    contents = [c.content for c in chunks if c.content]
    finish = [c.finish_reason for c in chunks if c.finish_reason]

    assert contents == ["Hi", " there"]
    assert finish == ["stop"]


@respx.mock
async def test_gemini_adapter_stream():
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:streamGenerateContent"
    )

    async def stream_response(request: httpx.Request):
        lines = [
            "data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}),
            "data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": "!"}]}}]}),
        ]
        body = "\n".join(lines) + "\n"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    route.side_effect = stream_response

    adapter = GeminiAdapter(api_key="test-key")
    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[{"role": "user", "content": "Hi"}],
        model="gemini-test",
        effort=0.5,
    ):
        chunks.append(chunk)

    contents = [c.content for c in chunks if c.content]
    assert contents == ["OK", "!"]


@respx.mock
async def test_openai_adapter_reasoner_no_temperature():
    route = respx.post("https://api.deepseek.com/v1/chat/completions")
    captured: dict = {}

    async def capture_request(request: httpx.Request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            text="data: "
            + json.dumps({"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]})
            + "\ndata: [DONE]\n",
            headers={"Content-Type": "text/event-stream"},
        )

    route.side_effect = capture_request

    adapter = OpenAIAdapter(
        api_key="test-key", base_url="https://api.deepseek.com/v1"
    )
    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[{"role": "user", "content": "Hi"}],
        model="deepseek-reasoner",
        effort=0.5,
    ):
        chunks.append(chunk)

    assert "temperature" not in captured["body"]
    assert "top_p" not in captured["body"]
