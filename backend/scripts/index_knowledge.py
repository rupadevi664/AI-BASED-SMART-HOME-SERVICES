"""Explicit knowledge-base indexing (Phase 8) — run manually, never at startup.

    .venv\\Scripts\\python scripts\\index_knowledge.py           # full reindex
    .venv\\Scripts\\python scripts\\index_knowledge.py --demo    # show retrieval examples

Flow: read documents → chunk → embed (local MiniLM) → store in ChromaDB.
Idempotent: deterministic chunk ids make a re-run an overwrite, not a
duplicate; the collection is cleared first so removed documents disappear.
"""
import argparse
import sys

from app.core.config import settings
from app.rag.chunker import chunk_documents
from app.rag.document_loader import load_documents
from app.rag.embeddings import embed_texts
from app.rag.vector_store import VectorStore


def reindex() -> int:
    docs = load_documents()
    if not docs:
        print(f"No documents found in {settings.RAG_KB_DIR} — nothing to index.")
        return 0
    print(f"Loaded {len(docs)} documents from {settings.RAG_KB_DIR}:")
    for d in docs:
        print(f"  - {d.source} [{d.category}] ({len(d.text)} chars)")

    chunks = chunk_documents(docs)
    print(f"Chunked into {len(chunks)} chunks "
          f"(size<={settings.RAG_CHUNK_SIZE}, overlap={settings.RAG_CHUNK_OVERLAP}).")

    print("Generating embeddings (local all-MiniLM-L6-v2)...")
    vectors = embed_texts([c.text for c in chunks])
    print(f"Embedded {len(vectors)} chunks (dim={len(vectors[0])}).")

    store = VectorStore()
    count = store.replace_all(chunks)
    print(f"Stored {count} chunks in ChromaDB collection "
          f"'{settings.RAG_COLLECTION_NAME}' at {settings.RAG_CHROMA_DIR}.")
    print("Indexing complete. The API server can now use the knowledge base.")
    return count


def demo() -> None:
    """Retrieval demo (spec section 24) — shows what RAG would fetch."""
    from app.rag.retriever import Retriever

    retriever = Retriever(VectorStore())
    queries = [
        "My kitchen tap is leaking.",
        "My AC is not cooling.",
        "My power switch is making a strange noise.",
        "I need help cleaning my house.",
        "What is the capital of France?",
    ]
    for q in queries:
        print(f"\nQuery: {q}")
        hits = retriever.retrieve(q)
        if not hits:
            print("  → no relevant documents (general-knowledge answer)")
        for i, h in enumerate(hits, 1):
            print(f"  {i}. {h['source']} - chunk {h['chunk_index']} (distance {h['distance']:.3f})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index the RAG knowledge base into ChromaDB")
    parser.add_argument("--demo", action="store_true", help="run retrieval examples instead of indexing")
    args = parser.parse_args()
    if args.demo:
        demo()
        sys.exit(0)
    reindex()
