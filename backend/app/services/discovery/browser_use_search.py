"""
Browser-use AI agent search: drives a real Chromium browser via Ollama LLM
with built-in stealth (anti-detection flags, ad-blocker, cookie-banner
dismisser, ClearURLs).  Uses DuckDuckGo by default (fewer CAPTCHAs) and
leverages the package's built-in ``find_elements`` action for zero-cost
link extraction.

Provides two public entry points:
  * ``browser_use_collect_links``   – general web search (all URLs)
  * ``browser_use_collect_linkedin_posts`` – LinkedIn post-specific search
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urlparse

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("discovery.browser_use")

_browser_use_loaded: bool = False
Agent: Any = None
BrowserProfile: Any = None
BrowserSession: Any = None
ChatOllama: Any = None
Tools: Any = None


def _ensure_browser_use() -> bool:
    """Lazy-import browser-use on first use so it never blocks server startup."""
    global _browser_use_loaded, Agent, BrowserProfile, BrowserSession, ChatOllama, Tools
    if _browser_use_loaded:
        return Agent is not None
    _browser_use_loaded = True
    try:
        from browser_use import Agent as _A, BrowserProfile as _BP, BrowserSession as _BS  # type: ignore
        from browser_use import ChatOllama as _CO, Tools as _T  # type: ignore
        Agent = _A
        BrowserProfile = _BP
        BrowserSession = _BS
        ChatOllama = _CO
        Tools = _T
        return True
    except Exception:
        return False


_REALISTIC_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

_BLOCKED_HOSTS = frozenset({
    "duckduckgo.com", "google.com", "www.google.com", "bing.com",
    "www.bing.com", "search.brave.com", "brave.com",
})


def _activity_id_to_date(aid: int) -> datetime | None:
    if aid <= 0:
        return None
    try:
        ts_ms = aid >> 22
        return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    except Exception:
        return None


def _extract_linkedin_post_urls(text: str) -> list[str]:
    raw: list[str] = []
    for m in re.findall(
        r"https?://(?:www\.)?linkedin\.com/(?:posts/[^\s\"'<>)]+|feed/update/[^\s\"'<>)]+)",
        text,
    ):
        raw.append(m.split("?")[0].rstrip("/"))
    seen: set[str] = set()
    out: list[str] = []
    for u in raw:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _get_ollama_model() -> str:
    return getattr(settings, "BROWSER_USE_OLLAMA_MODEL", "") or getattr(
        settings, "LLM_MODEL", "frob/qwen3.5-instruct:9b"
    )


def _get_ollama_host() -> str:
    base = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434") or "http://localhost:11434"
    return base.replace("/v1", "").rstrip("/")


def _ddg_time_filter(tf: str) -> str:
    return {"day": "d", "week": "w", "month": "m", "year": "y"}.get(tf, "m")


def _make_browser_profile() -> Any:
    return BrowserProfile(
        headless=True,
        enable_default_extensions=True,
        chromium_sandbox=False,
        user_agent=_REALISTIC_UA,
        wait_between_actions=1.0,
        minimum_wait_page_load_time=3.0,
        wait_for_network_idle_page_load_time=2.0,
        highlight_elements=False,
    )


def _is_result_link(url: str) -> bool:
    """Keep external content links, drop search-engine chrome."""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return bool(host) and host not in _BLOCKED_HOSTS


# ---------------------------------------------------------------------------
#  General-purpose web search (all URLs)
# ---------------------------------------------------------------------------


async def _browser_use_search_general(
    query: str,
    *,
    max_results: int = 20,
    time_filter: str = "month",
    max_agent_steps: int = 15,
) -> dict[str, Any]:
    """Navigate DuckDuckGo, extract all result links via CSS selector."""
    _ensure_browser_use()
    if Agent is None:
        log.warning("browser_use_not_installed")
        return {"urls": [], "total": 0, "error": "browser_use_not_installed", "agent_steps": 0}

    df = _ddg_time_filter(time_filter)
    encoded_q = quote_plus(query)
    search_url = f"https://duckduckgo.com/?q={encoded_q}&df={df}&ia=web"

    collected_urls: list[str] = []
    log.info("browser_use_general_start", query=query[:80], search_url=search_url[:120])

    try:
        llm = ChatOllama(model=_get_ollama_model(), host=_get_ollama_host())
        browser = BrowserSession(browser_profile=_make_browser_profile())
        tools = Tools()

        @tools.action(description="Save a URL you found in the search results.")
        def save_url(url: str) -> str:
            clean = url.split("?")[0].rstrip("/")
            if _is_result_link(clean):
                if clean not in collected_urls:
                    collected_urls.append(clean)
                    return f"Saved ({len(collected_urls)} total): {clean}"
                return f"Already saved: {clean}"
            return f"Skipped (search engine URL): {url}"

        task = f"""Collect result URLs from DuckDuckGo search results.

