from pathlib import Path

from app.services import llm_client


FIXTURES = Path(__file__).parent / "fixtures" / "evidence_gate"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_accepts_when_page_email_present_and_extracted(monkeypatch):
    markdown = _read("markdown_with_email.md")
    llm_payload = _read("llm_professors_email_ok.json")
    monkeypatch.setattr(llm_client, "_chat_completion", lambda *args, **kwargs: llm_payload)

    out = llm_client.extract_professors_from_markdown(
        markdown=markdown,
        university="Test University",
        page_url="https://uni.edu/faculty",
    )

    assert out is not None
    assert len(out) == 1
    evidence_types = {e["evidence_type"] for e in out[0]["_evidence"]}
    assert evidence_types == {"name", "email"}
    assert any((e.get("snippet") or "").strip() for e in out[0]["_evidence"])


def test_rejects_when_page_email_present_but_not_extracted(monkeypatch):
    markdown = _read("markdown_with_email.md")
    llm_payload = _read("llm_professors_missing_email.json")
    monkeypatch.setattr(llm_client, "_chat_completion", lambda *args, **kwargs: llm_payload)

    out = llm_client.extract_professors_from_markdown(
        markdown=markdown,
        university="Test University",
        page_url="https://uni.edu/faculty",
    )

    assert out is None


def test_accepts_profile_when_no_page_email(monkeypatch):
    markdown = _read("markdown_with_profile_only.md")
    llm_payload = _read("llm_professors_profile_ok.json")
    monkeypatch.setattr(llm_client, "_chat_completion", lambda *args, **kwargs: llm_payload)

    out = llm_client.extract_professors_from_markdown(
        markdown=markdown,
        university="Test University",
        page_url="https://uni.edu/lab",
    )

    assert out is not None
    assert len(out) == 1
    evidence_types = {e["evidence_type"] for e in out[0]["_evidence"]}
    assert evidence_types == {"name", "profile_url"}


def test_rejects_when_profile_url_not_in_page(monkeypatch):
    markdown = _read("markdown_with_profile_only.md")
    llm_payload = _read("llm_professors_profile_bad.json")
    monkeypatch.setattr(llm_client, "_chat_completion", lambda *args, **kwargs: llm_payload)

    out = llm_client.extract_professors_from_markdown(
        markdown=markdown,
        university="Test University",
        page_url="https://uni.edu/lab",
    )

    assert out is None
