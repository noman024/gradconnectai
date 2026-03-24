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

    async def _fake_browser_use(*args, **kwargs):
        return {"total": 0, "ranked_results": [], "errors": None}

    monkeypatch.setattr(harvester, "google_search_collect_links", _fake_google)
    monkeypatch.setattr(harvester, "google_search_collect_links_browser", _fake_google_browser)
    monkeypatch.setattr(harvester, "discover_linkedin_candidates", _fake_linkedin)
    monkeypatch.setattr(harvester, "browser_use_collect_linkedin_posts", _fake_browser_use)

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


def test_verified_filter_drops_noisy_domains():
    items = [
        {
            "url": "https://en.wikipedia.org/wiki/ML",
            "host": "en.wikipedia.org",
            "score": 1.0,
            "source": "google_http",
            "query": "q",
            "kind": None,
        },
        {
            "url": "https://www.linkedin.com/jobs/view/123",
            "host": "www.linkedin.com",
            "score": 0.8,
            "source": "linkedin",
            "query": "q2",
            "kind": "jobs",
        },
        {
            "url": "https://cs.example.edu/faculty",
            "host": "cs.example.edu",
            "score": 0.7,
            "source": "google_http",
            "query": "q3",
            "kind": None,
        },
    ]
    verified, dropped = harvester._apply_verified_filter(items)
    assert dropped == 1
    assert len(verified) == 2
    assert all(v.get("verification_reason") for v in verified)


def test_harvester_skips_http_when_browser_already_fallbacked(monkeypatch):
    monkeypatch.setattr(harvester.settings, "SEARCH_ENABLE_GOOGLE", True)

    async def _should_not_be_called(*args, **kwargs):
        raise AssertionError("google_search_collect_links should not run when browser fallback_used is true")

    async def _fake_google_browser(*args, **kwargs):
        return {
            "available": True,
            "fallback_used": True,
            "queries_count": 1,
            "total_deduped": 1,
            "deduped_results": [
                {"url": "https://uni.edu/faculty", "host": "uni.edu", "score": 0.7, "query": "q"}
            ],
        }

    async def _fake_linkedin(*args, **kwargs):
        return {
            "session": {"session_id": "s1"},
            "queries_count": 1,
            "total_ranked": 0,
            "ranked_results": [],
        }

    async def _fake_browser_use(*args, **kwargs):
        return {"total": 0, "ranked_results": [], "errors": None}

    monkeypatch.setattr(harvester, "google_search_collect_links", _should_not_be_called)
    monkeypatch.setattr(harvester, "google_search_collect_links_browser", _fake_google_browser)
    monkeypatch.setattr(harvester, "discover_linkedin_candidates", _fake_linkedin)
    monkeypatch.setattr(harvester, "browser_use_collect_linkedin_posts", _fake_browser_use)

    out = asyncio.run(
        harvester.run_automated_search_harvester(
            research_topics=["machine learning"],
            preferences={"fields": ["NLP"]},
            use_browser_google=True,
            top_k=10,
        )
    )
    assert out["google_http"]["total_deduped"] == 1
    assert out["google_browser"]["total_deduped"] == 1
    assert out["total_seed_urls"] >= 1


def test_filter_crawl_seed_candidates_drops_bare_and_linkedin_jobs():
    items = [
        {"url": "https://example.edu", "host": "example.edu", "score": 1.0, "source": "google_http"},
        {"url": "https://www.linkedin.com/jobs/view/123", "host": "www.linkedin.com", "score": 0.9, "source": "linkedin"},
        {"url": "https://www.linkedin.com/in/jane-doe", "host": "www.linkedin.com", "score": 0.8, "source": "linkedin"},
        {"url": "https://example.edu/faculty/ml-lab", "host": "example.edu", "score": 0.7, "source": "google_http"},
    ]
    filtered, dropped = harvester._filter_crawl_seed_candidates(items)
    assert dropped == 1
    urls = [x["url"] for x in filtered]
    assert "https://www.linkedin.com/jobs/view/123" in urls
    assert "https://www.linkedin.com/in/jane-doe" in urls
    assert "https://example.edu/faculty/ml-lab" in urls
