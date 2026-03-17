"""
Discovery crawler: fetch pages from allowed origins, respect robots.txt and rate limits.
Updates last_checked and active_flag when storing professor data.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.services.discovery.robots import check_robots, RobotsResult
from app.services.discovery.rate_limiter import RateLimiter

USER_AGENT = "GradConnectAI/1.0 (+https://gradconnectai.com)"


@dataclass
class CrawlResult:
    url: str
    status_code: int
    body: str
    allowed_by_robots: bool
    error: str | None = None


class DiscoveryCrawler:
    """
    Crawls public academic sources. Respects robots.txt and applies
    per-domain and global rate limiting. Use last_checked and active_flag
    when persisting professor records.
    """

    def __init__(
        self,
        requests_per_domain_per_minute: int | None = None,
        global_requests_per_minute: int | None = None,
    ):
        self.rate_limiter = RateLimiter(
            per_domain_per_minute=requests_per_domain_per_minute or settings.CRAWLER_REQUESTS_PER_MINUTE,
            global_per_minute=global_requests_per_minute or settings.CRAWLER_GLOBAL_REQUESTS_PER_MINUTE,
        )

    async def fetch(self, url: str) -> CrawlResult:
        """Fetch URL if allowed by robots.txt; otherwise return a result indicating disallowed."""
        robots = check_robots(url, user_agent=USER_AGENT)
        if not robots.allowed:
            return CrawlResult(
                url=url,
                status_code=0,
                body="",
                allowed_by_robots=False,
                error="Disallowed by robots.txt",
            )
        await self.rate_limiter.acquire(url)
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await client.get(url)
                return CrawlResult(
                    url=url,
                    status_code=resp.status_code,
                    body=resp.text,
                    allowed_by_robots=True,
                )
        except Exception as e:
            return CrawlResult(
                url=url,
                status_code=0,
                body="",
                allowed_by_robots=True,
                error=str(e),
            )

    @staticmethod
    def last_checked_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def active_flag_from_success(success: bool) -> bool:
        """Set active_flag True when we successfully verified/updated the professor."""
        return success
