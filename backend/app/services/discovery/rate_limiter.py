"""
Per-domain and global rate limiting for the crawler.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from urllib.parse import urlparse


class RateLimiter:
    """
    In-memory rate limiter: per-domain and global request caps.
    - per_domain: max requests per minute per host
    - global_: max requests per minute across all hosts
    """

    def __init__(
        self,
        per_domain_per_minute: int = 30,
        global_per_minute: int = 120,
    ):
        self.per_domain_per_minute = per_domain_per_minute
        self.global_per_minute = global_per_minute
        self._domain_times: dict[str, list[float]] = defaultdict(list)
        self._global_times: list[float] = []
        self._lock = asyncio.Lock()

    def _prune_old(self, times: list[float], window_sec: float = 60.0) -> None:
        cutoff = time.monotonic() - window_sec
        while times and times[0] < cutoff:
            times.pop(0)

    async def acquire(self, url: str) -> None:
        """Block until a request to url is allowed under rate limits."""
        host = urlparse(url).netloc or "unknown"
        async with self._lock:
            now = time.monotonic()
            self._prune_old(self._global_times)
            self._prune_old(self._domain_times[host])

            while True:
                if len(self._global_times) >= self.global_per_minute:
                    wait = 60 - (now - (self._global_times[0] if self._global_times else 0))
                    if wait > 0:
                        await asyncio.sleep(min(wait, 5.0))
                        now = time.monotonic()
                        self._prune_old(self._global_times)
                        self._prune_old(self._domain_times[host])
                    continue
                if len(self._domain_times[host]) >= self.per_domain_per_minute:
                    wait = 60 - (now - self._domain_times[host][0])
                    if wait > 0:
                        await asyncio.sleep(min(wait, 5.0))
                        now = time.monotonic()
                        self._prune_old(self._global_times)
                        self._prune_old(self._domain_times[host])
                    continue
                break

            now = time.monotonic()
            self._domain_times[host].append(now)
            self._global_times.append(now)
