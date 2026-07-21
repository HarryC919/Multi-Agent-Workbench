"""retrieve_notes skill — RAG retrieval over the user-selected knowledge base.

Unlike the other skills (echo, current_time) which are stateless module-level
singletons registered in ``registry._REGISTRY``, this one is **per-request**:
it binds a specific ``kb_id`` and a ``KnowledgeService``. It is therefore NOT
registered in the registry; instead ``routers/agent.py`` constructs it via
:func:`get_retrieve_notes_skill` and appends it to the skills list when the
request carries ``rag_knowledge_base_id``.

The skill flows through ``AgentService._wrap_skill_as_tool`` unchanged (it
duck-types the ``Skill`` Protocol: ``name``/``description``/``run``).

Important: the returned ``output`` must NOT include an ``Observation: ``
prefix — ``AgentService`` adds that when emitting the observation SSE event
(see ``agent_service.py``). We return the raw retrieved-chunks markdown.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.skills.base import SkillResult

if TYPE_CHECKING:
    from app.services.knowledge_service import KnowledgeService


class _RetrieveNotesSkill:
    name = "retrieve_notes"
    description = (
        "从用户选定的知识库中检索与查询相关的笔记片段。"
        "输入应为要检索的自然语言查询；返回按相关度排序的笔记片段，"
        "每段标注来源文件与标题。当知识库中没有相关内容时返回空结果。"
    )

    def __init__(self, kb_id: str, knowledge_service: "KnowledgeService") -> None:
        self._kb_id = kb_id
        self._svc = knowledge_service

    async def run(self, input: str = "", args: dict[str, Any] | None = None) -> SkillResult:
        args = args or {}
        top_k = int(args.get("top_k", 4))
        min_score = float(args.get("min_score", 0.3))
        chunks = await self._svc.retrieve(self._kb_id, input, top_k=top_k, min_score=min_score)

        if not chunks:
            return {
                "output": "未检索到相关笔记片段。",
                "metadata": {"chunks": [], "kb_id": self._kb_id},
            }

        lines = [f"检索到 {len(chunks)} 个片段:"]
        for c in chunks:
            heading_tag = f" #{c.heading}" if c.heading else ""
            lines.append(f"\n[来源: {c.filename}{heading_tag} | score={c.score:.2f}]\n{c.text}")
        output = "\n".join(lines)
        return {
            "output": output,
            "metadata": {"chunks": [c.model_dump() for c in chunks], "kb_id": self._kb_id},
        }


def get_retrieve_notes_skill(kb_id: str, knowledge_service: "KnowledgeService") -> _RetrieveNotesSkill:
    """Factory: build a per-request retrieve_notes skill bound to a KB."""
    return _RetrieveNotesSkill(kb_id=kb_id, knowledge_service=knowledge_service)
