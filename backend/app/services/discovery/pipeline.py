"""
Discovery pipeline: seed URLs (university/lab pages) -> crawl -> extract professor-like records.
Stores last_checked and active_flag when persisting to DB (see crawler.last_checked_now, active_flag_from_success).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.services.discovery.crawler import DiscoveryCrawler, CrawlResult
from app.services.discovery.crawl4ai_client import crawl_markdown, extract_name_lines
from app.services.llm_client import extract_professors_from_markdown


@dataclass
class RawProfessor:
    """Extracted professor record before dedup and DB; includes metadata for last_checked/active_flag."""
    name: str
    university: str
    email: str | None = None
    lab_url: str | None = None
    lab_focus: str | None = None
    research_topics: list[str] = field(default_factory=list)
    opportunity_score: float = 0.5
    sources: list[str] = field(default_factory=list)
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_flag: bool = False


def _extract_emails(text: str) -> list[str]:
    pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    return list(set(pattern.findall(text)))


def _extract_from_lab_page(html: str, url: str, university_hint: str) -> list[RawProfessor]:
    """Naive extraction from a single lab/faculty page. Override or extend for real sites."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[RawProfessor] = []
    # Heuristic: look for headings or list items that look like names (no @, reasonable length)
    for tag in soup.find_all(["h2", "h3", "li", "p"]):
        text = (tag.get_text() or "").strip()
        if not text or "@" in text or len(text) > 80:
            continue
        # Simple name-like: two or three words
        parts = text.split()
        if 2 <= len(parts) <= 5 and all(p[0].isupper() or not p.isalpha() for p in parts if p):
            emails = _extract_emails(tag.get_text() or "")
            results.append(
                RawProfessor(
                    name=text,
                    university=university_hint,
                    email=emails[0] if emails else None,
                    lab_url=url,
                    research_topics=[],
                    sources=[url],
                    active_flag=True,
                )
            )
    return results[:20]  # cap per page


async def run_university_lab_pipeline(seed_urls: list[str], university_name: str) -> list[RawProfessor]:
    """
    Crawl seed URLs (e.g. lab/faculty pages), respect robots and rate limits,
    and return raw professor-like records.

    Strategy:
    - Prefer Crawl4AI Markdown crawling when available for better extraction.
    - Fallback to simple HTML crawler otherwise.
    """
    logger = get_logger("discovery_pipeline")
    seen_names: set[tuple[str, str]] = set()
    all_raw: list[RawProfessor] = []

    # 1) Try Crawl4AI for richer Markdown-based extraction
    logger.info("discovery_start", seed_urls=seed_urls, university=university_name)
    md_results = await crawl_markdown(seed_urls)
    logger.info("discovery_crawl4ai_done", pages=len(md_results))
    for res in md_results:
        # First try LLM-based structured extraction
        prof_dicts = extract_professors_from_markdown(res.markdown, university_name, res.url)
        if prof_dicts:
            for p in prof_dicts:
                key = (p["name"].strip().lower(), university_name)
                if key in seen_names:
                    continue
                seen_names.add(key)
                all_raw.append(
                    RawProfessor(
                        name=p["name"],
                        university=university_name,
                        email=p.get("email"),
                        lab_url=res.url,
                        lab_focus=p.get("lab_focus"),
                        research_topics=p.get("research_topics") or [],
                        opportunity_score=float(p.get("opportunity_score") or 0.5),
                        sources=[res.url],
                        last_checked=datetime.now(timezone.utc),
                        active_flag=True,
                    )
                )
            continue

        # Fallback: simple name-line heuristic
        name_lines = extract_name_lines(res.markdown)
        for name in name_lines:
            key = (name.strip().lower(), university_name)
            if key in seen_names:
                continue
            seen_names.add(key)
            all_raw.append(
                RawProfessor(
                    name=name,
                    university=university_name,
                    email=None,
                    lab_url=res.url,
                    research_topics=[],
                    sources=[res.url],
                    last_checked=datetime.now(timezone.utc),
                    active_flag=True,
                )
            )

    # 2) Fallback / supplement with HTML crawler (preserves robots.txt + rate limiting)
    crawler = DiscoveryCrawler()
    for url in seed_urls:
        result = await crawler.fetch(url)
        if not result.allowed_by_robots or result.status_code != 200 or result.error:
            continue
        records = _extract_from_lab_page(result.body, url, university_name)
        for r in records:
            key = (r.name.strip().lower(), university_name)
            if key in seen_names:
                continue
            seen_names.add(key)
            r.last_checked = crawler.last_checked_now()
            r.active_flag = crawler.active_flag_from_success(True)
            all_raw.append(r)

    logger.info(
        "discovery_finished",
        total_raw=len(all_raw),
        unique_names=len(seen_names),
        seed_urls=seed_urls,
        university=university_name,
    )
    return all_raw
