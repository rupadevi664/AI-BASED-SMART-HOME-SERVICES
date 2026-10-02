"""Phase 7 tests: Gemini LLM assistant.

Runs offline — the network boundary (gemini_service._post) is replaced with
a fake, mirroring the payments suite's fake Razorpay client. Covers the
spec matrix: AC/plumbing/electrical questions (via the fake), empty message
→ 422, unauthenticated → 401, invalid key → controlled error, plus the
503 no-key gate, rate limit, timeout, network failure, empty generation and
server-side history capping.
"""
import httpx
import pytest

from app.core.config import settings
from tests.conftest import login, make_admin, register_customer, register_expert, token_headers

ADMIN_EMAIL = "llm.admin@example.com"

SUCCESS_PAYLOAD = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [{"text": "Possible causes include a dirty air filter, blocked "
                                   "airflow, low refrigerant, or a compressor issue. "
                                   "Consider booking an AC service expert."}],
            }
        }
    ]
}


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeGemini:
    """Stands in for gemini_service._post — records requests, returns a
    canned response (or raises a canned exception) without any network I/O."""

    def __init__(self):
        self.requests = []
        self.response = _FakeResponse(200, SUCCESS_PAYLOAD)

    def __call__(self, url, *, json_body=None, timeout=None):
        self.requests.append({"url": url, "body": json_body, "timeout": timeout})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture(scope="module")
def world(client):
    register_customer(client, email="llm.customer@example.com")
    register_expert(client, email="llm.expert@example.com")
    return {
        "customer_token": login(client, "llm.customer@example.com")["access_token"],
        "expert_token": login(client, "llm.expert@example.com")["access_token"],
    }


@pytest.fixture
def fake_gemini(monkeypatch):
    """Configure a key + replace the network boundary for one test."""
    from app.services import gemini_service

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-test-key")
    fake = _FakeGemini()
    monkeypatch.setattr(gemini_service, "_post", fake)
    return fake


def _chat(client, token, message="My AC is not cooling. What should I check?", **extra):
    body = {"message": message}
    body.update(extra)
    return client.post("/llm/chat", headers=token_headers(token), json=body)


class TestAuth:
    def test_unauthenticated_401(self, client):
        response = client.post("/llm/chat", json={"message": "My AC is not cooling"})
        assert response.status_code == 401

    def test_customer_allowed(self, client, world, fake_gemini):
        response = _chat(client, world["customer_token"])
        assert response.status_code == 200, response.text

    def test_expert_allowed(self, client, world, fake_gemini):
        response = _chat(client, world["expert_token"], "Which service for wiring problems?")
        assert response.status_code == 200, response.text

    def test_admin_forbidden(self, client, world):
        make_admin(email=ADMIN_EMAIL)
        admin_token = login(client, ADMIN_EMAIL)["access_token"]
        response = _chat(client, admin_token)
        assert response.status_code == 403


class TestValidation:
    def test_empty_message_422(self, client, world):
        response = _chat(client, world["customer_token"], "")
        assert response.status_code == 422

    def test_whitespace_message_422(self, client, world):
        response = _chat(client, world["customer_token"], "   \n\t  ")
        assert response.status_code == 422

    def test_missing_message_422(self, client, world):
        response = client.post(
            "/llm/chat", headers=token_headers(world["customer_token"]), json={}
        )
        assert response.status_code == 422

    def test_overlong_message_422(self, client, world):
        response = _chat(client, world["customer_token"], "x" * 2001)
        assert response.status_code == 422

    def test_too_many_history_turns_422(self, client, world):
        history = [{"role": "user", "text": f"q{i}"} for i in range(9)]
        response = _chat(client, world["customer_token"], "again?", history=history)
        assert response.status_code == 422

    def test_history_turn_overlong_422(self, client, world):
        history = [{"role": "user", "text": "x" * 1001}]
        response = _chat(client, world["customer_token"], "again?", history=history)
        assert response.status_code == 422

    def test_bad_history_role_422(self, client, world):
        response = _chat(
            client, world["customer_token"], "again?",
            history=[{"role": "admin", "text": "hi"}],
        )
        assert response.status_code == 422


class TestNotConfigured:
    def test_503_without_key(self, client, world, monkeypatch):
        monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
        response = _chat(client, world["customer_token"])
        assert response.status_code == 503
        assert response.json()["detail"]["error"]["code"] == "LLM_NOT_CONFIGURED"


