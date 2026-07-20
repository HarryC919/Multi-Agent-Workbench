#!/usr/bin/env python3
"""Manual smoke test for POST /api/agent-chat (AgentService phase 1).

Streams the SSE response from a locally-running backend and prints each
chunk type to stdout so you can verify the ReAct loop end-to-end with a
real model (e.g. DeepSeek).

Usage:
    # 1. Start the backend in another terminal:
    #    cd backend && uv run uvicorn main:app --reload
    # 2. Make sure at least one model is configured with a working key
    #    (e.g. DEEPSEEK_API_KEY in backend/.env).
    # 3. Run this script:
    #    python scripts/test-agent-chat.py [--model deepseek-chat] \\
    #        [--prompt "用一句话介绍 ReAct 算法"] [--max-steps 4]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

DEFAULT_URL = "http://localhost:8000/api/agent-chat"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default=DEFAULT_URL, help=f"Agent endpoint (default: {DEFAULT_URL})")
    ap.add_argument("--model", default="deepseek-chat", help="model_id to test against")
    ap.add_argument("--prompt", default="用一句话介绍 ReAct 算法。", help="user prompt")
    ap.add_argument("--max-steps", type=int, default=8, help="ReAct loop cap")
    ap.add_argument("--thinking", action="store_true", help="forward thinking flag")
    args = ap.parse_args()

    body = json.dumps(
        {
            "model": args.model,
            "messages": [{"role": "user", "content": args.prompt}],
            "stream": True,
            "thinking": args.thinking,
            "max_steps": args.max_steps,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        args.url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )

    print(f"POST {req.full_url}\nmodel={args.model} max_steps={args.max_steps}\n---")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if not line:
                    continue
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                t = payload.get("type")
                if t == "text":
                    print(payload.get("content", ""), end="", flush=True)
                elif t == "thinking":
                    print(f"\33[2m{payload.get('content', '')}\33[0m", end="", flush=True)
                elif t == "done":
                    print(f"\n[done finish_reason={payload.get('finish_reason')}]")
                    break
                elif t == "error":
                    print(f"\n[error: {payload.get('message')}]", file=sys.stderr)
                    return 1
                elif t == "warning":
                    print(f"\n[warning: {payload.get('message')}]", file=sys.stderr)
                else:
                    print(f"\n[{t}: {payload}]", file=sys.stderr)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())