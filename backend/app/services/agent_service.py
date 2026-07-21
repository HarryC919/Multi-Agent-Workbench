"""AgentService — phase 2a: ReAct loop with real tool calling.

Mixes LangChain (for message types + chat-model abstraction) into the
phase 1 ReAct loop, but keeps the parsing discipline on plain text since
our AdapterChatModel (see langchain_adapter.py) intentionally does not
bind vendor-native tool-calling APIs. The ReAct prompt is the contract.

Architecture frontiers strictly enforced:
    * LangChain imports live ONLY inside this module (and langchain_adapter).
        skills/base.py, adapters/*.py stay framework-agnostic.
    * Each registered Skill is wrapped as a `StructuredTool` so it satisfies
        LangChain's tool interface; the wrapper is purely a façade — calling
        the tool simply awaits `skill.run`.
    * `Message.metadata_` JSON column holds `{step_count, aborted, tool_calls}`.
        Plain chat stays untouched (empty dict).
    * Temperature knobs forwarded to the adapter; first call uses
        `agent_step_*` from config, no separate "final" call is made — once
        a step yields `Final Answer:`, that content is already final.

SSE contract:
    `text | thinking | action | observation | warning | done | error`
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import BaseAdapter
from app.config import settings
from app.models import Conversation
from app.schemas import AgentChatRequest
from app.services._chat_helpers import attach_files_to_messages
from app.services.conversation_service import ConversationService
from app.skills.base import Skill, SkillResult

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "react_system.txt"
try:
    _REACT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")
except FileNotFoundError:  # pragma: no cover — repo integrity issue
    logger.warning("Missing %s; falling back to inline ReAct prompt.", _PROMPT_PATH)
    _REACT_TEMPLATE = (
        "You are a ReAct agent. Think step by step, output `Final Answer:` "
        "followed by the answer when done."
    )

_FINAL_ANSWER_PREFIX = "Final Answer:"
_NO_TOOL_OBSERVATION = "Observation: 无可用工具，请基于已知信息继续推理。"


# ----------------------------------------------------------------- tool wrapper


class _ToolInput(BaseModel):
    """Single-string argument schema enforced by LangChain tools."""

    input: str = Field(..., description="The argument string to pass to the skill")


def _wrap_skill_as_tool(skill: Skill) -> StructuredTool:
    """Adapt a Skill to LangChain's `BaseTool` interface.

    The wrapper is a thin closure — the action simply awaits
    `skill.run(input=..., args={})` and surfaces the result. Errors are
    returned as `{"error": ...}` inside `output` rather than raised, so the
    ReAct loop can carry on with a recoverable observation.
    """

    async def _arun(input: str, **_: Any) -> str:
        try:
            result: SkillResult = await skill.run(input=input, args=None)
            return result.get("output", "")
        except Exception as exc:  # noqa: BLE001 — surface, don't crash loop
            return f"[tool error: {exc}]"

    def _run(input: str, **_: Any) -> str:
        # Sync path is never used in our async AgentService; provide a path
        # that adapters can resolve through a private loop if a test invokes
        # the tool synchronously (LangChain falls back here if `coroutine=`
        # is unset).
        try:
            return asyncio.run(_arun(input))
        except RuntimeError:
            return ""

    return StructuredTool.from_function(
        name=skill.name,
        description=skill.description,
        args_schema=_ToolInput,
        coroutine=_arun,
        func=_run,
    )


# ------------------------------------------------------------ ReAct parsing


_ACTION_RE = re.compile(r"Action\s*:\s*(.+?)(?:\n|$)", re.IGNORECASE)
_ACTION_INPUT_RE = re.compile(r"Action\s*Input\s*:\s*(.+?)(?:\n|$)", re.IGNORECASE)


def _parse_action(step_content: str) -> tuple[str | None, str]:
    """Best-effort `(name, input)` extraction from a ReAct step.

    Returns `(None, "")` when no `Action:` line appears. `name == "none"`
    is treated as "no tools this step" by the caller.
    """
    m_action = _ACTION_RE.search(step_content)
    if not m_action:
        return None, ""
    name = m_action.group(1).strip()
    m_input = _ACTION_INPUT_RE.search(step_content)
    action_input = m_input.group(1).strip() if m_input else ""
    return name, action_input


def _extract_final_answer(step_content: str) -> str | None:
    idx = step_content.find(_FINAL_ANSWER_PREFIX)
    if idx < 0:
        return None
    tail = step_content[idx + len(_FINAL_ANSWER_PREFIX) :]
    return tail.lstrip("\n").strip()


# --------------------------------------------------------------------- service


class AgentService:
    """Multi-step reasoning orchestrator. Lives next to ConversationService."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.conversation_service = ConversationService(db)

    async def stream_agent_chat(
        self,
        request: AgentChatRequest,
        adapter: BaseAdapter,
        conversation: Conversation,
        skills: list[Skill] | None = None,
    ) -> AsyncIterator[str]:
        """Run the ReAct loop and yield SSE lines.

        Caller (the agent router) is responsible for persisting the user
        turn; this method persists exactly one assistant Message whose
        `metadata_` column records `{step_count, aborted, tool_calls}`.
        """
        max_steps = max(1, int(request.max_steps or settings.agent_max_steps))

        # Tools available for this turn; filtered by request.enable_skills
        # (None ⇒ all registered; explicit list acts as a whitelist).
        tools = self._select_tools(skills, request.enable_skills)
        system_prompt = self._build_system_prompt(tools)

        messages: list[BaseMessage] = self._build_initial_messages(request, system_prompt)
        full_thinking = ""
        final_content = ""
        step_count = 0
        aborted = False
        tool_calls: list[dict[str, Any]] = []

        # Wrap adapter as a LangChain chat model and bind the step temperature.
        chat_model = self._build_chat_model(adapter, request)

        # Placeholder assistant message so the user sees a streaming row
        # immediately; we update its fields on finish/error.
        assistant_msg = await self.conversation_service.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content="",
            model=request.model,
            status="streaming",
        )

        async def persist_done(content: str, thinking: str, metadata: dict[str, Any]) -> None:
            await self.conversation_service.update_message_content(
                assistant_msg.id,
                content,
                status="done",
                thinking=thinking,
            )
            await self._persist_metadata(assistant_msg.id, metadata)

        async def persist_error(content_or_partial: str, thinking: str, metadata: dict[str, Any]) -> None:
            try:
                await self.conversation_service.update_message_content(
                    assistant_msg.id,
                    content_or_partial,
                    status="error",
                    thinking=thinking,
                )
                await self._persist_metadata(assistant_msg.id, metadata)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to persist agent error state for message %s", assistant_msg.id)

        try:
            while step_count < max_steps:
                step_count += 1
                step_number = step_count
                step_label = f"\n\n--- 第 {step_number} 步思考 ---\n"
                step_thinking = ""
                step_content = ""

                try:
                    async for chunk in chat_model._astream(messages, run_manager=None):
                        msg: AIMessageChunk = chunk.message
                        # Reasoning content lives in `additional_kwargs["thinking"]`
                        # (see langchain_adapter.AIMessage handling).
                        thinking_chunk = msg.additional_kwargs.get("thinking") if isinstance(msg.additional_kwargs, dict) else None
                        if thinking_chunk:
                            step_thinking += thinking_chunk
                            yield _sse({"type": "thinking", "content": thinking_chunk, "step": step_number})
                        if msg.content:
                            step_content += msg.content
                            yield _sse({"type": "text", "content": msg.content, "step": step_number})
                        # finish_reason lives in msg.response_metadata; we
                        # emit no event here because the loop terminator is
                        # the textual `Final Answer:` marker, not the SSE
                        # finish reason. The adapter's chunks already feed us
                        # both content and finish info and LangChain merges
                        # them into the message stream; a missing final
                        # chunk is handled by the soft-stop branch below.
                except asyncio.CancelledError:
                    aborted = True
                    await persist_error(
                        content_or_partial=final_content or step_content,
                        thinking=full_thinking + step_label + step_thinking,
                        metadata={"step_count": step_count, "aborted": True, "tool_calls": tool_calls},
                    )
                    return
                except Exception as exc:  # noqa: BLE001
                    await persist_error(
                        content_or_partial=final_content or step_content or f"[Agent 出错: {exc}]",
                        thinking=full_thinking + step_label + step_thinking,
                        metadata={"step_count": step_count, "aborted": False, "tool_calls": tool_calls, "error": str(exc)},
                    )
                    yield _sse({"type": "error", "message": str(exc)})
                    return

                # Persist step-level thinking with explicit boundary.
                if step_thinking or step_content:
                    full_thinking += step_label + step_thinking
                    # Step body (Thought / Action / Final Answer) also goes
                    # into the persisted thinking trail so users can read
                    # their ReAct transcript later.
                    full_thinking += "\n" + step_content

                if not step_content:
                    # Nothing came back from the model — soft stop to avoid
                    # infinite loops on broken upstreams.
                    final_content = final_content or ""
                    break

                # Final Answer?
                final_text = _extract_final_answer(step_content)
                if final_text is not None:
                    final_content = final_text
                    # Skip tool dispatch: this step committed to an answer.
                    break

                # Tool dispatch?
                name, action_input = _parse_action(step_content)
                if name and name.lower() != "none":
                    matching = next((t for t in tools if t.name == name), None)
                    if matching is None:
                        observation = f"Observation: 未知工具 `{name}`，可用工具：{', '.join(t.name for t in tools) or '（无）'}。"
                        yield _sse({"type": "observation", "name": name, "step": step_number, "content": observation})
                    else:
                        yield _sse({"type": "action", "name": name, "step": step_number, "input": action_input})
                        try:
                            observation_text = await matching.ainvoke({"input": action_input})
                        except Exception as exc:  # noqa: BLE001 — keep loop alive
                            observation_text = f"[tool error: {exc}]"
                        observation = f"Observation: {observation_text}"
                        yield _sse({"type": "observation", "name": name, "step": step_number, "content": observation})
                        tool_calls.append(
                            {"name": name, "step": step_number, "input": action_input, "output": observation_text}
                        )
                else:
                    # No tool requested (or `Action: none`): emit a no-tool
                    # observation so the next step has something to build on.
                    observation = _NO_TOOL_OBSERVATION
                    yield _sse({"type": "observation", "name": "none", "step": step_number, "content": observation})

                # Feed this step back as the assistant turn + observation as
                # the next user turn — preserves the ReAct transcript.
                messages.append(AIMessage(content=step_content))
                messages.append(HumanMessage(content=observation))

                if step_count >= max_steps:
                    final_content = step_content
                    yield _sse(
                        {
                            "type": "warning",
                            "message": "max-steps-exceeded",
                            "max_steps": max_steps,
                        }
                    )
        except asyncio.CancelledError:
            aborted = True
            await persist_error(
                content_or_partial=final_content,
                thinking=full_thinking,
                metadata={"step_count": step_count, "aborted": True, "tool_calls": tool_calls},
            )
            return

        await persist_done(
            final_content,
            full_thinking,
            {"step_count": step_count, "aborted": aborted, "tool_calls": tool_calls},
        )
        yield _sse({"type": "done", "finish_reason": "agent"})

    # ------------------------------------------------------------------ helpers

    def _select_tools(self, skills: list[Skill] | None, enable: list[str] | None) -> list:
        """Whitelist filter, never raises on unknown skill names.

        Returns a list of wrapped LangChain ``StructuredTool`` objects —
        never raw ``Skill`` instances — so the agent loop can call
        ``tool.ainvoke({...})`` uniformly.
        """
        if not skills:
            return []
        if enable is None:
            filtered = [s for s in skills if self._is_callable(s)]
        else:
            enable_set = {n for n in enable}
            filtered = [s for s in skills if s.name in enable_set and self._is_callable(s)]
        return [_wrap_skill_as_tool(s) for s in filtered]

    @staticmethod
    def _is_callable(skill: Skill) -> bool:
        return hasattr(skill, "run")

    def _build_system_prompt(self, tools: list) -> str:
        if not tools:
            tools_section = "（无可用工具）"
        else:
            lines = []
            for t in tools:
                desc = t.description
                lines.append(f"- {t.name}: {desc}")
            tools_section = "\n".join(lines)
        return _REACT_TEMPLATE.replace("{tools_section}", tools_section)

    def _build_initial_messages(self, request: AgentChatRequest, system_prompt: str) -> list[BaseMessage]:
        raw = [m.model_dump() for m in request.messages]
        raw = attach_files_to_messages(raw, request.files)
        out: list[BaseMessage] = [SystemMessage(content=system_prompt)]
        for m in raw:
            role, content = m.get("role", "user"), m.get("content", "")
            if role == "assistant":
                out.append(AIMessage(content=content))
            elif role == "system":
                # Secondary system blocks collapse into the ReAct preamble
                # since most vendors only honor one system slot — we append
                # as a user message to retain the content without overrides.
                out.append(HumanMessage(content=f"[system note] {content}"))
            else:
                out.append(HumanMessage(content=content))
        return out

    def _build_chat_model(self, adapter: BaseAdapter, request: AgentChatRequest) -> BaseChatModel:
        # Lazy import to keep framework boundary inside this module.
        from app.services.langchain_adapter import AdapterChatModel

        model = AdapterChatModel(
            adapter=adapter,
            model_id=request.model,
            thinking=request.thinking,
            temperature=settings.agent_step_temperature,
            top_p=None,
        )
        return model

    async def _persist_metadata(self, message_id: str, metadata: dict[str, Any]) -> None:
        """Update the JSON metadata column directly.

        ConversationService.update_message_content does not currently accept
        metadata; we hit the ORM here so we don't widen the service API just
        for this single agent feature.
        """
        from sqlalchemy import select, update
        from app.models import Message

        try:
            async with self.db.begin_nested():
                await self.db.execute(
                    update(Message).where(Message.id == message_id).values(metadata_=metadata)
                )
            await self.db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist metadata for message %s", message_id)


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


__all__ = ["AgentService"]