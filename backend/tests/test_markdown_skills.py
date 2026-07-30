"""Tests for markdown-defined skills (Phase 3 task 1).

Covers: YAML frontmatter parsing, fallback name/description, discovery,
reload, LLM invocation, and the GET /api/skills source field.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from app.skills.markdown_skill import MarkdownSkill, parse_markdown_skill
from app.skills.registry import discover_markdown_skills, reload_markdown_skills, _REGISTRY


# ------------------------------------------------------------------ helpers


def _write_md(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ------------------------------------------------------------------ parse_markdown_skill


def test_parse_with_full_frontmatter(tmp_path: Path):
    p = _write_md(
        tmp_path / "test_skill.md",
        textwrap.dedent("""\
        ---
        name: my_skill
        description: A custom skill for testing
        ---
        You are a helpful assistant. Answer concisely.
        """),
    )
    skill = parse_markdown_skill(p)
    assert skill is not None
    assert skill.name == "my_skill"
    assert skill.description == "A custom skill for testing"
    assert "You are a helpful assistant" in skill.instructions


def test_parse_frontmatter_without_description(tmp_path: Path):
    p = _write_md(
        tmp_path / "no_desc.md",
        textwrap.dedent("""\
        ---
        name: simple_skill
        ---
        # Simple Skill

        Just do the thing.
        """),
    )
    skill = parse_markdown_skill(p)
    assert skill is not None
    assert skill.name == "simple_skill"
    assert skill.description == "Simple Skill"  # from first heading
    assert "Just do the thing" in skill.instructions


def test_parse_no_frontmatter(tmp_path: Path):
    p = _write_md(
        tmp_path / "my_skill.md",
        textwrap.dedent("""\
        # My Skill Title

        This is the skill body.
        """),
    )
    skill = parse_markdown_skill(p)
    assert skill is not None
    assert skill.name == "my_skill"  # filename stem
    assert skill.description == "My Skill Title"  # first heading
    assert "This is the skill body" in skill.instructions


def test_parse_empty_file_returns_none(tmp_path: Path):
    p = _write_md(tmp_path / "empty.md", "")
    skill = parse_markdown_skill(p)
    assert skill is None


def test_parse_invalid_yaml_returns_skill_with_fallback(tmp_path: Path):
    p = _write_md(
        tmp_path / "bad_yaml.md",
        textwrap.dedent("""\
        ---
        name: [invalid: yaml: here
        ---
        # Fallback Skill

        Body text.
        """),
    )
    skill = parse_markdown_skill(p)
    assert skill is not None
    assert skill.name == "bad_yaml"  # filename fallback
    assert skill.description == "Fallback Skill"  # heading fallback


# ------------------------------------------------------------------ discover / reload


def test_discover_registers_markdown_skills(tmp_path: Path):
    _write_md(
        tmp_path / "alpha.md",
        textwrap.dedent("""\
        ---
        name: alpha
        description: First skill
        ---
        Do alpha things.
        """),
    )
    _write_md(
        tmp_path / "beta.md",
        textwrap.dedent("""\
        # Beta Skill
        Do beta things.
        """),
    )
    registered = discover_markdown_skills(tmp_path)
    assert len(registered) == 2
    names = {s.name for s in registered}
    assert names == {"alpha", "beta"}


def test_discover_skips_duplicate_names(tmp_path: Path):
    _write_md(
        tmp_path / "first.md",
        textwrap.dedent("""\
        ---
        name: echo
        description: Should be skipped
        ---
        Body.
        """),
    )
    registered = discover_markdown_skills(tmp_path)
    assert len(registered) == 0  # "echo" already in _REGISTRY


def test_reload_clears_and_reimports(tmp_path: Path):
    _write_md(
        tmp_path / "gamma.md",
        textwrap.dedent("""\
        ---
        name: gamma
        description: Gamma skill
        ---
        Gamma body.
        """),
    )
    # First load
    registered = discover_markdown_skills(tmp_path)
    assert len(registered) == 1
    assert "gamma" in _REGISTRY

    # Reload with same file
    count = reload_markdown_skills(tmp_path)
    assert count == 1
    assert "gamma" in _REGISTRY

    # Reload with no files
    # Remove the file and reload
    (tmp_path / "gamma.md").unlink()
    count = reload_markdown_skills(tmp_path)
    assert count == 0
    assert "gamma" not in _REGISTRY


# ------------------------------------------------------------------ MarkdownSkill.run


@pytest.mark.asyncio
async def test_markdown_skill_run_calls_llm():
    """Verify that run() sends the correct messages to the chat model."""
    skill = MarkdownSkill(
        name="test",
        description="Test skill",
        instructions="You are a test assistant.",
    )

    # Create an async mock for ainvoke (MagicMock can't be awaited).
    class _MockModel:
        async def ainvoke(self, messages):
            self._last_messages = messages
            return _MockResult(content="Mocked LLM response")

    class _MockResult:
        def __init__(self, content):
            self.content = content

    mock_model = _MockModel()
    skill.set_chat_model(mock_model)
    result = await skill.run(input="Hello")

    # Verify the LLM was called with correct messages.
    call_args = mock_model._last_messages
    assert len(call_args) == 2
    assert call_args[0].content == "You are a test assistant."  # system
    assert call_args[0].type == "system"
    assert call_args[1].content == "Hello"  # user
    assert call_args[1].type == "human"

    assert result["output"] == "Mocked LLM response"
    assert result["metadata"] == {"skill_name": "test"}


@pytest.mark.asyncio
async def test_markdown_skill_run_without_model_returns_error():
    skill = MarkdownSkill(
        name="orphan",
        description="No model",
        instructions="Instructions.",
    )
    result = await skill.run(input="test")
    assert "no chat model configured" in result["output"]
    assert result["metadata"]["error"] is True


@pytest.mark.asyncio
async def test_markdown_skill_run_llm_error_returns_error_shape():
    skill = MarkdownSkill(
        name="failing",
        description="Will fail",
        instructions="Instructions.",
    )

    class _FailingModel:
        async def ainvoke(self, messages):
            raise RuntimeError("Boom!")

    skill.set_chat_model(_FailingModel())
    result = await skill.run(input="test")
    assert "[markdown skill 'failing' error:" in result["output"]
    assert result["metadata"]["error"] is True


# ------------------------------------------------------------------ API tests


def test_list_skills_includes_source_field():
    client = TestClient(app)
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    items = resp.json()["skills"]
    for item in items:
        assert "source" in item
        assert item["source"] in ("python", "markdown")

    # Built-in skills should be source=python
    echo_item = next(it for it in items if it["name"] == "echo")
    assert echo_item["source"] == "python"


def test_reload_endpoint():
    client = TestClient(app)
    resp = client.post("/api/skills/reload")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "reloaded" in body