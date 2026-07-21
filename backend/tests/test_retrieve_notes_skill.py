"""Unit tests for the retrieve_notes skill (AgentService phase 2b-i).

Validates output format (source tags, no ``Observation:`` prefix —
AgentService adds that), metadata.chunks structure, and empty-result path.
Uses a fake KnowledgeService so no chromadb/embedding is touched.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.schemas import RetrievedChunk
from app.skills.base import Skill
from app.skills.retrieve_notes import get_retrieve_notes_skill


class _FakeKnowledgeService:
    """Records calls and returns canned RetrievedChunks."""

    def __init__(self, chunks: list[RetrievedChunk] | None = None) -> None:
        self._chunks = chunks if chunks is not None else [
            RetrievedChunk(
                doc_id="d1",
                filename="notes.md",
                heading="安装",
                score=0.91,
                text="用 uv 安装 fastapi。",
            ),
            RetrievedChunk(
                doc_id="d1",
                filename="notes.md",
                heading="部署",
                score=0.72,
                text="docker compose up。",
            ),
        ]
        self.calls: list[dict[str, Any]] = []

    async def retrieve(self, kb_id: str, query: str, top_k: int, min_score: float):
        self.calls.append(
            {"kb_id": kb_id, "query": query, "top_k": top_k, "min_score": min_score}
        )
        return self._chunks


def test_factory_returns_skill_matching_protocol():
    svc = _FakeKnowledgeService()
    skill = get_retrieve_notes_skill("kb1", svc)
    assert isinstance(skill, Skill)
    assert skill.name == "retrieve_notes"
    assert "知识库" in skill.description


def test_run_outputs_source_tags_without_observation_prefix():
    svc = _FakeKnowledgeService()
    skill = get_retrieve_notes_skill("kb1", svc)
    result = asyncio.run(skill.run(input="怎么安装?", args={"top_k": 3, "min_score": 0.3}))

    out = result["output"]
    # Must NOT carry the Observation: prefix — AgentService adds it.
    assert not out.startswith("Observation:")
    assert "检索到 2 个片段" in out
    assert "[来源: notes.md #安装 | score=0.91]" in out
    assert "用 uv 安装 fastapi。" in out
    assert "docker compose up。" in out


def test_run_metadata_carries_chunks_and_kb_id():
    svc = _FakeKnowledgeService()
    skill = get_retrieve_notes_skill("kb1", svc)
    result = asyncio.run(skill.run(input="q"))
    meta = result["metadata"]
    assert meta["kb_id"] == "kb1"
    assert len(meta["chunks"]) == 2
    assert meta["chunks"][0]["filename"] == "notes.md"
    assert meta["chunks"][0]["heading"] == "安装"


def test_run_passes_args_to_retrieve():
    svc = _FakeKnowledgeService()
    skill = get_retrieve_notes_skill("kb1", svc)
    asyncio.run(skill.run(input="查询词", args={"top_k": 7, "min_score": 0.5}))
    assert svc.calls == [
        {"kb_id": "kb1", "query": "查询词", "top_k": 7, "min_score": 0.5}
    ]


def test_run_uses_defaults_when_args_omitted():
    svc = _FakeKnowledgeService()
    skill = get_retrieve_notes_skill("kb1", svc)
    asyncio.run(skill.run(input="q"))
    assert svc.calls[0]["top_k"] == 4
    assert svc.calls[0]["min_score"] == 0.3


def test_run_empty_result_message():
    svc = _FakeKnowledgeService(chunks=[])
    skill = get_retrieve_notes_skill("kb1", svc)
    result = asyncio.run(skill.run(input="不相关的问题"))
    assert "未检索到" in result["output"]
    assert result["metadata"]["chunks"] == []
    assert result["metadata"]["kb_id"] == "kb1"


def test_run_handles_none_args():
    svc = _FakeKnowledgeService()
    skill = get_retrieve_notes_skill("kb1", svc)
    result = asyncio.run(skill.run(input="q", args=None))
    assert svc.calls[0]["top_k"] == 4
    assert "检索到" in result["output"]
