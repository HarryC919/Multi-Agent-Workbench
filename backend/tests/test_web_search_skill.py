"""Tests for the web_search skill (Phase 3 task 2).

All tests mock ``duckduckgo_search.DDGS`` to avoid real network calls.
The retry/backoff machinery is neutralized via ``_RETRY_DELAYS`` so the
suite stays fast.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.skills import web_search as ws_module
from app.skills.web_search import WebSearchSkill


def _fake_skill() -> WebSearchSkill:
    return WebSearchSkill()


# Neutralize retry backoff so error/no-result tests don't sleep.
_NO_DELAY = (0.0, 0.0, 0.0)


# ------------------------------------------------------------------ unit tests


@pytest.mark.asyncio
async def test_web_search_empty_query_returns_error():
    skill = _fake_skill()
    result = await skill.run(input="", args={})
    assert result["output"].startswith("[web_search: empty query")
    assert result["metadata"]["error"] is True


@pytest.mark.asyncio
async def test_web_search_strips_surrounding_quotes():
    skill = _fake_skill()
    fake_results = [{"title": "T", "href": "https://a.com", "body": "B"}]
    with (
        patch.object(ws_module, "_RETRY_DELAYS", _NO_DELAY),
        patch("app.skills.web_search._search_sync", return_value=fake_results) as mock_search,
    ):
        result = await skill.run(input='"Unity Documentation"', args={})
    # The query passed to _search_sync should have quotes stripped.
    assert mock_search.call_args[0][0] == "Unity Documentation"
    assert result["metadata"]["query"] == "Unity Documentation"


@pytest.mark.asyncio
async def test_web_search_returns_formatted_results():
    skill = _fake_skill()
    fake_results = [
        {"title": "Python 3.13 Released", "href": "https://example.com/py313", "body": "Python 3.13 is now available."},
        {"title": "Learn Python", "href": "https://example.com/learn", "body": "A comprehensive Python tutorial."},
    ]

    with (
        patch.object(ws_module, "_RETRY_DELAYS", _NO_DELAY),
        patch("app.skills.web_search._search_sync", return_value=fake_results),
    ):
        result = await skill.run(input="Python latest release", args={})

    assert "[web_search:" not in result["output"]
    assert "Python 3.13 Released" in result["output"]
    assert "https://example.com/py313" in result["output"]
    assert "Python 3.13 is now available" in result["output"]
    assert result["metadata"]["count"] == 2
    assert len(result["metadata"]["results"]) == 2
    assert result["metadata"]["results"][0]["title"] == "Python 3.13 Released"


@pytest.mark.asyncio
async def test_web_search_no_results():
    skill = _fake_skill()
    with (
        patch.object(ws_module, "_RETRY_DELAYS", _NO_DELAY),
        patch("app.skills.web_search._search_sync", return_value=[]),
    ):
        result = await skill.run(input="xyzzy_nonexistent_12345", args={})
    assert "no results" in result["output"]
    assert result["metadata"]["count"] == 0


@pytest.mark.asyncio
async def test_web_search_respects_max_results():
    skill = _fake_skill()
    fake_results = [
        {"title": "R1", "href": "https://a.com/1", "body": "B1"},
        {"title": "R2", "href": "https://a.com/2", "body": "B2"},
        {"title": "R3", "href": "https://a.com/3", "body": "B3"},
    ]

    with (
        patch.object(ws_module, "_RETRY_DELAYS", _NO_DELAY),
        patch("app.skills.web_search._search_sync", return_value=fake_results[:3]),
    ):
        result = await skill.run(input="test", args={"max_results": 3})
    assert result["metadata"]["count"] == 3


@pytest.mark.asyncio
async def test_web_search_max_results_clamped():
    skill = _fake_skill()
    fake_results = [{"title": "R", "href": "https://a.com", "body": "B"}]
    # max_results=0 -> clamped to 1
    with (
        patch.object(ws_module, "_RETRY_DELAYS", _NO_DELAY),
        patch("app.skills.web_search._search_sync", return_value=fake_results[:1]),
    ):
        result = await skill.run(input="test", args={"max_results": 0})
    assert result["metadata"]["count"] == 1


@pytest.mark.asyncio
async def test_web_search_retries_across_backends():
    """First backend returns [], second returns results -> skill recovers."""
    skill = _fake_skill()
    fake_results = [{"title": "Found", "href": "https://b.com", "body": "B"}]

    call_count = {"n": 0}

    def _side_effect(query, max_results, region, backend):
        call_count["n"] += 1
        return fake_results if call_count["n"] >= 2 else []

    with (
        patch.object(ws_module, "_RETRY_DELAYS", _NO_DELAY),
        patch("app.skills.web_search._search_sync", side_effect=_side_effect),
    ):
        result = await skill.run(input="test", args={})
    assert result["metadata"]["count"] == 1
    assert call_count["n"] == 2  # first backend empty, second succeeded


@pytest.mark.asyncio
async def test_web_search_all_backends_fail_returns_error_shape():
    skill = _fake_skill()
    with (
        patch.object(ws_module, "_RETRY_DELAYS", _NO_DELAY),
        patch("app.skills.web_search._search_sync", side_effect=RuntimeError("Connection refused")),
    ):
        result = await skill.run(input="test", args={})
    # All backends raised -> error shape with last_error.
    assert "no results" in result["output"]
    assert "Connection refused" in result["output"]
    assert result["metadata"]["error"] is True
    assert result["metadata"]["last_error"] is not None


# ------------------------------------------------------------------ API tests


def test_web_search_skill_appears_in_list():
    client = TestClient(app)
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["skills"]}
    assert "web_search" in names


def test_invoke_web_search_returns_ok():
    """End-to-end: invokes the real skill but with a mocked _search_sync."""
    client = TestClient(app)
    fake_results = [
        {"title": "Test Title", "href": "https://test.example.com", "body": "Test body text."},
    ]
    with (
        patch.object(ws_module, "_RETRY_DELAYS", _NO_DELAY),
        patch("app.skills.web_search._search_sync", return_value=fake_results),
    ):
        resp = client.post("/api/skills/web_search", json={"input": "test query"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["skill"] == "web_search"
    assert "Test Title" in body["output"]
    assert body["metadata"]["query"] == "test query"
    assert body["metadata"]["count"] == 1
