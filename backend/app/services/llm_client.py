"""
Thin OpenAI-compatible LLM client.

Intended to talk to a vLLM-served Qwen3.5 endpoint exposed via the OpenAI
Chat Completions API (e.g. Qwen/Qwen3.5-0.8B).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.logging import get_logger


def _llm_base_url() -> str:
    return (settings.LLM_BASE_URL or "").rstrip("/")


def _llm_api_key() -> str:
    return settings.LLM_API_KEY or "EMPTY"


def _llm_model() -> str:
    return settings.LLM_MODEL or "Qwen/Qwen3.5-0.8B"


class TopicsResponse(BaseModel):
    topics: List[str]


class ProfessorItem(BaseModel):
    name: str
    email: Optional[str] = None
    lab_focus: Optional[str] = None
    research_topics: List[str] = []
    opportunity_score: float = 0.5


class ProfessorsResponse(BaseModel):
    professors: List[ProfessorItem]


def _chat_completion(
    messages: List[Dict[str, Any]],
    max_tokens: int = 512,
    temperature: float = 0.3,
    response_format: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Call an OpenAI-compatible /v1/chat/completions endpoint and return content text.
    Returns None on any failure.
    """
    base = _llm_base_url()
    if not base:
        return None
    url = f"{base}/chat/completions"
    logger = get_logger("llm_client")
    payload: Dict[str, Any] = {
        "model": _llm_model(),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 0.9,
        "stream": False,
    }
    if response_format is not None:
        # OpenAI-compatible structured outputs; Ollama maps this to its `format` parameter.
        payload["response_format"] = response_format
    headers = {
        "Authorization": f"Bearer {_llm_api_key()}",
        "Content-Type": "application/json",
    }
    try:
        # Keep LLM calls bounded so UI requests don't hang for too long.
        logger.info(
            "llm_request",
            url=url,
            model=payload.get("model"),
            max_tokens=payload.get("max_tokens"),
            temperature=payload.get("temperature"),
            messages_count=len(payload.get("messages") or []),
        )
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(url, headers=headers, json=payload)
        text_preview = resp.text[:1000] if resp.text else ""
        if resp.status_code != 200:
            logger.warning(
                "llm_non_200",
                status_code=resp.status_code,
                body=text_preview,
            )
            return None
        logger.info(
            "llm_response_ok",
            status_code=resp.status_code,
            body_preview=text_preview,
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content
    except Exception as exc:  # pragma: no cover - network issues
        logger.warning("llm_request_failed", error=str(exc))
        return None


def extract_topics_from_cv(cv_text: str, preference_fields: List[str]) -> Optional[List[str]]:
    """
    Use LLM to extract up to ~15 clean research topics from CV text and preference fields.
    Returns list of topics or None on failure.
    """
    if not cv_text:
        return None
    logger = get_logger("llm_client")
    user_prompt = (
        "You are an academic assistant. Extract ONLY research domains, methods, and application areas from the CV.\n\n"
        "STRICT RULES:\n"
        "- Include: for example: machine learning, NLP, computer vision, deep learning, reinforcement learning, "
        "graph neural networks, causal inference, HCI, econometrics, bioinformatics, etc.\n"
        "- EXCLUDE: personal names (e.g. John, Ahmed), job titles (Senior Engineer, Research Assistant), "
        "contact info (email, phone), generic words (team, project, experience, skills).\n"
        "- Each topic must be a research domain or method, not a person or role.\n"
        "- Return at most 12 topics.\n"
        "- Output MUST be pure JSON only: {\"topics\": [\"topic1\", \"topic2\", ...]}.\n\n"
        f"CV text:\n{cv_text[:32000]}\n\n"
        f"Stated fields (use if relevant): {', '.join(preference_fields) or 'none'}"
    )
    messages = [
        {"role": "system", "content": "You extract clean research topics from academic CVs."},
        {"role": "user", "content": user_prompt},
    ]
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "TopicsResponse",
            "schema": TopicsResponse.model_json_schema(),
            "strict": True,
        },
    }
    content = _chat_completion(messages, response_format=response_format)
    if not content:
        return None
    try:
        parsed = TopicsResponse.model_validate_json(content)
        topics = [t.strip() for t in parsed.topics if isinstance(t, str) and t.strip()]
        logger.info("llm_topics_extracted", count=len(topics), sample=topics[:5])
        return topics or None
    except ValidationError as exc:
        logger.warning("llm_topics_parse_failed", error=str(exc), raw=content[:200])
        return None


