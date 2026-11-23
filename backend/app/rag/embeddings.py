"""Embedding generation for RAG (Phase 8).

Uses ChromaDB's bundled **local ONNX all-MiniLM-L6-v2** sentence-transformer
(384-dim) — no API key, no network, deterministic and free. The model file is
downloaded once by ChromaDB into ``~/.cache/chroma/onnx_models`` and reused;
queries at request time are pure local inference (~ms).

If a Google embedding model is ever preferred, add ``GOOGLE_EMBEDDING_MODEL``
and swap ``get_embedding_function`` for
``embedding_functions.GoogleGenerativeAiEmbeddingFunction(api_key=...)`` —
nothing else in the pipeline changes. (Note: a remote embedding API adds a
network round-trip to every /llm/chat; the local model avoids that.)
"""
import logging
import threading

from chromadb.utils import embedding_functions

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 384  # all-MiniLM-L6-v2

_lock = threading.Lock()
_function = None


class EmbeddingError(RuntimeError):
    """Raised when the local embedding model cannot load or embed."""


def get_embedding_function():
    """Return the shared embedding function (lazy singleton)."""
    global _function
    if _function is None:
        with _lock:
            if _function is None:
                logger.info("Loading embedding model %s (local ONNX)...", settings.RAG_EMBEDDING_MODEL)
                _function = embedding_functions.ONNXMiniLM_L6_V2()
    return _function


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts; used by the indexing script."""
    if not texts:
        return []
    try:
        vectors = get_embedding_function()(texts)
    except Exception as exc:  # model load/inference failure — controlled upstream
        raise EmbeddingError(f"Embedding generation failed: {exc.__class__.__name__}") from exc
    if not vectors or len(vectors) != len(texts):
        raise EmbeddingError("Embedding generation returned an unexpected shape")
    return [list(map(float, v)) for v in vectors]


def embed_query(text: str) -> list[float]:
    """Embed one query at request time."""
    return embed_texts([text])[0]
