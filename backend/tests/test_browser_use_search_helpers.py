from app.services.discovery.browser_use_search import (
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
