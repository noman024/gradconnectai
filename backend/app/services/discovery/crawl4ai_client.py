"""
Integration with Crawl4AI for richer, LLM-friendly crawling.

Used by the discovery pipeline to fetch pages and extract professor-like
records from Markdown instead of raw HTML when available.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.core.config import settings
from app.core.logging import get_logger

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    AsyncWebCrawler = None  # type: ignore
    BrowserConfig = None  # type: ignore
    CrawlerRunConfig = None  # type: ignore


@dataclass
class Crawl4AIResult:
    url: str
    markdown: str


def _truncate_for_log(value: str, max_len: int = 200) -> str:
    text = value or ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _is_linkedin_url(url: str) -> bool:
    try:
        return "linkedin.com" in (urlparse(url).netloc or "").lower()
    except Exception:
        return False


def _html_to_text_markdownish(html: str) -> str:
    """Convert raw HTML to plain markdown-ish text without extra dependencies."""
    text = html or ""
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)</div>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
    )
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_transport_timeout_error(exc: Exception) -> bool:
    msg = (repr(exc) + " " + str(exc)).lower()
    return any(
        token in msg
        for token in (
            "connecttimeout",
            "timed out",
            "handshake operation timed out",
            "net::err_timed_out",
            "acs-goto",
        )
    )


def _extract_outbound_urls(text: str) -> list[str]:
    src = text or ""
    urls: list[str] = []
    # Markdown-style links: [x](https://target)
    urls.extend(re.findall(r"\((https?://[^)\s]+)\)", src, flags=re.IGNORECASE))
    # Plain URLs
    urls.extend(re.findall(r"https?://[^\s\"'<>]+", src, flags=re.IGNORECASE))
    cleaned: list[str] = []
    for u in urls:
        v = u.strip().rstrip(").,;:\"'")
        if "](" in v:
            v = v.split("](", 1)[0]
        if "linkedin.com/redir/redirect?" in v:
            try:
                parsed = urlparse(v)
                target = parse_qs(parsed.query).get("url", [""])[0]
                if target:
                    v = unquote(target)
            except Exception:
                pass
        host = (urlparse(v).netloc or "").lower()
        path = (urlparse(v).path or "").lower()
        if not host or "linkedin.com" in host:
            continue
        if host.endswith("licdn.com"):
            continue
        if path.endswith((".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".woff", ".woff2")):
            continue
        if v not in cleaned:
            cleaned.append(v)
    return cleaned


def _jina_ai_mirror_url(target_url: str) -> str:
    # Free text mirror useful when direct LinkedIn transport is blocked.
    cleaned = (target_url or "").strip()
    cleaned = re.sub(r"^https?://", "", cleaned, flags=re.IGNORECASE)
    return f"https://r.jina.ai/http://{cleaned}"


async def _discover_outbound_links_from_linkedin(url: str, logger: Any) -> list[str]:
    try:
        mirror_url = _jina_ai_mirror_url(url)
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            resp = await client.get(mirror_url)
        if resp.status_code >= 400:
            logger.warning(
                "linkedin_bridge_mirror_http_failed",
                url=url,
                mirror_url=mirror_url,
                status_code=resp.status_code,
            )
            return []
        txt = resp.text or ""
        links = _extract_outbound_urls(txt)
        if not links:
            logger.warning("linkedin_bridge_no_outbound_links", url=url, mirror_url=mirror_url)
            return []
        logger.info("linkedin_bridge_links_discovered", url=url, count=len(links), sample=links[:3])
        return links[:5]
    except Exception as exc:
        logger.warning("linkedin_bridge_discovery_failed", url=url, error=repr(exc))
        return []


async def _crawl_single_url(url: str, headless_mode: bool, logger: Any) -> str:
    if AsyncWebCrawler is None or BrowserConfig is None:
        return ""
    browser_config = BrowserConfig(headless=headless_mode, verbose=True)
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            out = await crawler.arun(url=url)
        md = getattr(out, "markdown", None)
        if isinstance(md, str):
            return md
        if hasattr(md, "raw_markdown"):
            return md.raw_markdown or ""
    except Exception as exc:
        logger.warning("linkedin_bridge_crawl_failed", out_url=url, error=repr(exc))
    return ""


async def _crawl_recursive_outbound(
    seed_urls: list[str],
    *,
    headless_mode: bool,
    logger: Any,
    max_depth: int = 2,
    max_total_urls: int = 12,
) -> list[Crawl4AIResult]:
    """
    Recursively crawl discovered outbound URLs with bounded depth and volume.
    Designed for LinkedIn bridge mode when direct LinkedIn crawling is blocked.
    """
    results: list[Crawl4AIResult] = []
    visited: set[str] = set()
    queue: list[tuple[str, int]] = []
    for u in seed_urls:
        if u and u not in visited:
            queue.append((u, 0))

    while queue and len(visited) < max_total_urls:
        current_url, depth = queue.pop(0)
        if current_url in visited:
            continue
        visited.add(current_url)

        text = await _crawl_single_url(current_url, headless_mode=headless_mode, logger=logger)
        if not text:
            continue
        results.append(Crawl4AIResult(url=current_url, markdown=text))
        logger.info("linkedin_bridge_crawl_ok", out_url=current_url, depth=depth, markdown_len=len(text))

        if depth >= max_depth:
            continue
        for nxt in _extract_outbound_urls(text):
            if nxt in visited:
                continue
            if "linkedin.com" in (urlparse(nxt).netloc or "").lower():
                continue
            queue.append((nxt, depth + 1))
            if len(queue) + len(visited) >= max_total_urls:
                break

    return results


def _build_linkedin_run_config() -> Any | None:
    """
    LinkedIn pages are slower and often anti-bot gated.
    Give them a larger timeout and friendlier interaction defaults.
    """
    if CrawlerRunConfig is None:
        return None
    try:
        return CrawlerRunConfig(
            page_timeout=120000,
            wait_until="domcontentloaded",
            delay_before_return_html=0.5,
            wait_for_images=False,
            simulate_user=True,
            magic=True,
            remove_overlay_elements=True,
            scan_full_page=True,
        )
    except Exception:
        return None


def _linkedin_cookie_header() -> str | None:
    configured = (getattr(settings, "LINKEDIN_COOKIE_HEADER", "") or "").strip()
    if configured:
        return configured
    li_at = (getattr(settings, "LINKEDIN_LI_AT", "") or "").strip()
    if li_at:
        return f"li_at={li_at}"
    return None


def _install_linkedin_hooks(crawler: Any, logger: Any, cookie_header: str | None = None) -> None:
    """
    Install lightweight hooks to make LinkedIn navigation more reliable.
    Compatible with Crawl4AI 0.7.x/0.8.x by using **kwargs-friendly signatures.
    """
    strategy = getattr(crawler, "crawler_strategy", None)
    if strategy is None or not hasattr(strategy, "set_hook"):
        return

    async def on_page_context_created(page: Any, context: Any = None, **kwargs: Any) -> Any:
        try:
            if context is not None and hasattr(context, "route"):
                async def route_filter(route: Any) -> None:
                    try:
                        rt = str(getattr(route.request, "resource_type", "")).lower()
                        req_url = str(getattr(route.request, "url", "")).lower()
                        if rt in {"image", "font", "media"}:
                            await route.abort()
                            return
                        if any(k in req_url for k in ("doubleclick.net", "googletagmanager.com", "google-analytics.com")):
                            await route.abort()
                            return
                        await route.continue_()
                    except Exception:
                        try:
                            await route.continue_()
                        except Exception:
                            pass

                await context.route("**/*", route_filter)
            if hasattr(page, "set_viewport_size"):
                await page.set_viewport_size({"width": 1366, "height": 900})
        except Exception as exc:
            logger.warning("crawl4ai_linkedin_hook_page_context_failed", error=repr(exc))
        return page

    async def before_goto(page: Any, context: Any = None, url: str = "", **kwargs: Any) -> Any:
        try:
            if hasattr(page, "set_extra_http_headers"):
                headers = {
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.linkedin.com/",
                }
                if cookie_header:
                    headers["Cookie"] = cookie_header
                await page.set_extra_http_headers(headers)
        except Exception as exc:
            logger.warning("crawl4ai_linkedin_hook_before_goto_failed", url=url, error=repr(exc))
        return page

    async def after_goto(page: Any, context: Any = None, url: str = "", response: Any = None, **kwargs: Any) -> Any:
        try:
            content = await page.content() if hasattr(page, "content") else ""
            c = (content or "").lower()
            if any(
                marker in c
                for marker in (
                    "checkpoint/challenge",
                    "captcha",
                    "authwall",
                    "sign in to linkedin",
                )
            ):
                logger.warning("crawl4ai_linkedin_authwall_detected", url=url)
        except Exception as exc:
            logger.warning("crawl4ai_linkedin_hook_after_goto_failed", url=url, error=repr(exc))
        return page

    async def before_retrieve_html(page: Any, context: Any = None, **kwargs: Any) -> Any:
        try:
            if hasattr(page, "evaluate"):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        except Exception as exc:
            logger.warning("crawl4ai_linkedin_hook_before_html_failed", error=repr(exc))
        return page

    for hook_name, hook in (
        ("on_page_context_created", on_page_context_created),
        ("before_goto", before_goto),
        ("after_goto", after_goto),
        ("before_retrieve_html", before_retrieve_html),
    ):
        try:
            strategy.set_hook(hook_name, hook)
        except Exception as exc:
            logger.warning("crawl4ai_set_hook_failed", hook=hook_name, error=repr(exc))


async def _fetch_linkedin_fallback_markdown(url: str, logger: Any, cookie_header: str | None = None) -> str:
    """
    LinkedIn-aware fallback when Crawl4AI yields no markdown.
    We fetch raw HTML and convert to plain text so extraction can still run.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    attempts = (
        {"timeout": 20.0, "with_referer": False},
        {"timeout": 35.0, "with_referer": True},
    )
    saw_transport_timeout = False
    for idx, attempt in enumerate(attempts, start=1):
        req_headers = dict(headers)
        if attempt["with_referer"]:
            req_headers["Referer"] = "https://www.linkedin.com/"
        try:
            async with httpx.AsyncClient(
                timeout=attempt["timeout"],
                follow_redirects=True,
                headers=req_headers,
            ) as client:
                resp = await client.get(url)
            if resp.status_code >= 400:
                logger.warning(
                    "linkedin_fallback_http_failed",
                    url=url,
                    status_code=resp.status_code,
                    attempt=idx,
                )
                continue
            raw = resp.text or ""
            text = _html_to_text_markdownish(raw)
            if not text:
                logger.warning("linkedin_fallback_empty_text", url=url, attempt=idx)
                continue
            max_chars = int(getattr(settings, "LLM_MAX_INPUT_CHARS", 12000) or 12000)
            if len(text) > max_chars:
                text = text[:max_chars]
            return text
        except Exception as exc:
            if _is_transport_timeout_error(exc):
                saw_transport_timeout = True
                logger.warning(
                    "linkedin_transport_unreachable",
                    url=url,
                    attempt=idx,
                    classification="transport_timeout",
                    error=repr(exc),
                )
            logger.warning("linkedin_fallback_attempt_failed", url=url, attempt=idx, error=repr(exc))

    reason = "transport_unreachable" if saw_transport_timeout else "all_attempts_exhausted"
    logger.warning("linkedin_fallback_failed", url=url, reason=reason)
    return ""


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
    linkedin_cookie_header = _linkedin_cookie_header()
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            for url in urls:
                try:
                    run_config = None
                    if _is_linkedin_url(url):
                        _install_linkedin_hooks(crawler, logger, cookie_header=linkedin_cookie_header)
                        run_config = _build_linkedin_run_config()
                    out = await crawler.arun(url=url, config=run_config) if run_config is not None else await crawler.arun(url=url)
                except Exception as exc:
                    logger.warning("crawl4ai_page_failed", url=url, error=repr(exc))
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
        results = []

    # LinkedIn often returns sparse/blocked content to generic crawlers.
    # Fill missing LinkedIn pages via lightweight HTTP fallback text extraction.
    seen_result_urls = {r.url for r in results}
    for url in urls:
        if not _is_linkedin_url(url):
            continue
        if url in seen_result_urls:
            continue
        text = await _fetch_linkedin_fallback_markdown(url, logger, cookie_header=linkedin_cookie_header)
        if not text:
            outbound_links = await _discover_outbound_links_from_linkedin(url, logger)
            if outbound_links:
                logger.info(
                    "linkedin_bridge_crawl_start",
                    source_url=url,
                    outbound_count=len(outbound_links),
                )
                bridged = await _crawl_recursive_outbound(
                    outbound_links,
                    headless_mode=headless_mode,
                    logger=logger,
                    max_depth=2,
                    max_total_urls=12,
                )
                for r in bridged:
                    if r.url in seen_result_urls:
                        continue
                    results.append(r)
                    seen_result_urls.add(r.url)
            continue
        logger.info(
            "linkedin_fallback_page_ok",
            url=url,
            markdown_len=len(text),
            markdown_preview=text[:300].replace("\n", "\\n"),
        )
        results.append(Crawl4AIResult(url=url, markdown=text))
    return results

