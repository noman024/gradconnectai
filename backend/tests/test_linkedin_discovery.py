from app.services.discovery import linkedin_discovery as ld


def test_classify_linkedin_url():
    assert ld._classify_linkedin_url("https://www.linkedin.com/in/jane-doe") == "profile"
    assert ld._classify_linkedin_url("https://www.linkedin.com/posts/some-post") == "post"
    assert ld._classify_linkedin_url("https://www.linkedin.com/company/openai") == "company"


def test_recency_weight_prefers_posts_and_recent_year():
    w_profile = ld._recency_weight("https://www.linkedin.com/in/jane-doe")
    w_post = ld._recency_weight("https://www.linkedin.com/posts/jane-doe-2026-ai")
    assert w_post > w_profile


def test_session_reuse_and_use_count_increments():
    s1 = ld.get_or_create_linkedin_session(session_id="test-session-1")
    s2 = ld.get_or_create_linkedin_session(session_id="test-session-1")
    assert s1["session_id"] == s2["session_id"] == "test-session-1"
    assert s2["use_count"] >= 2