Steps:
1. Navigate to: {search_url}
2. Wait 3 seconds for the page to load.
3. Use the find_elements action with selector 'a.result__a' and attributes ["href"] to extract result links.
   If that gives no results, try selector 'a[data-testid="result-title-a"]' or 'a[href^="http"]'.
4. For every href that points to an external site (not duckduckgo.com), call save_url with the full URL.
5. Scroll down to see more results.
6. Repeat steps 3-5 until you have saved at least {min(max_results, 15)} URLs or no more results appear.
7. When done, call the done action.

IMPORTANT: Use find_elements to extract links. Do NOT click individual results."""

        agent = Agent(
            task=task, llm=llm, browser=browser, tools=tools,
            max_steps=max_agent_steps, use_vision=False, flash_mode=True,
        )
        result = await agent.run()
        steps = len(result.actions()) if hasattr(result, "actions") else 0

        try:
            for page in await browser.get_all_pages():
                try:
                    html = await page.content()
                    for m in re.findall(r'href="(https?://[^"]+)"', html):
                        clean = m.split("?")[0].rstrip("/")
                        if _is_result_link(clean) and clean not in collected_urls:
                            collected_urls.append(clean)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            await browser.close()
        except Exception:
            pass

    except Exception as exc:
        log.warning("browser_use_general_error", error=str(exc)[:300], query=query[:60])
        return {"urls": [], "total": 0, "error": str(exc)[:300], "agent_steps": 0}

    log.info("browser_use_general_done", urls_found=len(collected_urls), steps=steps, query=query[:60])
    return {"urls": collected_urls[:max_results], "total": len(collected_urls), "agent_steps": steps, "error": None}


async def browser_use_collect_links(
    queries: list[str],
    *,
    max_links_per_query: int = 20,
    time_filter: str = "month",
) -> dict[str, Any]:
    """
    General-purpose web search via browser-use + DuckDuckGo.
    Returns the same shape as ``google_search_collect_links_browser``.
    """
    by_query: dict[str, list[dict[str, Any]]] = {}
    dedup: dict[str, dict[str, Any]] = {}
    total_steps = 0
    errors: list[str] = []

    for raw_q in queries or []:
        q = (raw_q or "").strip()
        if not q:
            continue
        result = await _browser_use_search_general(
            q, max_results=max_links_per_query, time_filter=time_filter,
        )
        total_steps += result.get("agent_steps", 0)
        if result.get("error"):
            errors.append(f"{q}: {result['error']}")

        items: list[dict[str, Any]] = []
        for idx, url in enumerate(result.get("urls") or [], start=1):
            host = urlparse(url).netloc.lower()
            score = round(1.0 / idx, 6)
            if ".edu" in host or ".ac." in host:
                score += 0.35
            if "linkedin.com" in host:
                score += 0.10
            item = {"url": url, "host": host, "query": q, "rank": idx, "score": round(score, 6), "source": "browser_use"}
            items.append(item)
            if url not in dedup or item["score"] > dedup[url]["score"]:
                dedup[url] = item
        by_query[q] = items
        await asyncio.sleep(2)

    deduped_sorted = sorted(dedup.values(), key=lambda x: x["score"], reverse=True)
    return {
        "engine": "browser_use",
        "available": Agent is not None,
        "fallback_used": False,
        "queries_count": len(by_query),
        "per_query": by_query,
        "deduped_results": deduped_sorted,
        "total_deduped": len(deduped_sorted),
        "agent_steps": total_steps,
        "errors": errors or None,
    }


# ---------------------------------------------------------------------------
#  LinkedIn post-specific search
# ---------------------------------------------------------------------------


async def _browser_use_search_linkedin(
    query: str,
    *,
    max_results: int = 30,
    time_filter: str = "month",
    max_agent_steps: int = 20,
) -> dict[str, Any]:
    _ensure_browser_use()
    if Agent is None:
        log.warning("browser_use_not_installed")
        return {"urls": [], "total": 0, "error": "browser_use_not_installed", "agent_steps": 0}

    df = _ddg_time_filter(time_filter)
    search_q = f'site:linkedin.com/posts "{query}"'
    encoded_q = quote_plus(search_q)
    search_url = f"https://duckduckgo.com/?q={encoded_q}&df={df}&ia=web"

    collected_urls: list[str] = []
    all_page_texts: list[str] = []
    log.info("browser_use_linkedin_start", query=query[:80], search_url=search_url[:120])

    try:
        llm = ChatOllama(model=_get_ollama_model(), host=_get_ollama_host())
        browser = BrowserSession(browser_profile=_make_browser_profile())
        tools = Tools()

        @tools.action(description="Save a LinkedIn post URL. Pass the full URL.")
        def save_linkedin_url(url: str) -> str:
            clean = url.split("?")[0].rstrip("/")
            if "linkedin.com" in clean and ("/posts/" in clean or "/feed/update/" in clean):
                if clean not in collected_urls:
                    collected_urls.append(clean)
                    return f"Saved ({len(collected_urls)} total): {clean}"
                return f"Already saved: {clean}"
            return f"Skipped (not a LinkedIn post URL): {url}"

        task = f"""Collect LinkedIn post URLs from DuckDuckGo search results.

