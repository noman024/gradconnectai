"""Tests for the matching engine: cosine similarity and ranking logic."""
from app.services.matching.engine import (
    cosine_similarity,
    compute_final_rank,
    rank_matches,
    MatchResult,
    WEIGHT_SEMANTIC,
    WEIGHT_OPPORTUNITY,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors_clamped_to_zero(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_none_inputs(self):
        assert cosine_similarity(None, [1.0]) == 0.0
        assert cosine_similarity([1.0], None) == 0.0
        assert cosine_similarity(None, None) == 0.0

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_mismatched_lengths(self):
        assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_similar_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 2.9]
        sim = cosine_similarity(a, b)
        assert 0.99 < sim <= 1.0


class TestComputeFinalRank:
    def test_default_weights(self):
        rank = compute_final_rank(0.8, 0.6)
        expected = 0.8 * WEIGHT_SEMANTIC + 0.6 * WEIGHT_OPPORTUNITY
        assert rank == pytest.approx(expected, abs=1e-6)

    def test_custom_weights(self):
        rank = compute_final_rank(0.5, 1.0, weight_semantic=0.5, weight_opportunity=0.5)
        assert rank == pytest.approx(0.75, abs=1e-6)

    def test_zero_scores(self):
        assert compute_final_rank(0.0, 0.0) == 0.0


class TestRankMatches:
    def test_ranked_by_final_rank_descending(self):
        student_emb = [1.0, 0.0, 0.0]
        profs = [
            ("prof-a", [0.5, 0.5, 0.0], 0.3),
            ("prof-b", [1.0, 0.0, 0.0], 0.9),
            ("prof-c", [0.0, 1.0, 0.0], 0.5),
        ]
        results = rank_matches(student_emb, profs)
        assert len(results) == 3
        ranks = [r.final_rank for r in results]
        assert ranks == sorted(ranks, reverse=True)
        assert results[0].professor_id == "prof-b"

    def test_cold_start_no_student_embedding(self):
        profs = [("prof-a", [1.0, 0.0], 0.7)]
        results = rank_matches(None, profs)
        assert len(results) == 1
        assert results[0].score == 0.0
        assert results[0].final_rank == pytest.approx(0.7 * WEIGHT_OPPORTUNITY, abs=1e-6)

    def test_cold_start_no_professor_embedding(self):
        student_emb = [1.0, 0.0]
        profs = [("prof-a", None, 0.5)]
        results = rank_matches(student_emb, profs)
        assert results[0].score == 0.0

    def test_empty_professors(self):
        results = rank_matches([1.0], [])
        assert results == []


import pytest
