"""Booking Pydantic schemas (Phase 3)."""
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models.booking import BookingStatus
from app.schemas.expert import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
)

# 5-minute slot granularity keeps the conflict check simple and predictable.
SLOT_MINUTES = 5


def _floor_to_slot(value: time) -> time:
    return time(hour=value.hour, minute=(value.minute // SLOT_MINUTES) * SLOT_MINUTES)


class BookingCreate(BaseModel):
    """CUSTOMER-only booking request. `customer_id` is taken from the JWT,
    never from the body."""

    expert_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    service_address: str = Field(min_length=5, max_length=500)
    service_latitude: float | None = Field(default=None, ge=MIN_LATITUDE, le=MAX_LATITUDE)
    service_longitude: float | None = Field(default=None, ge=MIN_LONGITUDE, le=MAX_LONGITUDE)
    scheduled_date: date
    scheduled_time: time
    customer_notes: str | None = Field(default=None, max_length=1000)


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    expert_id: int
    service_id: int
    service_name: str
    service_price: float
    service_address: str
    service_latitude: float | None = None
    service_longitude: float | None = None
    scheduled_date: date
    scheduled_time: time
    customer_notes: str | None = None
    status: BookingStatus
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class BookingCancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class BookingRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class BookingStatusResponse(BaseModel):
    """Minimal status payload for lifecycle transitions."""

    id: int
    status: BookingStatus
    cancellation_reason: str | None = None
