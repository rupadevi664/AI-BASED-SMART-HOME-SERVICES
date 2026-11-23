"""Notification response and request schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    message: str
    type: str
    link: str | None = None
    is_read: bool
    created_at: datetime


class UnreadCountResponse(BaseModel):
    count: int
