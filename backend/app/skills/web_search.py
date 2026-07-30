"""Web-search skill - Tavily search via the official `tavily-python` SDK.

Phase 3 round 2: replaces the DuckDuckGo-based skill (which was unreliable
due to aggressive rate limiting / silent IP blocks) with Tavily, an AI-agent-
oriented search API. Uses ``AsyncTavilyClient`` so the call is natively async -
no ``asyncio.to_thread`` / connection-pool lifecycle to manage.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.skills.base import SkillResult

# Imported at module level (tavily-python is a hard dependency) so tests can
# patch ``app.skills.web_search.AsyncTavilyClient``.
from tavily import AsyncTavilyClient  # noqa: E402

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RESULTS = 5
_MAX_RESULTS_CAP = 10
_MIN_RESULTS_CAP = 1


class WebSearchSkill:
    """Search the web using Tavily and return formatted results.

    The skill is stateless - each ``run()`` call creates a fresh
    ``AsyncTavilyClient``. Network/SDK errors are surfaced as error-shaped
    results rather than raised, so the ReAct loop can carry on.
    """

    name = "web_search"
    description = (
        "Search the web via Tavily and return the top results with title, "
        "URL, and snippet. Use when you need up-to-date or factual information "
        "that is beyond your knowledge cutoff. Pass a concise search query "
        "(English keywords usually work well)."
    )

    async def run(self, input: str = "", args: dict[str, Any] | None = None) -> SkillResult:
        args = args or {}
        query = (input or "").strip()
        # Strip surrounding quotes - models often wrap Action Input in quotes,
        # which forces exact-phrase matching and yields fewer hits.
        if len(query) >= 2 and query[0] == query[-1] and query[0] in ('"', "'", "“", "”"):
            query = query[1:-1].strip()
        if not query:
            return {
                "output": "[web_search: empty query - please provide a search term]",
                "metadata": {"error": True},
            }

        api_key = settings.tavily_api_key
        if not api_key:
            return {
                "output": "[web_search: TAVILY_API_KEY not configured. Set it in backend/.env to enable web search.]",
                "metadata": {"error": True},
            }

        max_results_raw = args.get("max_results", _DEFAULT_MAX_RESULTS)
        try:
            max_results = int(max_results_raw)
        except (ValueError, TypeError):
            max_results = _DEFAULT_MAX_RESULTS
        max_results = max(_MIN_RESULTS_CAP, min(max_results, _MAX_RESULTS_CAP))

        client = AsyncTavilyClient(api_key=api_key)
        try:
            response = await client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",
            )
        except Exception as exc:  # noqa: BLE001 - surface to loop, don't crash
            logger.warning("web_search failed for query=%r: %s", query, exc)
            return {
                "output": f"[web_search error: {exc}]",
                "metadata": {"error": True, "query": query},
            }

        results: list[dict[str, Any]] = response.get("results", []) if isinstance(response, dict) else []
        if not results:
            return {
                "output": f"[web_search: no results for '{query}']",
                "metadata": {"query": query, "count": 0},
            }

        lines: list[str] = []
        for i, r in enumerate(results, 1):
            title = (r.get("title") or "").strip()
            href = (r.get("url") or "").strip()
            body = (r.get("content") or "").strip()
            lines.append(f"{i}. **{title}**\n   {href}\n   {body}")

        return {
            "output": "\n\n".join(lines),
            "metadata": {
                "query": query,
                "count": len(results),
                "results": [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
                    for r in results
                ],
            },
        }


SKILL = WebSearchSkill()

__all__ = ["WebSearchSkill", "SKILL"]
