from app.services.discovery.url_prioritizer import prioritize_seed_urls


def test_prioritizer_prefers_faculty_edu_urls():
    urls = [
        "https://example.com/admission",
        "https://cs.example.edu/faculty",
        "https://news.example.com/announcement",
    ]
    ranked = prioritize_seed_urls(urls, "Example University")
    assert ranked[0] == "https://cs.example.edu/faculty"


def test_prioritizer_keeps_stable_order_for_ties():
    urls = [
        "https://example.org/page-a",
        "https://example.org/page-b",
    ]
    ranked = prioritize_seed_urls(urls, "Unknown University")
    assert ranked == urls
