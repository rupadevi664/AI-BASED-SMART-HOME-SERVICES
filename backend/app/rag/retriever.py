"""Retriever: query the vector store and keep only relevant chunks (Phase 8).

Chroma returns cosine *distance* per hit (0 = identical, 2 = opposite).
``RAG_MAX_DISTANCE`` is the relevance threshold: hits above it are unrelated
("capital of France" must not leak plumbing docs into the prompt) and are
dropped. Optional metadata filtering by category is supported but never
mandatory.
"""
import logging

from app.core.config import settings
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """Distance-thresholded similarity retrieval over the knowledge base."""

    def __init__(self, store: VectorStore | None = None):
        self.store = store or VectorStore()

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        category: str | None = None,
    ) -> list[dict]:
        """Return relevant hits (closest first), thresholded.

        - top_k: how many candidates to fetch (default RAG_TOP_K).
        - category: optional Chroma metadata filter; None searches everything.
        """
        k = top_k or settings.RAG_TOP_K
        where = {"category": category} if category else None
        try:
            hits = self.store.query(query, top_k=k, where=where)
        except TypeError:
            # Test doubles without a `where` parameter.
            hits = self.store.query(query, top_k=k)

        threshold = settings.RAG_MAX_DISTANCE
        relevant = [h for h in hits if h["distance"] <= threshold]
        dropped = len(hits) - len(relevant)
        if hits:
            logger.info(
                "RAG retrieval query=%r fetched=%d relevant=%d dropped_above_threshold=%d",
                query[:80],
                len(hits),
                len(relevant),
                dropped,
            )
            for i, h in enumerate(relevant, 1):
                logger.info(
                    "  Retrieved %d. %s chunk %d (distance %.3f)",
                    i, h["source"], h["chunk_index"], h["distance"],
                )
        return relevant
