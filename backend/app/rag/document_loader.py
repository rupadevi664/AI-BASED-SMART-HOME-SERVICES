"""Document loader for the RAG knowledge base (Phase 8).

Reads every ``*.md`` file from ``backend/knowledge_base`` and parses it into
raw documents (name + text + category). Loading happens only during explicit
indexing (``scripts/index_knowledge.py``) — never per request.
"""
from pathlib import Path

from app.core.config import settings

# project root / knowledge_base  (sibling of backend/, per the Phase 8 layout)
KB_DIR = Path(__file__).resolve().parents[3] / settings.RAG_KB_DIR

# Known categories (used for metadata filtering and the demo). Unknown files
# map to "general" so adding a document never breaks indexing.
CATEGORIES = {
    "plumbing": "plumbing",
    "electrical": "electrical",
    "ac_repair": "ac_repair",
    "cleaning": "cleaning",
    "appliance_repair": "appliance_repair",
    "home_maintenance": "home_maintenance",
    "faq": "faq",
    "safety": "safety",
}


def _category_for(filename: str) -> str:
    return CATEGORIES.get(Path(filename).stem, "general")


class RawDocument:
    """One knowledge-base file before chunking."""

    __slots__ = ("category", "source", "text")

    def __init__(self, source: str, category: str, text: str):
        self.source = source
        self.category = category
        self.text = text

    def __repr__(self) -> str:  # handy for the indexing script's output
        return f"<RawDocument {self.source} category={self.category} chars={len(self.text)}>"


def load_documents(directory: Path | None = None) -> list[RawDocument]:
    """Load every ``*.md`` file in the knowledge base (sorted for stable ids).

    Kept separate from the API request flow: the FastAPI server never calls
    this — only the explicit indexing script does.
    """
    base = directory or KB_DIR
    if not base.exists():
        return []
    docs: list[RawDocument] = []
    for path in sorted(base.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        docs.append(RawDocument(path.name, _category_for(path.name), text))
    return docs
