"""Unit tests for KnowledgeService (AgentService phase 2b-i).

Uses a deterministic fake embedder (hash-derived non-zero vectors) so tests
never touch the real bge model or network. Each test gets a fresh temp chroma
persist dir to avoid cross-test collection leakage.

The fake embedder replaces the production ``embedding_service`` singleton via
direct attribute swap (the service caches ``_model`` / ``_backend``), so
``is_available()`` returns True and the real lazy-load path is skipped.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.database import AsyncSessionLocal
from app.schemas import KnowledgeBaseCreate
from app.services import knowledge_service as ks_module
from app.services.knowledge_service import KnowledgeService

_FAKE_DIM = 512


def _hash_vec(text: str, dim: int = _FAKE_DIM) -> list[float]:
    """Deterministic non-zero vector from text hash.

    Different texts → different vectors; identical texts → identical vectors.
    Normalized to unit length so cosine similarity behaves.
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # Stretch hash bytes to fill the vector dimension.
    raw = [float(h[i % len(h)]) for i in range(dim)]
    norm = sum(v * v for v in raw) ** 0.5 or 1.0
    return [v / norm for v in raw]


class _FakeModel:
    """Deterministic non-zero embedder standing in for bge."""

    def encode(self, texts, normalize_embeddings=True):  # noqa: ARG002
        if isinstance(texts, str):
            return _hash_vec(texts)
        return [_hash_vec(t) for t in texts]


@pytest.fixture
async def fake_embedder(tmp_path, monkeypatch):
    """Point chroma at a temp dir and swap in a deterministic fake model."""
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / ".chroma"))
    # settings is already constructed; patch the attribute the resolver reads.
    monkeypatch.setattr(
        "app.services.knowledge_service.settings.chroma_persist_dir",
        str(tmp_path / ".chroma"),
    )
    # Reset the cached chromadb client so it picks up the new persist dir.
    ks_module._chroma_client = None

    svc = ks_module.embedding_service
    saved_model = svc._model
    saved_backend = svc._backend
    saved_attempted = svc._load_attempted
    svc._model = _FakeModel()
    svc._backend = "bge"
    svc._load_attempted = True
    try:
        yield svc
    finally:
        svc._model = saved_model
        svc._backend = saved_backend
        svc._load_attempted = saved_attempted
        ks_module._chroma_client = None


@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def kb(fake_embedder, db_session):
    """A fresh KB for each test."""
    svc = KnowledgeService(db_session)
    created = await svc.create_knowledge_base(KnowledgeBaseCreate(name="测试KB", description="desc"))
    return created.id


_SIMPLE_MD = (
    "# 安装指南\n\n"
    "用 uv 安装 fastapi：`uv add fastapi`。\n\n"
    "## 系统要求\n\n"
    "需要 Python 3.11 或更高版本。\n\n"
    "# 部署\n\n"
    "用 docker compose 一键启动前后端。\n"
)


# ---------------------------------------------------------------------------
# KB CRUD
# ---------------------------------------------------------------------------


async def test_create_and_list_knowledge_base(fake_embedder, db_session):
    svc = KnowledgeService(db_session)
    kb = await svc.create_knowledge_base(KnowledgeBaseCreate(name="笔记", description="d"))
    assert kb.name == "笔记"
    assert kb.description == "d"
    assert kb.id

    kbs = await svc.list_knowledge_bases()
    assert any(k.id == kb.id for k in kbs)


