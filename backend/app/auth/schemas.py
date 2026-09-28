"""Auth request/response schemas."""
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.expert import AvailabilityStatus, VerificationStatus
from app.models.user import UserRole
from app.schemas.expert import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
)


class CustomerRegister(BaseModel):
    """Customer self-registration request (role is always forced to CUSTOMER)."""

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=8, max_length=128)


class ExpertRegister(BaseModel):
    """Expert self-registration request (role is always forced to EXPERT)."""

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    skills: str = Field(min_length=2, max_length=500)
    # Manually entered by the expert — never calculated by the system.
    experience_years: int = Field(ge=0, le=60)
    location: str = Field(min_length=2, max_length=255)
    # Static profile coordinates, manually provided (no live GPS).
    latitude: float | None = Field(default=None, ge=MIN_LATITUDE, le=MAX_LATITUDE)
    longitude: float | None = Field(default=None, ge=MIN_LONGITUDE, le=MAX_LONGITUDE)
    availability: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    # Services the expert offers (validated against the catalogue in the service layer).
    service_ids: list[int] | None = Field(default=None, min_length=0, max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ExpertProfileInfo(BaseModel):
    """Expert profile fields embedded in /auth/me for EXPERT users."""

    model_config = ConfigDict(from_attributes=True)

    skills: str
    experience_years: int
    location: str
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    verification_status: VerificationStatus
    availability: AvailabilityStatus


class MeResponse(BaseModel):
    """Response for GET /auth/me — never contains password_hash."""

    id: int
    name: str
    email: EmailStr
    phone: str
    role: UserRole
    is_active: bool
    expert_profile: ExpertProfileInfo | None = None
