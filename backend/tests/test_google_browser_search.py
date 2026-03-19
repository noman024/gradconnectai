import asyncio
from unittest.mock import AsyncMock, patch

from app.services.discovery import google_browser_search as gbs


def test_google_browser_scoring_prefers_edu_and_rank():
    high = gbs._score_google_url("https://cs.example.edu/faculty", "machine learning professor", 1)
    low = gbs._score_google_url("https://example.com/blog", "machine learning professor", 5)
    assert high > low


def test_google_browser_search_graceful_when_browser_use_missing(monkeypatch):
    monkeypatch.setattr(gbs, "_ensure_browser_use", lambda: False)
    mock_fallback = AsyncMock(return_value={
        "queries_count": 1, "per_query": {}, "deduped_results": [], "total_deduped": 0,
    })
    with patch.object(gbs, "google_search_collect_links", mock_fallback):
        out = asyncio.run(
            gbs.google_search_collect_links_browser(
                ["machine learning professor"], max_links_per_query=5,
            )
        )
    assert out["engine"] == "browser_use"
    assert out["available"] is False
    assert out["fallback_used"] is True
