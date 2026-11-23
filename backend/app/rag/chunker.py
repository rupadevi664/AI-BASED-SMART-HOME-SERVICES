"""Markdown-aware text chunking for RAG indexing (Phase 8).

Strategy: split each document on ``## `` section headings so a chunk is one
coherent topic (never splitting a "Problem / Causes / Safety" block mid-way),
then fall back to fixed-size windows with overlap for oversized sections.
Sizes are configurable via Settings (chars: MiniLM's practical context is
well above these).
"""
from app.core.config import settings


class Chunk:
    """One indexable piece of knowledge."""

    __slots__ = ("category", "chunk_id", "index", "source", "text")

    def __init__(self, text: str, source: str, category: str, chunk_id: str, index: int):
        self.text = text
        self.source = source
        self.category = category
        self.chunk_id = chunk_id
        self.index = index

    def __repr__(self) -> str:
        return f"<Chunk {self.chunk_id} {self.source}#{self.index}>"


def _window(text: str, size: int, overlap: int) -> list[str]:
    """Fixed-size windows with overlap for text longer than `size`."""
    if len(text) <= size:
        return [text]
    step = max(1, size - overlap)
    windows = []
    for start in range(0, len(text), step):
        piece = text[start:start + size].strip()
        if piece:
            windows.append(piece)
        if start + size >= len(text):
            break
    return windows


def chunk_document(text: str, source: str, category: str) -> list[Chunk]:
    """Split one document into chunks, preserving section context."""
    size = settings.RAG_CHUNK_SIZE
    overlap = settings.RAG_CHUNK_OVERLAP
    stem = source.rsplit(".", 1)[0]

    # A section = heading + its body (or the preamble before the first heading).
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())

    chunks: list[Chunk] = []
    counter = 0
    # Category tag on every chunk improves embedding quality for short queries.
    prefix = f"[{category.replace('_', ' ')}] "
    for section in sections:
        for piece in _window(section, size, overlap):
            if not piece:
                continue
            counter += 1
            chunks.append(
                Chunk(
                    text=f"{prefix}{piece}",
                    source=source,
                    category=category,
                    chunk_id=f"{stem}_{counter:03d}",
                    index=counter,
                )
            )
    return chunks


def chunk_documents(docs) -> list[Chunk]:
    """Chunk a list of RawDocument-like objects."""
    out: list[Chunk] = []
    for doc in docs:
        out.extend(chunk_document(doc.text, doc.source, doc.category))
    return out
