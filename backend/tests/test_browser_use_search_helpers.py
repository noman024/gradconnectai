import asyncio

from app.services.discovery.browser_use_search import (
    _browser_session_close_compat,
    _browser_session_get_pages_compat,
    _extract_ddg_result_urls,
    _is_valid_absolute_url,
    _is_result_link,
    _normalize_result_url,
)


def test_normalize_ddg_redirect_url_extracts_uddg():
    src = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.mit.edu%2Fresearch%2Fml"
    out = _normalize_result_url(src)
    assert out == "https://www.mit.edu/research/ml"


def test_extract_ddg_result_urls_uses_result_anchors_only():
    html = """
    <html>
      <body>
        <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fcs.stanford.edu%2Fpeople%2Ffaculty">Result 1</a>
        <a class="result__a" href="https://example.com/openings/phd">Result 2</a>
        <a href="https://duckduckgo.com/about">About DDG</a>
      </body>
    </html>
    """
    urls = _extract_ddg_result_urls(html)
    assert "https://cs.stanford.edu/people/faculty" in urls
    assert "https://example.com/openings/phd" in urls
    assert not any("duckduckgo.com/about" in u for u in urls)


def test_extract_ddg_result_urls_handles_href_before_class():
    html = """
    <html><body>
      <a href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fopenreview.net%2Fgroup%3Fid%3DML"
         class="result__a">ML Result</a>
    </body></html>
    """
    urls = _extract_ddg_result_urls(html)
    assert "https://openreview.net/group" in urls[0]


def test_extract_ddg_result_urls_supports_data_testid_anchor():
    html = """
    <html><body>
      <a data-testid="result-title-a" href="https://www.microsoft.com/en-us/research/careers/open-positions">
        Microsoft Open Positions
      </a>
    </body></html>
    """
    urls = _extract_ddg_result_urls(html)
    assert urls == ["https://www.microsoft.com/en-us/research/careers/open-positions"]


def test_extract_ddg_result_urls_fallback_absolute_links_when_no_markers():
    html = """
    <html><body>
      <a href="https://duckduckgo.com/about">About</a>
      <a href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fjobs.apple.com%2Fen-us%2Fdetails%2F200650849">
        Apple Job
      </a>
      <a href="https://www.microsoft.com/en-us/research/careers/open-positions">MSR Openings</a>
    </body></html>
    """
    urls = _extract_ddg_result_urls(html)
    assert "https://jobs.apple.com/en-us/details/200650849" in urls
    assert "https://www.microsoft.com/en-us/research/careers/open-positions" in urls
    assert not any("duckduckgo.com/about" in u for u in urls)


def test_is_result_link_filters_search_engines():
    assert _is_result_link("https://www.mit.edu") is True
    assert _is_result_link("https://duckduckgo.com/?q=test") is False
    assert _is_result_link("https://www.bing.com/search?q=test") is False


def test_invalid_pretty_breadcrumb_url_is_rejected():
    bad = "https://www.microsoft.com/en-us › research › careers"
    assert _is_valid_absolute_url(bad) is False


class _DummyPage:
    def __init__(self, url: str):
        self.url = url

    async def content(self) -> str:
        return "<html></html>"


class _BrowserWithGetPagesStop:
    def __init__(self):
        self.stopped = False

    async def get_pages(self):
        return [_DummyPage("https://example.com")]

    async def stop(self):
        self.stopped = True


class _BrowserWithLegacyMethods:
    def __init__(self):
        self.closed = False

    async def get_all_pages(self):
        return [_DummyPage("https://legacy.example.com")]

    async def close(self):
        self.closed = True


def test_browser_session_compat_prefers_modern_methods():
    browser = _BrowserWithGetPagesStop()
    pages = asyncio.run(_browser_session_get_pages_compat(browser))
    asyncio.run(_browser_session_close_compat(browser))
    assert len(pages) == 1
    assert pages[0].url == "https://example.com"
    assert browser.stopped is True


def test_browser_session_compat_supports_legacy_methods():
    browser = _BrowserWithLegacyMethods()
    pages = asyncio.run(_browser_session_get_pages_compat(browser))
    asyncio.run(_browser_session_close_compat(browser))
    assert len(pages) == 1
    assert pages[0].url == "https://legacy.example.com"
    assert browser.closed is True
