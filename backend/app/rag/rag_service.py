"""RAG service (Phase 8): retrieval → grounded context → Gemini.

Connects Phase 7's GeminiService with the knowledge base:
1. Embed the user's question (local MiniLM).
2. Retrieve the top-K relevant chunks from ChromaDB (distance-thresholded).
3. Build a context block; if nothing relevant is found, fall back to a
   clear general-knowledge prompt (the assistant is allowed to answer from
   general knowledge but must not pretend the knowledge base agreed).
4. Hand everything to the existing GeminiService — /llm/chat stays the only
   chat endpoint; no second chatbot.

Embedding/Chroma failures degrade gracefully: the request still reaches
Gemini without context rather than failing the user's chat.
"""
import logging
import threading

from app.core.config import settings
from app.rag.embeddings import EmbeddingError
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore, VectorStoreError

logger = logging.getLogger(__name__)

# Shared retriever — Chroma collection + embedding fn are process-wide.
_lock = threading.Lock()
_retriever: Retriever | None = None


def _get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        with _lock:
            if _retriever is None:
                _retriever = Retriever(VectorStore())
    return _retriever


def reset_retriever() -> None:
    """Drop the cached retriever (used by tests)."""
    global _retriever
    with _lock:
        _retriever = None


RAG_PROMPT_TEMPLATE = """You are the Smart Home Service Assistant.

Use the following retrieved knowledge-base context to answer the customer's question.

Retrieved Context:
{context}

Customer Question:
{question}

Instructions:
- Prefer the retrieved context; it reflects this platform's services and safety guidance.
- Do not invent facts that are not supported by the context or general home-service knowledge.
- If the context does not contain enough information, say so briefly and answer from general knowledge.
- Give clear, simple, concise answers (short paragraphs or a few bullets).
- Do not claim to physically diagnose a problem.
- Recommend an appropriate professional service category when necessary, and
  suggest booking an expert through the app.
- Never invent prices, availability, bookings or payments.
{grounding_note}"""


def _format_context(hits: list[dict]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(f"[{i}] ({h['source']} — {h['category']})\n{h['text']}")
    return "\n\n".join(parts)


def build_rag_prompt(message: str, service_context: str | None = None) -> tuple[str, bool, list[dict]]:
    """Return ``(final_prompt, used_knowledge_base, hits)``.

    - ``used_knowledge_base`` is True when at least one chunk passed the
      relevance threshold (frontend can badge the answer as grounded).
    - Embedding/Chroma problems are swallowed with a warning: the user still
      gets a Gemini answer, just without grounding.
    """
    grounded_note = ""
    try:
        hits = _get_retriever().retrieve(message)
    except (EmbeddingError, VectorStoreError) as exc:
        logger.warning("RAG retrieval unavailable (%s); answering without context", exc)
        hits = []

    if hits:
        context = _format_context(hits)
        used_kb = True
    else:
        context = "(No strongly relevant knowledge-base entries were found for this question.)"
        used_kb = False
        grounded_note = (
            "- The knowledge base had no strongly relevant entry for this question: "
            "answer from general home-service knowledge and say the platform's guide "
            "does not cover it specifically.\n"
        )

    question = message
    if service_context:
        question = f"{question}\n\n(Customer context: {service_context})"
    prompt = RAG_PROMPT_TEMPLATE.format(
        context=context, question=question, grounding_note=grounded_note
    )
    return prompt, used_kb, hits


def knowledge_base_stats() -> dict:
    """Chunk count + configured retrieval parameters (for health/debug)."""
    try:
        count = _get_retriever().store.count()
    except (EmbeddingError, VectorStoreError):
        count = 0
    return {
        "chunks_indexed": count,
        "top_k": settings.RAG_TOP_K,
        "max_distance": settings.RAG_MAX_DISTANCE,
        "collection": settings.RAG_COLLECTION_NAME,
    }
