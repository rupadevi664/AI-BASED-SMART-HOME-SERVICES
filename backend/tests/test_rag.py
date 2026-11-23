"""Phase 8 tests: RAG + embeddings + ChromaDB.

- Retrieval is exercised against a REAL local ChromaDB (persistent dir under
  a tmp session path) with the real local MiniLM embeddings - slow to load
  once, then fast; a module-scoped fixture indexes the real knowledge_base
  documents.
- /llm/chat integration reuses the Phase 7 fake `_post` boundary so no network
  call happens; the RAG prompt contents are asserted directly.
- Phase 1-7 regressions are covered by the rest of the suite (269+ tests run
  together).
"""
import pytest

from app.core.config import settings
from tests.conftest import login, register_customer, token_headers


@pytest.fixture(scope="module")
def rag_world(client, tmp_path_factory):
    """Real ChromaDB (tmp dir) + real KB docs + a customer for /llm/chat."""
    from app.rag import rag_service
    from app.rag.chunker import chunk_documents
    from app.rag.document_loader import load_documents
    from app.rag.vector_store import VectorStore

    # Point the shared retriever at an isolated store for this module.
    tmp_dir = tmp_path_factory.mktemp("chroma")
    store = VectorStore(persist_dir=tmp_dir)
    docs = load_documents()  # real knowledge_base/*.md
    assert docs, "knowledge_base documents missing"
    chunks = chunk_documents(docs)
    store.replace_all(chunks)

    old_retriever = rag_service._retriever
    rag_service._retriever = __import__("app.rag.retriever", fromlist=["Retriever"]).Retriever(store)

    register_customer(client, email="rag.customer@example.com")
    world = {
        "customer_token": login(client, "rag.customer@example.com")["access_token"],
        "chunks": chunks,
        "store": store,
    }
    yield world
    rag_service._retriever = old_retriever
    rag_service.reset_retriever()


@pytest.fixture
def fake_gemini(monkeypatch):
    """Fake the Gemini network boundary (Phase 7 pattern) and set a key."""
    from app.services import gemini_service

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "Grounded answer."}]}}]}

    calls = []

    def _fake_post(url, *, json_body=None, timeout=None):
        calls.append({"url": url, "body": json_body})
        return _FakeResponse()

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-test-key")
    monkeypatch.setattr(gemini_service, "_post", _fake_post)
    return calls


def _chat(client, token, message, **extra):
    body = {"message": message}
    body.update(extra)
    return client.post("/llm/chat", headers=token_headers(token), json=body)


class TestRetrieval:
    """Spec test matrix 1-5, against the real KB + real ChromaDB."""

    def test_plumbing_question_retrieves_plumbing(self, rag_world):
        from app.rag.retriever import Retriever

        hits = Retriever(rag_world["store"]).retrieve("My kitchen tap is leaking.")
        assert hits, "plumbing question retrieved nothing"
        assert any(h["category"] == "plumbing" for h in hits)
        assert "tap" in hits[0]["text"].lower() or "leak" in hits[0]["text"].lower()

    def test_ac_question_retrieves_ac(self, rag_world):
        from app.rag.retriever import Retriever

        hits = Retriever(rag_world["store"]).retrieve("My AC is not cooling.")
        assert hits
        assert any(h["category"] == "ac_repair" for h in hits)

    def test_electrical_question_retrieves_electrical(self, rag_world):
        from app.rag.retriever import Retriever

        hits = Retriever(rag_world["store"]).retrieve(
            "My power switch is making a strange noise."
        )
        assert hits
        assert any(h["category"] == "electrical" for h in hits)

    def test_cleaning_question_retrieves_cleaning(self, rag_world):
        from app.rag.retriever import Retriever

        hits = Retriever(rag_world["store"]).retrieve("I need help cleaning my house.")
        assert hits
        assert any(h["category"] == "cleaning" for h in hits)

    def test_relevant_distances_are_tight(self, rag_world):
        """Grounding quality guard: relevant questions must score well inside
        the relevance threshold (demo calibration: relevant <= 0.67)."""
        from app.rag.retriever import Retriever

        for question in (
            "My kitchen tap is leaking.",
            "My AC is not cooling.",
        ):
            hits = Retriever(rag_world["store"]).retrieve(question)
            assert hits and hits[0]["distance"] < 0.7, question

    def test_unknown_question_retrieves_nothing(self, rag_world):
        from app.rag.retriever import Retriever

        hits = Retriever(rag_world["store"]).retrieve("What is the capital of France?")
        assert hits == [], "unrelated question must not retrieve KB documents"

    def test_top_k_and_metadata_are_set(self, rag_world):
        from app.rag.retriever import Retriever

        hits = Retriever(rag_world["store"]).retrieve("washing machine will not drain")
        assert len(hits) <= settings.RAG_TOP_K
        for h in hits:
            assert {"text", "source", "category", "chunk_index", "distance"} <= set(h)
            assert 0.0 <= h["distance"] <= 2.0

    def test_category_filtering(self, rag_world):
        from app.rag.retriever import Retriever

        hits = Retriever(rag_world["store"]).retrieve("tap dripping under the sink", category="plumbing")
        assert hits
        assert all(h["category"] == "plumbing" for h in hits)


