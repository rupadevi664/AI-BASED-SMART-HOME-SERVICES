"""ChromaDB vector store for RAG (Phase 8).

A thin wrapper around a persistent Chroma collection:
- Storage: ``backend/chroma_data`` (PersistentClient — survives restarts).
- Embeddings: passed explicitly from :mod:`app.rag.embeddings` so indexing and
  querying are guaranteed to use the same model.
- The store is created lazily on first use and never re-indexed at startup —
  indexing is an explicit script run (no duplicate documents per boot).

Cosine distance (Chroma default): 0 = identical, 2 = opposite. Relevance is
thresholded on distance — a high-distance hit is unrelated knowledge and is
dropped instead of being sent to Gemini.
"""
import logging
from pathlib import Path

from app.core.config import settings
from app.rag.embeddings import get_embedding_function

logger = logging.getLogger(__name__)


class VectorStoreError(RuntimeError):
    """Raised when ChromaDB cannot initialise or answer a query."""


class VectorStore:
    """Persistent ChromaDB collection of knowledge-base chunks."""

    def __init__(self, persist_dir: str | Path | None = None):
        self._persist_dir = str(persist_dir or settings.RAG_CHROMA_DIR)
        self._collection_name = settings.RAG_COLLECTION_NAME
        self._collection = None

    # ------------------------------------------------------------------ init
    def _get_collection(self):
        """Lazily create/attach the persistent collection."""
        if self._collection is None:
            try:
                import chromadb

                client = chromadb.PersistentClient(path=self._persist_dir)
                self._collection = client.get_or_create_collection(
                    name=self._collection_name,
                    embedding_function=get_embedding_function(),
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as exc:
                raise VectorStoreError(
                    f"Vector database initialisation failed: {exc.__class__.__name__}"
                ) from exc
        return self._collection

    # ----------------------------------------------------------------- write
    def replace_all(self, chunks) -> int:
        """(Re)index everything: clears the collection, then upserts chunks.

        Explicit-only — called by scripts/index_knowledge.py, never at startup.
        """
        collection = self._get_collection()
        # Clear existing entries so removed documents disappear; deterministic
        # ids make the subsequent upsert an overwrite (idempotent re-index).
        existing = collection.get(include=[])
        if existing.get("ids"):
            collection.delete(ids=existing["ids"])
        if not chunks:
            return 0
        collection.upsert(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {"category": c.category, "source": c.source, "chunk_index": c.index}
                for c in chunks
            ],
        )
        return len(chunks)

    # ------------------------------------------------------------------ read
    def count(self) -> int:
        return self._get_collection().count()

    def query(self, query_text: str, top_k: int | None = None, where: dict | None = None):
        """Similarity search → list of {text, source, category, chunk_index,
        distance}. `where` is an optional Chroma metadata filter (e.g.
        {"category": "plumbing"}). Returns [] when the store is empty."""
        collection = self._get_collection()
        if collection.count() == 0:
            return []
        result = collection.query(
            query_texts=[query_text],
            n_results=min(top_k or settings.RAG_TOP_K, collection.count()),
            include=["documents", "metadatas", "distances"],
            where=where,
        )
        hits = []
        for doc, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
        ):
            hits.append(
                {
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "category": meta.get("category", "general"),
                    "chunk_index": int(meta.get("chunk_index", 0)),
                    "distance": float(dist),
                }
            )
        return hits
