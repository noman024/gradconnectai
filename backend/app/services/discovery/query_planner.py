"""
CV-driven query planning for external discovery sources.

Builds SEO-friendly Google and LinkedIn query strings from student topics and
preferences so discovery can expand beyond manually provided seed URLs.
"""
from __future__ import annotations

from typing import Any


def _clean(s: str) -> str:
    return " ".join((s or "").strip().split())


def _uniq_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        c = _clean(v)
        if not c:
            continue
        key = c.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _first_n(values: list[str], n: int) -> list[str]:
    return values[: max(0, n)]


def build_discovery_query_plan(
    *,
    research_topics: list[str] | None = None,
    preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a deterministic query plan for Google and LinkedIn discovery.
    """
    prefs = preferences or {}
    topics = _uniq_keep_order(list(research_topics or []) + list(prefs.get("fields") or []))
    universities = _uniq_keep_order(list(prefs.get("universities") or []))
    countries = _uniq_keep_order(list(prefs.get("countries") or []))

    top_topics = _first_n(topics, 8)
    top_universities = _first_n(universities, 4)
    top_countries = _first_n(countries, 3)

    google_queries: list[str] = []
    linkedin_queries: list[str] = []
    keywords: list[str] = []

    for t in top_topics[:6]:
        google_queries.append(f'"{t}" professor "open position"')
        google_queries.append(f'site:.edu "{t}" "PhD position"')
        linkedin_queries.append(f'"{t}" professor postdoc OR phd hiring site:linkedin.com')
        keywords.append(t)

    for u in top_universities:
        google_queries.append(f'"{u}" faculty "{top_topics[0] if top_topics else "research"}"')
        linkedin_queries.append(f'"{u}" professor "{top_topics[0] if top_topics else "research"}" site:linkedin.com')
        keywords.append(u)

    for c in top_countries:
        google_queries.append(f'"{c}" university "{top_topics[0] if top_topics else "research"}" phd')
        keywords.append(c)

    return {
        "keywords": _uniq_keep_order(keywords),
        "google_queries": _uniq_keep_order(google_queries)[:24],
        "linkedin_queries": _uniq_keep_order(linkedin_queries)[:24],
        "meta": {
            "topics_count": len(top_topics),
            "universities_count": len(top_universities),
            "countries_count": len(top_countries),
        },
    }
