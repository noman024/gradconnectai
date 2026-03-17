"""
Portfolio Analyzer: extract research topics and methods from CV/text and preferences;
produce a single embedding for the student profile (for matching).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.portfolio.embedding import embed_single, embed_texts, get_embedding_model_version


@dataclass
class PortfolioResult:
    research_topics: list[str]
    embedding: list[float]
    embedding_model_version: str


def _extract_topics_from_text(cv_text: str, preferences_fields: list[str]) -> list[str]:
    """
    Naive extraction: combine preference fields with first N words/phrases from CV.
    In production, use an LLM (Ollama) to extract research topics and methods.
    """
    topics = list(preferences_fields)
    # Simple: take first 200 chars and split into potential keywords (no real NLP)
    words = cv_text.replace("\n", " ").split()[:50]
    for w in words:
        if len(w) > 4 and w.isalpha() and w.lower() not in ("the", "and", "with", "from", "that", "this"):
            topics.append(w)
    return list(dict.fromkeys(topics))[:30]


def analyze_portfolio(
    cv_text: str,
    preferences: dict | None = None,
) -> PortfolioResult:
    """
    Extract research topics from CV and preferences, then compute one embedding
    for the full profile (concatenated topic string) for semantic matching.
    """
    prefs = preferences or {}
    fields = prefs.get("fields") or []
    topics = _extract_topics_from_text(cv_text or "", fields)
    combined = " ".join(topics) if topics else cv_text[:500] if cv_text else "general"
    embedding = embed_single(combined)
    return PortfolioResult(
        research_topics=topics,
        embedding=embedding,
        embedding_model_version=get_embedding_model_version(),
    )
