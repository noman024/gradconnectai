"""
Email Generator: produce personalized draft (subject + body) for student–professor pair.
Uses professor's recent focus / lab and student's experience; tone conservative (professional, concise).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

# Default tone: professional, concise
DEFAULT_TONE = "professional"
DEFAULT_LENGTH = "concise"


@dataclass
class EmailDraft:
    subject: str
    body: str


def _call_llm(prompt: str) -> str:
    """Call local Ollama or placeholder. Returns generated text."""
    try:
        import httpx
        base = settings.OLLAMA_BASE_URL.rstrip("/")
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{base}/api/generate",
                json={"model": "llama3.2", "prompt": prompt, "stream": False},
            )
            if r.status_code != 200:
                return ""
            return (r.json().get("response") or "").strip()
    except Exception:
        return ""


def generate_draft(
    student_name: str,
    student_research_topics: list[str],
    student_experience_snippet: str,
    professor_name: str,
    professor_university: str,
    professor_lab_focus: str,
    professor_recent_paper_or_topic: str | None = None,
    tone: str = DEFAULT_TONE,
    length: str = DEFAULT_LENGTH,
) -> EmailDraft:
    """
    Generate one email draft. Personalization: professor's lab/focus, student's topics and experience.
    """
    topics_str = ", ".join(student_research_topics[:10]) if student_research_topics else "research"
    prompt = f"""Write a single short email (professional, {length}) from a graduate applicant to a professor.

Student: {student_name}. Research interests: {topics_str}. Relevant experience: {student_experience_snippet or 'N/A'}.
Professor: {professor_name} at {professor_university}. Lab/focus: {professor_lab_focus}.
{f'Recent work: {professor_recent_paper_or_topic}' if professor_recent_paper_or_topic else ''}

Requirements: {tone} tone, {length}. Include: brief intro, why their lab fits, one sentence on own background, polite ask for possibility of PhD/Master's position. No flattery. Output only the email body, no subject line."""
    body = _call_llm(prompt)
    if not body:
        body = _fallback_body(
            student_name, professor_name, professor_university, topics_str
        )
    subject = f"PhD/Master's inquiry — {student_name}"
    return EmailDraft(subject=subject, body=body)


def _fallback_body(
    student_name: str,
    professor_name: str,
    university: str,
    topics: str,
) -> str:
    return f"""Dear Professor {professor_name.split()[-1]},

I am {student_name}, and I am very interested in pursuing a graduate position in your group at {university}. My research interests include {topics}.

I would be grateful to know if you might have openings for a PhD or Master's student in the near future. I would be happy to share my CV and discuss my background.

Thank you for your time.

Best regards,
{student_name}"""
