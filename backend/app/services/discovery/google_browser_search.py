"""
Browser-based Google search ingestion using Playwright.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.services.discovery.google_search import build_google_search_url, extract_google_result_links_from_html

try:
    from playwright.async_api import async_playwright  # type: ignore
except Exception:  # pragma: no cover - optional/runtime dependency
    async_playwright = None  # type: ignore


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
    # Lightweight lexical overlap boost.
    for token in [t for t in q.replace('"', " ").split() if len(t) > 2][:8]:
        if token in u:
            score += 0.03
    return round(score, 6)


async def google_search_collect_links_browser(
    queries: list[str],
    *,
    max_links_per_query: int = 10,
) -> dict[str, Any]:
    n = max(1, min(int(max_links_per_query), 20))
    if async_playwright is None:
        return {
            "engine": "playwright",
            "available": False,
            "error": "playwright_not_installed",
            "queries_count": len([q for q in queries or [] if (q or "").strip()]),
            "per_query": {},
            "deduped_results": [],
            "total_deduped": 0,
        }

    by_query: dict[str, list[dict[str, Any]]] = {}
    dedup: dict[str, dict[str, Any]] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=bool(settings.GOOGLE_BROWSER_HEADLESS))
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
        )
        try:
            for raw_q in queries or []:
                query = (raw_q or "").strip()
                if not query:
                    continue
                page = await context.new_page()
                items: list[dict[str, Any]] = []
                try:
                    url = build_google_search_url(query, n)
                    await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=int(settings.GOOGLE_BROWSER_TIMEOUT_MS),
                    )
                    await page.wait_for_timeout(int(settings.GOOGLE_BROWSER_WAIT_MS))
                    html = await page.content()
                    links = extract_google_result_links_from_html(html)[:n]
                    for idx, link in enumerate(links, start=1):
                        host = urlparse(link).netloc.lower()
                        item = {
                            "url": link,
                            "host": host,
                            "query": query,
                            "rank": idx,
                            "score": _score_google_url(link, query, idx),
                            "source": "browser",
                        }
                        items.append(item)
                        if link not in dedup or item["score"] > dedup[link]["score"]:
                            dedup[link] = item
                except Exception:
                    items = []
                finally:
                    await page.close()
                by_query[query] = items
        finally:
            await context.close()
            await browser.close()

    deduped_sorted = sorted(dedup.values(), key=lambda x: x["score"], reverse=True)
    return {
        "engine": "playwright",
        "available": True,
        "queries_count": len(by_query),
        "per_query": by_query,
        "deduped_results": deduped_sorted,
        "total_deduped": len(deduped_sorted),
    }
