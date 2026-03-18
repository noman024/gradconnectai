"""
Portfolio Analyzer: extract research topics and methods from CV/text and preferences;
produce a single embedding for the student profile (for matching).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.services.llm_client import extract_topics_from_cv
from app.services.portfolio.embedding import embed_single, get_embedding_model_version


@dataclass
class PortfolioResult:
    research_topics: list[str]
    embedding: list[float]
    embedding_model_version: str


def _extract_topics_from_text(cv_text: str, preferences_fields: list[str]) -> list[str]:
    """
    Prefer LLM-based extraction via Qwen/vLLM when configured; fallback to naive heuristic otherwise.
    """
    logger = get_logger("portfolio_analyzer")
    llm_topics = extract_topics_from_cv(cv_text, preferences_fields)
    if llm_topics:
        return llm_topics

    # Fallback: naive extraction (combine preference fields with first N words/phrases from CV)
    topics = list(preferences_fields)
    words = cv_text.replace("\n", " ").split()[:50]
    for w in words:
        if len(w) > 4 and w.isalpha() and w.lower() not in ("the", "and", "with", "from", "that", "this"):
            topics.append(w)
    topics = list(dict.fromkeys(topics))[:30]
    logger.info("fallback_topics_used", topics_count=len(topics), sample_topics=topics[:5])
    return topics


def analyze_portfolio(
    cv_text: str,
    preferences: dict | None = None,
) -> PortfolioResult:
    """
    Extract research topics from CV and preferences, then compute one embedding
    for the full profile (concatenated topic string) for semantic matching.
    """
    logger = get_logger("portfolio_analyzer")
    prefs = preferences or {}
    fields = prefs.get("fields") or []
    topics = _extract_topics_from_text(cv_text or "", fields)
    combined = " ".join(topics) if topics else cv_text[:500] if cv_text else "general"
    embedding = embed_single(combined)
    logger.info(
        "portfolio_analyzed",
        topics_count=len(topics),
        sample_topics=topics[:5],
        has_cv=bool(cv_text),
    )
    return PortfolioResult(
        research_topics=topics,
        embedding=embedding,
        embedding_model_version=get_embedding_model_version(),
    )
