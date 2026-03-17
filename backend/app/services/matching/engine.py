"""
Matching Engine: compute semantic similarity (score) and combine with opportunity_score
into final_rank. Handles cold start (no embedding => skip or placeholder).
Formula: final_rank = score * 0.7 + opportunity_score * 0.3 (weights configurable later).
"""
from __future__ import annotations

from dataclasses import dataclass

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
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
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
    results: list[MatchResult] = []
    for prof_id, prof_emb, opp_score in professor_embeddings:
        if student_embedding and prof_emb:
            score = cosine_similarity(student_embedding, prof_emb)
        else:
            score = 0.0
        final_rank = compute_final_rank(score, opp_score, weight_semantic, weight_opportunity)
        results.append(
            MatchResult(professor_id=prof_id, score=score, opportunity_score=opp_score, final_rank=final_rank)
        )
    results.sort(key=lambda x: x.final_rank, reverse=True)
    return results
