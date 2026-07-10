import io
import json
from unittest.mock import patch

import httpx
import pytest
from docx import Document

from main import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_list_models(client):
    response = await client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 11  # default seeded models
    assert any(m["model_id"] == "gpt-5.5" for m in data)


async def test_create_and_get_conversation(client):
    create_resp = await client.post("/api/conversations", json={})
    assert create_resp.status_code == 200
    conv = create_resp.json()
    conv_id = conv["id"]

    get_resp = await client.get(f"/api/conversations/{conv_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == conv_id


async def test_rename_conversation(client):
    create_resp = await client.post("/api/conversations", json={"title": "Old"})
    conv_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/api/conversations/{conv_id}", json={"title": "New"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "New"


async def test_delete_conversation(client):
    create_resp = await client.post("/api/conversations", json={})
    conv_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/conversations/{conv_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    get_resp = await client.get(f"/api/conversations/{conv_id}")
    assert get_resp.status_code == 404


async def test_upload_txt(client):
    response = await client.post(
        "/api/upload",
        files={"file": ("test.txt", io.BytesIO(b"Hello world"), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test.txt"
    assert data["text_content"] == "Hello world"


async def test_upload_docx(client):
    buffer = io.BytesIO()
    doc = Document()
    doc.add_paragraph("DOCX content")
    doc.save(buffer)
    buffer.seek(0)

    response = await client.post(
        "/api/upload",
        files={"file": ("test.docx", buffer, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    assert response.json()["text_content"] == "DOCX content"


async def test_upload_unsupported(client):
    response = await client.post(
        "/api/upload",
        files={"file": ("test.png", io.BytesIO(b"data"), "image/png")},
    )
    assert response.status_code == 400


async def test_chat_stream_creates_conversation(client):
    with patch("app.routers.chat.get_adapter_by_model_id") as mock_factory:
        async def fake_stream(*args, **kwargs):
            yield type("Chunk", (), {"content": "Hi", "finish_reason": None})()
            yield type("Chunk", (), {"content": "", "finish_reason": "stop"})()

        mock_factory.return_value.stream_chat = fake_stream

        response = await client.post(
            "/api/chat",
            json={
                "model": "gpt-5.5",
                "messages": [{"role": "user", "content": "Hello"}],
                "effort": 0.7,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        body = response.text
        assert 'text/event-stream' in response.headers["content-type"]
        assert "data:" in body
