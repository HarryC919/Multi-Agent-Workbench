"""Bridge between our ``BaseAdapter`` stack and LangChain's ``BaseChatModel``.

AgentService phase 2a keeps the Adapter/ModelConfig layer as the single
source of truth for vendor credentials and SSE parsing. LangGraph's
``create_react_agent`` only needs a ``BaseChatModel``-shaped object that it
can invoke and stream; here we wrap any ``BaseAdapter`` instance behind
that LangChain interface.

Scope:
    * Implements ``_generate`` (sync) and ``_agenerate`` (async). LangGraph
      prefers the async path under an event loop, so async is the hot path
      for ``/api/agent-chat`` consumers; sync is provided for parity and
      to power tests or sync callers.
    * Thinking (reasoning_content) chunks are folded into the AIMessage
      ``additional_metadata`` under ``thinking`` so AgentService can extract
      and stream them downstream.
    * ``temperature`` / ``top_p`` are accepted via constructor or via
      ``bind``-style kwargs at call time (LangChain invokes the model with
      ``model.bind(temperature=...)`` sometimes; we honor call-time overrides).
    * Tool binding is intentionally NOT implemented — phase 2a uses ReAct
      prompt injection instead of native tool-calling APIs. ``bind_tools``
      raises NotImplementedError so callers fail loudly.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, AsyncIterator, Iterator, Optional, Sequence

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import ConfigDict

from app.adapters.base import BaseAdapter, StreamChunk


def _messages_to_dicts(messages: Sequence[BaseMessage]) -> list[dict[str, str]]:
    """Convert LangChain messages to the dict form our adapters expect."""
    out: list[dict[str, str]] = []
    for m in messages:
        # type == "human" → role user; "ai" → assistant; "system" → system.
        lc_type = m.type
        role = {
            "human": "user",
            "ai": "assistant",
            "system": "system",
            "tool": "user",  # tool result fed back as a user turn for ReAct
        }.get(lc_type, lc_type or "user")
        content = m.content if isinstance(m.content, str) else str(m.content)
        out.append({"role": role, "content": content})
    return out


class AdapterChatModel(BaseChatModel):
    """LangChain ``BaseChatModel`` façade over our existing adapters."""

    adapter: BaseAdapter
    model_id: str
    thinking: bool = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    # Used as part of the cache key via _identifying_params.
    provider_name: str = "adapter-bridge"

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ------------------------------------------------------------------ LangChain

    @property
    def _llm_type(self) -> str:
        return "adapter-bridge"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        # Returned as a property so BaseChatModel.dict() can consume it as a
        # mapping (LangChain's RunnableBinding reads it via dict access, not
        # by calling the method).
        return {
            "model_id": self.model_id,
            "provider_name": self.provider_name,
            "thinking": self.thinking,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }

    # ------------------------------------------------------------------ generate

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # The adapter is async-native; sync callers run the coroutine on the
        # current loop if there is one (with a fresh private loop to avoid
        # baking one into a long-running event loop), else use asyncio.run.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an active loop — create a fresh loop on a worker
                # thread to avoid "loop already running" reentry.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    return ex.submit(lambda: asyncio.run(self._agenerate(messages, stop, None, **kwargs))).result()
        except RuntimeError:
            # No current loop; asyncio.run is safe.
            pass
        return asyncio.run(self._agenerate(messages, stop, None, **kwargs))

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Call-time kwargs (via model.bind(temperature=...)) override the
        # constructor defaults. ``stop`` sequences are not supported by our
        # adapters today; we ignore them rather than degrade silently.
        temperature = kwargs.get("temperature", self.temperature)
        top_p = kwargs.get("top_p", self.top_p)

        dict_messages = _messages_to_dicts(messages)
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        finish_reason: Optional[str] = None

        async for chunk in self.adapter.stream_chat(
            dict_messages,
            self.model_id,
            thinking=self.thinking,
            temperature=temperature,
            top_p=top_p,
        ):
            if chunk.thinking:
                thinking_parts.append(chunk.thinking)
            if chunk.content:
                content_parts.append(chunk.content)
            if chunk.finish_reason:
                finish_reason = chunk.finish_reason

        message = AIMessage(content="".join(content_parts))
        if thinking_parts:
            # AIMessage in langchain-core 0.3 exposes ``additional_kwargs``
            # (for tool-call args) rather than ``additional_metadata``. We
            # stash the reasoning trace here so AgentService can pop it off
            # and stream it as a separate ``thinking`` SSE event type.
            message.additional_kwargs["thinking"] = "".join(thinking_parts)
        if finish_reason:
            message.response_metadata["finish_reason"] = finish_reason

        gen = ChatGeneration(message=message)
        return ChatResult(generations=[gen])

    # ------------------------------------------------------------------ streaming

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        temperature = kwargs.get("temperature", self.temperature)
        top_p = kwargs.get("top_p", self.top_p)
        dict_messages = _messages_to_dicts(messages)
        async for chunk in self.adapter.stream_chat(
            dict_messages,
            self.model_id,
            thinking=self.thinking,
            temperature=temperature,
            top_p=top_p,
        ):
            if chunk.thinking:
                ai_chunk = AIMessageChunk(
                    content="",
                    additional_kwargs={"thinking": chunk.thinking},
                )
                yield ChatGenerationChunk(message=ai_chunk)
            if chunk.content:
                ai_chunk = AIMessageChunk(content=chunk.content)
                yield ChatGenerationChunk(message=ai_chunk)
            if chunk.finish_reason:
                ai_chunk = AIMessageChunk(
                    content="",
                    response_metadata={"finish_reason": chunk.finish_reason},
                )
                yield ChatGenerationChunk(message=ai_chunk)

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        # Mirror _generate: bridge async streaming through a private loop.
        async def collect() -> list[ChatGenerationChunk]:
            chunks: list[ChatGenerationChunk] = []
            async for c in self._astream(messages, stop, None, **kwargs):
                chunks.append(c)
            return chunks

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    for c in ex.submit(lambda: asyncio.run(collect())).result():
                        yield c
                return
        except RuntimeError:
            pass
        for c in asyncio.run(collect()):
            yield c

    # ------------------------------------------------------------------ tools

    def bind_tools(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        """Raise explicitly — phase 2a uses ReAct prompt injection."""
        raise NotImplementedError(
            "AdapterChatModel does not bind tools natively. "
            "AgentService phase 2a injects the tool list via the ReAct system "
            "prompt instead of vendor tool-calling APIs. Native tool-calling is "
            "deferred to a future phase."
        )


__all__ = ["AdapterChatModel"]