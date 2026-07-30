"""Tests for the web_search skill (Phase 3 round 2 - Tavily).

All tests mock ``tavily.AsyncTavilyClient`` to avoid real network calls.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.skills.web_search import WebSearchSkill


def _fake_skill() -> WebSearchSkill:
    return WebSearchSkill()


def _mock_search_return(results: list[dict]) -> dict:
    return {"results": results, "query": "test", "response_time": 0.5}


# ------------------------------------------------------------------ unit tests


@pytest.mark.asyncio
async def test_web_search_empty_query_returns_error():
    skill = _fake_skill()
    result = await skill.run(input="", args={})
    assert result["output"].startswith("[web_search: empty query")
    assert result["metadata"]["error"] is True


@pytest.mark.asyncio
async def test_web_search_empty_key_returns_error():
    skill = _fake_skill()
    with patch("app.skills.web_search.settings") as mock_settings:
        mock_settings.tavily_api_key = ""
        result = await skill.run(input="test", args={})
    assert "TAVILY_API_KEY not configured" in result["output"]
    assert result["metadata"]["error"] is True


@pytest.mark.asyncio
async def test_web_search_strips_surrounding_quotes():
    skill = _fake_skill()
    fake = _mock_search_return([{"title": "T", "url": "https://a.com", "content": "B"}])
    with (
        patch("app.skills.web_search.settings") as mock_settings,
        patch("app.skills.web_search.AsyncTavilyClient") as mock_cls,
    ):
        mock_settings.tavily_api_key = "test-key"
        mock_cls.return_value.search = AsyncMock(return_value=fake)
        await skill.run(input='"Unity Documentation"', args={})
    # The query passed to search should have quotes stripped.
    call_kwargs = mock_cls.return_value.search.call_args.kwargs
    assert call_kwargs["query"] == "Unity Documentation"


@pytest.mark.asyncio
async def test_web_search_returns_formatted_results():
    skill = _fake_skill()
    fake = _mock_search_return([
        {"title": "Python 3.13", "url": "https://example.com/py313", "content": "Python 3.13 is out."},
        {"title": "Learn Python", "url": "https://example.com/learn", "content": "A tutorial."},
    ])
    with (
        patch("app.skills.web_search.settings") as mock_settings,
        patch("app.skills.web_search.AsyncTavilyClient") as mock_cls,
    ):
        mock_settings.tavily_api_key = "test-key"
        mock_cls.return_value.search = AsyncMock(return_value=fake)
        result = await skill.run(input="Python release", args={})

    assert "[web_search:" not in result["output"]
    assert "Python 3.13" in result["output"]
    assert "https://example.com/py313" in result["output"]
    assert "Python 3.13 is out" in result["output"]
    assert result["metadata"]["count"] == 2
    assert result["metadata"]["results"][0]["title"] == "Python 3.13"
    # snippet maps from Tavily's content field.
    assert result["metadata"]["results"][0]["snippet"] == "Python 3.13 is out."


@pytest.mark.asyncio
async def test_web_search_no_results():
    skill = _fake_skill()
    with (
        patch("app.skills.web_search.settings") as mock_settings,
        patch("app.skills.web_search.AsyncTavilyClient") as mock_cls,
    ):
        mock_settings.tavily_api_key = "test-key"
        mock_cls.return_value.search = AsyncMock(return_value=_mock_search_return([]))
        result = await skill.run(input="xyzzy_nonexistent", args={})
    assert "no results" in result["output"]
    assert result["metadata"]["count"] == 0


@pytest.mark.asyncio
async def test_web_search_respects_max_results():
    skill = _fake_skill()
    fake = _mock_search_return([{"title": f"R{i}", "url": f"https://a.com/{i}", "content": "B"} for i in range(3)])
    with (
        patch("app.skills.web_search.settings") as mock_settings,
        patch("app.skills.web_search.AsyncTavilyClient") as mock_cls,
    ):
        mock_settings.tavily_api_key = "test-key"
        mock_cls.return_value.search = AsyncMock(return_value=fake)
        result = await skill.run(input="test", args={"max_results": 3})
    call_kwargs = mock_cls.return_value.search.call_args.kwargs
    assert call_kwargs["max_results"] == 3
    assert result["metadata"]["count"] == 3


@pytest.mark.asyncio
async def test_web_search_max_results_clamped():
    skill = _fake_skill()
    fake = _mock_search_return([{"title": "R", "url": "https://a.com", "content": "B"}])
    with (
        patch("app.skills.web_search.settings") as mock_settings,
        patch("app.skills.web_search.AsyncTavilyClient") as mock_cls,
    ):
        mock_settings.tavily_api_key = "test-key"
        mock_cls.return_value.search = AsyncMock(return_value=fake)
        await skill.run(input="test", args={"max_results": 0})
    # max_results=0 clamped to 1.
    assert mock_cls.return_value.search.call_args.kwargs["max_results"] == 1


@pytest.mark.asyncio
async def test_web_search_sdk_error_returns_error_shape():
    skill = _fake_skill()
    with (
        patch("app.skills.web_search.settings") as mock_settings,
        patch("app.skills.web_search.AsyncTavilyClient") as mock_cls,
    ):
        mock_settings.tavily_api_key = "test-key"
        mock_cls.return_value.search = AsyncMock(side_effect=RuntimeError("API timeout"))
        result = await skill.run(input="test", args={})
    assert "[web_search error:" in result["output"]
    assert "API timeout" in result["output"]
    assert result["metadata"]["error"] is True


@pytest.mark.asyncio
async def test_web_search_passes_search_depth_basic():
    skill = _fake_skill()
    fake = _mock_search_return([{"title": "T", "url": "https://a.com", "content": "B"}])
    with (
        patch("app.skills.web_search.settings") as mock_settings,
        patch("app.skills.web_search.AsyncTavilyClient") as mock_cls,
    ):
        mock_settings.tavily_api_key = "test-key"
        mock_cls.return_value.search = AsyncMock(return_value=fake)
        await skill.run(input="test", args={})
    assert mock_cls.return_value.search.call_args.kwargs["search_depth"] == "basic"


# ------------------------------------------------------------------ API tests


def test_web_search_skill_appears_in_list():
    client = TestClient(app)
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["skills"]}
    assert "web_search" in names


def test_invoke_web_search_returns_ok():
    """End-to-end: invokes the real skill but with a mocked AsyncTavilyClient."""
    client = TestClient(app)
    fake = _mock_search_return([
        {"title": "Test Title", "url": "https://test.example.com", "content": "Test body."},
    ])
    with (
        patch("app.skills.web_search.settings") as mock_settings,
        patch("app.skills.web_search.AsyncTavilyClient") as mock_cls,
    ):
        mock_settings.tavily_api_key = "test-key"
        mock_cls.return_value.search = AsyncMock(return_value=fake)
        resp = client.post("/api/skills/web_search", json={"input": "test query"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["skill"] == "web_search"
    assert "Test Title" in body["output"]
    assert body["metadata"]["query"] == "test query"
    assert body["metadata"]["count"] == 1
