"""Unit tests for the retrieve_notes skill (AgentService phase 2b-i).

The refactored ``RetrieveNotesSkill`` is bound to a ``kb_id`` at construction
and, on ``run``, opens its own short-lived DB session to verify the KB exists,
then calls the sync ``KnowledgeService.retrieve`` via ``asyncio.to_thread``.

To keep these tests off chromadb/embeddings we create a real KB row (so the
existence check passes) and monkeypatch ``KnowledgeService.retrieve`` on the
class to return canned ``KnowledgeRetrievalResult`` chunks.
"""
from __future__ import annotations

import asyncio

import pytest

from app.database import AsyncSessionLocal
from app.schemas import KnowledgeBaseCreate, KnowledgeRetrievalResult
from app.services.knowledge_service import KnowledgeService
from app.skills.base import Skill
from app.skills.retrieve_notes import RetrieveNotesSkill, get_retrieve_notes_skill


def _canned_chunks() -> list[KnowledgeRetrievalResult]:
    return [
        KnowledgeRetrievalResult(
            doc_id="d1",
            filename="notes.md",
            heading="安装",
            chunk_text="用 uv 安装 fastapi。",
            score=0.91,
        ),
        KnowledgeRetrievalResult(
            doc_id="d1",
            filename="notes.md",
            heading="部署",
            chunk_text="docker compose up。",
            score=0.72,
        ),
    ]


@pytest.fixture
async def real_kb_id(monkeypatch):
    """Create a real KB row and stub retrieve to return canned chunks.

    Returns the KB id; the skill's existence check queries the DB directly.
    """
    monkeypatch.setattr(
        KnowledgeService,
        "retrieve",
        lambda self, kb_id, query, top_k, min_score: _canned_chunks(),
    )
    async with AsyncSessionLocal() as db:
        kb = await KnowledgeService(db).create_kb(
            KnowledgeBaseCreate(name="测试KB", description="")
        )
        return kb.id


def test_factory_returns_skill_or_none():
    """Factory returns a Skill when kb_id is set, None when not."""
    assert get_retrieve_notes_skill("kb1") is not None
    assert get_retrieve_notes_skill(None) is None
    assert get_retrieve_notes_skill("") is None


def test_skill_matches_protocol():
    skill = RetrieveNotesSkill(kb_id="kb1")
    assert isinstance(skill, Skill)
    assert skill.name == "retrieve_notes"
    assert "knowledge base" in skill.description.lower()


def test_run_outputs_source_tags_without_observation_prefix(real_kb_id):
    skill = RetrieveNotesSkill(kb_id=real_kb_id)
    result = asyncio.run(skill.run(input="怎么安装?", args={"top_k": 3, "min_score": 0.3}))

    out = result["output"]
    # Must NOT carry the Observation: prefix — AgentService adds it.
    assert not out.startswith("Observation:")
    # Both chunks surfaced with source attribution + score.
    assert "[来源: notes.md # 安装 | score=0.91]" in out
    assert "用 uv 安装 fastapi。" in out
    assert "[来源: notes.md # 部署 | score=0.72]" in out
    assert "docker compose up。" in out


def test_run_metadata_carries_count_and_kb_id(real_kb_id):
    skill = RetrieveNotesSkill(kb_id=real_kb_id)
    result = asyncio.run(skill.run(input="q"))
    meta = result["metadata"]
    assert meta["kb_id"] == real_kb_id
    assert meta["count"] == 2


def test_run_empty_query_returns_envelope(real_kb_id):
    """An empty query short-circuits before hitting retrieve."""
    skill = RetrieveNotesSkill(kb_id=real_kb_id)
    result = asyncio.run(skill.run(input="   "))
    assert "empty query" in result["output"]
    assert result["metadata"]["error"] is True


def test_run_empty_result_message(monkeypatch, real_kb_id):
    """When retrieve returns no chunks, the output says so and count is 0."""
    monkeypatch.setattr(
        KnowledgeService, "retrieve", lambda self, kb_id, query, top_k, min_score: []
    )
    skill = RetrieveNotesSkill(kb_id=real_kb_id)
    result = asyncio.run(skill.run(input="不相关的问题"))
    assert "no matching chunks" in result["output"]
    assert result["metadata"]["count"] == 0


def test_run_unknown_kb_returns_error_envelope(monkeypatch):
    """When the KB doesn't exist, the skill returns a friendly error envelope
    instead of raising — so the ReAct loop can choose different reasoning."""
    monkeypatch.setattr(
        KnowledgeService, "retrieve", lambda self, kb_id, query, top_k, min_score: _canned_chunks()
    )
    skill = RetrieveNotesSkill(kb_id="does-not-exist")
    result = asyncio.run(skill.run(input="q"))
    assert "not found" in result["output"]
    assert result["metadata"]["error"] is True


def test_run_handles_none_args(real_kb_id):
    skill = RetrieveNotesSkill(kb_id=real_kb_id)
    result = asyncio.run(skill.run(input="q", args=None))
    # Defaults from settings (kb_top_k / kb_min_score) are applied without error.
    assert "[来源: notes.md" in result["output"]