Steps:
1. Navigate to: {search_url}
2. Wait 3 seconds for the page to load.
3. Use the find_elements action with selector 'a[href*="linkedin.com"]' and attributes ["href"] to extract all LinkedIn links on the page.
4. For every href that contains "linkedin.com/posts/" or "linkedin.com/feed/update/", call save_linkedin_url with the full URL.
5. Scroll down to see more results.
6. Repeat steps 3-5 until you have saved at least {min(max_results, 20)} URLs or no more results appear.
7. When done, call the done action.

IMPORTANT: Use find_elements to extract links. Do NOT click individual results."""

        agent = Agent(
            task=task, llm=llm, browser=browser, tools=tools,
            max_steps=max_agent_steps, use_vision=False, flash_mode=True,
        )
        result = await agent.run()
        steps = len(result.actions()) if hasattr(result, "actions") else 0

        try:
            for page in await browser.get_all_pages():
                try:
                    all_page_texts.append(await page.content())
                except Exception:
                    pass
        except Exception:
            pass

        try:
            await browser.close()
        except Exception:
            pass

    except Exception as exc:
        log.warning("browser_use_linkedin_error", error=str(exc)[:300], query=query[:60])
        return {"urls": [], "total": 0, "error": str(exc)[:300], "agent_steps": 0}

    for text in all_page_texts:
        for url in _extract_linkedin_post_urls(text):
            if url not in collected_urls:
                collected_urls.append(url)

    log.info("browser_use_linkedin_done", urls_found=len(collected_urls), steps=steps, query=query[:60])
    return {"urls": collected_urls[:max_results], "total": len(collected_urls), "agent_steps": steps, "error": None}


async def browser_use_collect_linkedin_posts(
    queries: list[str],
    *,
    max_links_per_query: int = 30,
    time_filter: str = "month",
) -> dict[str, Any]:
    """
    High-level wrapper: run browser-use LinkedIn search for multiple queries,
    deduplicate, and return scored results with recency from activity IDs.
    """
    all_urls: list[str] = []
    per_query: dict[str, list[str]] = {}
    errors: list[str] = []
    total_steps = 0

    for raw_q in queries or []:
        q = (raw_q or "").strip()
        if not q:
            continue
        result = await _browser_use_search_linkedin(
            q, max_results=max_links_per_query, time_filter=time_filter,
        )
        query_urls = result.get("urls") or []
        per_query[q] = query_urls
        for u in query_urls:
            if u not in all_urls:
                all_urls.append(u)
        total_steps += result.get("agent_steps", 0)
        if result.get("error"):
            errors.append(f"{q}: {result['error']}")
        await asyncio.sleep(2)

    now = datetime.now(timezone.utc)
    scored: list[dict[str, Any]] = []
    for rank, url in enumerate(all_urls, start=1):
        aid_match = re.search(r"activity[:\-](\d{10,})", url)
        activity_id = int(aid_match.group(1)) if aid_match else None
        post_date = _activity_id_to_date(activity_id) if activity_id else None
        age_days = (now - post_date).days if post_date else None

        recency_score = 0.0
        if age_days is not None:
            if age_days <= 7:
                recency_score = 1.0
            elif age_days <= 30:
                recency_score = 0.8
            elif age_days <= 90:
                recency_score = 0.5
            elif age_days <= 180:
                recency_score = 0.3
            elif age_days <= 365:
                recency_score = 0.15
            else:
                recency_score = 0.05

        rank_score = 1.0 / rank
        score = round(rank_score * 0.3 + recency_score * 0.7, 4)

        scored.append({
            "url": url, "rank": rank, "score": score,
            "activity_id": activity_id,
            "post_date": post_date.isoformat() if post_date else None,
            "age_days": age_days, "recency_score": recency_score,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    return {
        "provider": "browser_use",
        "queries_count": len(per_query),
        "per_query": per_query,
        "ranked_results": scored,
        "total": len(scored),
        "agent_steps": total_steps,
        "errors": errors or None,
    }
