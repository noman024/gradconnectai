"""
Email Generator: produce personalized draft (subject + body) for student–professor pair.
Uses professor's lab_focus and research_topics; student's research_topics and experience.
Tone: professional, concise. Sanitizes topics to avoid names/job titles in output.
"""
from __future__ import annotations

import re
from app.core.logging import get_logger
from app.services.llm_client import _chat_completion
from app.core.config import settings

# Default tone: professional, concise
DEFAULT_TONE = "professional"
DEFAULT_LENGTH = "concise"

# Words to exclude from research topics (noise, job titles, contact info)
_NOISE_WORDS = frozenset(
    {
        "email",
        "phone",
        "linkedin",
        "github",
        "cv",
        "resume",
        "senior",
        "junior",
        "engineer",
        "scientist",
        "researcher",
        "assistant",
        "intern",
        "student",
        "the",
        "and",
        "with",
        "from",
        "experience",
        "project",
        "team",
        "company",
    }
)


class EmailDraft:
    def __init__(self, subject: str, body: str) -> None:
        self.subject = subject
        self.body = body


def _sanitize_topics(topics: list[str]) -> list[str]:
    """Filter out names, job titles, and noise from research topics."""
    out = []
    for t in (t.strip() for t in topics if isinstance(t, str) and t.strip()):
        lower = t.lower()
        if lower in _NOISE_WORDS:
            continue
        if len(t) < 3:
            continue
        # Skip if looks like a single name (e.g. "Mutasim", "Billah")
        if re.match(r"^[A-Z][a-z]+$", t) and len(t) < 12:
            continue
        out.append(t)
    return out[:12]  # cap at 12 for prompt


def _call_llm(prompt: str) -> str:
    """Call LLM via OpenAI-compatible endpoint or fallback template."""
    logger = get_logger("email_generator")
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert academic writing assistant. You write SHORT, PRECISE, highly targeted outreach emails "
                "from graduate applicants to potential research supervisors.\n\n"
                "HARD REQUIREMENTS:\n"
                "- Output ONLY the final email body (no subject line), starting with a salutation like 'Dear Professor ...' "
                "and ending with the student's name.\n"
                "- DO NOT include any analysis, thinking process, self-talk, or explanation such as 'Let me think', "
                "'To answer this', 'Wait', or similar.\n"
                "- DO NOT mention that you are an AI or that you are composing an email. The text must read as if written "
                "directly by the student.\n"
                "- The email must be concise (8–12 sentences max) but MUST clearly demonstrate why the student is an "
                "excellent fit for the professor: connect the student's research topics and experience to the lab's focus.\n"
                "- Use ONLY the research topics and information provided. Do NOT invent extra publications, awards, or details.\n"
                "- Tone: professional, respectful, and specific about research fit. End with a polite ask about PhD/Master's "
                "opportunities and willingness to provide further materials.\n"
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]
    # Low temperature to reduce verbose / meta reasoning.
    max_out = int(getattr(settings, "LLM_MAX_OUTPUT_TOKENS_EMAIL", 768) or 768)
    text = _chat_completion(messages, max_tokens=max_out, temperature=0.1)
    if not text:
        logger.warning("email_llm_error", error="llm_empty_response")
        return ""
    logger.info("email_llm_success", length=len(text))
    return text


def generate_draft(
    student_name: str,
    student_research_topics: list[str],
    student_experience_snippet: str,
    professor_name: str,
    professor_university: str,
    professor_lab_focus: str,
    professor_research_topics: list[str] | None = None,
    professor_recent_paper_or_topic: str | None = None,
    tone: str = DEFAULT_TONE,
    length: str = DEFAULT_LENGTH,
) -> EmailDraft:
    """
    Generate one email draft. Personalization: professor's lab/focus, student's topics.
    Sanitizes topics to avoid names and noise in the output.
    """
    logger = get_logger("email_generator")
    clean_topics = _sanitize_topics(student_research_topics or [])
    topics_str = ", ".join(clean_topics) if clean_topics else "research"
    prof_topics = professor_research_topics or []
    prof_topics_str = ", ".join(prof_topics[:5]) if prof_topics else ""
    lab_focus = professor_lab_focus or prof_topics_str or "research"

    prompt = f"""Write a single short email (professional, {length}) from a graduate applicant to a professor.

Student: {student_name}.
Research interests (use these exact domains): {topics_str}.
Relevant experience: {student_experience_snippet or 'Graduate applicant with background in the above areas'}.

Professor: {professor_name} at {professor_university}.
Lab/research focus: {lab_focus}.
{f'Professor research areas: {prof_topics_str}.' if prof_topics_str else ''}
{f'Recent work: {professor_recent_paper_or_topic}' if professor_recent_paper_or_topic else ''}

Requirements:
- {tone} tone, {length}.
- Brief intro, why their lab fits your interests, one sentence on your background, polite ask for PhD/Master's position.
- Do NOT include personal names beyond the student and professor. Do NOT list job titles or generic words as research interests.
- Output ONLY the email body. No subject line."""

    body = _call_llm(prompt)
    # Post-process to remove meta-reasoning and keep only the actual email body.
    if body:
        # 1) Line-level filtering (drop whole meta lines).
        raw_lines = [ln.rstrip() for ln in body.splitlines()]
        META_PREFIXES = (
            "To answer this",
            "Let me think",
            "Let me start by",
            "Wait, let me",
            "Wait a minute",
            "Now, how can I",
            "First, I need to",
            "Next, I need to",
            "Now, let me",
        )
        line_filtered: list[str] = []
        for ln in raw_lines:
            stripped = ln.lstrip()
            if any(stripped.startswith(p) for p in META_PREFIXES):
                continue
            # Also drop trailing meta comment lines about the email itself.
            lower = stripped.lower()
            if "this email" in lower and ("aims to" in lower or "intends to" in lower):
                continue
            line_filtered.append(ln)

        # 2) Sentence-level filtering to remove meta sentences embedded in paragraphs.
        text = "\n".join(line_filtered)
        # Naive sentence split on ., ?, ! while preserving delimiters.
        import re as _re

        parts = _re.split(r"([\.!?])", text)
        sentences: list[str] = []
        for i in range(0, len(parts), 2):
            chunk = parts[i]
            if not chunk.strip():
                continue
            end = parts[i + 1] if i + 1 < len(parts) else ""
            sent = (chunk + end).strip()
            lower = sent.lower()
            if any(
                phrase in lower
                for phrase in (
                    "let me think",
                    "wait a minute",
                    "wait, let me",
                    "now, how can i",
                    "how can i best convey",
                )
            ):
                continue
            sentences.append(sent)

        cleaned = " ".join(sentences).strip()

        # 3) Keep only from first salutation to last non-empty line.
        cleaned_lines = [ln.rstrip() for ln in cleaned.splitlines() if ln.strip() or ln == ""]
        start_idx = 0
        for i, ln in enumerate(cleaned_lines):
            if ln.lstrip().startswith(("Dear ", "Hi ", "Hello ")):
                start_idx = i
                break
        end_idx = len(cleaned_lines)
        for i in range(len(cleaned_lines) - 1, -1, -1):
            if cleaned_lines[i].strip():
                end_idx = i + 1
                break
        body = "\n".join(cleaned_lines[start_idx:end_idx]).strip()
    if not body:
        body = _fallback_body(
            student_name, professor_name, professor_university, topics_str
        )
        logger.info("email_fallback_used")
    subject = f"PhD/Master's inquiry — {student_name}"
    logger.info(
        "email_generated",
        student_name=student_name,
        professor_name=professor_name,
        university=professor_university,
        topics_preview=topics_str[:80],
    )
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
