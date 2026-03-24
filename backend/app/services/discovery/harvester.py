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

from app.core.config import settings
from app.core.logging import get_logger
from app.services.discovery.query_planner import build_discovery_query_plan
from app.services.discovery.google_search import google_search_collect_links
from app.services.discovery.google_browser_search import google_search_collect_links_browser
from app.services.discovery.linkedin_discovery import discover_linkedin_candidates
from app.services.discovery.browser_use_search import browser_use_collect_linkedin_posts

logger = get_logger("discovery.harvester")


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
    if source in {"google_http", "google_browser", "browser_use"} and any(
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


def _is_crawl_seed_candidate(item: dict[str, Any]) -> bool:
    """
    Keep URLs that are likely crawlable/useful for `/discovery/run`.
    Drops obvious low-value and commonly blocked patterns.
    """
    raw_url = str(item.get("url") or "").strip()
    if not raw_url.startswith(("http://", "https://")):
        return False
    parsed = urlparse(raw_url)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower().rstrip("/")

    # Bare homepages are usually too noisy for extraction quality.
    if path in {"", "/"}:
        return False

    if "linkedin.com" in host:
        # Keep deep LinkedIn URLs (jobs/posts/profiles/company/school) and drop only
        # top-level or search chrome links that are low-signal.
        if path in {"", "/", "/feed"}:
            return False
        if path.startswith("/search"):
            return False
        return True

    return True


def _filter_crawl_seed_candidates(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    filtered: list[dict[str, Any]] = []
    dropped = 0
    for item in items:
        if _is_crawl_seed_candidate(item):
            filtered.append(item)
        else:
            dropped += 1
    return filtered, dropped


def _merge_ranked_url_items(
    google_items: list[dict[str, Any]],
    google_browser_items: list[dict[str, Any]],
    linkedin_items: list[dict[str, Any]],
    browser_use_items: list[dict[str, Any]] | None = None,
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
        _upsert(g, 0.05)
    for gb in google_browser_items:
        _upsert(gb, 0.08)
    for li in linkedin_items:
        _upsert(li, 0.12)
    for bu in browser_use_items or []:
        _upsert(bu, 0.15)

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
    logger.info("harvester_start", topics_count=len(research_topics or []), use_browser=use_browser_google, top_k=top_k)
    plan = build_discovery_query_plan(
        research_topics=research_topics or [],
        preferences=preferences or {},
    )
    google_queries = (plan.get("google_queries") or [])[: max(1, max_queries_per_source)]
    linkedin_queries = (plan.get("linkedin_queries") or [])[: max(1, max_queries_per_source)]
    logger.info("harvester_queries_planned", google_queries=len(google_queries), linkedin_queries=len(linkedin_queries))

    google_http: dict[str, Any] = {
        "queries_count": 0,
        "total_deduped": 0,
        "deduped_results": [],
    }
    google_http_items: list[dict[str, Any]] = []

    google_browser_items: list[dict[str, Any]] = []
    google_browser: dict[str, Any] = {
        "engine": "playwright",
        "available": False,
        "deduped_results": [],
        "total_deduped": 0,
    }
    should_use_browser = bool(use_browser_google and getattr(settings, "SEARCH_ENABLE_GOOGLE", True))
    logger.info("harvester_google_phase", use_browser=should_use_browser)
    if should_use_browser:
        google_browser = await google_search_collect_links_browser(
            google_queries,
            max_links_per_query=max_links_per_query,
        )
        raw_browser_items = _clean_urls(
            google_browser.get("deduped_results") or [],
            "google_browser",
        )
        if bool(google_browser.get("fallback_used")):
            # Browser path already reused HTTP collector; avoid re-running HTTP and duplicate scoring.
            google_http = {
                "queries_count": google_browser.get("queries_count"),
                "total_deduped": google_browser.get("total_deduped"),
                "deduped_results": google_browser.get("deduped_results") or [],
            }
            google_http_items = _clean_urls(google_http.get("deduped_results") or [], "google_http")
            google_browser_items = []
        elif raw_browser_items:
            google_browser_items = raw_browser_items
        else:
            google_http = await google_search_collect_links(
                google_queries,
                max_links_per_query=max_links_per_query,
            )
            google_http_items = _clean_urls(google_http.get("deduped_results") or [], "google_http")
    else:
        google_http = await google_search_collect_links(
            google_queries,
            max_links_per_query=max_links_per_query,
        )
        google_http_items = _clean_urls(google_http.get("deduped_results") or [], "google_http")

    logger.info("harvester_google_done", http_items=len(google_http_items), browser_items=len(google_browser_items))

    logger.info("harvester_linkedin_phase", queries=len(linkedin_queries))
    linkedin = await discover_linkedin_candidates(
        queries=linkedin_queries,
        session_id=linkedin_session_id,
        li_at_cookie=linkedin_li_at_cookie,
        max_links_per_query=max_links_per_query,
        use_authenticated_browser=False,
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
                use_authenticated_browser=False,
            )
    linkedin_items = _clean_urls(linkedin.get("ranked_results") or [], "linkedin")
    logger.info("harvester_linkedin_done", linkedin_items=len(linkedin_items))

    logger.info("harvester_browser_use_phase")
    browser_use_items: list[dict[str, Any]] = []
    browser_use_result: dict[str, Any] = {"total": 0, "errors": None}
    try:
        bu_queries = linkedin_queries[:3]
        browser_use_result = await browser_use_collect_linkedin_posts(
            bu_queries, max_links_per_query=max_links_per_query, time_filter="month",
        )
        for item in browser_use_result.get("ranked_results") or []:
            url = str(item.get("url") or "").strip()
            if url.startswith(("http://", "https://")):
                browser_use_items.append({
                    "url": url,
                    "host": urlparse(url).netloc.lower(),
                    "score": float(item.get("score") or 0.0),
                    "source": "browser_use",
                    "query": None,
                    "kind": "post",
                    "rank": item.get("rank"),
                })
    except Exception as exc:
        logger.warning("harvester_browser_use_error", error=str(exc)[:200])

    logger.info("harvester_browser_use_done", browser_use_items=len(browser_use_items))

    merged = _merge_ranked_url_items(
        google_items=google_http_items,
        google_browser_items=google_browser_items,
        linkedin_items=linkedin_items,
        browser_use_items=browser_use_items,
    )
    dropped_unverified = 0
    if verified_only:
        merged, dropped_unverified = _apply_verified_filter(merged)
    merged, dropped_uncrawlable = _filter_crawl_seed_candidates(merged)
    merged = merged[: max(1, int(top_k))]

    logger.info("harvester_complete", total_seed_urls=len(merged), sources={
        "google_http": len(google_http_items), "google_browser": len(google_browser_items),
        "linkedin": len(linkedin_items), "browser_use": len(browser_use_items),
    })
    return {
        "verified_only": bool(verified_only),
        "query_plan": plan,
        "sources": {
            "google_http_total": len(google_http_items),
            "google_browser_total": len(google_browser_items),
            "linkedin_total": len(linkedin_items),
            "browser_use_total": len(browser_use_items),
        },
        "quality": {
            "dropped_unverified": dropped_unverified,
            "dropped_uncrawlable": dropped_uncrawlable,
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
        "browser_use": {
            "total": browser_use_result.get("total", 0),
            "errors": browser_use_result.get("errors"),
        },
        "harvested": merged,
        "seed_urls": [x["url"] for x in merged],
        "total_seed_urls": len(merged),
    }
