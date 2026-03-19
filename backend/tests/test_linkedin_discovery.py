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


def test_build_linkedin_search_variants_prioritizes_posts():
    variants = ld._build_linkedin_search_variants("PhD in NLP funded scholarship")
    assert len(variants) >= 4
    assert variants[0].startswith("site:linkedin.com/posts ")
    assert any("feed/update" in v for v in variants)


def test_relevance_weight_detects_query_overlap():
    w_match = ld._relevance_weight(
        "https://www.linkedin.com/posts/ai-lab_funded-phd-nlp-activity-123",
        "funded PhD NLP",
    )
    w_miss = ld._relevance_weight(
        "https://www.linkedin.com/posts/random-sports-news-activity-123",
        "funded PhD NLP",
    )
    assert w_match > w_miss


def test_valid_linkedin_candidate_allows_feed_update_post():
    assert ld._is_valid_linkedin_candidate(
        "https://www.linkedin.com/feed/update/urn:li:activity:1234567890"
    )
    assert not ld._is_valid_linkedin_candidate(
        "https://www.linkedin.com/search/results/all/?keywords=phd%20in%20ai"
    )


def test_extract_native_linkedin_links_from_html():
    html = """
    <a href="/posts/some-user_activity-123">post</a>
    <a href="https://www.linkedin.com/in/jane-doe-12345">profile</a>
    <script>{"entityUrn":"urn:li:activity:7328837727785578497"}</script>
    <script>{"encoded":"urn%3Ali%3Aactivity%3A7328837727785578498"}</script>
    <script>{"unicodeEscaped":"urn\\\\u003Ali\\\\u003Aactivity\\\\u003A7328837727785578499"}</script>
    """
    links = ld._extract_native_linkedin_links(html)
    assert "https://www.linkedin.com/posts/some-user_activity-123" in links
    assert "https://www.linkedin.com/in/jane-doe-12345" in links
    assert "https://www.linkedin.com/feed/update/urn:li:activity:7328837727785578497" in links
    assert "https://www.linkedin.com/feed/update/urn:li:activity:7328837727785578498" in links


def test_build_linkedin_search_variants_removes_duplicate_site_operators():
    variants = ld._build_linkedin_search_variants(
        'site:linkedin.com/posts "nlp" professor phd hiring'
    )
    assert variants[0].count("site:linkedin.com/posts") == 1
    assert "site:linkedin.com/posts site:linkedin.com/posts" not in variants[0]


def test_linkedin_native_posts_search_url_uses_content_path():
    url = ld._linkedin_native_posts_search_url("phd in ai")
    assert "linkedin.com/search/results/content/" in url
    assert "keywords=phd+in+ai" in url


def test_normalize_linkedin_href_handles_relative_and_absolute():
    assert ld._normalize_linkedin_href("/posts/test-1") == "https://www.linkedin.com/posts/test-1"
    assert ld._normalize_linkedin_href("https://www.linkedin.com/in/user-1") == "https://www.linkedin.com/in/user-1"
    assert ld._normalize_linkedin_href("https://example.com/not-linkedin") == ""


def test_extract_activity_id_and_weight():
    url = "https://www.linkedin.com/feed/update/urn:li:activity:7328837727785578497/"
    aid = ld._extract_activity_id(url)
    assert aid == 7328837727785578497
    assert ld._activity_recency_weight(url) > 0


def test_build_linkedin_post_search_variants_posts_only():
    variants = ld._build_linkedin_post_search_variants('site:linkedin.com/posts "phd in ai"')
    assert variants
    assert all("site:linkedin.com/posts" in v or "site:linkedin.com/feed/update" in v for v in variants)


def test_cookie_header_parsing_helpers():
    header = "li_at=abc123; JSESSIONID=xyz; liap=true"
    assert ld._extract_li_at_from_cookie_header(header) == "abc123"
    pairs = ld._parse_cookie_header(header)
    assert ("li_at", "abc123") in pairs
    assert ("JSESSIONID", "xyz") in pairs
