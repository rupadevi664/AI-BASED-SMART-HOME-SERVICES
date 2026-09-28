"""Pydantic schemas for expert profiles and nearby search."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.expert import AvailabilityStatus, VerificationStatus
from app.schemas.service import ServiceResponse
from app.schemas.user import UserResponse

# Coordinate/radius bounds (validated by Pydantic before any DB access).
MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0
MAX_RADIUS_KM = 100.0


class ExpertProfileResponse(BaseModel):
    """Full expert profile — includes user info and offered services."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    email: str
    phone: str
    skills: str
    experience_years: int
    location: str
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    verification_status: VerificationStatus
    availability: AvailabilityStatus
    services: list[ServiceResponse] = []
    created_at: datetime


class ExpertRegisterResponse(BaseModel):
    """Response for POST /auth/register-expert: user + created profile."""

    model_config = ConfigDict(from_attributes=True)

    user: UserResponse
    expert_profile: ExpertProfileResponse


class ExpertProfileUpdate(BaseModel):
    """EXPERT-only partial profile update. `service_ids` replaces the offered
    services atomically. experience_years is always manually entered."""

    skills: str | None = Field(default=None, min_length=2, max_length=500)
    experience_years: int | None = Field(default=None, ge=0, le=60)
    location: str | None = Field(default=None, min_length=2, max_length=255)
    latitude: float | None = Field(default=None, ge=MIN_LATITUDE, le=MAX_LATITUDE)
    longitude: float | None = Field(default=None, ge=MIN_LONGITUDE, le=MAX_LONGITUDE)
    availability: AvailabilityStatus | None = None
    service_ids: list[int] | None = Field(default=None, min_length=0, max_length=50)


class NearbyExpertQuery(BaseModel):
    """Query-parameter validation for GET /experts/nearby (enforced via the
    endpoint signature; kept here for reuse and documentation)."""

    latitude: float = Field(ge=MIN_LATITUDE, le=MAX_LATITUDE)
    longitude: float = Field(ge=MIN_LONGITUDE, le=MAX_LONGITUDE)
    radius_km: float = Field(gt=0, le=MAX_RADIUS_KM)
    service_id: int | None = Field(default=None, gt=0)
    availability: AvailabilityStatus | None = None


class NearbyServiceInfo(BaseModel):
    id: int
    name: str


class NearbyExpertResponse(BaseModel):
    expert_id: int
    user_id: int
    name: str
    skills: str
    experience_years: int
    location: str
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    availability: AvailabilityStatus
    verification_status: VerificationStatus
    distance_km: float
    services: list[NearbyServiceInfo]
