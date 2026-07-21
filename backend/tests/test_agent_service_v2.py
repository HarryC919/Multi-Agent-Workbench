"""Tests for AgentService phase 2a (ReAct with real tool calls via Skills).

Six coverage groups:
    1. Single-step Final Answer — quick exit, no tool events.
    2. Multi-step with tool: step 1 emits Action: echo / Action Input: hi,
       the echo skill runs and produces an observation event; step 2 emits
       Final Answer.
    3. Unknown skill — `Action: fake_tool` yields a no-such-tool observation,
       loop continues and converges by Final Answer in step 2.
    4. max-steps-exceeded — warning event + final fallback.
    5. Adapter raises mid-stream — error event + persisted status=error +
       metadata.error.
    6. Abort (CancelledError) — metadata.aborted=true, status=error, no SSE
       done event.

This file stands alone from test_agent_service.py (phase-1 tests) so the
phase-1 path stays as a regression guard. The new FakeChatModel-backed
ChatModel path is the hot path for phase 2a.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

import pytest
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import ConfigDict

from app.database import AsyncSessionLocal
from app.models import Conversation, Message
from app.schemas import AgentChatRequest, ChatMessage
from app.services.agent_service import (
    AgentService,
    _wrap_skill_as_tool,
    _parse_action,
    _extract_final_answer,
)
from app.services.conversation_service import ConversationService
from app.skills.base import SkillResult
from app.skills.echo import EchoSkill


class _ScriptedChatModel(BaseChatModel):
    """Replays a list of per-step message replies.

    Each entry corresponds to one call to ``_astream`` (one ReAct step).
    The chunk list is yielded as separate ChatGenerationChunks so the
    agent loop observes streaming-like behavior.
    """

    turns: list[list[AIMessageChunk]]

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _identifying_params(self) -> dict[str, Any]:  # noqa: D401 — LC API
        return {"variant": "scripted"}

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        raise RuntimeError("ScriptedChatModel is async-only")

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop=None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatGenerationChunk]:
        if not self.turns:
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="Final Answer: (no turns left)")
            )
            return
        chunks = self.turns[0]
        self.turns = self.turns[1:]
        # Drain one turn's chunks; emit one final chunk signaling completion
        # for this stream-chat invocation so downstream sees finish_reason.
        for c in chunks:
            yield ChatGenerationChunk(message=c)
        # Sentinel: empty content with finish_reason so agent loop sees the
        # adapter "closed" this stream round.
        yield ChatGenerationChunk(
            message=AIMessageChunk(content="", response_metadata={"finish_reason": "stop"})
        )


def _aichunk(content: str = "", thinking: str = "") -> AIMessageChunk:
    if thinking:
        return AIMessageChunk(content=content, additional_kwargs={"thinking": thinking})
    return AIMessageChunk(content=content)


def _user_req(prompt="hi", max_steps=8, enable_skills=None) -> AgentChatRequest:
    return AgentChatRequest(
        model="mock-model",
        messages=[ChatMessage(role="user", content=prompt)],
        max_steps=max_steps,
        enable_skills=enable_skills,
    )


def _materialize(stream) -> tuple[list[dict], str]:
    events: list[dict] = []
    raw = ""
    import asyncio as _aio

    async def drain():
        nonlocal raw
        async for line in stream:
            raw += line
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    _aio.get_event_loop().run_until_complete(drain()) if False else None
    return events, raw


async def _drain(stream) -> tuple[list[dict], str]:
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


async def _get_assistant_msg(conv_id: str) -> Message:
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message).where(Message.conversation_id == conv_id, Message.role == "assistant")
        )
        return result.scalars().first()


def test_parse_action_and_final():
    assert _parse_action("Thought x\nAction: echo\nAction Input: hi\n") == ("echo", "hi")
    assert _parse_action("Action: none") == ("none", "")
    assert _parse_action("Thought only") == (None, "")
    assert _extract_final_answer("Thought\nFinal Answer: 42") == "42"
    assert _extract_final_answer("noanswer") is None


def test_wrap_skill_as_tool_invokes_skill():
    import asyncio
    tool = _wrap_skill_as_tool(EchoSkill())
    assert tool.name == "echo"
    out = asyncio.run(tool.ainvoke({"input": "hello"}))
    assert out == "hello"


@pytest.mark.asyncio
async def test_single_step_final_answer(monkeypatch):
    conv = await _create_conversation()
    chat_model = _ScriptedChatModel(turns=[
        [_aichunk(thinking="quick thought"), _aichunk(content="Final Answer: hi there")],
    ])
    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        # Inject scripted model by monkeypatching the factory method.
        monkeypatch.setattr(svc, "_build_chat_model", lambda adapter, request: chat_model)
        events, _ = await _drain(svc.stream_agent_chat(_user_req(), _FakeAdapter(), conv, skills=[]))

    types = [e["type"] for e in events]
    assert types[-1] == "done"
    assert not any(e["type"] == "action" for e in events)
    assert not any(e["type"] == "observation" for e in events)
    msg = await _get_assistant_msg(conv.id)
    assert msg.status == "done"
    assert msg.content == "hi there"
    assert msg.metadata_["step_count"] == 1
    assert msg.metadata_["aborted"] is False
    assert msg.metadata_["tool_calls"] == []


@pytest.mark.asyncio
async def test_two_step_with_tool_call(monkeypatch):
    conv = await _create_conversation()
    chat_model = _ScriptedChatModel(turns=[
        [_aichunk("Thought: i need to echo\nAction: echo\nAction Input: hello\n")],
        [_aichunk("Thought: got it\nFinal Answer: hello echoed")],
    ])
    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        monkeypatch.setattr(svc, "_build_chat_model", lambda adapter, request: chat_model)
        events, _ = await _drain(
            svc.stream_agent_chat(_user_req(), _FakeAdapter(), conv, skills=[EchoSkill()])
        )

    types = [e["type"] for e in events]
    assert "action" in types
    assert "observation" in types
    action = next(e for e in events if e["type"] == "action")
    assert action["name"] == "echo"
    assert action["input"] == "hello"
    obs = next(e for e in events if e["type"] == "observation")
    assert obs["name"] == "echo"
    assert "hello" in obs["content"]
    assert events[-1]["type"] == "done"
    msg = await _get_assistant_msg(conv.id)
    assert msg.status == "done"
    assert msg.content == "hello echoed"
    assert msg.metadata_["step_count"] == 2
    assert msg.metadata_["tool_calls"] == [
        {"name": "echo", "step": 1, "input": "hello", "output": "hello"}
    ]


@pytest.mark.asyncio
async def test_unknown_skill_yields_observation_and_continues(monkeypatch):
    conv = await _create_conversation()
    chat_model = _ScriptedChatModel(turns=[
        [_aichunk("Action: fake_tool\nAction Input: x\n")],
        [_aichunk("Final Answer: oh well")],
    ])
    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        monkeypatch.setattr(svc, "_build_chat_model", lambda adapter, request: chat_model)
        events, _ = await _drain(
            svc.stream_agent_chat(_user_req(), _FakeAdapter(), conv, skills=[EchoSkill()])
        )

    obs = [e for e in events if e["type"] == "observation"]
    assert len(obs) == 1
    assert "未知工具" in obs[0]["content"]
    assert obs[0]["name"] == "fake_tool"
    assert events[-1]["type"] == "done"
    msg = await _get_assistant_msg(conv.id)
    assert msg.content == "oh well"
    assert msg.metadata_["tool_calls"] == []


@pytest.mark.asyncio
async def test_max_steps_exceeded(monkeypatch):
    conv = await _create_conversation()
    chat_model = _ScriptedChatModel(turns=[
        [_aichunk("Thought: not done\nAction: none"), ],
        [_aichunk("Thought: still\nAction: none")],
    ])
    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        monkeypatch.setattr(svc, "_build_chat_model", lambda adapter, request: chat_model)
        events, _ = await _drain(
            svc.stream_agent_chat(_user_req(max_steps=2), _FakeAdapter(), conv, skills=[])
        )

    warnings = [e for e in events if e["type"] == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["message"] == "max-steps-exceeded"
    assert warnings[0]["max_steps"] == 2
    assert events[-1]["type"] == "done"
    msg = await _get_assistant_msg(conv.id)
    assert msg.metadata_["step_count"] == 2


@pytest.mark.asyncio
async def test_adapter_raises_surfaces_error(monkeypatch):
    class _ExplodingChatModel(_ScriptedChatModel):
        async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
            yield ChatGenerationChunk(message=_aichunk(thinking="partial"))
            raise RuntimeError("adapter exploded")

    conv = await _create_conversation()
    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        monkeypatch.setattr(
            svc, "_build_chat_model",
            lambda adapter, request: _ExplodingChatModel(turns=[[]]),
        )
        events, _ = await _drain(
            svc.stream_agent_chat(_user_req(), _FakeAdapter(), conv, skills=[])
        )

    assert events[-1]["type"] == "error"
    assert "adapter exploded" in events[-1]["message"]
    msg = await _get_assistant_msg(conv.id)
    assert msg.status == "error"
    assert "error" in msg.metadata_
    assert msg.metadata_["step_count"] == 1


@pytest.mark.asyncio
async def test_abort_persists_metadata_aborted(monkeypatch):
    class _AbortChatModel(_ScriptedChatModel):
        async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
            yield ChatGenerationChunk(message=_aichunk(thinking="thinking"))
            yield ChatGenerationChunk(message=_aichunk(content="partial text"))
            raise asyncio.CancelledError()

    conv = await _create_conversation()
    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        monkeypatch.setattr(
            svc, "_build_chat_model",
            lambda adapter, request: _AbortChatModel(turns=[[]]),
        )
        events, _ = await _drain(
            svc.stream_agent_chat(_user_req(), _FakeAdapter(), conv, skills=[])
        )

    # No done/error event — loop swallowed the cancel cleanly.
    types = [e["type"] for e in events]
    assert "done" not in types
    assert "error" not in types
    msg = await _get_assistant_msg(conv.id)
    assert msg.status == "error"
    assert msg.metadata_["aborted"] is True
    assert "thinking" in msg.thinking


# ---------------------------------------------------------------- dummy adapter


class _FakeAdapter:
    """No-op adapter stand-in — the real chat model is the scripted one."""

    async def stream_chat(self, *args, **kwargs):
        # Should never actually be called because the scripted ChatModel
        # replaces `_astream` entirely; yield nothing as a safety net.
        if False:
            yield


def test_router_still_registered():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    r = client.post("/api/agent-chat")
    assert r.status_code in (400, 422)


# ---------------------------------------------------------------- retrieve_notes integration


class _FakeRetrieveService:
    """Stands in for KnowledgeService — returns canned RetrievedChunks."""

    def __init__(self, chunks):
        self._chunks = chunks

    async def retrieve(self, kb_id, query, top_k, min_score):  # noqa: ARG002
        return self._chunks


@pytest.mark.asyncio
async def test_retrieve_notes_flows_through_agent_loop(monkeypatch):
    """The factory-built retrieve_notes skill runs like any other tool: the
    agent emits an ``action`` event, the skill runs, an ``observation`` event
    carries the retrieved chunks, and the transcript is persisted."""
    from app.schemas import RetrievedChunk
    from app.skills.retrieve_notes import get_retrieve_notes_skill

    chunks = [
        RetrievedChunk(doc_id="d1", filename="notes.md", heading="安装", score=0.9, text="用 uv 安装 fastapi。"),
    ]
    retrieve_svc = _FakeRetrieveService(chunks)

    conv = await _create_conversation()
    chat_model = _ScriptedChatModel(turns=[
        [_aichunk("Thought: 查笔记\nAction: retrieve_notes\nAction Input: 怎么安装?\n")],
        [_aichunk("Thought: ok\nFinal Answer: 用 uv 安装 fastapi。")],
    ])
    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        monkeypatch.setattr(svc, "_build_chat_model", lambda adapter, request: chat_model)
        skills = [get_retrieve_notes_skill("kb1", retrieve_svc)]
        events, _ = await _drain(
            svc.stream_agent_chat(_user_req("怎么安装?"), _FakeAdapter(), conv, skills=skills)
        )

    types = [e["type"] for e in events]
    assert "action" in types
    action = next(e for e in events if e["type"] == "action")
    assert action["name"] == "retrieve_notes"
    assert action["input"] == "怎么安装?"
    obs = next(e for e in events if e["type"] == "observation" and e["name"] == "retrieve_notes")
    # Observation carries the source-tagged chunk text (and the Observation:
    # prefix that AgentService adds), but NOT a duplicated "Observation:" from
    # the skill itself.
    assert "用 uv 安装 fastapi。" in obs["content"]
    assert "[来源: notes.md #安装" in obs["content"]
    assert events[-1]["type"] == "done"
    msg = await _get_assistant_msg(conv.id)
    assert msg.status == "done"
    tc = msg.metadata_["tool_calls"]
    assert len(tc) == 1
    assert tc[0]["name"] == "retrieve_notes"
    assert "用 uv 安装 fastapi。" in tc[0]["output"]


@pytest.mark.asyncio
async def test_retrieve_notes_empty_result_observation(monkeypatch):
    """When retrieve returns no chunks, the observation carries the empty
    message and the loop still converges."""
    from app.skills.retrieve_notes import get_retrieve_notes_skill

    retrieve_svc = _FakeRetrieveService([])
    conv = await _create_conversation()
    chat_model = _ScriptedChatModel(turns=[
        [_aichunk("Thought: 查笔记\nAction: retrieve_notes\nAction Input: 不相关\n")],
        [_aichunk("Thought: 没结果\nFinal Answer: 我不知道。")],
    ])
    async with AsyncSessionLocal() as db:
        svc = AgentService(db)
        monkeypatch.setattr(svc, "_build_chat_model", lambda adapter, request: chat_model)
        skills = [get_retrieve_notes_skill("kb1", retrieve_svc)]
        events, _ = await _drain(
            svc.stream_agent_chat(_user_req("不相关"), _FakeAdapter(), conv, skills=skills)
        )

    obs = next(e for e in events if e["type"] == "observation" and e["name"] == "retrieve_notes")
    assert "未检索到" in obs["content"]
    assert events[-1]["type"] == "done"