"""
Browser-based search ingestion using browser-use AI agent.

Replaces the previous raw-Playwright approach with browser-use which
provides built-in anti-detection (stealth flags, ad-blocker, cookie-banner
dismisser) and uses DuckDuckGo (fewer CAPTCHAs than Google/Brave from
VPN IPs).

Falls back to the HTTP search collector if browser-use is unavailable.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.core.logging import get_logger
from app.services.discovery.google_search import google_search_collect_links
from app.services.discovery.browser_use_search import browser_use_collect_links, _ensure_browser_use

logger = get_logger("discovery.google_browser_search")


def _score_google_url(url: str, query: str, rank: int) -> float:
    u = (url or "").lower()
    q = (query or "").lower()
    score = 1.0 / max(1, rank)
    if ".edu" in u or ".ac." in u:
        score += 0.35
    if "scholar.google.com" in u:
        score += 0.2
    if "linkedin.com" in u:
        score += 0.1
    for token in [t for t in q.replace('"', " ").split() if len(t) > 2][:8]:
        if token in u:
            score += 0.03
    return round(score, 6)


async def google_search_collect_links_browser(
    queries: list[str],
    *,
    max_links_per_query: int = 10,
) -> dict[str, Any]:
    """
    Collect and score web links using browser-use + DuckDuckGo.
    Falls back to HTTP search if browser-use is not available.
    """
    n = max(1, min(int(max_links_per_query), 20))

    if not _ensure_browser_use():
        logger.info("browser_use_unavailable_fallback_http", queries_count=len(queries or []))
        fallback = await google_search_collect_links(queries, max_links_per_query=n)
        return {
            "engine": "browser_use",
            "available": False,
            "fallback_used": True,
            "error": "browser_use_not_installed",
            "queries_count": fallback.get("queries_count"),
            "per_query": fallback.get("per_query"),
            "deduped_results": fallback.get("deduped_results"),
            "total_deduped": fallback.get("total_deduped"),
        }

    logger.info("browser_use_search_start", queries_count=len(queries or []), max_links=n)
    try:
        result = await browser_use_collect_links(queries, max_links_per_query=n)
    except Exception as exc:
        fallback = await google_search_collect_links(queries, max_links_per_query=n)
        return {
            "engine": "browser_use",
            "available": True,
            "fallback_used": True,
            "error": f"browser_use_failed:{type(exc).__name__}",
            "queries_count": fallback.get("queries_count"),
            "per_query": fallback.get("per_query"),
            "deduped_results": fallback.get("deduped_results"),
            "total_deduped": fallback.get("total_deduped"),
        }

    if not result.get("deduped_results"):
        fallback = await google_search_collect_links(queries, max_links_per_query=n)
        return {
            "engine": "browser_use",
            "available": True,
            "fallback_used": True,
            "queries_count": fallback.get("queries_count"),
            "per_query": fallback.get("per_query"),
            "deduped_results": fallback.get("deduped_results"),
            "total_deduped": fallback.get("total_deduped"),
        }

    by_query = result.get("per_query") or {}
    rescored_by_query: dict[str, list[dict[str, Any]]] = {}
    dedup: dict[str, dict[str, Any]] = {}

    for q, items in by_query.items():
        rescored: list[dict[str, Any]] = []
        for item in items:
            url = item.get("url", "")
            rank = item.get("rank", 1)
            new_score = _score_google_url(url, q, rank)
            enriched = {**item, "score": new_score, "source": "browser"}
            rescored.append(enriched)
            if url not in dedup or new_score > dedup[url]["score"]:
                dedup[url] = enriched
        rescored_by_query[q] = rescored

    deduped_sorted = sorted(dedup.values(), key=lambda x: x["score"], reverse=True)
    return {
        "engine": "browser_use",
        "available": True,
        "fallback_used": False,
        "queries_count": len(rescored_by_query),
        "per_query": rescored_by_query,
        "deduped_results": deduped_sorted,
        "total_deduped": len(deduped_sorted),
    }
