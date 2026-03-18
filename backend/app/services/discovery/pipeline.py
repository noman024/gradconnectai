"""
Discovery pipeline: seed URLs (university/lab pages) -> crawl -> extract professor-like records.
Stores last_checked and active_flag when persisting to DB (see crawler.last_checked_now, active_flag_from_success).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.services.discovery.crawler import DiscoveryCrawler, CrawlResult
from app.services.discovery.crawl4ai_client import crawl_markdown
from app.services.llm_client import extract_professors_from_markdown


@dataclass
class RawProfessor:
    """Extracted professor record before dedup and DB; includes metadata for last_checked/active_flag."""
    name: str
    university: str
    email: str | None = None
    profile_url: str | None = None
    lab_url: str | None = None
    lab_focus: str | None = None
    research_topics: list[str] = field(default_factory=list)
    opportunity_score: float = 0.5
    sources: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_flag: bool = False


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

    # 1) Crawl with Crawl4AI and use LLM-based extraction only.
    logger.info("discovery_start", seed_urls=seed_urls, university=university_name)
    md_results = await crawl_markdown(seed_urls)
    logger.info("discovery_crawl4ai_done", pages=len(md_results))
    for res in md_results:
        # Only use LLM-based structured extraction (Qwen). If it returns no professors,
        # we do NOT fall back to heuristic name extraction.
        prof_dicts = extract_professors_from_markdown(res.markdown, university_name, res.url)
        if not prof_dicts:
            continue
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
                    profile_url=p.get("profile_url"),
                    lab_url=res.url,
                    lab_focus=p.get("lab_focus"),
                    research_topics=p.get("research_topics") or [],
                    opportunity_score=float(p.get("opportunity_score") or 0.5),
                    sources=[res.url],
                    evidence=(p.get("_evidence") or []),
                    last_checked=datetime.now(timezone.utc),
                    active_flag=True,
                )
            )

    logger.info(
        "discovery_finished",
        total_raw=len(all_raw),
        unique_names=len(seen_names),
        seed_urls=seed_urls,
        university=university_name,
    )
    return all_raw
