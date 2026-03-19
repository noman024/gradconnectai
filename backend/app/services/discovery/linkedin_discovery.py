"""
LinkedIn discovery service.

MVP approach:
- Reuse web search queries to collect candidate links.
- Filter LinkedIn profile/post URLs.
- Keep lightweight session state for repeated discovery calls.
- Rank results with source + recency weighting.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from math import log10
from typing import Any
from urllib.parse import quote_plus, unquote

import httpx

from app.core.config import settings
from app.services.discovery.google_search import (
    collect_links_for_query,
)

try:
    from playwright.async_api import async_playwright  # type: ignore
except Exception:  # pragma: no cover - optional/runtime dependency
    async_playwright = None  # type: ignore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_SESSIONS: dict[str, dict[str, Any]] = {}


def _year_hints() -> list[int]:
    now = _utcnow().year
    return [now + 1, now, now - 1, now - 2]


def _classify_linkedin_url(url: str) -> str:
    u = (url or "").lower()
    if "/in/" in u:
        return "profile"
    if "/posts/" in u or "/feed/update/" in u:
        return "post"
    if "/jobs/" in u:
        return "jobs"
    if "/company/" in u:
        return "company"
    if "/school/" in u:
        return "school"
    return "other"


def _is_valid_linkedin_candidate(url: str) -> bool:
    u = (url or "").lower().strip()
    if "linkedin.com" not in u:
        return False
    if not u.startswith(("http://", "https://")):
        return False
    # Keep canonical post/profile/company/job/school pages, drop utility/search URLs.
    if "/feed/update/" in u or "/posts/" in u:
        return True
    blocked = (
        "linkedin.com/search/results",
        "linkedin.com/help",
        "linkedin.com/legal",
        "linkedin.com/authwall",
        "linkedin.com/learning",
        "linkedin.com/feed/?",
        "linkedin.com/feed/#",
    )
    return not any(b in u for b in blocked)


def _query_terms(query: str) -> list[str]:
    stop = {
        "site",
        "linkedin",
        "com",
        "and",
        "or",
        "the",
        "for",
        "in",
        "of",
        "a",
        "an",
    }
    terms = [t for t in re.split(r"\W+", (query or "").lower()) if len(t) > 2]
    return [t for t in terms if t not in stop][:12]


def _relevance_weight(url: str, query: str) -> float:
    u = (url or "").lower()
    terms = _query_terms(query)
    if not terms:
        return 0.0
    overlap = sum(1 for t in terms if t in u)
    return min(0.3, overlap * 0.05)


def _build_linkedin_search_variants(query: str) -> list[str]:
    q = (query or "").strip()
    if not q:
        return []
    # Avoid duplicated site operators when planner already includes them.
    q = re.sub(r"(?i)\bsite:linkedin\.com(?:/[a-z]+)?\b", "", q)
    q = " ".join(q.split())
    return [
        f'site:linkedin.com/posts {q}',
        f'site:linkedin.com/feed/update {q}',
        f'site:linkedin.com/in {q}',
        f'{q} site:linkedin.com',
    ]


def _build_linkedin_post_search_variants(query: str) -> list[str]:
    q = (query or "").strip()
    if not q:
        return []
    q = re.sub(r"(?i)\bsite:linkedin\.com(?:/[a-z]+)?\b", "", q)
    q = " ".join(q.split())
    return [
        f'site:linkedin.com/posts {q}',
        f'site:linkedin.com/feed/update {q}',
        f'{q} site:linkedin.com/posts',
    ]


def _linkedin_native_search_url(query: str) -> str:
    q = quote_plus((query or "").strip())
    return (
        "https://www.linkedin.com/search/results/all/"
        f"?keywords={q}&origin=GLOBAL_SEARCH_HEADER"
    )


def _linkedin_native_posts_search_url(query: str) -> str:
    q = quote_plus((query or "").strip())
    return (
        "https://www.linkedin.com/search/results/content/"
        f"?keywords={q}&origin=GLOBAL_SEARCH_HEADER"
    )


def _extract_native_linkedin_links(html: str) -> list[str]:
    if not html:
        return []
    links: list[str] = []
    # Absolute and escaped absolute links.
    patterns = [
        r'https://www\.linkedin\.com/(?:posts/[^"\\< ]+|feed/update/[^"\\< ]+|in/[^"\\< ]+|jobs/view/[^"\\< ]+|company/[^"\\< ]+|school/[^"\\< ]+)',
        r'https:\\/\\/www\.linkedin\.com\\/(?:posts\\/[^"\\< ]+|feed\\/update\\/[^"\\< ]+|in\\/[^"\\< ]+|jobs\\/view\\/[^"\\< ]+|company\\/[^"\\< ]+|school\\/[^"\\< ]+)',
    ]
    for p in patterns:
        for m in re.findall(p, html):
            u = m.replace("\\/", "/").strip()
            if u.startswith("http"):
                links.append(u)

    # Relative links seen in anchors.
    rel_pattern = re.compile(
        r'href="(/(?:posts/[^"]+|feed/update/[^"]+|in/[^"]+|jobs/view/[^"]+|company/[^"]+|school/[^"]+))"'
    )
    for rel in rel_pattern.findall(html):
        links.append(f"https://www.linkedin.com{unquote(rel)}")

    # Embedded JSON often contains activity URNs even when anchors are sparse.
    for aid in re.findall(r"urn:li:activity:(\d{10,})", html):
        links.append(f"https://www.linkedin.com/feed/update/urn:li:activity:{aid}")
    for aid in re.findall(r"urn%3Ali%3Aactivity%3A(\d{10,})", html):
        links.append(f"https://www.linkedin.com/feed/update/urn:li:activity:{aid}")
    for aid in re.findall(r"urn(?:\\\\u003a|\\u003a)li(?:\\\\u003a|\\u003a)activity(?:\\\\u003a|\\u003a)(\d{10,})", html):
        links.append(f"https://www.linkedin.com/feed/update/urn:li:activity:{aid}")

    # Escaped JSON URL forms.
    for raw in re.findall(
        r'https:\\/\\/www\.linkedin\.com\\/(?:posts\\/[^"\\< ]+|feed\\/update\\/urn:li:activity:\\d{10,})',
        html,
    ):
        links.append(raw.replace("\\/", "/"))

    # Unescaped JSON URL forms.
    for raw in re.findall(
        r'https://www\.linkedin\.com/(?:posts/[^"\\< ]+|feed/update/urn:li:activity:\d{10,})',
        html,
    ):
        links.append(raw)

    # order-preserving dedupe
    seen: set[str] = set()
    out: list[str] = []
    for u in links:
        clean = u.split("?", 1)[0].rstrip("/")
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def _normalize_linkedin_href(href: str) -> str:
    h = (href or "").strip()
    if not h:
        return ""
    if h.startswith("//"):
        h = f"https:{h}"
    elif h.startswith("/"):
        h = f"https://www.linkedin.com{h}"
    if not h.startswith(("http://", "https://")):
        return ""
    if "linkedin.com" not in h.lower():
        return ""
    return h


def _extract_activity_id(url: str) -> int | None:
    u = (url or "").lower()
    m = re.search(r"activity[:\-](\d{10,})", u)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _activity_recency_weight(url: str) -> float:
    """
    Use LinkedIn activity id magnitude as a lightweight freshness proxy.
    This is not an absolute timestamp, but newer activities generally have larger ids.
    """
    aid = _extract_activity_id(url)
    if not aid or aid <= 0:
        return 0.0
    return min(0.2, max(0.0, (log10(float(aid)) - 16.0) * 0.08))


async def _discover_linkedin_links_browser(
    *,
    queries: list[str],
    li_at_cookie: str,
    cookie_header: str | None,
    max_links_per_query: int,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    if async_playwright is None or not li_at_cookie:
        return {}, {"navigation_errors": 0, "sample_errors": []}

    out: dict[str, list[str]] = {}
    meta: dict[str, Any] = {"navigation_errors": 0, "sample_errors": []}
    headless = bool(getattr(settings, "LINKEDIN_BROWSER_HEADLESS", True))
    timeout_ms = int(getattr(settings, "LINKEDIN_BROWSER_TIMEOUT_MS", 30000) or 30000)
    scroll_steps = max(1, int(getattr(settings, "LINKEDIN_BROWSER_SCROLL_STEPS", 4) or 4))
    scroll_wait_ms = max(100, int(getattr(settings, "LINKEDIN_BROWSER_SCROLL_WAIT_MS", 1200) or 1200))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
        )
        parsed_cookies = _parse_cookie_header(cookie_header)
        if not parsed_cookies and li_at_cookie:
            parsed_cookies = [("li_at", li_at_cookie)]
        if parsed_cookies:
            await context.add_cookies(
                [
                    {
                        "name": name,
                        "value": value,
                        "domain": ".linkedin.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                    }
                    for name, value in parsed_cookies
                ]
            )
        page = await context.new_page()
        try:
            for raw_query in queries or []:
                query = (raw_query or "").strip()
                if not query:
                    continue
                links: list[str] = []
                for target_url in (_linkedin_native_posts_search_url(query), _linkedin_native_search_url(query)):
                    try:
                        await page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
                        await page.wait_for_timeout(scroll_wait_ms)
                        for _ in range(scroll_steps):
                            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                            await page.wait_for_timeout(scroll_wait_ms)
                        hrefs = await page.eval_on_selector_all(
                            "a",
                            "els => els.map(e => e.getAttribute('href') || '').filter(Boolean)",
                        )
                        html = await page.content()
                    except Exception:
                        meta["navigation_errors"] = int(meta.get("navigation_errors") or 0) + 1
                        if len(meta["sample_errors"]) < 3:
                            meta["sample_errors"].append(f"{target_url}:navigation_failed")
                        hrefs = []
                        html = ""
                    for h in hrefs:
                        url = _normalize_linkedin_href(str(h))
                        if not url:
                            continue
                        if url not in links:
                            links.append(url)
                    if html:
                        for url in _extract_native_linkedin_links(html):
                            if url not in links:
                                links.append(url)
                    if len(links) >= max_links_per_query:
                        break
                out[query] = links[:max_links_per_query]
        finally:
            await page.close()
            await context.close()
            await browser.close()
    return out, meta


def _recency_weight(url: str, query: str | None = None) -> float:
    u = (url or "").lower()
    q = (query or "").lower()
    now = _utcnow().year
    score = 0.2

    # URL-based hints
    if "/posts/" in u or "/feed/update/" in u:
        score += 0.45
    if "/in/" in u:
        score += 0.2

    # Year hints in URL
    if str(now) in u:
        score += 0.3
    elif str(now - 1) in u:
        score += 0.2
    elif str(now - 2) in u:
        score += 0.1

    # Query text hints
    if any(k in q for k in ("hiring", "open position", "phd", "postdoc", "students wanted")):
        score += 0.1

    return min(1.0, round(score, 6))


def _normalize_google_redirect(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("/url?q="):
        u = u[len("/url?q="):]
        u = u.split("&", 1)[0]
    return u


def _extract_google_links(html: str) -> list[str]:
    if not html:
        return []
    pattern = re.compile(r'href="(/url\?q=[^"]+)"')
    links: list[str] = []
    for part in pattern.findall(html):
        link = _normalize_google_redirect(part)
        if link.startswith("http://") or link.startswith("https://"):
            links.append(link)
    return links


def _session_hash_cookie(li_at_cookie: str | None) -> str | None:
    if not li_at_cookie:
        return None
    return hashlib.sha256(li_at_cookie.encode("utf-8")).hexdigest()[:12]


def _extract_li_at_from_cookie_header(cookie_header: str | None) -> str | None:
    if not cookie_header:
        return None
    m = re.search(r"(?:^|;\s*)li_at=([^;]+)", cookie_header)
    if not m:
        return None
    return (m.group(1) or "").strip() or None


def _parse_cookie_header(cookie_header: str | None) -> list[tuple[str, str]]:
    if not cookie_header:
        return []
    pairs: list[tuple[str, str]] = []
    for part in cookie_header.split(";"):
        chunk = part.strip()
        if "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        n = (name or "").strip()
        v = (value or "").strip()
        if not n:
            continue
        pairs.append((n, v))
    return pairs


def get_or_create_linkedin_session(
    *,
    session_id: str | None = None,
    li_at_cookie: str | None = None,
) -> dict[str, Any]:
    ttl_minutes = max(5, int(getattr(settings, "LINKEDIN_SESSION_TTL_MINUTES", 120) or 120))
    now = _utcnow()
    sid = session_id or str(uuid.uuid4())

    current = _SESSIONS.get(sid)
    if current and current.get("expires_at") and current["expires_at"] > now:
        current["last_used_at"] = now
        current["expires_at"] = now + timedelta(minutes=ttl_minutes)
        current["use_count"] = int(current.get("use_count") or 0) + 1
        if li_at_cookie:
            current["cookie_hash"] = _session_hash_cookie(li_at_cookie)
        return {
            "session_id": sid,
            "created_at": current["created_at"].isoformat(),
            "last_used_at": current["last_used_at"].isoformat(),
            "expires_at": current["expires_at"].isoformat(),
            "use_count": current["use_count"],
            "cookie_set": bool(current.get("cookie_hash")),
        }

    record = {
        "created_at": now,
        "last_used_at": now,
        "expires_at": now + timedelta(minutes=ttl_minutes),
        "use_count": 1,
        "cookie_hash": _session_hash_cookie(li_at_cookie),
    }
    _SESSIONS[sid] = record
    return {
        "session_id": sid,
        "created_at": record["created_at"].isoformat(),
        "last_used_at": record["last_used_at"].isoformat(),
        "expires_at": record["expires_at"].isoformat(),
        "use_count": record["use_count"],
        "cookie_set": bool(record.get("cookie_hash")),
    }


def _purge_expired_sessions() -> None:
    now = _utcnow()
    expired = [sid for sid, rec in _SESSIONS.items() if rec.get("expires_at") and rec["expires_at"] <= now]
    for sid in expired:
        _SESSIONS.pop(sid, None)


async def discover_linkedin_candidates(
    *,
    queries: list[str],
    session_id: str | None = None,
    li_at_cookie: str | None = None,
    max_links_per_query: int | None = None,
    use_authenticated_browser: bool = True,
    posts_only: bool = False,
    latest_first: bool = True,
    cookie_header: str | None = None,
) -> dict[str, Any]:
    _purge_expired_sessions()
    configured_cookie_header = (getattr(settings, "LINKEDIN_COOKIE_HEADER", None) or "").strip() or None
    cookie_header_effective = (cookie_header or configured_cookie_header or "").strip() or None
    li_at_effective = (
        li_at_cookie
        or _extract_li_at_from_cookie_header(cookie_header_effective)
        or (getattr(settings, "LINKEDIN_LI_AT", None) or "").strip()
        or None
    )
    session_meta = get_or_create_linkedin_session(
        session_id=session_id,
        li_at_cookie=li_at_effective,
    )

    n = max_links_per_query
    if n is None:
        n = int(getattr(settings, "LINKEDIN_MAX_RESULTS_PER_QUERY", 10) or 10)
    n = max(1, min(int(n), 100))

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    if cookie_header_effective:
        headers["Cookie"] = cookie_header_effective
    elif li_at_effective:
        headers["Cookie"] = f"li_at={li_at_effective}"

    by_query: dict[str, list[dict[str, Any]]] = {}
    dedup: dict[str, dict[str, Any]] = {}
    years = _year_hints()
    browser_links_by_query: dict[str, list[str]] = {}
    auth_attempted = bool(li_at_effective and use_authenticated_browser)
    auth_links_found = False
    auth_signin_wall_seen = False
    auth_browser_error: str | None = None
    auth_browser_meta: dict[str, Any] = {"navigation_errors": 0, "sample_errors": []}

    async def _search_with_fallback(search_query: str) -> list[str]:
        links, _provider = await collect_links_for_query(
            search_query,
            max_links=n,
            headers=headers,
            providers=["brave", "bing", "bing_rss", "google", "duckduckgo"],
        )
        return links

    if li_at_effective and use_authenticated_browser:
        try:
            browser_links_by_query, auth_browser_meta = await _discover_linkedin_links_browser(
                queries=queries,
                li_at_cookie=li_at_effective,
                cookie_header=cookie_header_effective,
                max_links_per_query=n,
            )
            if any(browser_links_by_query.get(q) for q in browser_links_by_query):
                auth_links_found = True
            elif int(auth_browser_meta.get("navigation_errors") or 0) > 0:
                auth_browser_error = "browser_navigation_failed"
        except Exception:
            auth_browser_error = "browser_discovery_failed"
            browser_links_by_query = {}

    async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
        for raw_query in queries or []:
            query = (raw_query or "").strip()
            if not query:
                continue

            items: list[dict[str, Any]] = []
            links: list[str] = list(browser_links_by_query.get(query) or [])

            # 1) Prefer native LinkedIn search results when authenticated.
            if li_at_effective and use_authenticated_browser and len(links) < max(3, n // 2):
                try:
                    li_resp = await client.get(_linkedin_native_search_url(query))
                    li_html = li_resp.text if li_resp.status_code == 200 else ""
                    if li_html and "Sign in" in li_html:
                        auth_signin_wall_seen = True
                    if li_html and "Sign in" not in li_html:
                        for link in _extract_native_linkedin_links(li_html):
                            if link not in links:
                                links.append(link)
                                auth_links_found = True
                except Exception:
                    pass

            # 2) Lightweight external fallback chain for robustness.
            needed = max(3, n // 2)
            if len(links) < needed:
                variants = (
                    _build_linkedin_post_search_variants(query)
                    if posts_only
                    else _build_linkedin_search_variants(query)
                )
                for sq in variants:
                    variant_links = await _search_with_fallback(sq)
                    for link in variant_links:
                        if link not in links:
                            links.append(link)
                    if len(links) >= n:
                        break

            rank = 1
            for link in links:
                if not _is_valid_linkedin_candidate(link):
                    continue
                kind = _classify_linkedin_url(link)
                if kind == "other":
                    continue
                if posts_only and kind != "post":
                    continue
                recency = _recency_weight(link, query)
                relevance = _relevance_weight(link, query)
                activity_recency = _activity_recency_weight(link)
                year_bonus = 0.0
                lower_link = link.lower()
                for i, y in enumerate(years):
                    if str(y) in lower_link:
                        year_bonus = max(year_bonus, max(0.0, 0.2 - (i * 0.05)))
                kind_bonus = {
                    "post": 0.35,
                    "profile": 0.2,
                    "company": 0.12,
                    "school": 0.12,
                    "jobs": 0.08,
                }.get(kind, 0.0)
                score = round(
                    (1.0 / rank) * 0.35
                    + recency * 0.35
                    + relevance
                    + kind_bonus
                    + year_bonus
                    + activity_recency,
                    6,
                )
                item = {
                    "url": link,
                    "query": query,
                    "kind": kind,
                    "rank": rank,
                    "recency_weight": recency,
                    "relevance_weight": relevance,
                    "activity_recency_weight": round(activity_recency, 6),
                    "activity_id": _extract_activity_id(link),
                    "score": score,
                }
                items.append(item)
                if link not in dedup or item["score"] > dedup[link]["score"]:
                    dedup[link] = item
                rank += 1
                if rank > n:
                    break
            by_query[query] = items

    if latest_first:
        ranked = sorted(
            dedup.values(),
            key=lambda x: (x["score"], int(x.get("activity_id") or 0)),
            reverse=True,
        )
    else:
        ranked = sorted(dedup.values(), key=lambda x: x["score"], reverse=True)
    return {
        "session": session_meta,
        "posts_only": bool(posts_only),
        "latest_first": bool(latest_first),
        "auth_diagnostics": {
            "attempted": auth_attempted,
            "links_found_from_auth": auth_links_found,
            "signin_wall_detected": auth_signin_wall_seen,
            "browser_total_links": sum(len(v or []) for v in browser_links_by_query.values()),
            "browser_queries_with_links": len([1 for v in browser_links_by_query.values() if v]),
            "browser_error": auth_browser_error,
            "browser_navigation_errors": int(auth_browser_meta.get("navigation_errors") or 0),
            "browser_sample_errors": list(auth_browser_meta.get("sample_errors") or []),
        },
        "queries_count": len(by_query),
        "per_query": by_query,
        "ranked_results": ranked,
        "total_ranked": len(ranked),
    }
