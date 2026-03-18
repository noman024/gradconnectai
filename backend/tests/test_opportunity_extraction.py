from app.services import llm_client


def test_extract_professor_includes_structured_opportunity_fields(monkeypatch):
    markdown = """
    [Dr. Jane Doe](https://uni.edu/faculty/jane-doe) leads the AI lab.
    We are currently hiring motivated PhD students for Fall 2026.
    """
    payload = (
        '{"professors":[{"name":"Dr. Jane Doe","email":null,'
        '"profile_url":"https://uni.edu/faculty/jane-doe",'
        '"lab_focus":"AI systems and learning.",'
        '"research_topics":["machine learning","ai systems"],'
        '"opportunity_score":0.61,'
        '"opportunities":[{"type":"phd","signal":"hiring PhD students","confidence":0.87,'
        '"source_text":"currently hiring motivated PhD students for Fall 2026"}],'
        '"opportunity_explanation":"Page explicitly mentions active PhD hiring for Fall 2026."}]}'
    )
    monkeypatch.setattr(llm_client, "_chat_completion", lambda *args, **kwargs: payload)

    out = llm_client.extract_professors_from_markdown(
        markdown=markdown,
        university="Test University",
        page_url="https://uni.edu/lab",
    )
    assert out is not None
    assert len(out) == 1
    first = out[0]
    assert first["opportunities"]
    assert first["opportunities"][0]["type"] == "phd"
    assert first["opportunity_score"] >= 0.87
    assert first["opportunity_explanation"]
