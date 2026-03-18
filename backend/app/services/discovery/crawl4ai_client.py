"""
Integration with Crawl4AI for richer, LLM-friendly crawling.

Used by the discovery pipeline to fetch pages and extract professor-like
records from Markdown instead of raw HTML when available.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

from app.core.config import settings
from app.core.logging import get_logger

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

    logger = get_logger("crawl4ai_client")
    headless_mode = bool(settings.CRAWL4AI_HEADLESS)
    if (
        not headless_mode
        and bool(getattr(settings, "CRAWL4AI_FORCE_HEADLESS_IF_NO_DISPLAY", True))
        and not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    ):
        # Avoid hard crashes in server environments without a display.
        logger.warning("crawl4ai_no_display_forced_headless")
        headless_mode = True

    browser_config = BrowserConfig(headless=headless_mode, verbose=True)
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            for url in urls:
                try:
                    out = await crawler.arun(url=url)
                except Exception as exc:
                    logger.warning("crawl4ai_page_failed", url=url, error=str(exc))
                    continue
                md = getattr(out, "markdown", None)
                text = ""
                if isinstance(md, str):
                    text = md
                elif hasattr(md, "raw_markdown"):
                    text = md.raw_markdown or ""
                if not text:
                    continue
                try:
                    logger.info(
                        "crawl4ai_page_ok",
                        url=url,
                        markdown_len=len(text),
                        markdown_preview=text[:300].replace("\n", "\\n"),
                    )
                except Exception:
                    pass
                results.append(Crawl4AIResult(url=url, markdown=text))
    except Exception as exc:
        # Common failure mode: Playwright browsers not installed.
        logger.error("crawl4ai_start_failed", error=str(exc))
        return []
    return results

