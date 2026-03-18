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


def _truncate(text: str, limit: int) -> str:
    if not text:
        return ""
    if limit <= 0:
        return ""
    return text[:limit]


class TopicsResponse(BaseModel):
    topics: List[str]


class ProfessorItem(BaseModel):
    name: str
    email: Optional[str] = None
    profile_url: Optional[str] = None
    lab_focus: Optional[str] = None
    research_topics: List[str] = []
    opportunity_score: float = 0.5
    opportunities: List[Dict[str, Any]] = []
    opportunity_explanation: Optional[str] = None


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
    max_in = int(getattr(settings, "LLM_MAX_INPUT_CHARS", 32000) or 32000)
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
        f"CV text:\n{_truncate(cv_text, max_in)}\n\n"
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
    max_out = int(getattr(settings, "LLM_MAX_OUTPUT_TOKENS_TOPICS", 256) or 256)
    content = _chat_completion(messages, max_tokens=max_out, response_format=response_format)
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
    - opportunities (optional list of structured opportunities)
    - opportunity_explanation (optional short rationale)
    """
    if not markdown:
        return None
    logger = get_logger("llm_client")
    max_in = int(getattr(settings, "LLM_MAX_INPUT_CHARS", 32000) or 32000)
    # Use a truncated, lowercased copy of the markdown to sanity-check that any
    # returned professor "name" actually occurs in the source text. This helps
    # avoid hallucinated people on generic opportunity/job pages.
    truncated_md = _truncate(markdown, max_in)
    text_for_matching = truncated_md.lower()
    user_prompt = (
        "You are helping build a directory of academic supervisors.\n"
        "From the following page content, extract information about people who could be potential supervisors.\n\n"
        "Requirements:\n"
        "- Only include people (faculty, researchers, lab heads). Skip students and staff without research roles.\n"
        "- IMPORTANT: Include a person even if their email is not shown, as long as a profile link exists on the page.\n"
        "  The page content is in Markdown; names are often written as Markdown links like: [Dr. Jane Doe](https://.../profile).\n"
        "- For each person, capture:\n"
        "  - name: their full name.\n"
        "  - email: their institutional email if present, otherwise null.\n"
        "  - profile_url: a URL pointing to their profile page if present on the page (e.g. faculty profile, lab profile, LinkedIn profile), otherwise null.\n"
        "  - lab_focus: one short sentence (<=20 words) summarizing their research group or main research focus.\n"
        "  - research_topics: an array of 3-5 concise research topics (domains, methods, or application areas).\n"
        "  - opportunity_score: a number between 0 and 1 estimating how likely they are to be recruiting students now.\n"
        "    Use signals like 'open positions', 'hiring', 'scholarship', 'students wanted', or recent grant/project announcements.\n"
        "  - opportunities: array (0-3) of structured opportunities, each with:\n"
        "    - type: one of \"master\", \"phd\", \"postdoc\".\n"
        "    - signal: short phrase indicating why opportunity may exist.\n"
        "    - confidence: number between 0 and 1.\n"
        "    - source_text: optional short quoted text (<=140 chars) from page that supports the signal.\n"
        "  - opportunity_explanation: one short sentence (<=24 words) summarizing why opportunity_score was assigned.\n"
        "- If there are no clear hiring signals, set opportunity_score around 0.4–0.6.\n"
        "- If the page is a faculty list, extract as many real faculty as possible (prefer those explicitly labeled Professor/Associate Professor/Assistant Professor).\n"
        "- Return at most 25 professors.\n"
        "- Output MUST be pure JSON with this exact shape and nothing else:\n"
        '{\"professors\": [\n'
        '  {\"name\": \"...\", \"email\": \"...\" or null, \"profile_url\": \"...\" or null, \"lab_focus\": \"...\" or null,\n'
        '   \"research_topics\": [\"...\"], \"opportunity_score\": 0.0-1.0,\n'
        '   \"opportunities\": [{\"type\":\"phd|master|postdoc\",\"signal\":\"...\",\"confidence\":0.0-1.0,\"source_text\":\"...\"}],\n'
        '   \"opportunity_explanation\": \"...\" },\n'
        "  ...\n"
        "]}.\n\n"
        f"University: {university}\n"
        f"Page URL: {page_url}\n\n"
        f"Page content (Markdown):\n{truncated_md}\n"
    )
    messages = [
        {"role": "system", "content": "You extract structured supervisor data from academic lab and faculty pages."},
        {"role": "user", "content": user_prompt},
    ]

    def _find_snippet(text: str, needle: str, radius: int = 120) -> Optional[str]:
        if not text or not needle:
            return None
        idx = text.lower().find(needle.lower())
        if idx < 0:
            return None
        start = max(0, idx - radius)
        end = min(len(text), idx + len(needle) + radius)
        snippet = text[start:end].strip()
        if not snippet:
            return None
        return snippet.replace("\n", " ")
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "ProfessorsResponse",
            "schema": ProfessorsResponse.model_json_schema(),
            "strict": True,
        },
    }
    # Allow larger outputs for faculty lists; the JSON schema is strict so truncation is the main risk.
    max_out = int(getattr(settings, "LLM_MAX_OUTPUT_TOKENS_PROFESSORS", 2048) or 2048)
    content = _chat_completion(messages, max_tokens=max_out, temperature=0.2, response_format=response_format)
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

        def _extract_emails_with_obfuscation(text: str) -> set[str]:
            """
            Extract emails from text including common obfuscations.
            Returns lowercased normalized emails.
            """
            import re as _re

            out: set[str] = set()
            # 1) Normal emails
            email_re = _re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
            for m in email_re.findall(text):
                out.add(m.strip().lower())

            # 2) Common obfuscations: name [at] domain [dot] edu / name(at)domain(dot)edu / " at " " dot "
            # Normalize spacing and brackets.
            t = text
            t = t.replace("\u00a0", " ")
            t = _re.sub(r"\s+", " ", t)
            # Replace HTML entities for @ when present as plain text.
            t = t.replace("&#64;", "@").replace("&commat;", "@").replace("&period;", ".")
            # Replace bracketed at/dot patterns
            replacements = [
                (r"\s*\[\s*at\s*\]\s*", "@"),
                (r"\s*\(\s*at\s*\)\s*", "@"),
                (r"\s+at\s+", "@"),
                (r"\s*\[\s*dot\s*\]\s*", "."),
                (r"\s*\(\s*dot\s*\)\s*", "."),
                (r"\s+dot\s+", "."),
            ]
            norm = t
            for pat, repl in replacements:
                norm = _re.sub(pat, repl, norm, flags=_re.IGNORECASE)
            # Remove obvious anti-spam tokens
            norm = _re.sub(r"\(remove\)|REMOVE_THIS|REMOVE\s+THIS", "", norm, flags=_re.IGNORECASE)
            # Re-extract after normalization
            for m in email_re.findall(norm):
                out.add(m.strip().lower())
            return out
        for p in parsed.professors:
            name = p.name.strip()
            if not name:
                continue
            lower_name = name.lower()
            # 1) Name must actually appear in the page text (avoid pure hallucinations).
            if lower_name not in text_for_matching:
                continue

            # Evidence gating:
            # - If an email exists anywhere on the page (including common obfuscations), we require capturing it.
            # - Otherwise we accept a profile_url if present and found on the page.
            page_emails = _extract_emails_with_obfuscation(truncated_md)
            extracted_email = (p.email or "").strip() if p.email else None
            extracted_profile = (p.profile_url or "").strip() if p.profile_url else None
            evidence: list[dict[str, Any]] = []
            evidence.append(
                {
                    "url": page_url,
                    "evidence_type": "name",
                    "evidence_value": name,
                    "raw_match": name,
                    "snippet": _find_snippet(truncated_md, name),
                    "selector": "markdown:text",
                    "confidence": 1.0,
                }
            )
            if page_emails:
                if not extracted_email:
                    continue
                if extracted_email.strip().lower() not in page_emails:
                    continue
                evidence.append(
                    {
                        "url": page_url,
                        "evidence_type": "email",
                        "evidence_value": extracted_email.strip(),
                        "raw_match": extracted_email.strip(),
                        "snippet": (
                            _find_snippet(truncated_md, extracted_email.strip())
                            or _find_snippet(truncated_md, extracted_email.strip().split("@")[0])
                        ),
                        "selector": "markdown:text",
                        "confidence": 1.0,
                    }
                )
            else:
                if not extracted_profile:
                    continue
                if extracted_profile.strip().lower() not in text_for_matching:
                    continue
                evidence.append(
                    {
                        "url": page_url,
                        "evidence_type": "profile_url",
                        "evidence_value": extracted_profile.strip(),
                        "raw_match": extracted_profile.strip(),
                        "snippet": _find_snippet(truncated_md, extracted_profile.strip()),
                        "selector": "markdown:link",
                        "confidence": 1.0,
                    }
                )

            topics = [t.strip() for t in (p.research_topics or []) if isinstance(t, str) and t.strip()]
            opp = p.opportunity_score
            if not (0.0 <= opp <= 1.0):
                opp = 0.5
            opportunities: list[dict[str, Any]] = []
            for o in (p.opportunities or []):
                if not isinstance(o, dict):
                    continue
                o_type = str(o.get("type") or "").strip().lower()
                if o_type not in {"master", "phd", "postdoc"}:
                    continue
                signal = str(o.get("signal") or "").strip()
                confidence = o.get("confidence")
                try:
                    confidence_f = float(confidence)
                except Exception:
                    confidence_f = 0.5
                confidence_f = min(1.0, max(0.0, confidence_f))
                source_text = str(o.get("source_text") or "").strip() or None
                opportunities.append(
                    {
                        "type": o_type,
                        "signal": signal or None,
                        "confidence": confidence_f,
                        "source_text": source_text,
                    }
                )
            if opportunities:
                # Opportunity score should at least reflect strongest structured signal.
                opp = max(opp, max(float(o["confidence"]) for o in opportunities))
                for o in opportunities[:3]:
                    signal = (o.get("signal") or "").strip()
                    if signal:
                        evidence.append(
                            {
                                "url": page_url,
                                "evidence_type": "opportunity_signal",
                                "evidence_value": signal,
                                "raw_match": signal,
                                "snippet": _find_snippet(truncated_md, signal) or o.get("source_text"),
                                "selector": "markdown:text",
                                "confidence": float(o.get("confidence") or 0.5),
                            }
                        )
            opp_explanation = (p.opportunity_explanation or "").strip() or None
            cleaned.append(
                {
                    "name": name,
                    "email": p.email or None,
                    "profile_url": p.profile_url or None,
                    "lab_focus": (p.lab_focus or None),
                    "research_topics": topics,
                    "opportunity_score": opp,
                    "opportunities": opportunities,
                    "opportunity_explanation": opp_explanation,
                    "_evidence": evidence,
                }
            )
        if not cleaned and len(parsed.professors) == 0:
            # Source-grounded fallback: extract likely faculty names directly from markdown links.
            import re as _re

            page_emails = _extract_emails_with_obfuscation(truncated_md)
            link_pattern = _re.compile(r"\[([^\]]{3,140})\]\((https?://[^)\s]+)\)")
            seen_fallback: set[tuple[str, str]] = set()
            for link_text, link_url in link_pattern.findall(truncated_md):
                text = " ".join((link_text or "").strip().split())
                url = (link_url or "").strip()
                if not text or not url:
                    continue
                # Detect a plausible faculty name from the link text.
                name_match = _re.search(
                    r"((?:Dr\.|Professor|Prof\.)\s+[A-Z][A-Za-z\-.]+(?:\s+[A-Z][A-Za-z\-.]+){0,6})",
                    text,
                )
                name = name_match.group(1).strip() if name_match else ""
                if not name:
                    # Secondary pattern for title-case names on faculty/profile links.
                    if any(k in url.lower() for k in ("faculty", "profile", "people", "/in/")):
                        tokens = [t for t in _re.split(r"\s+", text) if t]
                        if 2 <= len(tokens) <= 6 and all(
                            (t[0].isupper() if t and t[0].isalpha() else False) for t in tokens
                        ):
                            name = " ".join(tokens)
                if not name:
                    continue
                key = (name.lower(), url.lower())
                if key in seen_fallback:
                    continue
                seen_fallback.add(key)

                # Preserve evidence gate discipline:
                # - if page has emails, require at least one captured email from page (global signal).
                # - otherwise accept profile URL present in source (this link itself).
                email_val = next(iter(page_emails), None) if page_emails else None
                evidence = [
                    {
                        "url": page_url,
                        "evidence_type": "name",
                        "evidence_value": name,
                        "raw_match": name,
                        "snippet": _find_snippet(truncated_md, name) or _find_snippet(truncated_md, text),
                        "selector": "markdown:text",
                        "confidence": 0.7,
                    },
                    {
                        "url": page_url,
                        "evidence_type": "profile_url",
                        "evidence_value": url,
                        "raw_match": url,
                        "snippet": _find_snippet(truncated_md, url) or _find_snippet(truncated_md, text),
                        "selector": "markdown:link",
                        "confidence": 0.9,
                    },
                ]
                if email_val:
                    evidence.append(
                        {
                            "url": page_url,
                            "evidence_type": "email",
                            "evidence_value": email_val,
                            "raw_match": email_val,
                            "snippet": _find_snippet(truncated_md, email_val),
                            "selector": "markdown:text",
                            "confidence": 0.6,
                        }
                    )
                cleaned.append(
                    {
                        "name": name,
                        "email": email_val,
                        "profile_url": url,
                        "lab_focus": None,
                        "research_topics": [],
                        "opportunity_score": 0.5,
                        "opportunities": [],
                        "opportunity_explanation": None,
                        "_evidence": evidence,
                    }
                )
        logger.info("llm_profs_extracted", count=len(cleaned), sample=[c["name"] for c in cleaned[:3]])
        return cleaned or None
    except ValidationError as exc:
        logger.warning("llm_profs_parse_failed", error=str(exc), raw=content[:200])
        return None

