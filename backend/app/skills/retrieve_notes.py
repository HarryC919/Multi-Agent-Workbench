"""Retrieve-notes skill (AgentService phase 2b-i).

A `Skill` whose `run(input, args)` searches the active knowledge base for
markdown chunks most similar to `input` and returns them joined as a markdown
snippet for the ReAct loop to consume as its Observation.

The skill is instantiated per request with the active `kb_id` baked in — see
`get_retrieve_notes_skill(kb_id)` — so the agent never sees a free-standing
"list all KBs" control surface. This matches the design decision in
DEVELOPMENT_PLAN 11.4: in agent mode the KB is chosen by the user, the agent
only gets to retrieve against it.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.services.knowledge_service import KnowledgeService
from app.skills.base import Skill, SkillResult

logger = logging.getLogger(__name__)


class RetrieveNotesSkill:
    """Retrieve top-K markdown chunks from the bound KB.

    Bound state: ``self.kb_id``. Set by the factory at request time.
    """

    name = "retrieve_notes"
    description = (
        "Search the active knowledge base of markdown notes for chunks most "
        "relevant to the given query, returning the snippets with source "
        "attribution. Use when the user asks about content in their knowledge "
        "base (notes, docs, markdown)."
    )

    def __init__(self, kb_id: str):
        self.kb_id = kb_id

    async def run(self, input: str = "", args: dict[str, Any] | None = None) -> SkillResult:
        args = args or {}
        top_k = int(args.get("top_k", settings.kb_top_k))
        min_score = float(args.get("min_score", settings.kb_min_score))
        query = (input or "").strip()
        if not query:
            return {"output": "[retrieve_notes: empty query]", "metadata": {"error": True, "kb_id": self.kb_id}}

        # KnowledgeService.retrieve is a sync method, so we offload it to a
        # thread to keep the async ReAct loop responsive on heavy embedder
        # calls. The db session it opens internally is its own short-lived one.
        from app.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models import KnowledgeBase
        import asyncio

        async def _do() -> list:
            async with AsyncSessionLocal() as db:
                # Verify KB exists; otherwise raise so the caller can surface a
                # friendly error envelope instead of stalling the ReAct loop.
                result = await db.execute(
                    select(KnowledgeBase).where(KnowledgeBase.id == self.kb_id)
                )
                kb = result.scalar_one_or_none()
                if kb is None:
                    raise LookupError(f"knowledge base {self.kb_id} not found")
                svc = KnowledgeService(db)
                return await asyncio.to_thread(svc.retrieve, self.kb_id, query, top_k, min_score)

        try:
            chunks = await _do()
        except LookupError as exc:
            return {
                "output": f"[retrieve_notes: {exc}]",
                "metadata": {"error": True, "kb_id": self.kb_id},
            }
        except Exception as exc:  # noqa: BLE001 — surface to loop, do not crash
            return {
                "output": f"[retrieve_notes error: {exc}]",
                "metadata": {"error": True, "kb_id": self.kb_id},
            }

        if not chunks:
            return {"output": "[retrieve_notes: no matching chunks]", "metadata": {"kb_id": self.kb_id, "count": 0}}

        lines: list[str] = []
        for c in chunks:
            attribution = f"[来源: {c.filename}"
            if c.heading:
                attribution += f" # {c.heading}"
            attribution += f" | score={c.score:.2f}]"
            lines.append(f"{attribution}\n{c.chunk_text}")
        return {
            "output": "\n\n".join(lines),
            "metadata": {
                "kb_id": self.kb_id,
                "count": len(chunks),
                # Structured chunk payload (phase 2b-ii): the agent loop reads
                # this via `tool._last_metadata` and emits a `retrieved` SSE
                # event so the frontend can render source-attributed cards
                # instead of parsing the markdown observation string.
                "chunks": [
                    {
                        "doc_id": c.doc_id,
                        "filename": c.filename,
                        "heading": c.heading,
                        "score": c.score,
                        "text": c.chunk_text,
                    }
                    for c in chunks
                ],
            },
        }


def get_retrieve_notes_skill(kb_id: str | None) -> Skill | None:
    """Factory: returns a RetrieveNotesSkill bound to ``kb_id``, or None if no KB is active."""
    if not kb_id:
        return None
    return RetrieveNotesSkill(kb_id=kb_id)


__all__ = ["RetrieveNotesSkill", "get_retrieve_notes_skill"]