"""Web-search skill - DuckDuckGo text search via the `duckduckgo_search` library.

Phase 3 first round: gives the agent a `web_search` tool so it can retrieve
live web information during ReAct reasoning. The underlying library is the
same one that LangChain's `DuckDuckGoSearchResults` wraps, but we call it
directly to avoid pulling in the full `langchain-community` dependency.

Robustness notes:
  * Surrounding quotes are stripped from the query (models often wrap the
    `Action Input` in quotes, which forces DuckDuckGo into exact-phrase mode
    and returns far fewer hits).
  * DuckDuckGo aggressively rate-limits / silently blocks IPs after a handful
    of requests, returning an empty list instead of raising. We retry across
    backends (``auto`` -> ``html`` -> ``lite``) with a short backoff so a
    transient block on one backend doesn't immediately fail the turn.
"""
from __future__ import annotations

import asyncio
import logging
import time
import warnings
from typing import Any

from app.skills.base import SkillResult

logger = logging.getLogger(__name__)

# The `duckduckgo_search` package was renamed to `ddgs`; the old name still
# works but emits a RuntimeWarning on every DDGS() instantiation. Register a
# persistent filter (catch_warnings() is thread-local and doesn't cover the
# asyncio.to_thread worker) so the warning doesn't spam agent SSE logs.
warnings.filterwarnings(
    "ignore",
    message=r".*duckduckgo_search.*has been renamed.*",
    category=RuntimeWarning,
)

_DEFAULT_MAX_RESULTS = 5
_MAX_RESULTS_CAP = 10
_MIN_RESULTS_CAP = 1
# Backends tried in order; each gets a fresh DDGS() so a blocked session on one
# doesn't carry over. `lite` is last - it's the most reliable but tersest.
_SEARCH_BACKENDS = ("auto", "html", "lite")
_RETRY_DELAYS = (0.0, 1.5, 1.5)  # seconds before each backend attempt


class WebSearchSkill:
    """Search the web using DuckDuckGo and return formatted results.

    The skill is stateless - each ``run()`` call opens fresh ``DDGS``
    contexts. Network errors and rate limits are surfaced as error-shaped
    results rather than raised, so the ReAct loop can carry on.
    """

    name = "web_search"
    description = (
        "Search the web via DuckDuckGo and return the top results with title, "
        "URL, and snippet. Use when you need up-to-date or factual information "
        "that is beyond your knowledge cutoff. Pass a concise search query "
        "(English keywords usually work better than long Chinese phrases)."
    )

    async def run(self, input: str = "", args: dict[str, Any] | None = None) -> SkillResult:
        args = args or {}
        query = (input or "").strip()
        # Strip surrounding quotes - models often wrap Action Input in quotes,
        # which forces DuckDuckGo exact-phrase matching and yields fewer hits.
        if len(query) >= 2 and query[0] == query[-1] and query[0] in ('"', "'", "“", "”"):
            query = query[1:-1].strip()
        if not query:
            return {
                "output": "[web_search: empty query - please provide a search term]",
                "metadata": {"error": True},
            }

        max_results_raw = args.get("max_results", _DEFAULT_MAX_RESULTS)
        try:
            max_results = int(max_results_raw)
        except (ValueError, TypeError):
            max_results = _DEFAULT_MAX_RESULTS
        max_results = max(_MIN_RESULTS_CAP, min(max_results, _MAX_RESULTS_CAP))

        region = str(args.get("region", "wt-wt"))

        results: list[dict[str, str]] = []
        last_error: str | None = None
        for i, backend in enumerate(_SEARCH_BACKENDS):
            if _RETRY_DELAYS[i]:
                await asyncio.sleep(_RETRY_DELAYS[i])
            try:
                got = await asyncio.to_thread(_search_sync, query, max_results, region, backend)
                if got:
                    results = got
                    break
                logger.info("web_search backend=%s returned 0 results for query=%r", backend, query)
            except ImportError:
                return {
                    "output": "[web_search: duckduckgo-search package is not installed]",
                    "metadata": {"error": True},
                }
            except Exception as exc:  # noqa: BLE001 - try next backend
                last_error = f"{exc}"
                logger.warning("web_search backend=%s failed for query=%r: %s", backend, query, exc)

        if not results:
            msg = f"[web_search: no results for '{query}'"
            if last_error:
                msg += f" (last error: {last_error})"
            msg += ". DuckDuckGo may be rate-limiting this host; try again later or rephrase with English keywords.]"
            return {
                "output": msg,
                "metadata": {"query": query, "count": 0, "error": True, "last_error": last_error},
            }

        lines: list[str] = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "").strip()
            href = r.get("href", "").strip()
            body = r.get("body", "").strip()
            lines.append(f"{i}. **{title}**\n   {href}\n   {body}")

        return {
            "output": "\n\n".join(lines),
            "metadata": {
                "query": query,
                "count": len(results),
                "results": [
                    {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                    for r in results
                ],
            },
        }


def _search_sync(query: str, max_results: int, region: str, backend: str) -> list[dict[str, str]]:
    """Synchronous search callable, offloaded to a thread by ``asyncio.to_thread``."""
    from duckduckgo_search import DDGS

    with DDGS() as ddgs:
        return list(
            ddgs.text(
                query,
                region=region,
                max_results=max_results,
                safesearch="moderate",
                backend=backend,
            )
        )


SKILL = WebSearchSkill()

__all__ = ["WebSearchSkill", "SKILL"]