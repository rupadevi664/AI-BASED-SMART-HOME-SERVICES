"""LLM business logic (Phase 7): Google Gemini chat for the AI assistant.

Architecture / security invariants:
- GEMINI_API_KEY lives only on the backend (backend/.env via Settings) and is
  never returned to any client or included in any logged payload.
- Only the customer's question (plus optional caller-supplied context and a
  short validated history) is sent to Gemini — never passwords, JWTs, payment
  secrets or other application data.
- The endpoint returns ONLY clean assistant text; the raw Gemini payload is
  never forwarded to clients.
- Every failure mode (missing key, rejected key, upstream outage, rate limit,
  timeout, network failure, empty generation) maps to a controlled
  `{"error": {"code", "message"}}` response — no stack traces or provider
  internals leak out.
- The assistant has no tool access: it can only suggest service categories.
  It can never create bookings or payments, and the system prompt forbids
  claiming any action was performed (only the real booking/payment APIs do).
- No data is persisted (Phase 7 has no chat history table — the frontend
  keeps the conversation in React state).
"""
import logging
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.services.booking_service import _fail

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Controlled persona: general guidance only, no invented application data.
SYSTEM_PROMPT = """You are the Smart Home Service Assistant for a home-services platform.

Your job:
- Help customers understand common home-service problems (electrical, plumbing,
  AC/appliance, cleaning, pest control, carpentry, painting and similar).
- Explain POSSIBLE causes in simple language; never claim certainty about a
  physical problem you cannot inspect.
- Give only safe, general troubleshooting guidance. For anything involving
  electricity, gas, water damage or safety risks, tell the customer to stop and
  wait for a professional.
- Suggest the appropriate service category and which type of expert to book.

Strict rules:
- You provide general guidance only. Never claim to physically diagnose a
  device or property, and never pretend to be a human technician.
- Never invent prices, fees, expert availability, schedules, bookings,
  payments, or any other application data. You do not have access to that.
- Never claim a booking was created or any action was performed — you can only
  recommend; the customer performs actions themselves in the app.
- If professional inspection is appropriate, recommend booking an expert
  through the app.
- Keep answers concise, friendly and easy to understand (short paragraphs or a
  few bullet points). Match the customer's language."""


def _key_configured() -> bool:
    return bool(settings.GEMINI_API_KEY)


def _fail_503() -> HTTPException:
    return _fail(
        "LLM_NOT_CONFIGURED",
        503,
        "The AI assistant is not configured on this server (GEMINI_API_KEY missing). "
        "Add it to backend/.env and restart.",
    )


def _post(url: str, *, json_body: dict, timeout: float) -> httpx.Response:
    """Thin wrapper around httpx so tests can stub the network boundary
    without patching the httpx module itself."""
    return httpx.post(url, json=json_body, timeout=timeout)


def _extract_text(data: dict[str, Any]) -> str | None:
    """Pull the first non-empty text out of a Gemini generateContent payload."""
    for candidate in data.get("candidates") or []:
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        texts = [
            part.get("text", "").strip()
            for part in parts
            if isinstance(part, dict) and part.get("text")
        ]
        joined = "\n".join(t for t in texts if t).strip()
        if joined:
            return joined
    return None


def _map_upstream_error(resp: httpx.Response) -> HTTPException:
    """Translate a non-200 Gemini response into a controlled client error.

    The provider's message is logged server-side only; the client gets a
    stable code + friendly message.
    """
    try:
        err = resp.json().get("error") or {}
    except ValueError:
        err = {}
    message = str(err.get("message", ""))
    logger.warning(
        "Gemini API error: status=%s status_text=%s provider_message=%r",
        resp.status_code,
        err.get("status"),
        message[:200],
    )

    if resp.status_code in (401, 403) or "API key not valid" in message or "API_KEY_INVALID" in message:
        # Server-side misconfiguration; never echo provider detail to clients.
        return _fail(
            "LLM_AUTH_ERROR",
            502,
            "The AI assistant is misconfigured on this server. Please contact support.",
        )
    if resp.status_code == 429:
        return _fail(
            "LLM_RATE_LIMITED",
            429,
            "The AI assistant is busy right now. Please try again in a moment.",
        )
    if resp.status_code >= 500:
        return _fail(
            "LLM_UPSTREAM_ERROR",
            502,
            "The AI assistant is temporarily unavailable. Please try again.",
        )
    # Other 4xx (bad request, safety block, unknown model, ...)
    return _fail(
        "LLM_REQUEST_ERROR",
        502,
        "The AI assistant could not process this request. Please try again.",
    )


class GeminiService:
    """Builds Gemini requests, calls the REST API, returns clean text only."""

    @staticmethod
    def generate_reply(
        message: str,
        service_context: str | None = None,
        history: list[dict] | None = None,
    ) -> str:
        """Send the conversation to Gemini and return the assistant's text.

        `history` items are `{"role": "user"|"assistant", "text": ...}` —
        already validated by the schema and truncated to
        GEMINI_MAX_HISTORY_TURNS here as defense in depth.
        """
        if not _key_configured():
            raise _fail_503()

        url = (
            f"{GEMINI_BASE_URL}/models/{settings.GEMINI_MODEL}:generateContent"
            f"?key={settings.GEMINI_API_KEY}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": GeminiService._build_contents(message, service_context, history),
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 512},
        }

        try:
            resp = _post(url, json_body=payload, timeout=settings.GEMINI_TIMEOUT_SECONDS)
        except httpx.TimeoutException as exc:
            logger.warning("Gemini request timed out after %ss", settings.GEMINI_TIMEOUT_SECONDS)
            raise _fail(
                "LLM_TIMEOUT",
                504,
                "The AI assistant took too long to respond. Please try again.",
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Gemini request failed at the network level: %s", exc.__class__.__name__)
            raise _fail(
                "LLM_UNREACHABLE",
                502,
                "The AI assistant is temporarily unavailable. Please try again.",
            ) from exc

        if resp.status_code != 200:
            raise _map_upstream_error(resp)

        text = _extract_text(resp.json())
        if not text:
            # Empty generation (e.g. safety filter) — controlled, friendly.
            raise _fail(
                "LLM_EMPTY_RESPONSE",
                502,
                "The AI assistant could not answer that. Please rephrase and try again.",
            )
        return text

    # ------------------------------------------------------------------ build
    @staticmethod
    def _build_contents(
        message: str,
        service_context: str | None = None,
        history: list[dict] | None = None,
    ) -> list[dict]:
        """Map the client conversation to Gemini's `contents` format.

        Roles: "assistant" → Gemini's "model". History is capped at
        GEMINI_MAX_HISTORY_TURNS (last N turns kept) server-side.
        """
        cap = max(0, settings.GEMINI_MAX_HISTORY_TURNS)
        recent = (history or [])[-cap:]

        contents: list[dict] = []
        for turn in recent:
            role = "model" if turn.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": turn.get("text", "")}]})

        final = message.strip()
        if service_context and service_context.strip():
            final = f"{final}\n\n(Customer context: {service_context.strip()})"
        contents.append({"role": "user", "parts": [{"text": final}]})
        return contents
