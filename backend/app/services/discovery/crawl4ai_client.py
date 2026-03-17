"""
Integration with Crawl4AI for richer, LLM-friendly crawling.

Used by the discovery pipeline to fetch pages and extract professor-like
records from Markdown instead of raw HTML when available.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Iterable
import os

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    AsyncWebCrawler = None  # type: ignore
    BrowserConfig = None  # type: ignore


@dataclass
class Crawl4AIResult:
    url: str
    markdown: str


async def crawl_markdown(urls: Iterable[str]) -> list[Crawl4AIResult]:
    """
    Crawl a small set of URLs and return their Markdown content.
    Fallback to empty list if Crawl4AI is not installed.
    """
    if AsyncWebCrawler is None or BrowserConfig is None:
        return []

    results: list[Crawl4AIResult] = []

    # Allow debugging in a real browser when CRAWL4AI_HEADLESS=0 or =false
    headless_env = os.getenv("CRAWL4AI_HEADLESS", "1").lower()
    headless = not (headless_env in ("0", "false", "no"))
    browser_config = BrowserConfig(headless=headless, verbose=True)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls:
            try:
                out = await crawler.arun(url=url)
            except Exception:
                continue
            md = getattr(out, "markdown", None)
            text = ""
            if isinstance(md, str):
                text = md
            elif hasattr(md, "raw_markdown"):
                text = md.raw_markdown or ""
            if not text:
                continue
            results.append(Crawl4AIResult(url=url, markdown=text))
    return results


def extract_name_lines(markdown: str) -> list[str]:
    """
    Very simple heuristic over Markdown to find name-like lines:
    - Not too long
    - 2–5 words
    - Mostly capitalized words
    """
    candidates: list[str] = []
    for line in markdown.splitlines():
        line = line.strip()
        if not line or "@" in line or len(line) > 80:
            continue
        # Skip obvious headings with numbers or bullets
        if line.startswith(("#", "-", "*", ">")):
            line = line.lstrip("#-* >").strip()
        parts = line.split()
        if not (2 <= len(parts) <= 5):
            continue
        if not any(p[0].isupper() for p in parts if p.isalpha()):
            continue
        if sum(1 for p in parts if p and p[0].isupper()) < len(parts) / 2:
            continue
        candidates.append(line)
    # Deduplicate while preserving order
    seen = set()
    out: list[str] = []
    for c in candidates:
        key = c.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out