async def test_get_knowledge_base(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    found = await svc.get_knowledge_base(kb)
    assert found is not None
    assert found.id == kb
    assert await svc.get_knowledge_base("nonexistent") is None


async def test_delete_knowledge_base_cascades(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    await svc.upload_document(kb, "notes.md", _SIMPLE_MD.encode("utf-8"))
    assert len(await svc.list_documents(kb)) == 1

    assert await svc.delete_knowledge_base(kb) is True
    assert await svc.get_knowledge_base(kb) is None
    # Documents cascade-deleted.
    assert len(await svc.list_documents(kb)) == 0
    # Idempotent: deleting again returns False.
    assert await svc.delete_knowledge_base(kb) is False


# ---------------------------------------------------------------------------
# Document upload + chunking + dedup
# ---------------------------------------------------------------------------


async def test_upload_document_chunks_and_indexes(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    resp = await svc.upload_document(kb, "notes.md", _SIMPLE_MD.encode("utf-8"))
    assert resp.deduplicated is False
    assert resp.filename == "notes.md"
    assert resp.chunks >= 2  # at least the two header sections
    assert resp.doc_id

    docs = await svc.list_documents(kb)
    assert len(docs) == 1
    assert docs[0].filename == "notes.md"
    assert docs[0].sha256


async def test_upload_document_dedup(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    first = await svc.upload_document(kb, "notes.md", _SIMPLE_MD.encode("utf-8"))
    second = await svc.upload_document(kb, "notes.md", _SIMPLE_MD.encode("utf-8"))
    assert second.deduplicated is True
    assert second.chunks == 0
    assert second.doc_id == first.doc_id
    # Still only one doc row.
    assert len(await svc.list_documents(kb)) == 1


async def test_upload_document_rejects_bad_type(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    with pytest.raises(ValueError, match="Unsupported file type"):
        await svc.upload_document(kb, "doc.pdf", b"%PDF-1.4 ...")


async def test_upload_document_rejects_oversized(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    big = b"x" * (11 * 1024 * 1024)
    with pytest.raises(ValueError, match="too large"):
        await svc.upload_document(kb, "big.txt", big)


async def test_upload_unknown_kb_raises(fake_embedder, db_session):
    svc = KnowledgeService(db_session)
    with pytest.raises(ValueError, match="not found"):
        await svc.upload_document("nope", "notes.md", _SIMPLE_MD.encode("utf-8"))


# ---------------------------------------------------------------------------
# Delete document
# ---------------------------------------------------------------------------


async def test_delete_document(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    resp = await svc.upload_document(kb, "notes.md", _SIMPLE_MD.encode("utf-8"))
    assert await svc.delete_document(kb, resp.doc_id) is True
    assert len(await svc.list_documents(kb)) == 0
    assert await svc.delete_document(kb, resp.doc_id) is False


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


async def test_retrieve_returns_ranked_chunks(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    await svc.upload_document(kb, "notes.md", _SIMPLE_MD.encode("utf-8"))
    chunks = await svc.retrieve(kb, "安装", top_k=3, min_score=0.0)
    assert len(chunks) >= 1
    # Scores are in [0, 1] and sorted descending by chromadb.
    scores = [c.score for c in chunks]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)
    # Each chunk carries source metadata.
    for c in chunks:
        assert c.filename == "notes.md"
        assert c.doc_id
        assert c.text


async def test_retrieve_min_score_filter(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    await svc.upload_document(kb, "notes.md", _SIMPLE_MD.encode("utf-8"))
    # A min_score of 1.0 (exact match) should filter everything out because
    # hash vectors are deterministic but not identical to the query vector.
    chunks = await svc.retrieve(kb, "安装", top_k=5, min_score=1.0)
    assert chunks == []


async def test_retrieve_empty_kb(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    chunks = await svc.retrieve(kb, "anything", top_k=4)
    assert chunks == []


async def test_retrieve_unknown_kb(fake_embedder, db_session):
    svc = KnowledgeService(db_session)
    assert await svc.retrieve("nonexistent", "q") == []


# ---------------------------------------------------------------------------
# FakeEmbedder no-op path (when real model unavailable)
# ---------------------------------------------------------------------------


async def test_retrieve_returns_empty_when_embedding_unavailable(db_session, tmp_path, monkeypatch):
    """When is_available() is False, retrieve short-circuits to [] (no chroma)."""
    monkeypatch.setattr(
        "app.services.knowledge_service.settings.chroma_persist_dir",
        str(tmp_path / ".chroma"),
    )
    ks_module._chroma_client = None

    svc_obj = ks_module.embedding_service
    saved = (svc_obj._model, svc_obj._backend, svc_obj._load_attempted)
    svc_obj._model = None
    svc_obj._backend = "fake"
    svc_obj._load_attempted = True
    try:
        assert svc_obj.is_available() is False
        svc = KnowledgeService(db_session)
        kb_obj = await svc.create_knowledge_base(KnowledgeBaseCreate(name="k"))
        assert await svc.retrieve(kb_obj.id, "q") == []
    finally:
        svc_obj._model, svc_obj._backend, svc_obj._load_attempted = saved
        ks_module._chroma_client = None


async def test_upload_raises_when_embedding_unavailable(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.knowledge_service.settings.chroma_persist_dir",
        str(tmp_path / ".chroma"),
    )
    ks_module._chroma_client = None

    svc_obj = ks_module.embedding_service
    saved = (svc_obj._model, svc_obj._backend, svc_obj._load_attempted)
    svc_obj._model = None
    svc_obj._backend = "fake"
    svc_obj._load_attempted = True
    try:
        svc = KnowledgeService(db_session)
        kb_obj = await svc.create_knowledge_base(KnowledgeBaseCreate(name="k"))
        with pytest.raises(RuntimeError, match="unavailable"):
            await svc.upload_document(kb_obj.id, "notes.md", _SIMPLE_MD.encode("utf-8"))
    finally:
        svc_obj._model, svc_obj._backend, svc_obj._load_attempted = saved
        ks_module._chroma_client = None
