"""
Embedding service: produce vectors for student research topics (and professors).
Uses sentence-transformers locally or Ollama if configured; dimension must match DB.
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import EMBEDDING_DIM

_st_model: Optional[Any] = None
_st_device: Optional[str] = None
_st_load_failed: bool = False


def get_embedding_model_version() -> str:
    return getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text") + "-v1"


def _resolve_st_model_name(raw_model_name: str) -> tuple[str, bool]:
    """
    Resolve EMBEDDING_MODEL into a sentence-transformers compatible model id.
    Returns (resolved_name, changed).
    """
    name = (raw_model_name or "").strip()
    if not name:
        return "all-MiniLM-L6-v2", True
    alias_map = {
        "nomic-embed-text": "nomic-ai/nomic-embed-text-v1.5",
    }
    if name in alias_map:
        return alias_map[name], True
    # Ollama tags are not valid sentence-transformers IDs.
    if ":" in name:
        return "all-MiniLM-L6-v2", True
    return name, False


def _get_sentence_transformer_model() -> Optional[Any]:
    """Load sentence-transformers model once and cache it in memory (prefer GPU if available)."""
    global _st_model, _st_device, _st_load_failed
    logger = get_logger("embedding_service")
    if _st_model is not None:
        return _st_model
    if _st_load_failed:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        import torch
    except ImportError:
        logger.info("st_not_installed_falling_back")
        return None
    try:
        # Allow explicit override via settings (e.g. "cuda:0", "cuda:1", "cpu", "mps").
        configured_device = (getattr(settings, "EMBEDDING_DEVICE", None) or "").strip()
        if configured_device:
            device = configured_device
        else:
            device = "cpu"
            if hasattr(torch, "cuda") and torch.cuda.is_available():
                # Let CUDA_VISIBLE_DEVICES control which GPU(s) are visible; default to first visible.
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
        model_name = settings.EMBEDDING_MODEL
        resolved_model, changed = _resolve_st_model_name(model_name)
        if changed:
            logger.info(
                "st_model_resolved",
                requested_model=model_name,
                resolved_model=resolved_model,
            )
        logger.info("st_loading_model", model_name=resolved_model, device=device)
        try:
            _st_model = SentenceTransformer(resolved_model, device=device)
        except Exception:
            # Support configs where EMBEDDING_MODEL targets Ollama rather than HF.
            fallback_model = "all-MiniLM-L6-v2"
            if resolved_model != fallback_model:
                logger.info(
                    "st_model_fallback",
                    requested_model=resolved_model,
                    fallback_model=fallback_model,
                )
                _st_model = SentenceTransformer(fallback_model, device=device)
            else:
                raise
        _st_device = device
        logger.info("st_loaded_model")
        return _st_model
    except Exception as exc:  # pragma: no cover - env issues
        logger.warning("st_load_failed", error=str(exc))
        _st_model = None
        _st_load_failed = True
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
        result: list[list[float]] = []
        for v in vecs:
            result.append(v[:EMBEDDING_DIM])
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
                out.append(vec)
        return out
    except Exception as exc:
        logger.warning("ollama_embedding_failed", error=str(exc))
        pass
    # Placeholder: zero vector so pipeline doesn't break
    return [[0.0] * EMBEDDING_DIM for _ in texts]


def embed_single(text: str) -> list[float]:
    return embed_texts([text])[0]
