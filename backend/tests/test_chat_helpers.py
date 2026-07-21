"""Tests for _chat_helpers (attach_files_to_messages + inject_retrieved_context)."""
from __future__ import annotations

from types import SimpleNamespace

from app.services._chat_helpers import attach_files_to_messages, inject_retrieved_context


def _chunk(filename, heading, text):
    return SimpleNamespace(filename=filename, heading=heading, text=text)


def test_inject_retrieved_context_prepends_to_last_user_message():
    messages = [
        {"role": "user", "content": "original question"},
        {"role": "assistant", "content": "prev answer"},
        {"role": "user", "content": "new question"},
    ]
    chunks = [_chunk("notes.md", "安装", "用 uv 安装。")]
    out = inject_retrieved_context(messages, chunks)
    # Original content preserved after the injected section.
    assert out[-1]["content"].endswith("new question")
    assert "[知识库检索结果]" in out[-1]["content"]
    assert "[以下为用户原始问题]" in out[-1]["content"]
    assert "用 uv 安装。" in out[-1]["content"]
    assert "[来源: notes.md #安装]" in out[-1]["content"]
    # Other messages untouched.
    assert out[0]["content"] == "original question"
    assert out[1]["content"] == "prev answer"
    # Original list not mutated.
    assert messages[-1]["content"] == "new question"


def test_inject_retrieved_context_empty_chunks_is_noop():
    messages = [{"role": "user", "content": "q"}]
    out = inject_retrieved_context(messages, [])
    assert out == messages


def test_inject_retrieved_context_no_user_message():
    messages = [{"role": "assistant", "content": "a"}]
    out = inject_retrieved_context(messages, [_chunk("n.md", "", "t")])
    # No user message to mutate → returned unchanged (shallow copy).
    assert out[0]["content"] == "a"


def test_inject_retrieved_context_heading_omitted_when_empty():
    messages = [{"role": "user", "content": "q"}]
    out = inject_retrieved_context(messages, [_chunk("n.md", "", "text")])
    # No trailing " #" when heading is empty.
    assert "[来源: n.md]" in out[0]["content"]
    assert "#]" not in out[0]["content"].replace("[来源: n.md]", "")


def test_attach_files_still_appends_after_inject():
    """Files attach after RAG injection in the chat router; both should
    coexist on the same user message."""
    messages = [{"role": "user", "content": "q"}]
    messages = inject_retrieved_context(messages, [_chunk("n.md", "h", "rag text")])
    file_obj = SimpleNamespace(name="data.csv", content="col1,col2")
    messages = attach_files_to_messages(messages, [file_obj])
    content = messages[-1]["content"]
    assert "[知识库检索结果]" in content
    assert "[文件: data.csv]" in content
    assert content.endswith("col1,col2")
