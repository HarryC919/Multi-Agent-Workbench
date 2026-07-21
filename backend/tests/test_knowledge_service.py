"""Unit tests for KnowledgeService (AgentService phase 2b-i, refactored API).

The refactored service exposes: create_kb / list_kbs / get_kb / delete_kb /
list_documents / add_document(kb_id, filename, text) / delete_document /
retrieve (sync, returns KnowledgeRetrievalResult).

To avoid the real bge model + chromadb on-disk store we:
  * monkeypatch EmbeddingService.embed_texts to return deterministic hash
    vectors (so retrieval is meaningful for exact/near-exact text matches),
  * point the chromadb persist dir at a per-test temp path and reset the
    cached client singleton between tests.
"""
from __future__ import annotations

import hashlib

import pytest

from app.database import AsyncSessionLocal
from app.schemas import KnowledgeBaseCreate
from app.services import knowledge_service as ks_module
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_service import KnowledgeService

_FAKE_DIM = 1024  # matches EmbeddingService._FAKE_DIM used by the real fake path


def _hash_vec(text: str, dim: int = _FAKE_DIM) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [float(h[i % len(h)]) for i in range(dim)]
    norm = sum(v * v for v in raw) ** 0.5 or 1.0
    return [v / norm for v in raw]


@pytest.fixture
async def fake_embedder(tmp_path, monkeypatch):
    """Temp chroma dir + deterministic embed_texts stub."""
    monkeypatch.setattr(
        "app.services.knowledge_service.settings.chroma_persist_dir",
        str(tmp_path / ".chroma"),
    )
    # Reset the cached chromadb client so it picks up the new persist dir.
    KnowledgeService._chroma_client_singleton = None

    emb = EmbeddingService.instance()
    saved = emb.embed_texts
    monkeypatch.setattr(
        emb,
        "embed_texts",
        lambda texts: [_hash_vec(t) for t in texts],
    )
    yield emb
    KnowledgeService._chroma_client_singleton = None


@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def kb(fake_embedder, db_session):
    svc = KnowledgeService(db_session)
    created = await svc.create_kb(KnowledgeBaseCreate(name="测试KB", description="desc"))
    return created.id


_MD = (
    "# 安装\n\n"
    "用 uv 安装 fastapi：`uv add fastapi`。\n\n"
    "## 系统要求\n\n"
    "需要 Python 3.11 或更高版本。\n\n"
    "# 部署\n\n"
    "用 docker compose 一键启动前后端。\n"
)


# ----------------------------------------------------------------- KB CRUD


async def test_create_and_list_kb(fake_embedder, db_session):
    svc = KnowledgeService(db_session)
    kb = await svc.create_kb(KnowledgeBaseCreate(name="笔记", description="d"))
    assert kb.name == "笔记"
    assert kb.id

    kbs = await svc.list_kbs()
    assert any(k.id == kb.id for k in kbs)


async def test_get_kb(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    assert (await svc.get_kb(kb)) is not None
    assert await svc.get_kb("nonexistent") is None


async def test_delete_kb_cascades_docs(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    await svc.add_document(kb, "notes.md", _MD)
    assert len(await svc.list_documents(kb)) == 1

    assert await svc.delete_kb(kb) is True
    assert await svc.get_kb(kb) is None
    assert len(await svc.list_documents(kb)) == 0
    assert await svc.delete_kb(kb) is False


# ------------------------------------------------------- add_document / dedup


async def test_add_document_indexes_chunks(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    doc = await svc.add_document(kb, "notes.md", _MD)
    assert doc.filename == "notes.md"
    assert doc.sha256
    assert doc.text == _MD

    docs = await svc.list_documents(kb)
    assert len(docs) == 1


async def test_add_document_same_text_creates_second_row(fake_embedder, db_session, kb):
    """There is no DB unique constraint on sha256, so re-uploading identical
    text creates a second doc row. Retrieve still surfaces the content."""
    svc = KnowledgeService(db_session)
    first = await svc.add_document(kb, "notes.md", _MD)
    second = await svc.add_document(kb, "notes2.md", _MD)
    assert first.id != second.id
    assert first.sha256 == second.sha256
    assert len(await svc.list_documents(kb)) == 2
    chunks = svc.retrieve(kb, "安装", top_k=5, min_score=0.0)
    assert len(chunks) >= 1


async def test_add_document_unknown_kb_raises(fake_embedder, db_session):
    svc = KnowledgeService(db_session)
    with pytest.raises(ValueError, match="not found"):
        await svc.add_document("nope", "notes.md", _MD)


# --------------------------------------------------------------- delete doc


async def test_delete_document(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    doc = await svc.add_document(kb, "notes.md", _MD)
    assert await svc.delete_document(kb, doc.id) is True
    assert len(await svc.list_documents(kb)) == 0
    assert await svc.delete_document(kb, doc.id) is False


# ----------------------------------------------------------------- retrieve


async def test_retrieve_returns_chunks(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    await svc.add_document(kb, "notes.md", _MD)
    chunks = svc.retrieve(kb, "安装", top_k=3, min_score=0.0)
    assert len(chunks) >= 1
    for c in chunks:
        assert 0.0 <= c.score <= 1.0
        assert c.filename == "notes.md"
        assert c.chunk_text
        assert c.doc_id


async def test_retrieve_min_score_filter(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    await svc.add_document(kb, "notes.md", _MD)
    # score = 1 - distance; a min_score of 1.0 (exact) filters everything
    # because hash vectors of different texts are not identical.
    assert svc.retrieve(kb, "安装", top_k=5, min_score=1.0) == []


async def test_retrieve_empty_kb(fake_embedder, db_session, kb):
    svc = KnowledgeService(db_session)
    # No docs indexed → collection doesn't exist yet → retrieve returns [].
    assert svc.retrieve(kb, "anything") == []


async def test_retrieve_unknown_kb(fake_embedder, db_session):
    svc = KnowledgeService(db_session)
    # Collection for unknown kb doesn't exist → [].
    assert svc.retrieve("nonexistent", "q") == []
