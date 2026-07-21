"""Pure-function helpers shared by /api/chat and /api/agent-chat routers.

Kept dependency-free so they can be imported from both routers and tests
without pulling in a service class.
"""
from __future__ import annotations

from typing import Any


def attach_files_to_messages(messages: list[dict[str, Any]], files: list[Any]) -> list[dict[str, Any]]:
    """Append file text blocks to the trailing user message.

    ``files`` is any iterable of objects exposing ``.name`` and ``.content``
    (pydantic ``FileContent`` or duck-typed equivalents). The returned list
    is a shallow copy so callers may safely mutate it.
    """
    if not files:
        return messages

    file_texts = "\n\n".join(f"[文件: {f.name}]\n{f.content}" for f in files)
    out = [dict(m) for m in messages]
    for i in range(len(out) - 1, -1, -1):
        if out[i].get("role") == "user":
            out[i]["content"] = f"{out[i]['content']}\n\n{file_texts}"
            break
    return out


def inject_retrieved_context(messages: list[dict[str, Any]], chunks: list[Any]) -> list[dict[str, Any]]:
    """Prepend retrieved knowledge-base chunks to the trailing user message.

    Used by the normal chat path when a KB is selected: retrieved top-K
    passages are surfaced as a ``[知识库检索结果]`` section **before** the
    user's original question (which is preserved verbatim). ``chunks`` is any
    iterable of objects exposing ``.filename``, ``.heading``, and ``.text``
    (pydantic ``RetrievedChunk`` or duck-typed equivalents). Returns a shallow
    copy; a no-op when ``chunks`` is empty.
    """
    chunks = list(chunks)
    if not chunks:
        return messages

    block = "\n\n".join(
        f"[来源: {c.filename}{' #' + c.heading if c.heading else ''}]\n{c.text}" for c in chunks
    )
    retrieved_section = f"[知识库检索结果]\n{block}\n\n[以下为用户原始问题]"
    out = [dict(m) for m in messages]
    for i in range(len(out) - 1, -1, -1):
        if out[i].get("role") == "user":
            out[i]["content"] = f"{retrieved_section}\n\n{out[i]['content']}"
            break
    return out