class TestRagPrompt:
    def test_grounding_marker_true(self, rag_world):
        prompt, used_kb, hits = __import__(
            "app.rag.rag_service", fromlist=["build_rag_prompt"]
        ).build_rag_prompt("My kitchen tap is leaking.")
        assert used_kb is True
        assert hits
        assert "Retrieved Context:" in prompt
        assert "My kitchen tap is leaking." in prompt
        assert any(h["source"].endswith(".md") for h in hits)

    def test_fallback_marker_false(self, rag_world):
        from app.rag.rag_service import build_rag_prompt

        prompt, used_kb, hits = build_rag_prompt("What is the capital of France?")
        assert used_kb is False
        assert hits == []
        assert "does not cover it specifically" in prompt


class TestLLMChatIntegration:
    def test_grounded_chat_shape(self, client, rag_world, fake_gemini):
        response = _chat(client, rag_world["customer_token"], "My AC is not cooling.")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["grounded"] is True
        # The Gemini request must carry the RAG prompt with retrieved context.
        contents = fake_gemini[0]["body"]["contents"]
        final_text = contents[-1]["parts"][0]["text"]
        assert "Retrieved Context:" in final_text
        assert "air filter" in final_text.lower() or "cooling" in final_text.lower()

    def test_ungrounded_chat_flags_false(self, client, rag_world, fake_gemini):
        response = _chat(client, rag_world["customer_token"], "What is the capital of France?")
        assert response.status_code == 200
        body = response.json()
        assert body["grounded"] is False
        final_text = fake_gemini[0]["body"]["contents"][-1]["parts"][0]["text"]
        assert "does not cover it specifically" in final_text

    def test_auth_still_required(self, client):
        assert client.post("/llm/chat", json={"message": "hi"}).status_code == 401

    def test_empty_message_still_422(self, client, rag_world):
        assert _chat(client, rag_world["customer_token"], "  ").status_code == 422

    def test_rag_failure_degrades_not_breaks(self, client, rag_world, fake_gemini, monkeypatch):
        from app.rag import rag_service

        class _Broken:
            def retrieve(self, *a, **k):
                from app.rag.vector_store import VectorStoreError

                raise VectorStoreError("boom")

        old = rag_service._retriever
        rag_service._retriever = _Broken()
        try:
            response = _chat(client, rag_world["customer_token"], "My tap is leaking")
            assert response.status_code == 200
            assert response.json()["grounded"] is False
        finally:
            rag_service._retriever = old


class TestStoreIntegrity:
    def test_index_count_matches_chunks(self, rag_world):
        # Every indexed chunk is addressable and the count is sane.
        assert rag_world["store"].count() == len(rag_world["chunks"])
        assert rag_world["store"].count() > 20

    def test_reindex_is_idempotent(self, rag_world):
        from app.rag.chunker import chunk_documents
        from app.rag.document_loader import load_documents

        chunks = chunk_documents(load_documents())
        before = rag_world["store"].count()
        rag_world["store"].replace_all(chunks)
        assert rag_world["store"].count() == before  # no duplicates
