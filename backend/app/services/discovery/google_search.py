"""
Google search ingestion (MVP): query -> links collection -> dedupe -> scoring.
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus, unquote, urlparse
from typing import Any

import httpx


GOOGLE_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


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

    async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
        for q in queries or []:
            query = (q or "").strip()
            if not query:
                continue
            url = build_google_search_url(query, num=n)
            try:
                resp = await client.get(url)
            except Exception:
                resp = None
            links: list[str] = []
            provider = "google"
            if resp is not None and resp.status_code == 200:
                links = extract_google_result_links_from_html(resp.text)[:n]
            # Fallback provider if Google returns no parseable links.
            if not links:
                try:
                    ddg = await client.get(build_duckduckgo_search_url(query))
                    if ddg.status_code == 200:
                        links = extract_http_links_from_html(ddg.text)[:n]
                        provider = "duckduckgo"
                except Exception:
                    links = []
            if not links:
                try:
                    bing = await client.get(build_bing_search_url(query, num=n))
                    if bing.status_code == 200:
                        links = extract_http_links_from_html(bing.text)[:n]
                        provider = "bing"
                except Exception:
                    links = []
            if not links:
                try:
                    bing_rss = await client.get(build_bing_rss_search_url(query))
                    if bing_rss.status_code == 200:
                        links = extract_links_from_bing_rss(bing_rss.text)[:n]
                        provider = "bing_rss"
                except Exception:
                    links = []
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
