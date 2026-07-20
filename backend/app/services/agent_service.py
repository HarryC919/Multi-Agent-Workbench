"""AgentService — phase 1: pure reasoning loop (ReAct, no tools).

Scope (per PROGRESS.md):
    * Multi-step reasoning within a single user turn.
    * No tool calling, no RAG. Any "Action:" in the model output is met with
      a fixed "no tools available" observation and the loop continues.
    * Adapter / ConversationService / streaming architecture untouched.

The streaming contract matches ``/api/chat``: SSE lines of
``data: {"type": "text|thinking|done|error|warning", ...}``.

Design notes:
    * Temperature knobs (``step_temperature`` / ``final_temperature``) are
      accepted by the schema and config but **not** forwarded to adapters
      yet — adapters do not currently accept a temperature argument. Phase
      2 will wire them through.
    * On abort, we catch ``asyncio.CancelledError``, persist whatever partial
      content/thinking has accumulated so far with ``status="error"``, and
      swallow the exception so ASGI does not log a noisy traceback. No new
      DB column is added (per the "no schema changes" constraint).
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import BaseAdapter
from app.config import settings
from app.models import Conversation
from app.schemas import AgentChatRequest
from app.services._chat_helpers import attach_files_to_messages
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "react_system.txt"
try:
    REACT_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")
except FileNotFoundError:  # pragma: no cover — repo integrity issue
    logger.warning("Missing %s; falling back to inline ReAct prompt.", _PROMPT_PATH)
    REACT_SYSTEM_PROMPT = (
        "You are a ReAct agent. Think step by step, then output "
        "`Final Answer:` followed by the answer when done."
    )

# Sentinel prefix the model is asked to emit to terminate the loop.
_FINAL_ANSWER_PREFIX = "Final Answer:"
# Observation fed back when there are no tools. Kept short and explicit so
# the model stays grounded rather than hallucinating tool output.
_NO_TOOL_OBSERVATION = "Observation: 无可用工具，请基于已知信息继续推理。"


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
    ) -> AsyncIterator[str]:
        """Run the ReAct loop and yield SSE lines.

        Side effects: persists one assistant Message via ConversationService
        (status='streaming' → 'done'/'error'). User message persistence is
        the caller's responsibility (the router), matching /api/chat.
        """
        max_steps = max(1, int(request.max_steps or settings.agent_max_steps))

        messages = self._build_initial_messages(request)
        full_thinking = ""
        final_content = ""
        step = 0
        max_steps_exceeded = False

        # Placeholder assistant message — created lazily so we only hit the
        # DB once the loop has actually started (avoids an empty row when
        # adapter construction already failed upstream).
        assistant_msg = await self.conversation_service.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content="",
            model=request.model,
            status="streaming",
        )

        try:
            while step < max_steps:
                step_label = f"\n\n--- 第 {step + 1} 步思考 ---\n"
                step_thinking = ""
                step_content = ""
                finish_reason_seen = False

                try:
                    async for chunk in adapter.stream_chat(
                        messages,
                        request.model,
                        thinking=request.thinking,
                    ):
                        if chunk.thinking:
                            step_thinking += chunk.thinking
                            yield _sse({"type": "thinking", "content": chunk.thinking})
                        if chunk.content:
                            step_content += chunk.content
                            yield _sse({"type": "text", "content": chunk.content})
                        if chunk.finish_reason:
                            finish_reason_seen = True
                except asyncio.CancelledError:
                    # Persist partials with error status and exit cleanly.
                    await self._finalize_on_error(
                        assistant_msg.id,
                        content_or_partial=final_content or step_content or "",
                        thinking=full_thinking + step_label + step_thinking,
                        error_message="[Agent aborted by client]",
                    )
                    return
                except Exception as exc:  # noqa: BLE001 — surface to client SSE
                    partial = full_thinking + step_label + step_thinking
                    await self._finalize_on_error(
                        assistant_msg.id,
                        content_or_partial=final_content or step_content or "",
                        thinking=partial,
                        error_message=f"[Agent 出错: {exc}]",
                    )
                    yield _sse({"type": "error", "message": str(exc)})
                    return

                # Persist step-level thinking (with an explicit boundary) so
                # downstream UI and DB viewers can see each step.
                if step_thinking or step_content:
                    full_thinking += step_label + step_thinking

                if not finish_reason_seen and not step_content:
                    # Adapter returned nothing usable; treat as a soft stop
                    # to avoid an infinite loop on broken upstreams.
                    final_content = step_content or final_content
                    break

                final_text = self._extract_final_answer(step_content)
                if final_text is not None:
                    final_content = final_text
                    break

                # Loop continuation: feed this step back as the assistant
                # turn, and reply with a no-tool observation so the model
                # keeps reasoning instead of stalling on Action: foo.
                messages.append({"role": "assistant", "content": step_content})
                messages.append({"role": "user", "content": _NO_TOOL_OBSERVATION})

                step += 1
                if step >= max_steps:
                    max_steps_exceeded = True
                    final_content = step_content or final_content
                    yield _sse(
                        {
                            "type": "warning",
                            "message": "max-steps-exceeded",
                            "max_steps": max_steps,
                        }
                    )
        except asyncio.CancelledError:
            # Outer guard for cancellation during non-adapter awaits.
            await self._finalize_on_error(
                assistant_msg.id,
                content_or_partial=final_content,
                thinking=full_thinking,
                error_message="[Agent aborted by client]",
            )
            return

        # Persist the final answer.
        await self.conversation_service.update_message_content(
            assistant_msg.id,
            final_content,
            status="done",
            thinking=full_thinking,
        )
        yield _sse({"type": "done", "finish_reason": "agent"})

    # ------------------------------------------------------------------ helpers

    def _build_initial_messages(self, request: AgentChatRequest) -> list[dict[str, Any]]:
        """Assemble the message list that opens the ReAct conversation."""
        raw = [m.model_dump() for m in request.messages]
        raw = attach_files_to_messages(raw, request.files)

        system_block = {"role": "system", "content": REACT_SYSTEM_PROMPT}
        # ChatRequest.messages does not enforce a leading system entry, so we
        # prepend our own ReAct prompt. If the caller already included a
        # system message it stays in place (ordering: react system → caller
        # messages), which keeps user-supplied instructions intact.
        return [system_block, *raw]

    def _extract_final_answer(self, step_content: str) -> str | None:
        """Return the substring after ``Final Answer:`` if present, else None.

        Handles the sentinel appearing anywhere in the step text. We split on
        the first occurrence so a multi-paragraph answer is preserved verbatim.
        """
        idx = step_content.find(_FINAL_ANSWER_PREFIX)
        if idx < 0:
            return None
        tail = step_content[idx + len(_FINAL_ANSWER_PREFIX) :]
        # Trim a single leading newline so the answer does not start with a
        # blank line in the UI.
        return tail.lstrip("\n").strip()

    async def _finalize_on_error(
        self,
        message_id: str,
        *,
        content_or_partial: str,
        thinking: str,
        error_message: str,
    ) -> None:
        """Persist partials with status='error'. Never raises to the caller."""
        try:
            await self.conversation_service.update_message_content(
                message_id,
                content_or_partial or error_message,
                status="error",
                thinking=thinking,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist agent error state for message %s", message_id)


def _sse(payload: dict[str, Any]) -> str:
    """Serialize a ChatChunk-shaped dict as an SSE ``data:`` line."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"