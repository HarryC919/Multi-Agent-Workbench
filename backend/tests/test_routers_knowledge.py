"""End-to-end router tests for the knowledge base API (phase 2b-i, refactored).

Uses httpx ASGITransport against the real app. A deterministic fake embedder
+ temp chroma dir isolate these from the real bge model and on-disk store.
"""
from __future__ import annotations

import hashlib

import httpx
import pytest
from main import app

from app.services.embedding_service import EmbeddingService
from app.services.knowledge_service import KnowledgeService

_FAKE_DIM = 1024


def _hash_vec(text: str, dim: int = _FAKE_DIM) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [float(h[i % len(h)]) for i in range(dim)]
    norm = sum(v * v for v in raw) ** 0.5 or 1.0
    return [v / norm for v in raw]


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.knowledge_service.settings.chroma_persist_dir",
        str(tmp_path / ".chroma"),
    )
    KnowledgeService._chroma_client_singleton = None

    emb = EmbeddingService.instance()
    monkeypatch.setattr(
        emb, "embed_texts", lambda texts: [_hash_vec(t) for t in texts]
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
    KnowledgeService._chroma_client_singleton = None


_MD = "# 安装\n\n用 uv 安装 fastapi。\n\n# 部署\n\ndocker compose up。\n"


async def test_list_returns_array(client):
    resp = await client.get("/api/knowledge-bases")
    assert resp.status_code == 200
    assert isinstance(resp.json()["knowledge_bases"], list)


async def test_create_and_list_knowledge_base(client):
    before = await client.get("/api/knowledge-bases")
    count_before = len(before.json()["knowledge_bases"])

    resp = await client.post(
        "/api/knowledge-bases", json={"name": "我的笔记", "description": "d"}
    )
    assert resp.status_code == 200, resp.text
    kb = resp.json()
    assert kb["name"] == "我的笔记"
    assert kb["document_count"] == 0

    listing = await client.get("/api/knowledge-bases")
    names = [k["name"] for k in listing.json()["knowledge_bases"]]
    assert "我的笔记" in names
    assert len(listing.json()["knowledge_bases"]) == count_before + 1


async def test_delete_knowledge_base(client):
    kb = (await client.post("/api/knowledge-bases", json={"name": "k"})).json()
    resp = await client.delete(f"/api/knowledge-bases/{kb['id']}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert (await client.delete(f"/api/knowledge-bases/{kb['id']}")).status_code == 404


async def test_upload_document_and_list(client):
    kb = (await client.post("/api/knowledge-bases", json={"name": "k"})).json()
    resp = await client.post(
        f"/api/knowledge-bases/{kb['id']}/documents",
        files={"file": ("notes.md", _MD.encode("utf-8"), "text/markdown")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["filename"] == "notes.md"
    assert data["knowledge_base_id"] == kb["id"]
    assert data["text_length"] == len(_MD)

    docs = await client.get(f"/api/knowledge-bases/{kb['id']}/documents")
    assert docs.status_code == 200
    assert len(docs.json()["documents"]) == 1
    assert docs.json()["documents"][0]["filename"] == "notes.md"


async def test_upload_document_rejects_bad_type(client):
    kb = (await client.post("/api/knowledge-bases", json={"name": "k"})).json()
    resp = await client.post(
        f"/api/knowledge-bases/{kb['id']}/documents",
        files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert resp.status_code == 400
    assert ".md" in resp.json()["detail"]


async def test_upload_document_unknown_kb(client):
    resp = await client.post(
        "/api/knowledge-bases/nonexistent/documents",
        files={"file": ("notes.md", _MD.encode("utf-8"), "text/markdown")},
    )
    assert resp.status_code == 404


async def test_delete_document(client):
    kb = (await client.post("/api/knowledge-bases", json={"name": "k"})).json()
    upload = await client.post(
        f"/api/knowledge-bases/{kb['id']}/documents",
        files={"file": ("notes.md", _MD.encode("utf-8"), "text/markdown")},
    )
    doc_id = upload.json()["id"]
    resp = await client.delete(f"/api/knowledge-bases/{kb['id']}/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    docs = await client.get(f"/api/knowledge-bases/{kb['id']}/documents")
    assert len(docs.json()["documents"]) == 0


async def test_list_documents_unknown_kb(client):
    resp = await client.get("/api/knowledge-bases/nonexistent/documents")
    assert resp.status_code == 404
