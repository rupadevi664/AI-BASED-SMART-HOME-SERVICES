"""Chat schemas (Phase 4): REST history + WebSocket envelopes."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGE_LENGTH = 2000


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    sender_id: int
    message: str
    created_at: datetime


# --- WebSocket envelopes -----------------------------------------------------


class WebSocketError(BaseModel):
    type: str = "error"
    message: str


class IncomingWebSocketMessage(BaseModel):
    """Validated incoming client payload. `message` is trimmed and length-checked."""

    type: str = "message"
    message: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)

    def model_post_init(self, __context) -> None:
        if self.message is not None:
            self.message = self.message.strip()


class OutgoingChatMessage(BaseModel):
    type: str = "message"
    booking_id: int
    sender_id: int
    sender_role: str
    message: str
    timestamp: datetime


class JoinEvent(BaseModel):
    type: str  # "user_joined" | "user_left"
    user_id: int


class PongEvent(BaseModel):
    type: str = "pong"
