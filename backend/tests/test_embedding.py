"""Tests for embedding service: model loading, dimension handling, fallbacks."""
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from app.services.portfolio.embedding import (
    embed_texts,
    embed_single,
    get_embedding_model_version,
    EMBEDDING_DIM,
)
from app.db.models import EMBEDDING_DIM as MODEL_EMBEDDING_DIM


def test_embedding_dim_matches_model_config():
    assert EMBEDDING_DIM == MODEL_EMBEDDING_DIM == 384


def test_get_embedding_model_version():
    version = get_embedding_model_version()
    assert "v1" in version


class TestEmbedTexts:
    def test_returns_correct_count(self, monkeypatch):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(3, EMBEDDING_DIM)
        monkeypatch.setattr(
            "app.services.portfolio.embedding._get_sentence_transformer_model",
            lambda: mock_model,
        )
        results = embed_texts(["text1", "text2", "text3"])
        assert len(results) == 3
        assert all(len(v) == EMBEDDING_DIM for v in results)

    def test_returns_vectors_of_correct_dimension(self, monkeypatch):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(1, EMBEDDING_DIM)
        monkeypatch.setattr(
            "app.services.portfolio.embedding._get_sentence_transformer_model",
            lambda: mock_model,
        )
        results = embed_texts(["test"])
        assert len(results[0]) == EMBEDDING_DIM

    def test_fallback_to_zero_vectors(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.portfolio.embedding._get_sentence_transformer_model",
            lambda: None,
        )
        monkeypatch.setattr(
            "app.services.portfolio.embedding.settings",
            MagicMock(OLLAMA_BASE_URL="http://localhost:99999", EMBEDDING_MODEL="test"),
        )
        results = embed_texts(["text"])
        assert len(results) == 1
        assert results[0] == [0.0] * EMBEDDING_DIM


class TestEmbedSingle:
    def test_returns_single_vector(self, monkeypatch):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(1, EMBEDDING_DIM)
        monkeypatch.setattr(
            "app.services.portfolio.embedding._get_sentence_transformer_model",
            lambda: mock_model,
        )
        result = embed_single("test text")
        assert isinstance(result, list)
        assert len(result) == EMBEDDING_DIM