class TestChat:
    def test_clean_text_only(self, client, world, fake_gemini):
        response = _chat(client, world["customer_token"], "My AC is not cooling")
        assert response.status_code == 200
        body = response.json()
        # Only the clean text — never the raw provider payload.
        assert set(body.keys()) == {"response"}
        assert "air filter" in body["response"]

    def test_request_hits_gemini_with_key_and_model(self, client, world, fake_gemini):
        _chat(client, world["customer_token"], "My pipe is leaking")
        request = fake_gemini.requests[0]
        assert "/models/gemini-2.0-flash:generateContent" in request["url"]
        assert "key=fake-test-key" in request["url"]
        # The key travels in the URL only — never inside the request body.
        assert "fake-test-key" not in str(request["body"])

    def test_system_prompt_and_contents_shape(self, client, world, fake_gemini):
        _chat(client, world["customer_token"], "Which service should I book for wiring?")
        body = fake_gemini.requests[0]["body"]
        assert "Smart Home Service Assistant" in body["system_instruction"]["parts"][0]["text"]
        contents = body["contents"]
        assert contents[-1]["role"] == "user"
        assert contents[-1]["parts"][0]["text"].endswith("wiring?")

    def test_service_context_appended(self, client, world, fake_gemini):
        _chat(
            client, world["customer_token"], "Which service should I book?",
            service_context="AC is not cooling",
        )
        final_text = fake_gemini.requests[0]["body"]["contents"][-1]["parts"][0]["text"]
        assert "AC is not cooling" in final_text

    def test_history_roles_mapped(self, client, world, fake_gemini):
        history = [
            {"role": "user", "text": "My AC is not cooling."},
            {"role": "assistant", "text": "Check the filter; consider an AC service."},
        ]
        _chat(client, world["customer_token"], "Which expert should I book?", history=history)
        contents = fake_gemini.requests[0]["body"]["contents"]
        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"  # assistant → Gemini's "model"
        assert contents[-1]["role"] == "user"

    def test_history_capped_server_side(self, client, world, fake_gemini, monkeypatch):
        monkeypatch.setattr(settings, "GEMINI_MAX_HISTORY_TURNS", 2)
        history = [{"role": "user", "text": f"question {i}"} for i in range(6)]
        _chat(client, world["customer_token"], "one more question", history=history)
        contents = fake_gemini.requests[0]["body"]["contents"]
        # 2 capped history turns + the final question.
        assert len(contents) == 3
        assert contents[0]["parts"][0]["text"] == "question 4"

    def test_invalid_key_controlled_error(self, client, world, fake_gemini):
        fake_gemini.response = _FakeResponse(
            400,
            {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.",
                       "status": "INVALID_ARGUMENT"}},
        )
        response = _chat(client, world["customer_token"])
        assert response.status_code == 502
        detail = response.json()["detail"]["error"]
        assert detail["code"] == "LLM_AUTH_ERROR"
        assert "API key not valid" not in detail["message"]  # provider detail never leaks

    def test_rate_limited_429(self, client, world, fake_gemini):
        fake_gemini.response = _FakeResponse(
            429, {"error": {"code": 429, "message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}}
        )
        response = _chat(client, world["customer_token"])
        assert response.status_code == 429
        assert response.json()["detail"]["error"]["code"] == "LLM_RATE_LIMITED"

    def test_upstream_error_502(self, client, world, fake_gemini):
        fake_gemini.response = _FakeResponse(500, {"error": {"message": "internal"}})
        response = _chat(client, world["customer_token"])
        assert response.status_code == 502
        assert response.json()["detail"]["error"]["code"] == "LLM_UPSTREAM_ERROR"

    def test_timeout_504(self, client, world, fake_gemini):
        fake_gemini.response = httpx.TimeoutException("timed out")
        response = _chat(client, world["customer_token"])
        assert response.status_code == 504
        assert response.json()["detail"]["error"]["code"] == "LLM_TIMEOUT"

    def test_network_failure_502(self, client, world, fake_gemini):
        fake_gemini.response = httpx.ConnectError("no network")
        response = _chat(client, world["customer_token"])
        assert response.status_code == 502
        assert response.json()["detail"]["error"]["code"] == "LLM_UNREACHABLE"

    def test_empty_generation_controlled_error(self, client, world, fake_gemini):
        fake_gemini.response = _FakeResponse(200, {"candidates": []})
        response = _chat(client, world["customer_token"])
        assert response.status_code == 502
        assert response.json()["detail"]["error"]["code"] == "LLM_EMPTY_RESPONSE"
