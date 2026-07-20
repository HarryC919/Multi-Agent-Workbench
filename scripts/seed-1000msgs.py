#!/usr/bin/env python3
"""Seed a conversation with 1000 messages into the backend SQLite DB.

Usage:
    python scripts/seed-1000msgs.py [path_to_db]

Defaults to backend/workbench.db. Safe to re-run: a new conversation is
created each invocation. Intended for manually verifying the virtual
scroller's smoothness at the 1000-message threshold (DEVELOPMENT_PLAN
acceptance criterion #5).
"""
from __future__ import annotations

import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("backend/workbench.db")
    if not db_path.exists():
        print(f"DB not found at {db_path.resolve()}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        conv_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conv_id, "Perf batch 1000", now, now),
        )

        rows = []
        for i in range(1000):
            role = "user" if i % 2 == 0 else "assistant"
            content = f"Message {i}: " + ("lorem ipsum " * 20)
            rows.append(
                (
                    str(uuid.uuid4()),
                    conv_id,
                    role,
                    content,
                    "",        # thinking
                    "mock-model" if role == "assistant" else None,
                    "done",
                    now,
                )
            )
        cur.executemany(
            """INSERT INTO messages
               (id, conversation_id, role, content, thinking, model, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
        print(f"Inserted conversation {conv_id} with 1000 messages into {db_path}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())