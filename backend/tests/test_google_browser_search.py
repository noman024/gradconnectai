import asyncio

from app.services.discovery import google_browser_search as gbs


def test_google_browser_scoring_prefers_edu_and_rank():
    high = gbs._score_google_url("https://cs.example.edu/faculty", "machine learning professor", 1)
    low = gbs._score_google_url("https://example.com/blog", "machine learning professor", 5)
    assert high > low


def test_google_browser_search_graceful_when_playwright_missing(monkeypatch):
    monkeypatch.setattr(gbs, "async_playwright", None)
    out = asyncio.run(
        gbs.google_search_collect_links_browser(
            ["machine learning professor"],
            max_links_per_query=5,
        )
    )
    assert out["engine"] == "playwright"
    assert out["available"] is False
    assert out["total_deduped"] == 0
