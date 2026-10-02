"""Live-location Pydantic schemas (Phase 5).

Validation lives here so the WebSocket handler and the REST endpoints share
one source of truth — a coordinate that fails `LocationUpdate` can never be
persisted, on either transport.
"""
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.expert import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
)

# Optional GPS metadata bounds (validated only when supplied).
MAX_ACCURACY = 100000.0  # metres — generous bound against absurd values
MAX_SPEED = 1000.0  # m/s (~3600 km/h)


class LocationUpdate(BaseModel):
    """Incoming expert payload over the location WebSocket.

    `latitude`/`longitude` are required; accuracy/heading/speed/timestamp are
    optional. Validation happens here, before anything touches the database.
    """

    type: str = "location_update"
    latitude: float = Field(ge=MIN_LATITUDE, le=MAX_LATITUDE)
    longitude: float = Field(ge=MIN_LONGITUDE, le=MAX_LONGITUDE)
    accuracy: float | None = Field(default=None, ge=0.0, le=MAX_ACCURACY)
    heading: float | None = Field(default=None, ge=0.0, le=360.0)
    speed: float | None = Field(default=None, ge=0.0, le=MAX_SPEED)
    timestamp: datetime | None = None

    @field_validator("latitude", "longitude", "accuracy", "heading", "speed")
    @classmethod
    def _finite(cls, value: float | None) -> float | None:
        # Reject NaN/inf: comparisons alone would let them slip through.
        if value is not None and (value != value or value in (float("inf"), float("-inf"))):
            raise ValueError("must be a finite number")
        return value

    @field_validator("timestamp")
    @classmethod
    def _not_far_future(cls, value: datetime | None) -> datetime | None:
        """Reject timestamps > 5 minutes in the future (clock-skew guard).

        Aware values are normalized to naive UTC and compared against naive
        UTC *now* — comparing against local time would misjudge timestamps on
        non-UTC machines (e.g. UTC+5:30).
        """
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if value > now_utc_naive + timedelta(minutes=5):
            raise ValueError("timestamp must not be in the future")
        return value

    @model_validator(mode="after")
    def _reject_unknown_type(self) -> "LocationUpdate":
        if self.type != "location_update":
            raise ValueError("type must be 'location_update'")
        return self


class LocationResponse(BaseModel):
    """One stored GPS fix (latest endpoint or history item)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    expert_id: int
    latitude: float
    longitude: float
    accuracy: float | None = None
    heading: float | None = None
    speed: float | None = None
    timestamp: datetime
    created_at: datetime


class LocationHistoryResponse(BaseModel):
    """REST history envelope: ASC-ordered points + how many were returned."""

    booking_id: int
    count: int
    points: list[LocationResponse]


class LocationWebSocketMessage(BaseModel):
    """Broadcast frame sent to location subscribers after a valid update."""

    type: str = "location_update"
    booking_id: int
    expert_id: int
    latitude: float
    longitude: float
    accuracy: float | None = None
    heading: float | None = None
    speed: float | None = None
    timestamp: datetime

    def broadcast_dict(self) -> dict:
        """JSON-safe dict for `send_json` (no Decimal/enum surprises)."""
        return {key: value for key, value in self.model_dump(mode="json").items()}
