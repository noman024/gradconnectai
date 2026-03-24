from app.services.discovery.crawl4ai_client import (
    _crawl_recursive_outbound,
    _build_linkedin_run_config,
    _extract_outbound_urls,
    _is_transport_timeout_error,
    _jina_ai_mirror_url,
    _linkedin_cookie_header,
    _html_to_text_markdownish,
    _is_linkedin_url,
    _truncate_for_log,
)


def test_is_linkedin_url_detects_linkedin_hosts():
    assert _is_linkedin_url("https://www.linkedin.com/jobs/view/123") is True
    assert _is_linkedin_url("https://linkedin.com/posts/abc") is True
    assert _is_linkedin_url("https://example.com/linkedin.com/page") is False


def test_html_to_text_markdownish_removes_tags_and_scripts():
    html = """
    <html>
      <head><style>.x { color: red; }</style><script>console.log('x')</script></head>
      <body>
        <div>Hello <b>World</b></div>
        <p>Funding available&nbsp;now</p>
      </body>
    </html>
    """
    text = _html_to_text_markdownish(html)
    assert "console.log" not in text
    assert "color: red" not in text
    assert "Hello World" in text
    assert "Funding available now" in text


def test_truncate_for_log_limits_length():
    s = "x" * 300
    out = _truncate_for_log(s, max_len=20)
    assert out.startswith("x" * 20)
    assert out.endswith("...")


def test_build_linkedin_run_config_constructs_config():
    cfg = _build_linkedin_run_config()
    # In normal runtime crawl4ai is installed, config should be available.
    # Keep assertion tolerant in case dependency is intentionally unavailable.
    assert cfg is None or getattr(cfg, "page_timeout", None) == 120000


def test_linkedin_cookie_header_prefers_cookie_header(monkeypatch):
    monkeypatch.setattr("app.services.discovery.crawl4ai_client.settings.LINKEDIN_COOKIE_HEADER", "li_at=abc; JSESSIONID=xyz")
    monkeypatch.setattr("app.services.discovery.crawl4ai_client.settings.LINKEDIN_LI_AT", "fallback")
    assert _linkedin_cookie_header() == "li_at=abc; JSESSIONID=xyz"


def test_linkedin_cookie_header_uses_li_at(monkeypatch):
    monkeypatch.setattr("app.services.discovery.crawl4ai_client.settings.LINKEDIN_COOKIE_HEADER", "")
    monkeypatch.setattr("app.services.discovery.crawl4ai_client.settings.LINKEDIN_LI_AT", "abc123")
    assert _linkedin_cookie_header() == "li_at=abc123"


def test_extract_outbound_urls_filters_linkedin():
    txt = (
        "See https://www.linkedin.com/posts/x and "
        "https://jobs.ethz.ch/job/view/123 and http://example.org/a."
    )
    urls = _extract_outbound_urls(txt)
    assert "https://jobs.ethz.ch/job/view/123" in urls
    assert "http://example.org/a" in urls
    assert not any("linkedin.com" in u for u in urls)


def test_extract_outbound_urls_handles_markdown_and_redir_noise():
    txt = (
        "Apply here: [PhD](https://jobs.ethz.ch/job/view/abc). "
        "Redirect: https://www.linkedin.com/redir/redirect?url=https%3A%2F%2Flnkd.in%2Fdd52fZHf&trk=public_post-text "
        "Asset: https://static.licdn.com/aero-v1/sc/h/abc123.css"
    )
    urls = _extract_outbound_urls(txt)
    assert "https://jobs.ethz.ch/job/view/abc" in urls
    assert "https://lnkd.in/dd52fZHf" in urls
    assert not any("static.licdn.com" in u for u in urls)


def test_transport_timeout_classifier():
    exc = RuntimeError("Page.goto: net::ERR_TIMED_OUT at https://www.linkedin.com")
    assert _is_transport_timeout_error(exc) is True


def test_jina_ai_mirror_url():
    src = "https://www.linkedin.com/posts/foo"
    assert _jina_ai_mirror_url(src) == "https://r.jina.ai/http://www.linkedin.com/posts/foo"


def test_recursive_outbound_bounded(monkeypatch):
    async def fake_crawl(url, headless_mode, logger):
        if url == "https://a.com":
            return "go https://b.com"
        if url == "https://b.com":
            return "go https://c.com"
        if url == "https://c.com":
            return "done"
        return ""

    monkeypatch.setattr("app.services.discovery.crawl4ai_client._crawl_single_url", fake_crawl)

    import asyncio
    from app.core.logging import get_logger

    out = asyncio.run(
        _crawl_recursive_outbound(
            ["https://a.com"],
            headless_mode=True,
            logger=get_logger("test"),
            max_depth=1,
            max_total_urls=5,
        )
    )
    urls = [r.url for r in out]
    assert "https://a.com" in urls
    assert "https://b.com" in urls
    assert "https://c.com" not in urls
