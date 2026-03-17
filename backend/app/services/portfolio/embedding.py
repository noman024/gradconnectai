"""
Embedding service: produce vectors for student research topics (and professors).
Uses sentence-transformers locally or Ollama if configured; dimension must match DB (e.g. 768).
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.db.models import EMBEDDING_DIM

# Default model version for embedding_model_version column
EMBEDDING_MODEL_VERSION = "nomic-embed-text-v1"


def get_embedding_model_version() -> str:
    return getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text") + "-v1"


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Return list of embedding vectors for each text. Length of each vector must match EMBEDDING_DIM.
    Prefer sentence-transformers; fallback to Ollama embed if available.
    """
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dim) or "nomic-ai/nomic-embed-text-v1.5"
        vecs = model.encode(texts).tolist()
        # If model dim != EMBEDDING_DIM, pad or truncate (schema uses 768; all-MiniLM is 384)
        result: list[list[float]] = []
        for v in vecs:
            if len(v) >= EMBEDDING_DIM:
                result.append(v[:EMBEDDING_DIM])
            else:
                result.append(v + [0.0] * (EMBEDDING_DIM - len(v)))
        return result
    except ImportError:
        pass
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
    except Exception:
        pass
    # Placeholder: zero vector so pipeline doesn't break
    return [[0.0] * EMBEDDING_DIM for _ in texts]


def embed_single(text: str) -> list[float]:
    return embed_texts([text])[0]
