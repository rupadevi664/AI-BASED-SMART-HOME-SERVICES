"""LLM Pydantic schemas (Phase 7).

Only the customer's own words travel to Gemini — never user identity,
tokens, payment data or other application state. The response schema
carries a single clean `response` string; the raw provider payload is
never forwarded to clients.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Hard caps mirroring GEMINI_MAX_HISTORY_TURNS in config (defense in depth:
# the service truncates again server-side from settings).
MAX_HISTORY_TURNS = 8


class ChatTurn(BaseModel):
    """One earlier exchange in the client-side conversation."""

    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty or whitespace only")
        return v.strip()


class LLMRequest(BaseModel):
    """Body of POST /llm/chat.

    - `message` is required and may not be blank (validated, not just
      non-empty — "   " is rejected too).
    - `service_context` is optional, caller-supplied context (e.g. what the
      customer was looking at) — NOT server-side secrets or user data.
    - `history` is optional recent conversation so follow-up questions read
      naturally; the frontend keeps it in React state, capped server-side.
    """

    message: str = Field(min_length=1, max_length=2000)
    service_context: str | None = Field(default=None, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be empty or whitespace only")
        return v.strip()

    @field_validator("service_context")
    @classmethod
    def _context_strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None  # empty after strip → treat as absent


class LLMResponse(BaseModel):
    """Exactly one clean assistant text — nothing else leaks from Gemini."""

    response: str = Field(min_length=1)