def extract_professors_from_markdown(
    markdown: str,
    university: str,
    page_url: str,
) -> Optional[List[Dict[str, Any]]]:
    """
    Use LLM to extract professor-like records from Markdown.
    Returns list of dicts with keys:
    - name (required)
    - email (optional)
    - lab_focus (optional short text)
    - research_topics (optional list[str])
    - opportunity_score (optional float 0-1)
    """
    if not markdown:
        return None
    logger = get_logger("llm_client")
    # Use a truncated, lowercased copy of the markdown to sanity-check that any
    # returned professor "name" actually occurs in the source text. This helps
    # avoid hallucinated people on generic opportunity/job pages.
    text_for_matching = markdown[:32000].lower()
    user_prompt = (
        "You are helping build a directory of academic supervisors.\n"
        "From the following page content, extract information about people who could be potential supervisors.\n\n"
        "Requirements:\n"
        "- Only include people (faculty, researchers, lab heads). Skip students and staff without research roles.\n"
        "- For each person, capture:\n"
        "  - name: their full name.\n"
        "  - email: their institutional email if present, otherwise null.\n"
        "  - lab_focus: one short sentence (~20-30 words) summarizing their research group or main research focus.\n"
        "  - research_topics: an array of 3-8 concise research topics (domains, methods, or application areas).\n"
        "  - opportunity_score: a number between 0 and 1 estimating how likely they are to be recruiting students now.\n"
        "    Use signals like 'open positions', 'hiring', 'scholarship', 'students wanted', or recent grant/project announcements.\n"
        "- If there are no clear hiring signals, set opportunity_score around 0.4–0.6.\n"
        "- Output MUST be pure JSON with this exact shape and nothing else:\n"
        '{\"professors\": [\n'
        '  {\"name\": \"...\", \"email\": \"...\" or null, \"lab_focus\": \"...\" or null,\n'
        '   \"research_topics\": [\"...\"], \"opportunity_score\": 0.0-1.0 },\n'
        "  ...\n"
        "]}.\n\n"
        f"University: {university}\n"
        f"Page URL: {page_url}\n\n"
        f"Page content (Markdown):\n{markdown[:32000]}\n"
    )
    messages = [
        {"role": "system", "content": "You extract structured supervisor data from academic lab and faculty pages."},
        {"role": "user", "content": user_prompt},
    ]
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "ProfessorsResponse",
            "schema": ProfessorsResponse.model_json_schema(),
            "strict": True,
        },
    }
    content = _chat_completion(messages, max_tokens=768, temperature=0.3, response_format=response_format)
    if not content:
        return None
    try:
        parsed = ProfessorsResponse.model_validate_json(content)
        cleaned: List[Dict[str, Any]] = []
        # Log raw structured output for debugging (truncated).
        try:
            logger.info(
                "llm_profs_raw",
                total=len(parsed.professors),
                sample=[(p.name or "")[:80] for p in parsed.professors[:5]],
            )
        except Exception:
            pass

        forbidden_name_tokens = {
            "university",
            "department",
            "faculty",
            "school",
            "institute",
            "center",
            "centre",
            "college",
        }
        forbidden_role_tokens = {
            "phd",
            "student",
            "position",
            "positions",
            "scholarship",
            "fellowship",
            "postdoc",
            "vacancy",
            "opportunity",
            "opportunities",
        }
        forbidden_ui_tokens = {
            "application",
            "applications",
            "application form",
            "apply",
            "apply now",
            "contact",
            "contact us",
            "home",
            "news",
            "events",
            "people",
            "team",
            "staff",
        }
        for p in parsed.professors:
            name = p.name.strip()
            if not name:
                continue
            lower_name = name.lower()
            # 1) Name must actually appear in the page text (avoid pure hallucinations).
            if lower_name not in text_for_matching:
                continue
            parts = [part for part in name.split() if part.strip()]
            # 2) Require at least two tokens.
            if len(parts) < 2:
                continue
            # 3) Drop obvious organization / non-person terms.
            if any(tok in lower_name for tok in forbidden_name_tokens):
                continue
            # 4) Drop titles/roles / UI labels that clearly indicate a position, not a person.
            if any(tok in lower_name for tok in forbidden_role_tokens | forbidden_ui_tokens):
                continue
            # 5) Require that at least two tokens look like proper-name style (e.g. "Alice", "Smith").
            def _looks_like_name_token(t: str) -> bool:
                return len(t) > 1 and t[0].isupper() and t[1:].islower()

            name_like_tokens = [t for t in parts if _looks_like_name_token(t)]
            if len(name_like_tokens) < 2:
                continue
            # 6) Drop tokens that are all-caps short acronyms (e.g. "AI", "ML", "NLP").
            if any(t.isupper() and len(t) <= 4 for t in parts):
                continue
            topics = [t.strip() for t in (p.research_topics or []) if isinstance(t, str) and t.strip()]
            opp = p.opportunity_score
            if not (0.0 <= opp <= 1.0):
                opp = 0.5
            cleaned.append(
                {
                    "name": name,
                    "email": p.email or None,
                    "lab_focus": (p.lab_focus or None),
                    "research_topics": topics,
                    "opportunity_score": opp,
                }
            )
        logger.info("llm_profs_extracted", count=len(cleaned), sample=[c["name"] for c in cleaned[:3]])
        return cleaned or None
    except ValidationError as exc:
        logger.warning("llm_profs_parse_failed", error=str(exc), raw=content[:200])
        return None

