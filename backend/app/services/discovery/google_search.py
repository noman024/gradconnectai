"""
Google search ingestion (MVP): query -> links collection -> dedupe -> scoring.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from urllib.parse import quote_plus, unquote, urlparse
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.timezone import now_dhaka

logger = get_logger("discovery.google_search")


GOOGLE_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)
SEARCH_REQUEST_TIMEOUT_S = 8.0
_PROXY_ROTATE_INDEX = 0
_GOOGLE_COOLDOWN_UNTIL: datetime | None = None
_BRAVE_COOLDOWN_UNTIL: datetime | None = None
_BRAVE_LAST_REQUEST: float = 0.0
_BRAVE_MIN_INTERVAL_S = 1.5


def _now() -> datetime:
    return now_dhaka()


def _split_csv(value: str | None) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def _provider_order() -> list[str]:
    configured = _split_csv(getattr(settings, "SEARCH_PROVIDER_ORDER", "brave,bing,bing_rss,google,duckduckgo"))
    allowed = {"google", "bing", "bing_rss", "duckduckgo", "brave"}
    order = [p for p in configured if p in allowed]
    return order or ["brave", "bing", "bing_rss", "google", "duckduckgo"]


def _proxy_pool() -> list[str]:
    return _split_csv(getattr(settings, "SEARCH_PROXY_URLS", ""))


def _next_proxy() -> str | None:
    global _PROXY_ROTATE_INDEX
    pool = _proxy_pool()
    if not pool:
        return None
    chosen = pool[_PROXY_ROTATE_INDEX % len(pool)]
    _PROXY_ROTATE_INDEX += 1
    return chosen


def _google_on_cooldown() -> bool:
    return _GOOGLE_COOLDOWN_UNTIL is not None and _GOOGLE_COOLDOWN_UNTIL > _now()


def _mark_google_cooldown() -> None:
    global _GOOGLE_COOLDOWN_UNTIL
    seconds = max(10, int(getattr(settings, "SEARCH_GOOGLE_COOLDOWN_SECONDS", 300) or 300))
    _GOOGLE_COOLDOWN_UNTIL = _now() + timedelta(seconds=seconds)


def _brave_on_cooldown() -> bool:
    return _BRAVE_COOLDOWN_UNTIL is not None and _BRAVE_COOLDOWN_UNTIL > _now()


def _mark_brave_cooldown() -> None:
    global _BRAVE_COOLDOWN_UNTIL
    _BRAVE_COOLDOWN_UNTIL = _now() + timedelta(seconds=60)


async def _brave_throttle() -> None:
    """Enforce minimum interval between Brave requests to avoid 429s."""
    import time
    global _BRAVE_LAST_REQUEST
    now = time.monotonic()
    elapsed = now - _BRAVE_LAST_REQUEST
    if elapsed < _BRAVE_MIN_INTERVAL_S:
        await asyncio.sleep(_BRAVE_MIN_INTERVAL_S - elapsed)
    _BRAVE_LAST_REQUEST = time.monotonic()


def build_google_search_url(query: str, num: int = 10) -> str:
    q = quote_plus((query or "").strip())
    n = max(1, min(int(num), 20))
    return f"https://www.google.com/search?q={q}&num={n}&hl=en"


def _normalize_result_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    # Common Google redirect wrapper.
    if u.startswith("/url?q="):
        u = u[len("/url?q="):]
        u = u.split("&", 1)[0]
        u = unquote(u)
    return u


def extract_google_result_links_from_html(html: str) -> list[str]:
    """
    Parse Google result links from search HTML by extracting /url?q=... anchors.
    """
    if not html:
        return []
    links: list[str] = []
    pattern = re.compile(r'href="(/url\?q=[^"]+)"')
    for m in pattern.findall(html):
        u = _normalize_result_url(m)
        if not u:
            continue
        if u.startswith("http://") or u.startswith("https://"):
            links.append(u)
    # Fallback: extract direct result anchors where Google serves plain URLs.
    if not links:
        links.extend(extract_http_links_from_html(html))
    return links


def extract_http_links_from_html(html: str) -> list[str]:
    """
    Generic fallback extractor for absolute http(s) links from HTML.
    """
    if not html:
        return []
    links: list[str] = []
    # 1) Absolute links.
    for href in re.findall(r'href="(https?://[^"]+)"', html):
        u = href.strip()
        if not u:
            continue
        if any(bad in u for bad in ("google.com/preferences", "google.com/search?", "accounts.google.com")):
            continue
        netloc = (urlparse(u).netloc or "").lower()
        if any(
            blocked in netloc
            for blocked in (
                "google.com",
                "www.google.com",
                "bing.com",
                "www.bing.com",
                "duckduckgo.com",
                "www.duckduckgo.com",
                "brave.com",
                "search.brave.com",
            )
        ):
            continue
        links.append(u)
    # 2) DuckDuckGo redirect links: /l/?uddg=<encoded_target>
    for href in re.findall(r'href="(/l/\?[^"]+)"', html):
        m = re.search(r"uddg=([^&]+)", href)
        if not m:
            continue
        u = unquote(m.group(1)).strip()
        if u.startswith(("http://", "https://")):
            links.append(u)
    # 3) Generic Google redirect links.
    for href in re.findall(r'href="(/url\?q=[^"]+)"', html):
        u = _normalize_result_url(href)
        if u.startswith(("http://", "https://")):
            links.append(u)
    # Preserve order with dedupe.
    seen: set[str] = set()
    out: list[str] = []
    for u in links:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def build_duckduckgo_search_url(query: str) -> str:
    q = quote_plus((query or "").strip())
    return f"https://duckduckgo.com/html/?q={q}"


def build_brave_search_url(query: str, num: int = 20) -> str:
    q = quote_plus((query or "").strip())
    n = max(1, min(int(num), 50))
    return f"https://search.brave.com/search?q={q}&count={n}&source=web"


def build_bing_search_url(query: str, num: int = 10) -> str:
    q = quote_plus((query or "").strip())
    n = max(1, min(int(num), 50))
    return f"https://www.bing.com/search?q={q}&count={n}"


def build_bing_rss_search_url(query: str) -> str:
    q = quote_plus((query or "").strip())
    return f"https://www.bing.com/search?format=rss&setlang=en-US&mkt=en-US&q={q}"


def extract_links_from_bing_rss(xml_text: str) -> list[str]:
    if not xml_text:
        return []
    links = re.findall(r"<link>(.*?)</link>", xml_text)
    out: list[str] = []
    for u in links:
        url = (u or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        parsed = urlparse(url)
        netloc = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        if "bing.com" in netloc and path == "/search":
            continue
        out.append(url)
    # order-preserving dedupe
    seen: set[str] = set()
    uniq: list[str] = []
    for u in out:
        if u in seen:
            continue
        seen.add(u)
        uniq.append(u)
    return uniq


async def collect_links_for_query(
    query: str,
    *,
    max_links: int,
    headers: dict[str, str] | None = None,
    providers: list[str] | None = None,
) -> tuple[list[str], str]:
    """
    Collect links for one query using configured provider order and optional proxy rotation.
    Returns (links, provider_used).
    """
    n = max(1, min(int(max_links), 20))
    provider_list = providers or _provider_order()
    hdrs = headers or {
        "User-Agent": GOOGLE_UA,
        "Accept-Language": "en-US,en;q=0.9",
    }

    _brave_hdrs = dict(hdrs)
    _brave_hdrs["Accept-Encoding"] = "gzip, deflate"

    logger.info("search_query_start", query=query[:80], providers=provider_list)
    for provider in provider_list:
        if provider == "google":
            if not bool(getattr(settings, "SEARCH_ENABLE_GOOGLE", True)):
                logger.debug("search_provider_skip", provider="google", reason="disabled")
                continue
            if _google_on_cooldown():
                logger.debug("search_provider_skip", provider="google", reason="cooldown")
                continue
        if provider == "brave" and _brave_on_cooldown():
            logger.debug("search_provider_skip", provider="brave", reason="cooldown")
            continue
        proxy = _next_proxy()
        try:
            async with httpx.AsyncClient(
                timeout=SEARCH_REQUEST_TIMEOUT_S,
                headers=_brave_hdrs if provider == "brave" else hdrs,
                follow_redirects=True,
                proxy=proxy,
            ) as client:
                if provider == "brave":
                    await _brave_throttle()
                    resp = await client.get(build_brave_search_url(query, num=n))
                    links: list[str] = []
                    if resp.status_code == 200:
                        links = extract_http_links_from_html(resp.text)[:n]
                    if resp.status_code == 429:
                        logger.warning("search_brave_429", query=query[:60])
                        _mark_brave_cooldown()
                    if links:
                        logger.info("search_provider_hit", provider="brave", links=len(links), query=query[:60])
                        return links, "brave"
                    logger.debug("search_provider_miss", provider="brave", status=resp.status_code, query=query[:60])
                    continue
                if provider == "google":
                    resp = await client.get(build_google_search_url(query, num=n))
                    links = []
                    if resp.status_code == 200:
                        links = extract_google_result_links_from_html(resp.text)[:n]
                    if resp.status_code == 429 or "google.com/sorry" in str(resp.url):
                        logger.warning("search_google_429", query=query[:60])
                        _mark_google_cooldown()
                    if links:
                        logger.info("search_provider_hit", provider="google", links=len(links), query=query[:60])
                        return links, "google"
                    logger.debug("search_provider_miss", provider="google", status=resp.status_code, query=query[:60])
                    continue
                if provider == "bing":
                    resp = await client.get(build_bing_search_url(query, num=n))
                    if resp.status_code == 200:
                        links = extract_http_links_from_html(resp.text)[:n]
                        if links:
                            logger.info("search_provider_hit", provider="bing", links=len(links), query=query[:60])
                            return links, "bing"
                    logger.debug("search_provider_miss", provider="bing", status=resp.status_code, query=query[:60])
                    continue
                if provider == "bing_rss":
                    resp = await client.get(build_bing_rss_search_url(query))
                    if resp.status_code == 200:
                        links = extract_links_from_bing_rss(resp.text)[:n]
                        if links:
                            logger.info("search_provider_hit", provider="bing_rss", links=len(links), query=query[:60])
                            return links, "bing_rss"
                    logger.debug("search_provider_miss", provider="bing_rss", status=resp.status_code, query=query[:60])
                    continue
                if provider == "duckduckgo":
                    resp = await client.get(build_duckduckgo_search_url(query))
                    if resp.status_code == 200:
                        links = extract_http_links_from_html(resp.text)[:n]
                        if links:
                            logger.info("search_provider_hit", provider="duckduckgo", links=len(links), query=query[:60])
                            return links, "duckduckgo"
                    logger.debug("search_provider_miss", provider="duckduckgo", status=resp.status_code, query=query[:60])
                    continue
        except Exception as exc:
            logger.warning("search_provider_error", provider=provider, error=str(exc)[:120], query=query[:60])
            continue
    logger.warning("search_all_providers_failed", query=query[:80])
    return [], "none"


def _score_url_for_query(url: str, query: str, rank: int) -> float:
    u = (url or "").lower()
    q = (query or "").lower()
    score = 1.0 / max(rank, 1)
    if ".edu" in u or ".ac." in u:
        score += 0.3
    if "scholar.google" in u:
        score += 0.2
    # Mild lexical overlap with query terms.
    q_terms = [t for t in re.split(r"\W+", q) if len(t) > 2]
    overlap = sum(1 for t in q_terms if t in u)
    score += min(0.4, overlap * 0.05)
    return round(score, 6)


async def google_search_collect_links(
    queries: list[str],
    *,
    max_links_per_query: int = 10,
) -> dict[str, Any]:
    """
    Fetch Google search result pages and return deduped/scored links.
    """
    out_by_query: dict[str, list[dict[str, Any]]] = {}
    dedupe: dict[str, dict[str, Any]] = {}
    n = max(1, min(int(max_links_per_query), 20))

    headers = {
        "User-Agent": GOOGLE_UA,
        "Accept-Language": "en-US,en;q=0.9",
    }

    for q in queries or []:
        query = (q or "").strip()
        if not query:
            continue
        links, provider = await collect_links_for_query(
            query,
            max_links=n,
            headers=headers,
        )
        q_items: list[dict[str, Any]] = []
        for idx, link in enumerate(links, start=1):
            parsed = urlparse(link)
            host = parsed.netloc.lower()
            item = {
                "url": link,
                "host": host,
                "query": query,
                "rank": idx,
                "score": _score_url_for_query(link, query, idx),
                "search_provider": provider,
            }
            q_items.append(item)
            if link not in dedupe or item["score"] > dedupe[link]["score"]:
                dedupe[link] = item
        out_by_query[query] = q_items

    deduped_sorted = sorted(dedupe.values(), key=lambda x: x["score"], reverse=True)
    return {
        "queries_count": len([q for q in queries or [] if (q or "").strip()]),
        "per_query": out_by_query,
        "deduped_results": deduped_sorted,
        "total_deduped": len(deduped_sorted),
    }
