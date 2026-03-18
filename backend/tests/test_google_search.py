from pathlib import Path

from app.services.discovery.google_search import (
    build_google_search_url,
    extract_google_result_links_from_html,
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
