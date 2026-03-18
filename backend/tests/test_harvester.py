import asyncio

from app.services.discovery import harvester


def test_merge_ranked_url_items_dedupes_and_boosts_sources():
    merged = harvester._merge_ranked_url_items(
        google_items=[{"url": "https://a.edu/faculty", "score": 0.5, "source": "google_http", "query": "q1"}],
        google_browser_items=[{"url": "https://a.edu/faculty", "score": 0.45, "source": "google_browser", "query": "q1"}],
        linkedin_items=[{"url": "https://linkedin.com/in/x", "score": 0.6, "source": "linkedin", "query": "q2", "kind": "profile"}],
    )
    assert len(merged) == 2
    a = [x for x in merged if x["url"] == "https://a.edu/faculty"][0]
    assert "google_http" in a["sources"]
    assert "google_browser" in a["sources"]
    assert a["score"] > 0.5


def test_run_automated_search_harvester_with_stubbed_sources(monkeypatch):
    async def _fake_google(*args, **kwargs):
        return {
            "queries_count": 1,
            "total_deduped": 1,
            "deduped_results": [{"url": "https://uni.edu/faculty", "host": "uni.edu", "score": 0.7, "query": "q"}],
        }

    async def _fake_google_browser(*args, **kwargs):
        return {"available": True, "total_deduped": 0, "deduped_results": []}

    async def _fake_linkedin(*args, **kwargs):
        return {
            "session": {"session_id": "s1"},
            "queries_count": 1,
            "total_ranked": 1,
            "ranked_results": [{"url": "https://www.linkedin.com/in/jane", "score": 0.8, "query": "q2", "kind": "profile"}],
        }

    monkeypatch.setattr(harvester, "google_search_collect_links", _fake_google)
    monkeypatch.setattr(harvester, "google_search_collect_links_browser", _fake_google_browser)
    monkeypatch.setattr(harvester, "discover_linkedin_candidates", _fake_linkedin)

    out = asyncio.run(
        harvester.run_automated_search_harvester(
            research_topics=["machine learning"],
            preferences={"fields": ["NLP"]},
            use_browser_google=True,
            top_k=10,
        )
    )
    assert out["total_seed_urls"] >= 2
    assert out["seed_urls"][0].startswith("http")
    assert "query_plan" in out
