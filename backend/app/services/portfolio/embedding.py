"""
Embedding service: produce vectors for student research topics (and professors).
Uses sentence-transformers locally or Ollama if configured; dimension must match DB (e.g. 768).
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import EMBEDDING_DIM

# Default model version for embedding_model_version column
EMBEDDING_MODEL_VERSION = "nomic-embed-text-v1"

_st_model: Optional[Any] = None
_st_device: Optional[str] = None


def get_embedding_model_version() -> str:
    return getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text") + "-v1"


def _get_sentence_transformer_model() -> Optional[Any]:
    """Load sentence-transformers model once and cache it in memory (prefer GPU if available)."""
    global _st_model, _st_device
    logger = get_logger("embedding_service")
    if _st_model is not None:
        return _st_model
    try:
        from sentence_transformers import SentenceTransformer
        import torch
    except ImportError:
        logger.info("st_not_installed_falling_back")
        return None
    try:
        device = "cpu"
        if hasattr(torch, "cuda") and torch.cuda.is_available():
            device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        logger.info("st_loading_model", model_name="all-MiniLM-L6-v2", device=device)
        _st_model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        _st_device = device
        logger.info("st_loaded_model")
        return _st_model
    except Exception as exc:  # pragma: no cover - env issues
        logger.warning("st_load_failed", error=str(exc))
        _st_model = None
        return None


def preload_embedding_model() -> None:
    """Hook for server startup to warm up the embedding model."""
    _get_sentence_transformer_model()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Return list of embedding vectors for each text. Length of each vector must match EMBEDDING_DIM.
    Prefer sentence-transformers; fallback to Ollama embed if available.
    """
    logger = get_logger("embedding_service")
    model = _get_sentence_transformer_model()
    if model is not None:
        # model is already placed on CPU/GPU/MPS in _get_sentence_transformer_model
        vecs = model.encode(texts, convert_to_numpy=True).tolist()
        # If model dim != EMBEDDING_DIM, pad or truncate (schema uses 768; all-MiniLM is 384)
        result: list[list[float]] = []
        for v in vecs:
            if len(v) >= EMBEDDING_DIM:
                result.append(v[:EMBEDDING_DIM])
            else:
                result.append(v + [0.0] * (EMBEDDING_DIM - len(v)))
        return result
    # Ollama fallback (HTTP API)
    try:
        import httpx
        base = settings.OLLAMA_BASE_URL.rstrip("/")
        out: list[list[float]] = []
        for t in texts:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(f"{base}/api/embeddings", json={"model": settings.EMBEDDING_MODEL, "prompt": t})
                if r.status_code != 200:
                    raise RuntimeError(r.text)
                vec = (r.json().get("embedding") or [])[:EMBEDDING_DIM]
                if len(vec) < EMBEDDING_DIM:
                    vec = vec + [0.0] * (EMBEDDING_DIM - len(vec))
                out.append(vec)
        return out
    except Exception as exc:
        logger = get_logger("embedding_service")
        logger.warning("ollama_embedding_failed", error=str(exc))
        pass
    # Placeholder: zero vector so pipeline doesn't break
    return [[0.0] * EMBEDDING_DIM for _ in texts]


def embed_single(text: str) -> list[float]:
    return embed_texts([text])[0]
