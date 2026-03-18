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
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.core.config import settings
from app.services.discovery.google_search import (
    extract_http_links_from_html,
    build_duckduckgo_search_url,
    build_bing_search_url,
    build_bing_rss_search_url,
    extract_links_from_bing_rss,
)


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


def _google_query_url(query: str, num: int) -> str:
    q = quote_plus((query or "").strip())
    n = max(1, min(int(num), 20))
    return f"https://www.google.com/search?q={q}&num={n}&hl=en"


def _session_hash_cookie(li_at_cookie: str | None) -> str | None:
    if not li_at_cookie:
        return None
    return hashlib.sha256(li_at_cookie.encode("utf-8")).hexdigest()[:12]


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
) -> dict[str, Any]:
    _purge_expired_sessions()
    li_at_effective = li_at_cookie or (getattr(settings, "LINKEDIN_LI_AT", None) or "").strip() or None
    session_meta = get_or_create_linkedin_session(
        session_id=session_id,
        li_at_cookie=li_at_effective,
    )

    n = max_links_per_query
    if n is None:
        n = int(getattr(settings, "LINKEDIN_MAX_RESULTS_PER_QUERY", 10) or 10)
    n = max(1, min(int(n), 20))

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    if li_at_effective:
        headers["Cookie"] = f"li_at={li_at_effective}"

    by_query: dict[str, list[dict[str, Any]]] = {}
    dedup: dict[str, dict[str, Any]] = {}
    years = _year_hints()

    async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
        for raw_query in queries or []:
            query = (raw_query or "").strip()
            if not query:
                continue
            # Push discovery towards LinkedIn sources (profiles, posts, jobs, companies).
            linkedin_query = f"{query} site:linkedin.com"
            search_url = _google_query_url(linkedin_query, n)
            items: list[dict[str, Any]] = []
            try:
                resp = await client.get(search_url)
                html = resp.text if resp.status_code == 200 else ""
            except Exception:
                html = ""

            links = _extract_google_links(html)
            if not links:
                # Fallback provider for robustness in regions where Google results are hard to parse.
                try:
                    ddg = await client.get(build_duckduckgo_search_url(linkedin_query))
                    if ddg.status_code == 200:
                        links = extract_http_links_from_html(ddg.text)
                except Exception:
                    links = []
            if not links:
                try:
                    bing = await client.get(build_bing_search_url(linkedin_query, num=n))
                    if bing.status_code == 200:
                        links = extract_http_links_from_html(bing.text)
                except Exception:
                    links = []
            if not links:
                try:
                    bing_rss = await client.get(build_bing_rss_search_url(linkedin_query))
                    if bing_rss.status_code == 200:
                        links = extract_links_from_bing_rss(bing_rss.text)
                except Exception:
                    links = []
            rank = 1
            for link in links:
                if "linkedin.com" not in link.lower():
                    continue
                kind = _classify_linkedin_url(link)
                if kind == "other":
                    continue
                recency = _recency_weight(link, query)
                year_bonus = 0.0
                lower_link = link.lower()
                for i, y in enumerate(years):
                    if str(y) in lower_link:
                        year_bonus = max(year_bonus, max(0.0, 0.2 - (i * 0.05)))
                score = round((1.0 / rank) * 0.4 + recency * 0.5 + year_bonus, 6)
                item = {
                    "url": link,
                    "query": query,
                    "kind": kind,
                    "rank": rank,
                    "recency_weight": recency,
                    "score": score,
                }
                items.append(item)
                if link not in dedup or item["score"] > dedup[link]["score"]:
                    dedup[link] = item
                rank += 1
                if rank > n:
                    break
            by_query[query] = items

    ranked = sorted(dedup.values(), key=lambda x: x["score"], reverse=True)
    return {
        "session": session_meta,
        "queries_count": len(by_query),
        "per_query": by_query,
        "ranked_results": ranked,
        "total_ranked": len(ranked),
    }
