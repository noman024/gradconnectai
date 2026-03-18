from app.services import llm_client


def test_markdown_link_fallback_extracts_professors_when_llm_empty(monkeypatch):
    markdown = """
    ### [Dr. Jane Doe](https://uni.edu/faculty/jane-doe)
    ### [Dr. John Smith](https://uni.edu/faculty/john-smith)
    """
    # Simulate weak LLM output.
    monkeypatch.setattr(llm_client, "_chat_completion", lambda *args, **kwargs: '{"professors":[]}')

    out = llm_client.extract_professors_from_markdown(
        markdown=markdown,
        university="Test University",
        page_url="https://uni.edu/faculty",
    )
    assert out is not None
    assert len(out) >= 2
    names = [x["name"] for x in out]
    assert any("Dr. Jane Doe" in n for n in names)
    assert all((x.get("profile_url") or "").startswith("https://") for x in out)
