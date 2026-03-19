from pathlib import Path

from app.services.discovery.google_search import (
    build_brave_search_url,
    build_google_search_url,
    extract_google_result_links_from_html,
    extract_http_links_from_html,
    extract_links_from_bing_rss,
)


FIXTURES = Path(__file__).parent / "fixtures" / "google_search"


def test_build_google_search_url_encodes_query():
    url = build_google_search_url("machine learning phd", num=12)
    assert "q=machine+learning+phd" in url
    assert "num=12" in url


def test_extract_google_result_links_from_fixture():
    html = (FIXTURES / "google_results_sample.html").read_text(encoding="utf-8")
    links = extract_google_result_links_from_html(html)
    assert len(links) == 3
    assert links[0] == "https://cs.example.edu/faculty"
    assert links[1].startswith("https://scholar.google.com/")


def test_extract_http_links_supports_ddg_redirect_pattern():
    html = '<a href="/l/?kh=-1&uddg=https%3A%2F%2Fexample.edu%2Ffaculty">x</a>'
    links = extract_http_links_from_html(html)
    assert "https://example.edu/faculty" in links


def test_extract_links_from_bing_rss_filters_search_link():
    xml = (
        "<rss><channel>"
        "<link>https://www.bing.com/search?q=test</link>"
        "<item><link>https://example.edu/faculty</link></item>"
        "</channel></rss>"
    )
    links = extract_links_from_bing_rss(xml)
    assert links == ["https://example.edu/faculty"]


def test_build_brave_search_url_encodes_query():
    url = build_brave_search_url("phd in ai", num=20)
    assert "q=phd+in+ai" in url
    assert "search.brave.com" in url


def test_extract_http_links_excludes_brave_own_urls():
    html = (
        '<a href="https://search.brave.com/something">x</a>'
        '<a href="https://www.linkedin.com/posts/test-post-123">y</a>'
        '<a href="https://example.edu/faculty">z</a>'
    )
    links = extract_http_links_from_html(html)
    assert "https://www.linkedin.com/posts/test-post-123" in links
    assert "https://example.edu/faculty" in links
    assert all("brave.com" not in u for u in links)
