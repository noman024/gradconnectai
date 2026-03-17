"""
Respect robots.txt: fetch and parse, exclude disallowed paths and honour crawl-delay if present.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Callable

import httpx

try:
    from robotexclusionrulesparser import RobotExclusionRulesParser
except ImportError:
    RobotExclusionRulesParser = None  # type: ignore


@dataclass
class RobotsResult:
    allowed: bool
    crawl_delay_seconds: float | None  # None = not specified


def _no_parser(url: str, path: str, user_agent: str) -> RobotsResult:
    """When robotexclusionrulesparser is not installed, allow by default but log."""
    return RobotsResult(allowed=True, crawl_delay_seconds=None)


def _check_with_parser(url: str, path: str, user_agent: str) -> RobotsResult:
    if not RobotExclusionRulesParser:
        return _no_parser(url, path, user_agent)
    parsed = urllib.parse.urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urllib.parse.urljoin(base_url, "/robots.txt")
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(robots_url, headers={"User-Agent": user_agent})
            if resp.status_code != 200:
                return RobotsResult(allowed=True, crawl_delay_seconds=None)
            parser = RobotExclusionRulesParser()
            parser.parse(resp.text)
            allowed = parser.is_allowed(user_agent, urllib.parse.urljoin(base_url, path or "/"))
            delay: float | None = getattr(parser, "crawl_delay", None)
            if delay is not None:
                try:
                    delay = float(delay)
                except (TypeError, ValueError):
                    delay = None
            return RobotsResult(allowed=bool(allowed), crawl_delay_seconds=delay)
    except Exception:
        return RobotsResult(allowed=True, crawl_delay_seconds=None)


def check_robots(url: str, path: str | None = None, user_agent: str = "GradConnectAI/1.0") -> RobotsResult:
    """
    Return whether the given path (or URL path) is allowed for user_agent.
    path should be the path component of the URL (e.g. /faculty/name).
    """
    if path is None:
        path = urllib.parse.urlparse(url).path or "/"
    return _check_with_parser(url, path, user_agent)
