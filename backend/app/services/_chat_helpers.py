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