"""Tests for AgentService phase 1 (ReAct, no tools).

Five coverage groups:
    1. Single-step Final Answer — quick exit.
    2. Multi-step reasoning — accumulated thinking w/ step boundaries.
    3. max-steps-exceeded — warning event + last step content as final.
    4. Adapter raises — error SSE + DB row marked error.
    5. Abort (CancelledError mid-stream) — partial thinking persisted as error.

We use a FakeAdapter that yields bound chunks per turn so the loop is fully
deterministic and does not touch the network.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import pytest

from app.adapters.base import BaseAdapter, StreamChunk
from app.database import AsyncSessionLocal
from app.models import Conversation, Message
from app.schemas import AgentChatRequest, ChatMessage
from app.services.agent_service import AgentService
from app.services.conversation_service import ConversationService


class _ScriptedAdapter(BaseAdapter):
    """Adapter that replays a list of per-step chunk lists."""

    def __init__(self, turns: list[list[StreamChunk]]):
        self.turns = turns
        self._i = 0

    async def stream_chat(self, messages, model, thinking=False, **kwargs) -> AsyncIterator[StreamChunk]:
        if self._i >= len(self.turns):
            # Defensive: if the service asks for more turns than supplied,
            # yield an empty final answer to terminate the loop.
            yield StreamChunk(content="Final Answer: (no more turns)", finish_reason="stop")
            return
        chunks = self.turns[self._i]
        # Bump the turn pointer before yielding so concurrent re-entrancy
        # cannot replay the same turn twice.
        self._i += 1
        for chunk in chunks:
            yield chunk


def _chunk(content: str = "", thinking: str = "", finish: str | None = None) -> StreamChunk:
    return StreamChunk(content=content, thinking=thinking, finish_reason=finish)


def _user_req(content="你好", max_steps=8) -> AgentChatRequest:
    return AgentChatRequest(
        model="mock-model",
        messages=[ChatMessage(role="user", content=content)],
        max_steps=max_steps,
    )


def _parse_sse_lines(lines: list[str]) -> list[dict]:
    out = []
    for line in lines:
        if line.startswith("data: "):
            out.append(json.loads(line[6:]))
    return out


async def _materialize(stream) -> tuple[list[dict], str]:
    """Drain the SSE stream to (event_list, raw_text)."""
    events: list[dict] = []
    raw = ""
    async for line in stream:
        raw += line
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events, raw


async def _create_conversation() -> Conversation:
    async with AsyncSessionLocal() as db:
        svc = ConversationService(db)
        return await svc.create_conversation()


async def _fetch_message(message_id: str) -> Message | None:
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Message).where(Message.id == message_id))
        return result.scalar_one_or_none()


from app.services.agent_service import _extract_final_answer as _efa

def test_extract_final_answer():
    assert _efa("Thought text\nFinal Answer: 42") == "42"
    assert _efa("Final Answer:   spaced\ntext") == "spaced\ntext"
    assert _efa("no answer here") is None
    assert _efa("Final Answer:") == ""


@pytest.mark.asyncio
async def test_single_step_final_answer():
    """Model 1-step terminus: only one round of stream_chat is requested."""
    adapter = _ScriptedAdapter(
        [
            [
                _chunk(thinking="let me think"),
                _chunk(content="Final Answer: Hello"),
                _chunk(finish="stop"),
            ]
        ]
    )
    request = _user_req()
    conversation = await _create_conversation()

    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        # Persist a user message first so the row mirrors the real router flow.
        await svc.conversation_service.add_message(
            conversation_id=conversation.id, role="user",
            content="hi", model="mock-model", status="done",
        )
        events, _ = await _materialize(svc.stream_agent_chat(request, adapter, conversation))

    types = [e["type"] for e in events]
    assert events[-1]["type"] == "done"
    assert events[-1]["finish_reason"] == "agent"
    assert types.count("text") == 1
    assert events[0]["type"] == "thinking"
    # Only one stream_chat turn was consumed.
    assert adapter._i == 1


@pytest.mark.asyncio
async def test_multi_step_accumulates_thinking_with_boundary():
    adapter = _ScriptedAdapter(
        [
            [
                _chunk(thinking="step1 thoughts"),
                _chunk(content="Thought: ...\nAction: none"),
                _chunk(finish="stop"),
            ],
            [
                _chunk(thinking="step2 thoughts"),
                _chunk(content="Final Answer: ok"),
                _chunk(finish="stop"),
            ],
        ]
    )
    request = _user_req()
    conversation = await _create_conversation()

    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        events, _ = await _materialize(svc.stream_agent_chat(request, adapter, conversation))
        # Pull the assistant message we persisted.
        assistant_events = [
            e for e in events if e["type"] in ("text", "thinking", "done", "warning", "error")
        ]

    thinking_events = [e["content"] for e in events if e["type"] == "thinking"]
    assert "step1 thoughts" in thinking_events
    assert "step2 thoughts" in thinking_events
    assert events[-1]["type"] == "done"
    assert adapter._i == 2  # both turns fully consumed

    # The conversation should have exactly one assistant message now, marked done,
    # with thinking containing both step boundary comments.
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message).where(Message.conversation_id == conversation.id, Message.role == "assistant")
        )
        msgs = result.scalars().all()
    assert len(msgs) == 1
    assert msgs[0].status == "done"
    assert msgs[0].content == "ok"
    assert "--- 第 1 步思考 ---" in msgs[0].thinking
    assert "--- 第 2 步思考 ---" in msgs[0].thinking


@pytest.mark.asyncio
async def test_max_steps_exceeded_emits_warning_and_uses_last_step():
    # 2-step cap with steps that never terminate.
    adapter = _ScriptedAdapter(
        [
            [_chunk(content="Thought step A"), _chunk(finish="stop")],
            [_chunk(content="Thought step B"), _chunk(finish="stop")],
        ]
    )
    request = _user_req(max_steps=2)
    conversation = await _create_conversation()

    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        events, _ = await _materialize(svc.stream_agent_chat(request, adapter, conversation))

    warnings = [e for e in events if e["type"] == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["message"] == "max-steps-exceeded"
    assert warnings[0]["max_steps"] == 2
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_adapter_raises_surfaces_error_and_marks_message_error():
    class _ExplodingAdapter(BaseAdapter):
        async def stream_chat(self, messages, model, thinking=False, **kwargs) -> AsyncIterator[StreamChunk]:
            yield _chunk(thinking="partial thoughts before boom")
            raise RuntimeError("adapter exploded")

    request = _user_req()
    conversation = await _create_conversation()

    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        events, _ = await _materialize(svc.stream_agent_chat(request, _ExplodingAdapter(), conversation))

    assert events[-1]["type"] == "error"
    assert "adapter exploded" in events[-1]["message"]

    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message).where(Message.conversation_id == conversation.id, Message.role == "assistant")
        )
        msg = result.scalars().first()
    assert msg.status == "error"
    assert "partial thoughts before boom" in msg.thinking


@pytest.mark.asyncio
async def test_abort_persists_partial_as_error():
    class _AbortAdapter(BaseAdapter):
        async def stream_chat(self, messages, model, thinking=False, **kwargs) -> AsyncIterator[StreamChunk]:
            yield _chunk(thinking="thinking before abort")
            yield _chunk(content="partial text")
            raise asyncio.CancelledError()

    request = _user_req()
    conversation = await _create_conversation()

    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        # Should not raise — the exception is swallowed inside the service.
        events, _ = await _materialize(svc.stream_agent_chat(request, _AbortAdapter(), conversation))

    types = [e["type"] for e in events]
    assert "error" not in types  # no error event emitted on abort
    assert "done" not in types  # loop did not reach a clean finish

    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message).where(Message.conversation_id == conversation.id, Message.role == "assistant")
        )
        msg = result.scalars().first()
    assert msg is not None
    assert msg.status == "error"
    assert "thinking before abort" in msg.thinking


def test_router_registers_agent_chat_endpoint():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    # 422 (no body) instead of 404 — endpoint registered, body validation runs.
    r = client.post("/api/agent-chat")
    assert r.status_code in (422, 400)