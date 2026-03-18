"""
Integrated search harvester for discovery.

Combines:
- CV-driven query planning
- Google search ingestion (HTTP and/or browser)
- LinkedIn discovery

Produces a unified, deduped, ranked URL set suitable for discovery crawl seeds.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.services.discovery.query_planner import build_discovery_query_plan
from app.services.discovery.google_search import google_search_collect_links
from app.services.discovery.google_browser_search import google_search_collect_links_browser
from app.services.discovery.linkedin_discovery import discover_linkedin_candidates


_NOISY_HOST_KEYWORDS = (
    "wikipedia.org",
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "pinterest.",
    "reddit.com",
    "quora.com",
    "zhihu.com",
    "baidu.com",
    "stackoverflow.com",
)


def _clean_urls(items: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        host = str(item.get("host") or urlparse(url).netloc).lower()
        score = item.get("score")
        try:
            score_f = float(score)
        except Exception:
            score_f = 0.0
        out.append(
            {
                "url": url,
                "host": host,
                "score": score_f,
                "source": source,
                "query": item.get("query"),
                "kind": item.get("kind"),
                "rank": item.get("rank"),
            }
        )
    return out


def _verification_reason(item: dict[str, Any]) -> str | None:
    host = str(item.get("host") or "").lower()
    url = str(item.get("url") or "").lower()
    source = str(item.get("source") or "")
    kind = str(item.get("kind") or "").lower()

    if not host:
        return None
    if any(n in host for n in _NOISY_HOST_KEYWORDS):
        return None
    if "linkedin.com" in host:
        if kind in {"post", "profile", "jobs", "company", "school"}:
            return f"linkedin_{kind}"
        if "/jobs/" in url:
            return "linkedin_jobs"
        return None
    if ".edu" in host or ".ac." in host:
        if any(k in url for k in ("/faculty", "/people", "/lab", "/research", "/department", "/professor")):
            return "academic_domain_research_page"
        return "academic_domain"
    # Trust targeted search sources when URL pattern looks opportunity-relevant.
    if source in {"google_http", "google_browser"} and any(
        k in url for k in ("phd", "postdoc", "funded", "scholarship", "admission", "graduate")
    ):
        return "search_engine_opportunity_pattern"
    return None


def _apply_verified_filter(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    verified: list[dict[str, Any]] = []
    dropped = 0
    for item in items:
        reason = _verification_reason(item)
        if not reason:
            dropped += 1
            continue
        enriched = dict(item)
        enriched["verification_reason"] = reason
        verified.append(enriched)
    return verified, dropped


def _merge_ranked_url_items(
    google_items: list[dict[str, Any]],
    google_browser_items: list[dict[str, Any]],
    linkedin_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    def _upsert(item: dict[str, Any], bonus: float) -> None:
        url = item["url"]
        base = float(item.get("score") or 0.0)
        final = round(base + bonus, 6)
        cur = merged.get(url)
        if cur is None:
            merged[url] = {
                "url": url,
                "host": item.get("host"),
                "score": final,
                "base_score": base,
                "sources": [item.get("source")],
                "queries": [item.get("query")] if item.get("query") else [],
                "kind": item.get("kind"),
            }
            return
        if final > float(cur.get("score") or 0.0):
            cur["score"] = final
            cur["base_score"] = base
            if item.get("kind"):
                cur["kind"] = item.get("kind")
        src = item.get("source")
        if src and src not in cur["sources"]:
            cur["sources"].append(src)
        q = item.get("query")
        if q and q not in cur["queries"]:
            cur["queries"].append(q)

    for g in google_items:
        _upsert(g, 0.05)  # generic web source boost
    for gb in google_browser_items:
        _upsert(gb, 0.08)  # browser-verified source slightly higher
    for li in linkedin_items:
        _upsert(li, 0.12)  # direct LinkedIn relevance boost

    ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    return ranked


async def run_automated_search_harvester(
    *,
    research_topics: list[str] | None = None,
    preferences: dict[str, Any] | None = None,
    use_browser_google: bool = True,
    max_queries_per_source: int = 6,
    max_links_per_query: int = 10,
    top_k: int = 40,
    verified_only: bool = False,
    linkedin_session_id: str | None = None,
    linkedin_li_at_cookie: str | None = None,
) -> dict[str, Any]:
    plan = build_discovery_query_plan(
        research_topics=research_topics or [],
        preferences=preferences or {},
    )
    google_queries = (plan.get("google_queries") or [])[: max(1, max_queries_per_source)]
    linkedin_queries = (plan.get("linkedin_queries") or [])[: max(1, max_queries_per_source)]

    google_http = await google_search_collect_links(
        google_queries,
        max_links_per_query=max_links_per_query,
    )
    google_http_items = _clean_urls(google_http.get("deduped_results") or [], "google_http")

    google_browser_items: list[dict[str, Any]] = []
    google_browser: dict[str, Any] = {
        "engine": "playwright",
        "available": False,
        "deduped_results": [],
        "total_deduped": 0,
    }
    if use_browser_google:
        google_browser = await google_search_collect_links_browser(
            google_queries,
            max_links_per_query=max_links_per_query,
        )
        google_browser_items = _clean_urls(
            google_browser.get("deduped_results") or [],
            "google_browser",
        )

    linkedin = await discover_linkedin_candidates(
        queries=linkedin_queries,
        session_id=linkedin_session_id,
        li_at_cookie=linkedin_li_at_cookie,
        max_links_per_query=max_links_per_query,
    )
    if int(linkedin.get("total_ranked") or 0) <= 0:
        keywords = list(plan.get("keywords") or [])
        fallback_li_queries = []
        fallback_li_queries.extend(
            [
                "machine learning professor hiring",
                "artificial intelligence professor jobs",
                "nlp phd position",
            ]
        )
        for kw in keywords[:4]:
            fallback_li_queries.append(f"{kw} professor hiring jobs")
            fallback_li_queries.append(f"{kw} phd openings")
        if fallback_li_queries:
            linkedin = await discover_linkedin_candidates(
                queries=fallback_li_queries[: max(6, max_queries_per_source + 2)],
                session_id=(linkedin.get("session") or {}).get("session_id") or linkedin_session_id,
                li_at_cookie=linkedin_li_at_cookie,
                max_links_per_query=max_links_per_query,
            )
    linkedin_items = _clean_urls(linkedin.get("ranked_results") or [], "linkedin")

    merged = _merge_ranked_url_items(
        google_items=google_http_items,
        google_browser_items=google_browser_items,
        linkedin_items=linkedin_items,
    )
    dropped_unverified = 0
    if verified_only:
        merged, dropped_unverified = _apply_verified_filter(merged)
    merged = merged[: max(1, int(top_k))]

    return {
        "verified_only": bool(verified_only),
        "query_plan": plan,
        "sources": {
            "google_http_total": len(google_http_items),
            "google_browser_total": len(google_browser_items),
            "linkedin_total": len(linkedin_items),
        },
        "quality": {
            "dropped_unverified": dropped_unverified,
            "verified_count": len(merged),
        },
        "google_http": {
            "queries_count": google_http.get("queries_count"),
            "total_deduped": google_http.get("total_deduped"),
        },
        "google_browser": {
            "available": google_browser.get("available"),
            "total_deduped": google_browser.get("total_deduped"),
        },
        "linkedin": {
            "session": linkedin.get("session"),
            "queries_count": linkedin.get("queries_count"),
            "total_ranked": linkedin.get("total_ranked"),
        },
        "harvested": merged,
        "seed_urls": [x["url"] for x in merged],
        "total_seed_urls": len(merged),
    }
