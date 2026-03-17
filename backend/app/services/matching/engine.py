"""
Matching Engine: compute semantic similarity (score) and combine with opportunity_score
into final_rank. Handles cold start (no embedding => skip or placeholder).
Formula: final_rank = score * 0.7 + opportunity_score * 0.3 (weights configurable later).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger

# Default weights (plan: 0.7 fit, 0.3 opportunity)
WEIGHT_SEMANTIC = 0.7
WEIGHT_OPPORTUNITY = 0.3


@dataclass
class MatchResult:
    professor_id: str
    score: float
    opportunity_score: float
    final_rank: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    # Handle list-like and array-like inputs (e.g. NumPy, pgvector) without truthiness checks.
    if a is None or b is None:
        return 0.0
    try:
        len_a = len(a)
        len_b = len(b)
    except TypeError:
        return 0.0
    if len_a == 0 or len_b == 0 or len_a != len_b:
        return 0.0
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    norm_a = sum(float(x) * float(x) for x in a) ** 0.5
    norm_b = sum(float(y) * float(y) for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def compute_final_rank(
    score: float,
    opportunity_score: float,
    weight_semantic: float = WEIGHT_SEMANTIC,
    weight_opportunity: float = WEIGHT_OPPORTUNITY,
) -> float:
    return score * weight_semantic + opportunity_score * weight_opportunity


def rank_matches(
    student_embedding: list[float] | None,
    professor_embeddings: list[tuple[str, list[float] | None, float]],
    weight_semantic: float = WEIGHT_SEMANTIC,
    weight_opportunity: float = WEIGHT_OPPORTUNITY,
) -> list[MatchResult]:
    """
    professor_embeddings: list of (professor_id, embedding or None, opportunity_score).
    Cold start: if student_embedding or professor embedding is None, use 0.0 for score.
    """
    logger = get_logger("matching_engine")
    results: list[MatchResult] = []
    for prof_id, prof_emb, opp_score in professor_embeddings:
        # Avoid ambiguous truth-value checks on array-like embeddings (e.g. NumPy arrays).
        has_student_emb = student_embedding is not None
        has_prof_emb = prof_emb is not None
        score = cosine_similarity(student_embedding, prof_emb) if has_student_emb and has_prof_emb else 0.0
        final_rank = compute_final_rank(score, opp_score, weight_semantic, weight_opportunity)
        results.append(
            MatchResult(professor_id=prof_id, score=score, opportunity_score=opp_score, final_rank=final_rank)
        )
    results.sort(key=lambda x: x.final_rank, reverse=True)
    top_preview = [
        {
            "professor_id": r.professor_id,
            "score": round(r.score, 4),
            "opportunity_score": round(r.opportunity_score, 4),
            "final_rank": round(r.final_rank, 4),
        }
        for r in results[:5]
    ]
    logger.info(
        "matches_ranked",
        total_professors=len(professor_embeddings),
        total_results=len(results),
        top_results=top_preview,
        weight_semantic=weight_semantic,
        weight_opportunity=weight_opportunity,
    )
    return results
